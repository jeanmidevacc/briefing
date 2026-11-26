"""How a deck renders (#197): one HTML page of slides, every block drawn by its own renderer.

The slides sit on a stage drawn at :data:`WIDTH` × :data:`HEIGHT` and scaled to the window by
``static/deck.js``, which also moves between them, fits what overflows and opens the overview.
Without JavaScript the slides show one under another, at their full size.
"""
from __future__ import annotations

import html as _html
import re
import warnings

from briefing._error import BriefingError
from briefing._version import __version__
from briefing.blocks.banner import Banner
from briefing.blocks.base import Block, ContainerBlock
from briefing.blocks.layout import Briefing
from briefing.blocks.text import Text
from briefing.deck._blocks import Deck, Slide
from briefing.renderers.formatting import Formatting
from briefing.renderers.html import (
    _CSS,
    _JS,
    _jinja_env,
    _load_static,
    block_scripts,
    footer_text,
    render_block,
    with_block_styles,
)
from briefing.renderers.inline import inline_markdown, inline_plain
from briefing.renderers.links import claim_slide_links
from briefing.renderers.plot import get_runtime_scripts, runtime_script, runtime_sources, scan_for_plots
from briefing.renderers.registry import IdGen, iter_blocks, renderer_for
from briefing.renderers.size import RUNTIME_NAMES, Part, block_parts

#: The size every slide is drawn at, in CSS pixels (16:9); deck.js scales it to the window.
WIDTH, HEIGHT = 1280, 720
#: Above this many words of text, a slide is flagged: it reads best with less.
MAX_WORDS = 120

_DECK_CSS = _load_static("deck.css")
_DECK_JS = _load_static("deck.js")
_WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")


def _kind(slide: Slide) -> str:
    """The slide's extra class: a section slide (only a title) or a title slide (only a Banner)."""
    if not slide.blocks:
        return " bf-slide--section"
    if len(slide.blocks) == 1 and isinstance(slide.blocks[0], Banner) and slide.title is None:
        return " bf-slide--banner"
    return ""


def slide_html(slide: Slide, idgen: IdGen, number: int | None = None, total: int | None = None,
               footer: str = "") -> str:
    """A slide: its title, its blocks top to bottom, and with *number* its footer line and number."""
    title = f'<h2 class="bf-slide__title">{inline_markdown(slide.title)}</h2>' if slide.title else ""
    body = "\n".join(render_block(child, idgen) for child in slide.blocks)
    body = f'<div class="bf-slide__body"><div class="bf-slide__content">{body}</div></div>' if body else ""
    foot = ""
    attrs = ""
    if number is not None and total is not None:
        foot = (f'<footer class="bf-slide__footer"><span class="bf-slide__made">{footer}</span>'
                f'<span class="bf-slide__number">{number} / {total}</span></footer>')
        label = f"Slide {number} of {total}" + (f": {inline_plain(slide.title)}" if slide.title else "")
        attrs = f' data-bf-slide="{number}" aria-label="{_html.escape(label)}"'
    return f'<section class="bf-slide{_kind(slide)}"{attrs}>{title}{body}{foot}</section>'


@renderer_for(Slide)
def render_slide(block: Slide, idgen: IdGen) -> str:
    """A slide drawn on its own, without its place in a deck (``validate`` draws blocks this way)."""
    return slide_html(block, idgen)


def check_deck(deck: object) -> Deck:
    """*deck*, checked again: its slides may have changed since it was built."""
    if not isinstance(deck, Deck):
        hint = " For a report, use bf.save or bf.stringify." if isinstance(deck, Briefing) else ""
        raise BriefingError(f"bf.deck saves a bf.deck.Deck, not {type(deck).__name__}.{hint}")
    return Deck(*deck.slides, footer=deck.footer)


