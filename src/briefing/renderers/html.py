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

import base64
import html as _html
import os
import warnings
from datetime import UTC, datetime
from importlib.resources import files

from jinja2 import Environment, PackageLoader

from briefing._version import __version__
from briefing.blocks.asset import DataTable, Plot, Table
from briefing.blocks.banner import Banner
from briefing.blocks.base import Block
from briefing.blocks.layout import Briefing, Group, Select, SelectType, Toggle, VAlign
from briefing.blocks.text import HTML, Alert, BigNumber, Code, Formula, Text
from briefing.renderers.formatting import Formatting
from briefing.renderers.formula import latex_to_mathml
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
_EXPORT_JS = _load_static("export.js")
_EXPORT_CSS = _load_static("export.css")
_EXPORT_LABELS = {"png": "Save as PNG", "pdf": "Print"}

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


def _markdown(text: str) -> str:
    """Markdown as Text renders it: CommonMark plus pipe tables."""
    from markdown_it import MarkdownIt

    return str(MarkdownIt("commonmark").enable("table").render(text))


@renderer_for(Text)
def _render_text(block: Text, _: _IdGen) -> str:
    return f'<div class="bf-block bf-text">{_markdown(block.content)}</div>'


def _veil(block: Banner) -> str:
    """The veil's background: one rgba layer, or a gradient that eases in over 20 % of the width."""
    alpha = block.opacity / 100
    if not block.fade:
        return f"background: rgba(var(--bf-bg-rgb), {alpha:g})"
    pos = block.text_position
    # Smoothstep stops across the fade, so there is no visible edge where it starts or ends.
    ramp = [(k / 8) ** 2 * (3 - 2 * k / 8) for k in range(9)]
    if block.side == "right":  # clear on the left, fading in towards the text at pos
        stops = [(0.0, 0.0)] + [(pos - 20 + 20 * k / 8, alpha * s) for k, s in enumerate(ramp)] + [(100.0, alpha)]
    else:  # text on the left up to pos, fading out after it
        stops = [(0.0, alpha)] + [(pos + 20 * k / 8, alpha * (1 - s)) for k, s in enumerate(ramp)] + [(100.0, 0.0)]
    parts = ", ".join(f"rgba(var(--bf-bg-rgb), {a:.4g}) {x:.4g}%" for x, a in stops)
    return f"background-image: linear-gradient(to right, {parts})"


@renderer_for(Banner)
def _render_banner(block: Banner, _: _IdGen) -> str:
    src = f"data:{block.mime};base64,{base64.b64encode(block.image).decode('ascii')}"
    alt = f'alt="{_html.escape(block.alt)}"' if block.alt else 'alt="" aria-hidden="true"'
    mode = f"bf-banner--{block.side}" if block.fade else "bf-banner--uniform"
    style = (f"--bf-banner-h: {block.height}; --bf-banner-pos: {block.text_position:g}%; "
             f"--bf-banner-focus: {block.focus[0]:g}% {block.focus[1]:g}%")
    return (
        f'<div class="bf-block bf-banner {mode}" style="{style}">'
        f'<img class="bf-banner__image" src="{src}" {alt}>'
        f'<div class="bf-banner__veil" style="{_veil(block)}"></div>'
        f'<div class="bf-banner__text bf-text">{_markdown(block.text)}</div>'
        f"</div>"
    )


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
    caption = (
        f'<div class="bf-formula__caption">{_html.escape(block.caption)}</div>'
        if block.caption
        else ""
    )
    mathml = latex_to_mathml(block.content)
    if mathml is not None:
        content = f'<div class="bf-formula__content">{mathml}</div>'
    else:
        warnings.warn(
            f"Formula: couldn't convert {block.content[:80]!r} to MathML; the report shows the LaTeX source. "
            "Check for typos, unbalanced braces or unsupported commands.",
            UserWarning,
            stacklevel=2,
        )
        content = (
            '<div class="bf-formula__error" role="note">'
            "⚠ This formula couldn't be rendered; showing its LaTeX source.</div>"
            f'<pre class="bf-formula__source"><code>{_html.escape(block.content)}</code></pre>'
        )
    return f'<div class="bf-block bf-formula">{content}{caption}</div>'



@renderer_for(BigNumber)
def _render_bignumber(block: BigNumber, _: _IdGen) -> str:
    heading = _html.escape(str(block.heading))
    value = _html.escape(str(block.value))

    change_html = ""
    if block.change is not None:
        # The arrow comes from is_upward_change, the colour from is_positive_intent
        # (falling back to the arrow's --up/--down colour); neither → neutral (#71).
        cls = ["bf-bignumber__change"]
        arrow = ""
        if block.is_upward_change is not None:
            cls.append("bf-bignumber__change--up" if block.is_upward_change else "bf-bignumber__change--down")
            arrow = "▲ " if block.is_upward_change else "▼ "
        if block.is_positive_intent is not None:
            cls.append("bf-bignumber__change--good" if block.is_positive_intent else "bf-bignumber__change--bad")
        if len(cls) == 1:
            cls.append("bf-bignumber__change--neutral")
        change_html = f'<div class="{" ".join(cls)}">{arrow}{_html.escape(block.change)}</div>'

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
def _render_table(block: Table, idgen: _IdGen) -> str:
    return render_table(block, idgen)


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
    export = getattr(normalised, "export", ())
    if export:  # the menu's script only ships in reports that asked for the menu
        extra_js.append(_EXPORT_JS)
    report_js = "\n".join([_JS, *extra_js])

    idgen = _IdGen()
    content_html = _render_block(normalised, idgen)

    now = _resolve_now(now)
    template = _jinja_env.get_template("report.html.j2")

    return template.render(
        report_name=_html.escape(name),
        report_date=now.strftime("%Y-%m-%d %H:%M UTC"),
        report_date_iso=now.isoformat(),
        css_vars=fmt.to_css_vars(),
        report_css=_CSS,
        report_js=report_js,
        head_scripts=head_scripts,
        content_html=content_html,
        show_header=name != "Report" or bool(export),
        version=__version__,
        footer_text=_footer_text(normalised.footer),
        export_html=_export_menu(export),
        export_css=_EXPORT_CSS if export else "",
    )


def _footer_text(prefix: str | None) -> str:
    """The report's last line: who made it, if the report says so, and with which version."""
    made_with = f"Made with briefing {__version__}"
    return f"{_html.escape(prefix)} · {made_with}" if prefix else made_with


def _export_menu(export: tuple[str, ...]) -> str:
    """The header's export buttons, or nothing (so other reports render exactly as before)."""
    if not export:
        return ""
    buttons = "".join(
        f'<button class="bf-export__btn" type="button" data-export="{a}">{_EXPORT_LABELS[a]}</button>' for a in export
    )
    return f'<div class="bf-export" role="group" aria-label="Export">{buttons}</div>'


__all__ = ["render_report"]
