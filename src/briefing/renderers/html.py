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
import hashlib
import html as _html
import os
import re
import typing as t
import warnings
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, PackageLoader

from briefing._colors import css_color
from briefing._prose import slug
from briefing._version import __version__
from briefing.blocks.asset import DataTable, Plot, Table
from briefing.blocks.banner import Banner
from briefing.blocks.base import Block, ContainerBlock
from briefing.blocks.chips import Chip, Chips
from briefing.blocks.files import Attachment, Image
from briefing.blocks.layout import Briefing, Card, Group, Select, SelectType, Toggle, VAlign
from briefing.blocks.text import HTML, Alert, BigNumber, Code, Formula, Text
from briefing.renderers.copy_embed import RUNTIME_GLOBALS, embed_label
from briefing.renderers.formatting import Formatting
from briefing.renderers.formula import latex_to_mathml
from briefing.renderers.header import render_header
from briefing.renderers.inline import inline_markdown, inline_plain
from briefing.renderers.links import claim_links
from briefing.renderers.markup import close_open_markup
from briefing.renderers.normalize import normalize
from briefing.renderers.pack import UNPACK_JS, pack
from briefing.renderers.plot import (
    get_runtime_scripts,
    render_figure,
    runtime_script,
    runtime_sources,
    scan_for_plots,
)
from briefing.renderers.registry import (
    IdGen as _IdGen,
)
from briefing.renderers.registry import (
    asset_js_for,
    iter_blocks,
    lookup_renderer,
    renderer_for,
)
from briefing.renderers.size import RUNTIME_NAMES, Part, block_parts, format_size
from briefing.renderers.table import csv_text, from_json, render_datatable, render_table

# ── package resource loading ──────────────────────────────────────────────────

_pkg = files("briefing")


def _load_static(name: str) -> str:
    return (_pkg / "static" / name).read_text(encoding="utf-8")


_CSS = _load_static("report.css")
_JS = _load_static("report.js")
_EXPORT_JS = _load_static("export.js")
_EXPORT_CSS = _load_static("export.css")
_EXPORT_LABELS = {"png": "Save as PNG"}
_COPY_JS = _load_static("copy-embed.js")
_COPY_CSS = _load_static("copy-embed.css")
#: Stands for the report's id prefix while it renders, until a hash of the report names it (#124).
_REPORT_TOKEN = "bfreportidtoken"

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


#: ``## Methodology {#methodology}``: a heading's explicit name, at the end of its text (#24).
_HEADING_NAME = re.compile(r"\s*\{#([a-zA-Z][a-zA-Z0-9_-]*)\}\s*$")

_LINK_ICON = (
    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" '
    'stroke-linecap="round" aria-hidden="true"><path d="M6.5 9.5l3-3"/>'
    '<path d="M7 4.5l1-1a2.83 2.83 0 0 1 4 4l-1 1"/><path d="M9 11.5l-1 1a2.83 2.83 0 0 1-4-4l1-1"/></svg>'
)


def _heading_actions(link: str) -> str:
    """The buttons shown beside a named heading: copy its link (room for more, #124)."""
    return (
        f'<span class="bf-heading-actions"><a class="bf-heading-link" href="#{link}" '
        f'aria-label="Copy link to this section" title="Copy link">{_LINK_ICON}</a></span>'
    )


def _name_headings(state: t.Any) -> None:
    """markdown-it core rule: ``{#name}`` at the end of a heading becomes its link id."""
    claim = state.env.get("bf_heading")
    tokens = state.tokens
    for i, token in enumerate(tokens):
        if claim is None or token.type != "heading_open" or not tokens[i + 1].children:
            continue
        last = tokens[i + 1].children[-1]
        match = _HEADING_NAME.search(last.content) if last.type == "text" else None
        if match is None:
            continue
        last.content = last.content[:match.start()]
        name = match.group(1)
        if name == "auto":  # a slug of the heading's text (#184)
            words = "".join(c.content for c in tokens[i + 1].children if c.type in ("text", "code_inline"))
            name = slug(words)
        link = claim(name)
        token.attrSet("id", link)
        token.attrSet("data-bf-link", "")
        tokens[i + 2].meta["bf_link"] = link


