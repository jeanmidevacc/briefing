"""Turn a rendered report into its golden snapshot text (#45).

A golden snapshot is the report's bytes with three kinds of content swapped for
a short marker, so that snapshots only change when briefing's own output does:

- **briefing's static files** (``static/report.css``, ``lab/static/lab.js``, …),
  inlined verbatim, become ``/* golden: static/report.js sha256 … */``. A change
  to the file still changes every snapshot that inlines it, by that one line.
- **chart libraries' output** (the Plotly and Vega runtimes, Matplotlib's SVG, a
  Plotly figure, an Altair spec) becomes a marker without a hash: it changes with
  the library's release, not with briefing. Ids that briefing gives a chart stay.
- **briefing's version** in ``<meta name="generator">`` and the footer becomes
  ``{version}``, so a release doesn't rewrite every snapshot.

Each swap only applies to text that is exactly what it expects; anything else
stays in the snapshot, so a change to how a file or chart is inlined shows up.
"""
from __future__ import annotations

import functools
import hashlib
import re
from datetime import UTC, datetime
from importlib.resources import files

import briefing as bf

#: The header date of every golden report.
NOW = datetime(2024, 1, 2, 3, 4, tzinfo=UTC)

_FIGURE = re.compile(
    r'(?P<open><figure class="bf-block bf-plot">)(?P<inner>.*?)'
    r'(?P<close><figcaption class="bf-plot__caption">|</figure>)',
    re.S,
)
_ALTAIR_SPEC = re.compile(r'(<script type="application/json" class="bf-altair__spec">).*?(</script>)', re.S)
_MPL_ID = re.compile(r'\bid="(mpl-\d+-)?[^"]*"')
_PLOTLY_ID = re.compile(r'<div id="([^"]+)" class="plotly-graph-div"')


@functools.cache
def static_files() -> dict[str, str]:
    """briefing's CSS and JS files, as {path inside the package: content}."""
    found: dict[str, str] = {}
    for package, folder in (("briefing", "static"), ("briefing.lab", "lab/static")):
        for entry in sorted((files(package) / "static").iterdir(), key=lambda e: e.name):
            if entry.is_file() and entry.name.endswith((".css", ".js")):
                found[f"{folder}/{entry.name}"] = entry.read_text(encoding="utf-8")
    return found


def static_marker(path: str, content: str) -> str:
    """The line that stands for the static file at *path* in a snapshot."""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    return f"/* golden: {path} sha256 {digest} */"


@functools.cache
def _runtimes() -> tuple[tuple[str, str], ...]:
    """The chart runtimes a report can inline, as (exact text, marker), for the libraries installed."""
    found: list[tuple[str, str]] = []
    try:
        from plotly.offline import get_plotlyjs
    except ImportError:
        pass
    else:
        found.append((get_plotlyjs(), "/* golden: plotly.js runtime from the plotly package */"))
    from briefing.renderers.plot import _vega_bundle

    vega = _vega_bundle()
    if vega is not None:
        found.append((vega, "/* golden: Vega runtime from vl-convert-python */"))
    return tuple(found)


def _figure_marker(match: re.Match[str]) -> str:
    inner = match["inner"]
    if inner.startswith("<svg"):
        # Every id briefing scoped shows as its prefix; an id it missed shows in full.
        ids = sorted({m.group(1) or m.group(0) for m in _MPL_ID.finditer(inner)})
        inner = f"<!-- golden: SVG from Matplotlib, ids {' '.join(ids)} -->"
    elif 'class="plotly-graph-div"' in inner:
        ids = _PLOTLY_ID.findall(inner)
        inner = f"<!-- golden: Plotly figure in div {' '.join(ids)} -->"
    elif inner.startswith('<div class="bf-altair"'):
        inner = _ALTAIR_SPEC.sub(r"\1/* golden: Vega-Lite spec from Altair */\2", inner)
    return f"{match['open']}{inner}{match['close']}"


def mask(html: str) -> str:
    """The golden snapshot text of *html*: see the module docstring for what is swapped."""
    for path, content in static_files().items():
        html = html.replace(content, static_marker(path, content))
    for text, marker in _runtimes():
        html = html.replace(text, marker)
    html = _FIGURE.sub(_figure_marker, html)
    return html.replace(f"briefing {bf.__version__}", "briefing {version}")