def render_slides(deck: Deck, idgen: IdGen) -> str:
    """The HTML of *deck*'s slides, with the link ids their names claim (a named slide scopes names)."""
    claim_slide_links(deck.slides, idgen)
    footer = footer_text(deck.footer)
    total = len(deck.slides)
    html = "\n".join(_with_link(slide_html(slide, idgen, i, total, footer), idgen.link(slide))
                     for i, slide in enumerate(deck.slides, start=1))
    idgen.check_links()
    return html


def _with_link(html: str, link: str | None) -> str:
    """Put a named slide's link id on its ``<section>``, as a report does for a named block."""
    if link is None:
        return html
    return html.replace("<section ", f'<section id="{_html.escape(link)}" data-bf-link ', 1)


def _words(slide: Slide) -> int:
    """How many words of text *slide* holds, in its Text blocks however deep."""
    return sum(len(_WORD.findall(block.content)) for block in iter_blocks(slide) if isinstance(block, Text))


def long_text(deck: Deck) -> list[tuple[int, str]]:
    """Each slide with more text than a slide reads well with: its index, and what to say."""
    found = []
    for index, slide in enumerate(deck.slides):
        words = _words(slide)
        if words > MAX_WORDS:
            named = f" ({inline_plain(slide.title)!r})" if slide.title else ""
            found.append((index, f"Slide {index + 1}{named} holds {words} words of text; a slide reads best with "
                                 f"fewer than about {MAX_WORDS}. Shorten it, or split it over two slides."))
    return found


def _warn_long_text(deck: Deck, stacklevel: int) -> None:
    """Warn about :func:`long_text`; *stacklevel* as ``warnings.warn`` takes it."""
    for _, message in long_text(deck):
        warnings.warn(message, UserWarning, stacklevel=stacklevel)


def render_deck(
    deck: Deck,
    name: str = "Deck",
    formatting: Formatting | None = None,
    *,
    parts: list[Part] | None = None,
    stacklevel: int = 2,
) -> str:
    """Render *deck* to one self-contained HTML page; *parts*, when given, gets what it weighs (#38).

    *stacklevel* points warnings at the caller, as ``warnings.warn`` counts from here: 2 is
    render_deck's caller.
    """
    deck = check_deck(deck)
    _warn_long_text(deck, stacklevel + 1)
    fmt = formatting or Formatting()
    tree = Briefing(*deck.slides)
    libraries = scan_for_plots(tree)
    scripts = [_JS, *block_scripts(tree), _DECK_JS, "briefing.init(document);"]
    idgen = IdGen(weigh=parts is not None)
    slides = render_slides(deck, idgen)
    if parts is not None:
        paths = {id(slide): f"/slides/{i}" for i, slide in enumerate(deck.slides)}
        for i, slide in enumerate(deck.slides):
            for j, child in enumerate(slide.blocks):
                _paths(child, f"/slides/{i}/blocks/{j}", paths)
        parts += block_parts(tree, idgen.weights or {}, paths)
        parts += [Part(RUNTIME_NAMES.get(defined, defined), len(runtime_script(defined, source).encode()))
                  for defined, source in runtime_sources(libraries)]
    return _jinja_env.get_template("deck.html.j2").render(
        deck_name=_html.escape(name),
        css=f"{with_block_styles(_CSS, tree)}\n{_DECK_CSS}\n{fmt.to_css_vars()}",
        head_scripts=get_runtime_scripts(libraries),
        slides_html=slides,
        version=__version__,
        width=WIDTH,
        height=HEIGHT,
        scripts="\n".join(scripts),
    )


def _paths(block: Block, path: str, paths: dict[int, str]) -> None:
    paths[id(block)] = path
    for i, child in enumerate(block.blocks if isinstance(block, ContainerBlock) else []):
        _paths(child, f"{path}/blocks/{i}", paths)


__all__ = ["HEIGHT", "MAX_WORDS", "WIDTH", "check_deck", "long_text", "render_deck", "render_slide",
           "render_slides", "slide_html"]