def _close_heading(renderer: t.Any, tokens: t.Any, idx: int, options: t.Any, env: t.Any) -> str:
    link = tokens[idx].meta.get("bf_link")
    closing = str(renderer.renderToken(tokens, idx, options, env))
    return _heading_actions(link) + closing if link else closing


def _markdown(text: str, heading: Callable[[str], str] | None = None) -> str:
    """Markdown as Text renders it: CommonMark plus pipe tables, its raw HTML kept inside the block.

    *heading* claims the link id of a heading named with ``{#name}``; without it the
    text stays as written.
    """
    from markdown_it import MarkdownIt

    md = MarkdownIt("commonmark").enable("table")
    md.core.ruler.push("bf_heading_names", _name_headings)
    md.add_render_rule("heading_close", _close_heading)
    return close_open_markup(str(md.render(text, {"bf_heading": heading})))


def _headings_of(block: Block, idgen: _IdGen) -> Callable[[str], str]:
    return lambda name: idgen.claim(block, name, f"the heading {{#{name}}}")


@renderer_for(Text)
def _render_text(block: Text, idgen: _IdGen) -> str:
    return f'<div class="bf-block bf-text">{_markdown(block.content, _headings_of(block, idgen))}</div>'


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
def _render_banner(block: Banner, idgen: _IdGen) -> str:
    src = f"data:{block.mime};base64,{base64.b64encode(block.image).decode('ascii')}"
    alt = f'alt="{_html.escape(block.alt)}"' if block.alt else 'alt="" aria-hidden="true"'
    mode = f"bf-banner--{block.side}" if block.fade else "bf-banner--uniform"
    kicker = f'<p class="bf-banner__kicker">{_html.escape(block.kicker)}</p>' if block.kicker else ""
    style = (f"--bf-banner-h: {block.height}; --bf-banner-pos: {block.text_position:g}%; "
             f"--bf-banner-focus: {block.focus[0]:g}% {block.focus[1]:g}%")
    return (
        f'<div class="bf-block bf-banner {mode}" style="{style}">'
        f'<img class="bf-banner__image" src="{src}" {alt}>'
        f'<div class="bf-banner__veil" style="{_veil(block)}"></div>'
        f'<div class="bf-banner__text bf-text">{kicker}{_markdown(block.text, _headings_of(block, idgen))}</div>'
        f"</div>"
    )


@renderer_for(Image)
def _render_image(block: Image, _: _IdGen) -> str:
    src = f"data:{block.mime};base64,{base64.b64encode(block.image).decode('ascii')}"
    alt = block.alt if block.alt is not None else inline_plain(block.caption or "")
    style = f' style="width: {block.width}"' if block.width else ""
    caption = (
        f'<figcaption class="bf-image__caption">{inline_markdown(block.caption)}</figcaption>' if block.caption else ""
    )
    return (
        f'<figure class="bf-block bf-image"><img class="bf-image__img" src="{src}" alt="{_html.escape(alt)}"'
        f"{style}>{caption}</figure>"
    )


#: Types an attachment stores as packed text (#38), besides text/*.
_TEXT_TYPES = {"application/json", "application/xml", "image/svg+xml", "application/javascript", "application/sql"}


def attachment_content(block: Attachment) -> tuple[bytes, bool]:
    """What an attachment downloads, and whether it is text (stored packed)."""
    if not isinstance(block.file, bytes):
        return csv_text(block.file).encode(), True
    if not (block.mime.startswith("text/") or block.mime in _TEXT_TYPES):
        return block.file, False
    try:
        block.file.decode()
    except UnicodeDecodeError:
        return block.file, False
    return block.file, True


@renderer_for(Attachment)
def _render_attachment(block: Attachment, _: _IdGen) -> str:
    data, text = attachment_content(block)
    if text:
        encoded, size = pack(data.decode())
        stored = f'data-size="{size}" data-packed'
    else:
        encoded, stored = base64.b64encode(data).decode("ascii"), f'data-size="{len(data)}"'
    kind = Path(block.filename).suffix.lstrip(".").upper() or "File"
    return (
        f'<div class="bf-block bf-attachment">'
        f'<button class="bf-attachment__button" type="button" data-bf-filename="{_html.escape(block.filename)}" '
        f'data-bf-type="{_html.escape(block.mime)}">'
        f'<span class="bf-attachment__label">{_html.escape(block.label or block.filename)}</span>'
        f'<span class="bf-attachment__meta">{_html.escape(kind)}, {format_size(len(data))}</span>'
        f"</button>"
        f'<span class="bf-attachment__note" aria-live="polite"></span>'
        f'<script type="application/json" class="bf-attachment__data" {stored}>"{encoded}"</script>'
        f"</div>"
    )


