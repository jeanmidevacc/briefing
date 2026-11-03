"""HTML rendering engine for briefing reports.

Architecture
------------
- :func:`render_report` is the main entry point — it runs normalization,
  renders every block to an HTML string, then stitches everything together
  via the Jinja2 ``report.html.j2`` template.
- :func:`_render_block` is a dispatcher that routes each block type to its
  dedicated render function.
- An :class:`_IdGen` instance is threaded through every render call so that
  interactive blocks (Select, Toggle) get unique, collision-free DOM IDs.
- A pre-pass scans the block tree for Plot blocks so that library runtimes
  (e.g. plotlyjs) are embedded once in ``<head>`` rather than per-figure.
- Static assets (CSS, JS) are read from the package at import time and cached.
"""
from __future__ import annotations

import html as _html
import os
from datetime import UTC, datetime
from importlib.resources import files

from jinja2 import Environment, PackageLoader

from briefing.blocks.asset import DataTable, Plot, Table
from briefing.blocks.base import Block
from briefing.blocks.layout import Briefing, Group, Select, SelectType, Toggle, VAlign
from briefing.blocks.text import HTML, Alert, BigNumber, Code, Formula, Text
from briefing.renderers.formatting import Formatting
from briefing.renderers.normalize import normalize
from briefing.renderers.plot import get_runtime_scripts, render_figure, scan_for_plots
from briefing.renderers.registry import (
    IdGen as _IdGen,
)
from briefing.renderers.registry import (
    asset_js_for,
    iter_blocks,
    lookup_renderer,
    renderer_for,
)
from briefing.renderers.table import render_datatable, render_table

# ── package resource loading ──────────────────────────────────────────────────

_pkg = files("briefing")


def _load_static(name: str) -> str:
    return (_pkg / "static" / name).read_text(encoding="utf-8")


_CSS = _load_static("report.css")
_JS = _load_static("report.js")

_jinja_env = Environment(
    loader=PackageLoader("briefing", "templates"),
    autoescape=False,  # we control all HTML; user HTML goes in via safe blocks
    keep_trailing_newline=True,
)


# ── block renderers ───────────────────────────────────────────────────────────
#
# Each is registered with the shared renderer registry via ``@renderer_for``.
# ``briefing.lab`` (and any other optional subpackage) registers its own blocks
# the same way when imported.


@renderer_for(Text)
def _render_text(block: Text, _: _IdGen) -> str:
    from markdown_it import MarkdownIt

    md = MarkdownIt("commonmark").enable("table")
    body = md.render(block.content)
    return f'<div class="bf-block bf-text">{body}</div>'


@renderer_for(HTML)
def _render_html(block: HTML, _: _IdGen) -> str:
    return f'<div class="bf-block bf-html">{block.content}</div>'


