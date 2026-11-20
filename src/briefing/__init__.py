"""briefing — build beautiful, self-contained HTML reports from Python analysis.

Quick start::

    import briefing as bf

    report = bf.Briefing(
        bf.Text("# My Analysis"),
        bf.Group(
            bf.BigNumber("Accuracy", "92.4%", change="+1.2%", is_upward_change=True),
            bf.BigNumber("F1 Score", 0.89),
            columns=2,
        ),
        bf.Select(
            bf.Plot(fig, label="Chart"),
            bf.DataTable(df, label="Data"),
        ),
    )

    bf.save(report, "analysis.html")
"""
import typing as t
import warnings
import webbrowser
from datetime import datetime
from pathlib import Path

# ── lab: custom-visualisation blocks (briefing.lab.DataProfile / .DataDive) ───
# Same wheel; importing it registers its renderers. `briefing[lab]` only adds
# the pandas dependency those blocks need at render time.
from briefing import lab
from briefing._error import BriefingError
from briefing._preview import Preview, preview
from briefing._version import __version__

# ── blocks ────────────────────────────────────────────────────────────────────
from briefing.blocks import (
    HTML,
    Alert,
    AlertLevel,
    Banner,
    BigNumber,
    Block,
    Briefing,
    Code,
    DataTable,
    Formula,
    Group,
    Page,
    Plot,
    Select,
    SelectType,
    Table,
    Text,
    Toggle,
    VAlign,
    wrap_block,
)

# ── export: images and PDFs (Playwright is imported only when called) ────────
from briefing.export import save_image, save_pdf

# ── formatting ────────────────────────────────────────────────────────────────
from briefing.renderers.formatting import Formatting, TextAlignment, Width

# ── renderer ──────────────────────────────────────────────────────────────────
from briefing.renderers.fragment import render_embed_assets, render_fragment
from briefing.renderers.html import render_report

# ── public API ────────────────────────────────────────────────────────────────


def _render(
    blocks: Briefing | list[t.Any] | object,
    name: str,
    formatting: Formatting | None,
    now: datetime | None,
    full_html: bool,
    include_assets: bool,
    embed_id: str | None,
    header: bool | None,
) -> str:
    """A full report, or with ``full_html=False`` a fragment (#122)."""
    wrapped = Briefing.wrap(blocks)
    if full_html:
        options = {"include_assets": not include_assets, "embed_id": embed_id, "header": header}
        given = [option for option, set_ in options.items() if set_]
        if given:
            raise BriefingError(
                f"{', '.join(given)} only apply to a fragment: pass full_html=False as well, or leave them out."
            )
        return render_report(wrapped, name=name, formatting=formatting, now=now)
    return render_fragment(
        wrapped, name=name, formatting=formatting, now=now,
        include_assets=include_assets, embed_id=embed_id, header=bool(header),
    )


def save(
    blocks: Briefing | list[t.Any] | object,
    path: str,
    *,
    open: bool = False,  # noqa: A002
    name: str = "Report",
    formatting: Formatting | None = None,
    now: datetime | None = None,
    full_html: bool = True,
    include_assets: bool = True,
    embed_id: str | None = None,
    header: bool | None = None,
) -> None:
    """Save *blocks* as a self-contained HTML file at *path*, or as a fragment to embed.

    Args:
        blocks: A :class:`~briefing.Briefing` instance, a list of blocks, or a
            single block.  Lists and single blocks are automatically wrapped.
        path: Destination file path (e.g. ``"report.html"``).
        open: Open the file in your default browser after saving.
        name: Document title shown in the browser tab and report header.
        formatting: A :class:`~briefing.Formatting` instance controlling the theme.
        now: Pin the header timestamp for byte-reproducible output (see also the
            ``SOURCE_DATE_EPOCH`` environment variable).
        full_html: ``False`` saves a fragment, one ``<div>`` to put into another page,
            as :func:`stringify` describes.
        include_assets: With ``full_html=False``: ``False`` leaves out the CSS and
            scripts, for a page that loads :func:`embed_assets` once.
        embed_id: With ``full_html=False``: the fragment's id, which starts every id
            in it. Defaults to the name of its only block, else a hash of it.
        header: With ``full_html=False``: ``True`` shows *name* and the date above it.

    Example::

        bf.save(report, "analysis.html", name="Q1 Analysis", open=True)
        bf.save(chart, "revenue-embed.html", full_html=False)
    """
    html = _render(blocks, name, formatting, now, full_html, include_assets, embed_id, header)
    dest = Path(path)
    dest.write_text(html, encoding="utf-8")
    if open:
        webbrowser.open(dest.resolve().as_uri())