@renderer_for(HTML)
def _render_html(block: HTML, _: _IdGen) -> str:
    return f'<div class="bf-block bf-html">{close_open_markup(block.content)}</div>'


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
        f'<div class="bf-code__caption">{inline_markdown(block.caption)}</div>'
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
        f'<div class="bf-formula__caption">{inline_markdown(block.caption)}</div>'
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



def _shown(block: BigNumber, number: t.Any) -> str:
    """*number* as the BigNumber's ``format`` shows it."""
    how = block.format
    if how is None:
        return str(number)
    return str(how(number)) if callable(how) else how.format(number)


def _computed_change(block: BigNumber) -> tuple[str, bool | None, bool | None]:
    """The change from ``prev_value`` (#35): its text, whether it went up (``None``: equal), and whether that's good."""
    raw = t.cast(float, block.value) - t.cast(float, block.prev_value)  # ints stay ints: +5, not +5.0
    prev, delta = float(t.cast(float, block.prev_value)), float(raw)
    up = None if delta == 0 else delta > 0
    sign = "+" if delta > 0 else "-" if delta < 0 else ""
    if block.change_as == "points":
        percent_format = isinstance(block.format, str) and "%}" in block.format
        text = f"{sign}{abs(delta) * (100 if percent_format else 1):.1f} pt"
    elif block.change_as == "percent" and prev != 0:
        text = f"{sign}{abs(delta) / abs(prev) * 100:.1f}%"
    else:  # absolute, or a percent change from zero
        text = f"{sign}{_shown(block, abs(raw))}"
    good = None if up is None else up == block.higher_is_better
    return text, up, good


def _sparkline(block: BigNumber) -> str:
    """The trend line: an SVG path scaled to the card's width; missing values leave gaps."""
    points = block.sparkline or []
    known = [p for p in points if p is not None]
    lo, hi = min(known), max(known)
    span = hi - lo
    step = 100 / max(len(points) - 1, 1)
    path, last = "", (0.0, 0.0)
    pen_up = True
    for i, v in enumerate(points):
        if v is None:
            pen_up = True
            continue
        # 2 units of room at the top and bottom; a flat series runs at mid height.
        x, y = i * step, (22 - (v - lo) / span * 20) if hi > lo else 12.0
        path += f"{'M' if pen_up else 'L'}{x:.2f} {y:.2f}"
        pen_up, last = False, (x, y)
    from briefing.renderers.table import _fmt as number  # the series may not be in the value's unit

    label = f"Trend of {len(points)} values, from {number(known[0])} to {number(known[-1])}"
    return (f'<svg class="bf-bignumber__spark" viewBox="0 0 100 24" preserveAspectRatio="none" role="img" '
            f'aria-label="{_html.escape(label)}"><path d="{path}"/>'
            f'<path class="bf-bignumber__spark-end" d="M{last[0]:.2f} {last[1]:.2f}h0"/></svg>')


@renderer_for(BigNumber)
def _render_bignumber(block: BigNumber, _: _IdGen) -> str:
    heading = inline_markdown(str(block.heading))
    value = _html.escape(_shown(block, block.value))

    change, up, good = block.change, block.is_upward_change, block.is_positive_intent
    title = ""
    if block.prev_value is not None:
        change, up, good = _computed_change(block)
        title = f' title="Previous: {_html.escape(_shown(block, block.prev_value))}"'

    change_html = ""
    if change is not None:
        # The arrow comes from is_upward_change, the colour from is_positive_intent
        # (falling back to the arrow's --up/--down colour); neither → neutral (#71).
        cls = ["bf-bignumber__change"]
        arrow = ""
        if up is not None:
            cls.append("bf-bignumber__change--up" if up else "bf-bignumber__change--down")
            arrow = "▲ " if up else "▼ "
        if good is not None:
            cls.append("bf-bignumber__change--good" if good else "bf-bignumber__change--bad")
        if len(cls) == 1:
            cls.append("bf-bignumber__change--neutral")
        change_html = f'<div class="{" ".join(cls)}"{title}>{arrow}{_html.escape(change)}</div>'

    spark = _sparkline(block) if block.sparkline else ""
    accent = (f' bf-bignumber--accent" style="--bf-number-accent: {_html.escape(css_color(block.accent))}'
              if block.accent else "")
    return (
        f'<div class="bf-block bf-bignumber{accent}">'
        f'<div class="bf-bignumber__heading">{heading}</div>'
        f'<div class="bf-bignumber__value">{value}</div>'
        f"{change_html}{spark}"
        f"</div>"
    )