def _highlight(code: str, language: str) -> str:
    """Return *code* as Pygments token ``<span>``s (escaped); plain escaped text for an unknown language."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound

    try:
        lexer = get_lexer_by_name(language, stripnl=False)
    except ClassNotFound:
        return _html.escape(code)
    return str(highlight(code, lexer, HtmlFormatter(nowrap=True))).removesuffix("\n")


@renderer_for(Code)
def _render_code(block: Code, _: _IdGen) -> str:
    lang = _html.escape(block.language)
    code = _highlight(block.content, block.language)
    header = f'<div class="bf-code__header"><span>{lang}</span></div>'
    caption = (
        f'<div class="bf-code__caption">{_html.escape(block.caption)}</div>'
        if block.caption
        else ""
    )
    return (
        f'<div class="bf-block bf-code">'
        f"{header}"
        f'<pre><code class="language-{lang}">{code}</code></pre>'
        f"{caption}"
        f"</div>"
    )


@renderer_for(Formula)
def _render_formula(block: Formula, _: _IdGen) -> str:
    content = _html.escape(block.content)
    caption = (
        f'<div class="bf-formula__caption">{_html.escape(block.caption)}</div>'
        if block.caption
        else ""
    )
    return (
        f'<div class="bf-block bf-formula">'
        f'<span class="bf-formula__content">\\({content}\\)</span>'
        f"{caption}"
        f"</div>"
    )


@renderer_for(BigNumber)
def _render_bignumber(block: BigNumber, _: _IdGen) -> str:
    heading = _html.escape(str(block.heading))
    value = _html.escape(str(block.value))

    change_html = ""
    if block.change is not None:
        direction = "up" if block.is_upward_change else "down"
        arrow = "▲" if block.is_upward_change else "▼"
        # Without is_positive_intent the colour follows the arrow (the --up/--down class).
        tone = ""
        if block.is_positive_intent is not None:
            tone = " bf-bignumber__change--good" if block.is_positive_intent else " bf-bignumber__change--bad"
        change_html = (
            f'<div class="bf-bignumber__change bf-bignumber__change--{direction}{tone}">'
            f"{arrow} {_html.escape(block.change)}"
            f"</div>"
        )

    return (
        f'<div class="bf-block bf-bignumber">'
        f'<div class="bf-bignumber__heading">{heading}</div>'
        f'<div class="bf-bignumber__value">{value}</div>'
        f"{change_html}"
        f"</div>"
    )


@renderer_for(Alert)
def _render_alert(block: Alert, _: _IdGen) -> str:
    level = block.level.value
    title_html = (
        f'<div class="bf-alert__title">{_html.escape(block.title)}</div>'
        if block.title
        else ""
    )
    return (
        f'<div class="bf-block bf-alert bf-alert--{level}" role="alert">'
        f"{title_html}"
        f'<div class="bf-alert__message">{_html.escape(block.message)}</div>'
        f"</div>"
    )


@renderer_for(Group)
def _render_group(block: Group, idgen: _IdGen) -> str:
    inner = "\n".join(_render_block(b, idgen) for b in block.blocks)

    if block.widths:
        cols_css = " ".join(f"{w}fr" for w in block.widths)
        style = f'style="grid-template-columns: {cols_css};"'
    else:
        style = f'style="--bf-cols: {block.columns};"'

    valign_cls = (
        f" bf-group--valign-{block.valign}" if block.valign != VAlign.TOP else ""
    )
    return f'<div class="bf-block bf-group{valign_cls}" {style}>{inner}</div>'


@renderer_for(Select)
def _render_select(block: Select, idgen: _IdGen) -> str:
    uid = idgen.next("sel")

    if block.type == SelectType.TABS:
        tabs_html = ""
        panels_html = ""
        for i, child in enumerate(block.blocks):
            tab_id = f"{uid}-tab-{i}"
            panel_id = f"{uid}-panel-{i}"
            label = _html.escape(child.label or f"Tab {i + 1}")
            tabs_html += (
                f'<button class="bf-select__tab" role="tab" '
                f'id="{tab_id}" aria-controls="{panel_id}">'
                f"{label}</button>"
            )
            panel_html = _render_block(child, idgen)
            panels_html += (
                f'<div class="bf-select__panel" role="tabpanel" '
                f'id="{panel_id}" aria-labelledby="{tab_id}">'
                f"{panel_html}</div>"
            )
        return (
            f'<div class="bf-block bf-select" id="{uid}">'
            f'<div class="bf-select__tablist" role="tablist">{tabs_html}</div>'
            f"{panels_html}"
            f"</div>"
        )

    else:  # DROPDOWN
        options_html = ""
        panels_html = ""
        for i, child in enumerate(block.blocks):
            label = _html.escape(child.label or f"Option {i + 1}")
            options_html += f'<option value="{i}">{label}</option>'
            panel_html = _render_block(child, idgen)
            panels_html += f'<div class="bf-select__panel">{panel_html}</div>'
        return (
            f'<div class="bf-block bf-select bf-select--dropdown" id="{uid}">'
            f'<select class="bf-select__select" aria-label="Select view">'
            f"{options_html}</select>"
            f"{panels_html}"
            f"</div>"
        )


@renderer_for(Toggle)
def _render_toggle(block: Toggle, idgen: _IdGen) -> str:
    uid = idgen.next("tog")
    label = _html.escape(block.label or "Details")
    inner = "\n".join(_render_block(b, idgen) for b in block.blocks)
    chevron = (
        '<svg class="bf-toggle__icon" width="16" height="16" viewBox="0 0 20 20" '
        'fill="currentColor" aria-hidden="true">'
        '<path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938'
        "a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 "
        '01.02-1.06z" clip-rule="evenodd"/></svg>'
    )
    return (
        f'<div class="bf-block bf-toggle" id="{uid}">'
        f'<button class="bf-toggle__header" aria-expanded="false" '
        f'aria-controls="{uid}-body">'
        f"<span>{label}</span>{chevron}"
        f"</button>"
        f'<div class="bf-toggle__body" id="{uid}-body" hidden>{inner}</div>'
        f"</div>"
    )


@renderer_for(Plot)
def _render_plot(block: Plot, idgen: _IdGen) -> str:
    return render_figure(block, idgen)


@renderer_for(Table)
def _render_table(block: Table, _: _IdGen) -> str:
    return render_table(block)


@renderer_for(DataTable)
def _render_datatable(block: DataTable, _: _IdGen) -> str:
    return render_datatable(block)


def _render_placeholder(block: Block, _: _IdGen) -> str:
    name = _html.escape(type(block).__name__)
    hint = (
        " — install its subpackage (e.g. briefing[lab])"
        if type(block).__module__.startswith("briefing.")
        else ""
    )
    return (
        f'<div class="bf-block bf-placeholder">'
        f"⚙ <strong>{name}</strong> has no registered renderer{hint}."
        f"</div>"
    )


# ── dispatcher ────────────────────────────────────────────────────────────────


def _render_block(block: Block, idgen: _IdGen) -> str:
    if isinstance(block, Briefing):
        inner = "\n".join(_render_block(b, idgen) for b in block.blocks)
        return f'<div class="bf-blocks">{inner}</div>'

    renderer = lookup_renderer(block)
    if renderer is not None:
        return renderer(block, idgen)

    return _render_placeholder(block, idgen)


# ── public API ────────────────────────────────────────────────────────────────


def _resolve_now(now: datetime | None) -> datetime:
    """Timestamp for the report header.

    Precedence: explicit *now* argument, then the ``SOURCE_DATE_EPOCH``
    environment variable (the reproducible-builds standard), then the wall
    clock. The first two make :func:`render_report` output byte-stable, which
    snapshot tests and "did the agent change anything" diffs rely on.
    """
    if now is not None:
        return now
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), tz=UTC)
    return datetime.now(tz=UTC)


def render_report(
    blocks: Briefing,
    name: str = "Report",
    formatting: Formatting | None = None,
    now: datetime | None = None,
) -> str:
    """Render *blocks* to a fully self-contained HTML string.

    Pass *now* (or set ``SOURCE_DATE_EPOCH``) to pin the header timestamp and
    get byte-identical output for identical input.
    """
    fmt = formatting or Formatting()
    normalised = normalize(blocks)

    # Pre-pass: detect which library runtimes are needed and build <head> scripts.
    libraries = scan_for_plots(normalised)
    head_scripts = get_runtime_scripts(libraries)

    # Pre-pass: collect JS assets that optional blocks (e.g. briefing.lab's
    # DataDive) need, so the core report.js stays lean when they're unused.
    extra_js: list[str] = []
    for block in iter_blocks(normalised):
        js = asset_js_for(block)
        if js is not None and js not in extra_js:
            extra_js.append(js)
    report_js = "\n".join([_JS, *extra_js])

    idgen = _IdGen()
    content_html = _render_block(normalised, idgen)

    now = _resolve_now(now)
    template = _jinja_env.get_template("report.html.j2")

    return template.render(
        report_name=name,
        report_date=now.strftime("%Y-%m-%d %H:%M UTC"),
        report_date_iso=now.isoformat(),
        css_vars=fmt.to_css_vars(),
        report_css=_CSS,
        report_js=report_js,
        head_scripts=head_scripts,
        content_html=content_html,
        show_header=name != "Report",
    )


__all__ = ["render_report"]
