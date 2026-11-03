"""Plot block rendering — library-agnostic figure-to-HTML conversion.

Detection strategy
------------------
We use duck typing on the figure's module path rather than ``isinstance``
checks so that briefing never hard-imports any plotting library.  Only the
library actually used is imported at render time.

Library support summary
-----------------------
| Library    | Output   | Self-contained | Notes                              |
|------------|----------|----------------|------------------------------------|
| Matplotlib | SVG      | ✓ always       | Handles Figure and Axes objects    |
| Seaborn    | SVG      | ✓ always       | Via underlying Matplotlib figure   |
| Plotnine   | SVG      | ✓ always       | Via underlying Matplotlib figure   |
| Plotly     | HTML+JS  | ✓ if installed | plotlyjs embedded once per report  |
| Bokeh      | iframe   | ✓ always       | INLINE resources, base64 srcdoc    |
| Altair     | HTML+JS  | ✓ with         | Vega runtime embedded once per     |
|            |          | vl-convert     | report (briefing[altair])          |
"""
from __future__ import annotations

import base64
import contextlib
import functools
import html as _html
import io
import json
import re
import typing as t

from briefing._error import BriefingError
from briefing.renderers.registry import IdGen

if t.TYPE_CHECKING:
    from briefing.blocks.asset import Plot
    from briefing.blocks.base import Block

_SUPPORTED = {"altair", "bokeh", "matplotlib", "plotly"}


# ── detection ─────────────────────────────────────────────────────────────────


def detect_library(fig: t.Any) -> str:
    """Return the library name for *fig*, or raise :class:`~briefing.BriefingError`."""
    module = type(fig).__module__.split(".")[0]

    if module == "plotly":
        return "plotly"
    if module in ("altair",):
        return "altair"
    if module == "bokeh":
        return "bokeh"
    # matplotlib-compatible: matplotlib, seaborn FacetGrid, plotnine ggplot
    if hasattr(fig, "savefig") or hasattr(fig, "get_figure"):
        return "matplotlib"

    raise BriefingError(
        f"Unsupported figure type: {type(fig).__module__}.{type(fig).__qualname__!r}. "
        f"Supported libraries: {', '.join(sorted(_SUPPORTED))}."
    )


# ── tree scan (pre-pass) ──────────────────────────────────────────────────────


def scan_for_plots(root: Block) -> set[str]:
    """Walk *root* depth-first and return the set of libraries used in Plot blocks."""
    from briefing.blocks.asset import Plot as PlotBlock
    from briefing.blocks.base import ContainerBlock

    needed: set[str] = set()
    stack: list[Block] = [root]

    while stack:
        block = stack.pop()
        if isinstance(block, PlotBlock):
            # An unknown figure type is surfaced properly at render time.
            with contextlib.suppress(BriefingError):
                needed.add(detect_library(block.figure))
        if isinstance(block, ContainerBlock):
            stack.extend(block.blocks)

    return needed


# ── runtime JS (embedded once in <head>) ──────────────────────────────────────


def get_runtime_scripts(libraries: set[str]) -> str:
    """Return ``<script>`` tags to embed in ``<head>`` for *libraries*.

    Plotly and Altair (Vega) need a bundled runtime; other libraries either
    need no JS (Matplotlib/SVG) or embed their runtime per-figure (Bokeh/iframe).
    """
    parts: list[str] = []

    if "plotly" in libraries:
        parts.append(_plotlyjs_script())
    if "altair" in libraries:
        vega = _vega_bundle()
        if vega is not None:  # without it, each Altair chart renders an install hint
            parts.append(f"<script>{vega}</script>")

    return "\n".join(parts)


_ALTAIR_INSTALL_HINT = (
    "Altair charts need vl-convert-python to embed the Vega runtime offline. "
    "Install it with: pip install briefing[altair]"
)


@functools.cache
def _vega_bundle() -> str | None:
    """Vega, Vega-Lite and vega-embed as one script (it sets ``window.vegaEmbed``), or ``None``.

    The bundle comes from vl-convert-python, the package Altair's own inline
    HTML export uses, matched to the installed Altair's Vega-Lite version.
    """
    try:
        import vl_convert
    except ImportError:
        return None
    try:
        from altair.utils._importers import vl_version_for_vl_convert

        version: str | None = vl_version_for_vl_convert()
    except Exception:  # private helper; fall back to vl-convert's default Vega-Lite
        version = None
    return vl_convert.javascript_bundle(_VEGA_GLOBALS, vl_version=version)


#: Bundled after the libraries: exposes them to report.js as globals.
_VEGA_GLOBALS = "window.vegaEmbed = vegaEmbed; window.vegaLite = vegaLite; window.vega = vega;"