def stringify(
    blocks: Briefing | list[t.Any] | object,
    *,
    name: str = "Report",
    formatting: Formatting | None = None,
    now: datetime | None = None,
    full_html: bool = True,
    include_assets: bool = True,
    embed_id: str | None = None,
    header: bool | None = None,
) -> str:
    """Render *blocks* to a self-contained HTML string, or to a fragment to embed.

    In a notebook you don't need this: a block or a ``Briefing`` displays itself
    as an isolated preview, and :func:`preview` adds a name or a theme.

    Pass *now* (or set ``SOURCE_DATE_EPOCH``) for byte-reproducible output.

    With ``full_html=False`` the result is a fragment, like Plotly's
    ``to_html(full_html=False)``: one ``<div class="bf-embed">`` to put into another
    page (a docs site, a notebook, a Confluence HTML macro). It carries its theme,
    keeps its CSS and scripts to itself, and works next to other fragments.

    Args:
        blocks: A :class:`Briefing`, a list of blocks, or a single block.
        name: Report title, shown in the browser tab and the header.
        formatting: A :class:`Formatting` instance controlling the theme.
        now: Pin the header timestamp for byte-reproducible output (see also
            the ``SOURCE_DATE_EPOCH`` environment variable).
        full_html: ``False`` returns a fragment instead of a whole document.
        include_assets: With ``full_html=False``: ``False`` leaves out the CSS and
            scripts, for a page that loads :func:`embed_assets` once in its ``<head>``.
        embed_id: With ``full_html=False``: the fragment's id, which starts every id
            in it. Defaults to the name of its only block, else ``bf-e`` and 8 hex
            digits of a hash of the fragment. Two fragments on a page need two ids.
        header: With ``full_html=False``: ``True`` shows *name* and the date above it.

    Returns:
        The complete HTML document, or the fragment.

    Example::

        html = bf.stringify(bf.Text("# Hello"), name="Greeting")
        email_body = html  # or write it anywhere a string goes
        fragment = bf.stringify(bf.Plot(fig, name="revenue"), full_html=False)  # <div id="revenue" …>
    """
    return _render(blocks, name, formatting, now, full_html, include_assets, embed_id, header)


def embed_assets(blocks: Briefing | list[t.Any] | object) -> str:
    """The CSS and scripts of fragments, once, for the ``<head>`` of a page that holds several.

    Like Plotly's ``get_plotlyjs()``: put it in the page once, then render each
    fragment with ``include_assets=False``. It holds briefing's CSS scoped to
    fragments, ``report.js``, the scripts of lab blocks and the chart runtimes
    (Plotly, Vega) that *blocks* need.

    Args:
        blocks: The blocks the page's fragments hold: a block, a :class:`Briefing`,
            or a list of either.

    Returns:
        ``<style>`` and ``<script>`` tags.

    Example::

        head = bf.embed_assets([chart, table])
        parts = [bf.stringify(b, full_html=False, include_assets=False) for b in (chart, table)]
    """
    items = blocks if isinstance(blocks, list) else [blocks]
    return render_embed_assets(Briefing.wrap(item) for item in items)


__all__: list[str] = [
    # error
    "BriefingError",
    # blocks — text
    "Alert",
    "AlertLevel",
    "BigNumber",
    "Code",
    "Formula",
    "HTML",
    "Text",
    # blocks — layout
    "Block",
    "Briefing",
    "Group",
    "Page",
    "Select",
    "SelectType",
    "Toggle",
    "VAlign",
    "wrap_block",
    # blocks — asset
    "Banner",
    "DataTable",
    "Plot",
    "Table",
    # custom-visualisation subpackage (bf.lab.DataProfile / bf.lab.DataDive)
    "lab",
    # formatting
    "Formatting",
    "TextAlignment",
    "Width",
    # api
    "Preview",
    "embed_assets",
    "preview",
    "save",
    "save_image",
    "save_pdf",
    "stringify",
    # meta
    "__version__",
]


# ── deprecated aliases (removed after 0.2) ───────────────────────────────────

#: old name -> (new name, object)
_RENAMED: dict[str, tuple[str, object]] = {
    "Blocks": ("Briefing", Briefing),
    "BaseBlock": ("Block", Block),
    "save_report": ("save", save),
    "stringify_report": ("stringify", stringify),
}

#: names that moved into the briefing.lab subpackage
_MOVED_TO_LAB: frozenset[str] = frozenset({"DataProfile", "DataDive"})


def __getattr__(name: str) -> t.Any:
    if name in _RENAMED:
        new, obj = _RENAMED[name]
        warnings.warn(
            f"briefing.{name} is deprecated and will be removed after 0.2 — "
            f"use briefing.{new}.",
            DeprecationWarning,
            stacklevel=2,
        )
        return obj
    if name in _MOVED_TO_LAB:
        warnings.warn(
            f"briefing.{name} moved to briefing.lab.{name} (pip install briefing[lab]) "
            f"and will be removed after 0.2 — use briefing.lab.{name}.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(lab, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