def chips_html(chips: list[Chip], cls: str = "") -> str:
    """A ``<ul>`` of pills (#27): Chips blocks and a Card's tags."""
    items = []
    for chip in chips:
        attrs = f' title="{_html.escape(chip.tooltip)}"' if chip.tooltip else ""
        if chip.color:
            attrs += f' style="--bf-chip: {_html.escape(css_color(chip.color))}"'
        kind = "bf-chip bf-chip--color" if chip.color else "bf-chip"
        items.append(f'<li class="{kind}"{attrs}>{_html.escape(chip.text)}</li>')
    return f'<ul class="bf-chips{cls}">{"".join(items)}</ul>'


@renderer_for(Chips)
def _render_chips(block: Chips, _: _IdGen) -> str:
    return chips_html(block.items, " bf-block")


@renderer_for(Alert)
def _render_alert(block: Alert, _: _IdGen) -> str:
    level = block.level.value
    title_html = (
        f'<div class="bf-alert__title">{inline_markdown(block.title)}</div>'
        if block.title
        else ""
    )
    return (
        f'<div class="bf-block bf-alert bf-alert--{level}" role="alert">'
        f"{title_html}"
        f'<div class="bf-alert__message">{inline_markdown(block.message)}</div>'
        f"</div>"
    )


@renderer_for(Group)
def _render_group(block: Group, idgen: _IdGen) -> str:
    inner = "\n".join(_render_block(b, idgen) for b in block.blocks)

    extra = ""
    if block.min_width:  # as many per row as fit, up to columns when above 1 (#27)
        style = f'style="--bf-min: {block.min_width}; --bf-cols: {block.columns if block.columns > 1 else 0};"'
        extra = " bf-group--fit"
    elif block.widths:
        cols_css = " ".join(f"{w}fr" for w in block.widths)
        style = f'style="grid-template-columns: {cols_css};"'
    else:
        style = f'style="--bf-cols: {block.columns};"'
    if block.columns >= 3 and not block.min_width:
        extra += " bf-group--wide"  # two per row on tablets (#27)

    valign_cls = (
        f" bf-group--valign-{block.valign}" if block.valign != VAlign.TOP else ""
    )
    return f'<div class="bf-block bf-group{extra}{valign_cls}" {style}>{inner}</div>'