def _script_json(value: t.Any) -> str:
    """JSON that is safe inside ``<script type="application/json">``: no ``<``, ``>`` or ``&``."""
    text = json.dumps(value, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _plotlyjs_script() -> str:
    try:
        from plotly.offline import get_plotlyjs

        js = get_plotlyjs()
        return f"<script>{js}</script>"
    except ImportError as exc:
        raise BriefingError(
            "plotly is not installed. Run: pip install plotly"
        ) from exc


# ── per-library renderers ─────────────────────────────────────────────────────


def _render_matplotlib(fig: t.Any, responsive: bool, salt: str) -> str:
    import matplotlib

    # Accept both Figure and Axes-like objects (seaborn, plotnine, etc.)
    actual = fig.get_figure() if (hasattr(fig, "get_figure") and not hasattr(fig, "savefig")) else fig

    # A salt from the render's IdGen (instead of a random one) and no date
    # metadata keep the SVG byte-identical from one render to the next.
    buf = io.StringIO()
    with matplotlib.rc_context({"svg.hashsalt": salt}):
        actual.savefig(buf, format="svg", bbox_inches="tight", metadata={"Date": None})
    svg = buf.getvalue()
    buf.close()

    # Strip XML / DOCTYPE preamble — keep only the <svg> element
    if "<svg" in svg:
        svg = svg[svg.index("<svg"):]

    if responsive:
        # Matplotlib 3.10+ escapes quotes inside SVG attributes (width=\"500pt\")
        svg = re.sub(r'(<svg\b[^>]*?)\s+width=\\?"[^"\\]*\\?"', r'\1 width="100%"', svg, count=1)
        svg = re.sub(r'(<svg\b[^>]*?)\s+height=\\?"[^"\\]*\\?"', r'\1', svg, count=1)

    return svg


def _render_plotly(fig: t.Any, responsive: bool, div_id: str) -> str:
    try:
        import plotly.io as pio
    except ImportError as exc:
        raise BriefingError("plotly is not installed. Run: pip install plotly") from exc

    return str(
        pio.to_html(
            fig,
            full_html=False,
            include_plotlyjs=False,  # already embedded in <head> via get_runtime_scripts()
            config={"responsive": responsive},
            div_id=div_id,  # Plotly's default is a random uuid
        )
    )


def _render_altair(fig: t.Any, responsive: bool, div_id: str) -> str:
    try:
        import altair as alt  # noqa: F401
    except ImportError as exc:
        raise BriefingError("altair is not installed. Run: pip install altair") from exc
    if _vega_bundle() is None:
        raise BriefingError(_ALTAIR_INSTALL_HINT)

    if responsive:
        with contextlib.suppress(Exception):
            fig = fig.properties(width="container")

    # Drawn in the page by report.js with the Vega runtime embedded in <head>.
    return (
        f'<div class="bf-altair" id="{div_id}"></div>'
        f'<script type="application/json" class="bf-altair__spec">{_script_json(fig.to_dict())}</script>'
    )


def _render_bokeh(fig: t.Any) -> str:
    try:
        from bokeh.embed import file_html
        from bokeh.resources import INLINE
    except ImportError as exc:
        raise BriefingError("bokeh is not installed. Run: pip install bokeh") from exc

    full_html = file_html(fig, resources=INLINE)
    b64 = base64.b64encode(full_html.encode("utf-8")).decode("ascii")
    return (
        f'<iframe src="data:text/html;base64,{b64}" '
        f'width="100%" height="500" style="border:none;" title="Bokeh chart" '
        f'loading="lazy"></iframe>'
    )


# ── public render entry ───────────────────────────────────────────────────────


def render_figure(block: Plot, idgen: IdGen | None = None) -> str:
    """Render a :class:`~briefing.Plot` block to a self-contained HTML fragment.

    *idgen* is the render pass's id generator; chart ids and salts come from it
    so the output is deterministic and unique within the report.
    """
    idgen = idgen or IdGen()
    fig = block.figure

    # Normalise Axes → Figure for matplotlib-compatible objects
    if hasattr(fig, "get_figure") and not hasattr(fig, "savefig"):
        fig = fig.get_figure()

    try:
        lib = detect_library(fig)
    except BriefingError as exc:
        return (
            f'<div class="bf-placeholder">'
            f"⚠ {_html.escape(str(exc))}"
            f"</div>"
        )

    try:
        if lib == "matplotlib":
            inner = _render_matplotlib(fig, block.responsive, salt=idgen.next("mpl"))
        elif lib == "plotly":
            inner = _render_plotly(fig, block.responsive, div_id=idgen.next("plotly"))
        elif lib == "altair":
            inner = _render_altair(fig, block.responsive, div_id=idgen.next("altair"))
        elif lib == "bokeh":
            inner = _render_bokeh(fig)
        else:
            inner = f'<div class="bf-placeholder">Unknown library: {lib}</div>'
    except BriefingError as exc:
        return f'<div class="bf-placeholder">⚠ {_html.escape(str(exc))}</div>'

    caption_html = (
        f'<figcaption class="bf-plot__caption">{_html.escape(block.caption)}</figcaption>'
        if block.caption
        else ""
    )
    return f'<figure class="bf-block bf-plot">{inner}{caption_html}</figure>'


__all__ = ["detect_library", "get_runtime_scripts", "render_figure", "scan_for_plots"]
