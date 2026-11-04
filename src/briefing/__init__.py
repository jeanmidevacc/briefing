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
from briefing.renderers.html import render_report

# ── public API ────────────────────────────────────────────────────────────────


def save(
    blocks: Briefing | list[t.Any] | object,
    path: str,
    *,
    open: bool = False,  # noqa: A002
    name: str = "Report",
    formatting: Formatting | None = None,
    now: datetime | None = None,
) -> None:
    """Save *blocks* as a self-contained HTML file at *path*.

    Args:
        blocks: A :class:`~briefing.Briefing` instance, a list of blocks, or a
            single block.  Lists and single blocks are automatically wrapped.
        path: Destination file path (e.g. ``"report.html"``).
        open: Open the file in your default browser after saving.
        name: Document title shown in the browser tab and report header.
        formatting: A :class:`~briefing.Formatting` instance controlling the theme.
        now: Pin the header timestamp for byte-reproducible output (see also the
            ``SOURCE_DATE_EPOCH`` environment variable).

    Example::

        bf.save(report, "analysis.html", name="Q1 Analysis", open=True)
    """
    wrapped = Briefing.wrap(blocks)
    html = render_report(wrapped, name=name, formatting=formatting, now=now)
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
) -> str:
    """Render *blocks* to a self-contained HTML string.

    In a notebook you don't need this: a block or a ``Briefing`` displays itself
    as an isolated preview, and :func:`preview` adds a name or a theme.

    Pass *now* (or set ``SOURCE_DATE_EPOCH``) for byte-reproducible output.

    Args:
        blocks: A :class:`Briefing`, a list of blocks, or a single block.
        name: Report title, shown in the browser tab and the header.
        formatting: A :class:`Formatting` instance controlling the theme.
        now: Pin the header timestamp for byte-reproducible output (see also
            the ``SOURCE_DATE_EPOCH`` environment variable).

    Returns:
        The complete HTML document.

    Example::

        html = bf.stringify(bf.Text("# Hello"), name="Greeting")
        email_body = html  # or write it anywhere a string goes
    """
    wrapped = Briefing.wrap(blocks)
    return render_report(wrapped, name=name, formatting=formatting, now=now)


__version__ = "0.2.0"

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