@renderer_for(Card)
def _render_card(block: Card, idgen: _IdGen) -> str:
    """A frame with a heading line, its blocks stacked, its tags at the bottom (#27).

    A link is the title's ``<a>``, stretched over the card by CSS; controls inside stay on top.
    """
    head = ""
    if block.title or block.icon:
        icon = f'<span class="bf-card__icon" aria-hidden="true">{_html.escape(block.icon)}</span>' if block.icon else ""
        title = inline_markdown(block.title) if block.title else ""
        if block.link:
            title = f'<a class="bf-card__link" href="#{_html.escape(block.link)}">{inline_plain(block.title or "")}</a>'
        head = f'<div class="bf-card__head">{icon}<div class="bf-card__title">{title}</div></div>'
    body = "\n".join(_render_block(b, idgen) for b in block.blocks)
    body = f'<div class="bf-card__body">{body}</div>' if body else ""
    tags = chips_html(block.tags, " bf-card__tags") if block.tags else ""
    linked = " bf-card--link" if block.link else ""
    return f'<div class="bf-block bf-card{linked}">{head}{body}{tags}</div>'


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
            f'<div class="bf-block bf-select{block.style.classes() if block.style else ""}" id="{uid}">'
            f'<div class="bf-select__tablist" role="tablist">{tabs_html}</div>'
            f"{panels_html}"
            f"</div>"
        )

    else:  # DROPDOWN
        # Named after the Select's label, linked to the panel it shows (#29).
        options_html = ""
        panels_html = ""
        for i, child in enumerate(block.blocks):
            label = _html.escape(child.label or f"Option {i + 1}")
            panel_id = f"{uid}-panel-{i}"
            options_html += f'<option value="{i}">{label}</option>'
            panel_html = _render_block(child, idgen)
            panels_html += (f'<div class="bf-select__panel" role="region" id="{panel_id}" aria-label="{label}">'
                            f"{panel_html}</div>")
        name = _html.escape(block.label or "Choose a view")
        controls = f' aria-controls="{uid}-panel-0"' if block.blocks else ""
        return (
            f'<div class="bf-block bf-select bf-select--dropdown" id="{uid}">'
            f'<select class="bf-select__select" aria-label="{name}"{controls}>'
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


def render_block(block: Block, idgen: _IdGen) -> str:
    """The HTML of *block*, with its link id and copy-embed marks; what containers call for each child."""
    return _render_block(block, idgen)


def _render_block(block: Block, idgen: _IdGen) -> str:
    if isinstance(block, Briefing):
        inner = "\n".join(_render_block(b, idgen) for b in block.blocks)
        return f'<div class="bf-blocks">{inner}</div>'

    renderer = lookup_renderer(block)
    html = renderer(block, idgen) if renderer is not None else _render_placeholder(block, idgen)
    if idgen.weights is not None and not isinstance(block, ContainerBlock):
        idgen.weights[id(block)] = len(html.encode())  # the size budget's parts (#38)
    link = idgen.link(block)
    marks = ""
    label = embed_label(block, page=idgen.is_page(block)) if idgen.embeds is not None or idgen.snaps else None
    if label is not None and idgen.snaps:
        marks += f' data-bf-snap="{_html.escape(label)}"'  # a snapshot button (#215), for export.js
    if label is not None and idgen.embeds is not None:
        # A copy-embed button (#124): what copy-embed.js needs to cut this block out as a fragment.
        marks += f' data-bf-embed="{_html.escape(label)}" data-bf-embed-id="{len(idgen.embeds)}"'
        libraries = scan_for_plots(block)
        idgen.embeds.append({
            "runtimes": sorted(RUNTIME_GLOBALS[lib] for lib in libraries if lib in RUNTIME_GLOBALS),
            "scripts": block_scripts(block),
        })
    return _with_attrs(html, link, marks) if link or marks else html


#: The first start tag of a block's HTML: its name and its attributes (quoted values may hold ">").
_FIRST_TAG = re.compile(r"""\s*<([a-zA-Z][\w-]*)((?:[^>"']|"[^"]*"|'[^']*')*)>""")
_ID_ATTR = re.compile(r'\sid="[^"]*"')


def _with_attrs(html: str, link: str | None, marks: str) -> str:
    """Put a named block's link id (in place of any id made up for it, #24) and *marks* on its outer element."""
    named = f' id="{link}" data-bf-link' if link else ""
    match = _FIRST_TAG.match(html)
    if match is None:
        return f"<div{named}{marks}>{html}</div>"
    attrs = _ID_ATTR.sub("", match.group(2), count=1) if link else match.group(2)
    return f"<{match.group(1)}{named}{marks}{attrs}>{html[match.end():]}"


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
    *,
    parts: list[Part] | None = None,
    paths: dict[int, str] | None = None,
) -> str:
    """Render *blocks* to a fully self-contained HTML string.

    Pass *now* (or set ``SOURCE_DATE_EPOCH``) to pin the header timestamp and
    get byte-identical output for identical input. *parts*, when given, is filled
    with what the report is made of and its bytes (#38): each block, at its place
    in *paths* (by default its place in *blocks*), each chart runtime, the
    copy-embed data.
    """
    fmt = formatting or Formatting()
    normalised = normalize(blocks)
    export = getattr(normalised, "export", ())
    embed = "embed" in export
    snaps = "snapshot" in export  # a camera button on each block (#215)

    # Pre-pass: detect which library runtimes are needed and build <head> scripts.
    libraries = scan_for_plots(normalised)
    head_scripts = get_runtime_scripts(libraries, tagged=embed)

    extra_js = block_scripts(normalised)
    if "png" in export or snaps:  # the export script only ships in reports that asked for it
        extra_js.append(_EXPORT_JS)
    if embed:
        extra_js.append(_COPY_JS)
    # The scripts register their parts with window.briefing; a full report then wires up the
    # whole document once (#123). With copy-embed (#124) each script gets its own tag, so the
    # button can put the ones a block needs into its fragment.
    scripts = [_JS, *extra_js]
    if embed:
        report_scripts = "".join(f'<script data-bf-script="{i}">{js}</script>' for i, js in enumerate(scripts))
        report_scripts += "<script>briefing.init(document);</script>"
    else:
        report_scripts = f"<script>{chr(10).join([*scripts, 'briefing.init(document);'])}</script>"

    embed_data = ""
    if embed:
        # Copy-embed (#124): made-up ids start with a hash of the report, so a block cut out of
        # it becomes a fragment by renaming that prefix; links keep their addresses.
        from briefing.renderers.fragment import copy_data

        idgen = _IdGen(prefix=_REPORT_TOKEN, prefix_links=False, embeds=True, snaps=snaps,
                       weigh=parts is not None)
        content_html = render_content(normalised, idgen)
        report_id = "bf-r" + hashlib.sha256(content_html.encode()).hexdigest()[:8]
        content_html = content_html.replace(_REPORT_TOKEN, report_id)
        embeds = idgen.embeds or []
        embed_data = copy_data(normalised, fmt, content_html, f"{report_id}-", embeds, scripts) + "\n  "
    else:
        idgen = _IdGen(snaps=snaps, weigh=parts is not None)
        content_html = render_content(normalised, idgen)

    if parts is not None:
        parts += block_parts(blocks, idgen.weights or {}, paths)
        parts += [Part(RUNTIME_NAMES.get(defined, defined), len(runtime_script(defined, source).encode()))
                  for defined, source in runtime_sources(libraries)]
        if embed_data:
            parts.append(Part("the copy-embed data", len(embed_data.encode())))

    now = _resolve_now(now)
    template = _jinja_env.get_template("report.html.j2")

    return template.render(
        report_name=_html.escape(name),
        header_html=render_header(name, normalised.header, now, _export_menu(export)),
        css_vars=fmt.to_css_vars(),
        report_css=_CSS,
        report_scripts=report_scripts,
        head_scripts=head_scripts,
        content_html=content_html,
        version=__version__,
        footer_text=footer_text(normalised.footer),
        # copy-embed.css also styles the snapshot button: both sit in one toolbar on a block.
        export_css=(_EXPORT_CSS if "png" in export else "") + (_COPY_CSS if embed or snaps else ""),
        embed_data=embed_data,
    )


def block_scripts(root: Block) -> list[str]:
    """The scripts that optional blocks under *root* need (e.g. briefing.lab's), each once.

    Only these are inlined, so the core report.js stays lean when they're unused.
    """
    scripts: list[str] = []
    for block in iter_blocks(root):
        js = asset_js_for(block)
        if js is None and isinstance(block, DataTable) and from_json(block):
            js = UNPACK_JS  # a big table's rows are packed (#38)
        if js is None and isinstance(block, Attachment) and attachment_content(block)[1]:
            js = UNPACK_JS  # so is a text attachment (#36)
        if js is not None and js not in scripts:
            scripts.append(js)
    return scripts


def render_content(normalised: Briefing, idgen: _IdGen) -> str:
    """The HTML of a normalised tree's blocks, with the link ids its names claim (#24)."""
    claim_links(normalised, idgen)
    content_html = _render_block(normalised, idgen)
    idgen.check_links()
    return content_html


def footer_text(prefix: str | None) -> str:
    """The last line of a report or fragment: who made it, if it says so, and with which version."""
    made_with = f"Made with briefing {__version__}"
    return f"{_html.escape(prefix)} · {made_with}" if prefix else made_with


def _export_menu(export: tuple[str, ...]) -> str:
    """The header's export buttons, or nothing (so other reports render exactly as before)."""
    actions = [a for a in export if a in _EXPORT_LABELS]  # "embed" puts its buttons on the blocks
    if not actions:
        return ""
    buttons = "".join(
        f'<button class="bf-export__btn" type="button" data-export="{a}">{_EXPORT_LABELS[a]}</button>' for a in actions
    )
    return f'<div class="bf-export" role="group" aria-label="Export">{buttons}</div>'


__all__ = ["render_report"]
