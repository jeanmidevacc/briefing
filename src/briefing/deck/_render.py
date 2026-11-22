"""How a slide renders (#197): a ``<section>`` holding its title and its blocks, drawn by their own renderers."""
from __future__ import annotations

from briefing.deck._blocks import Slide
from briefing.renderers.html import render_block
from briefing.renderers.inline import inline_markdown
from briefing.renderers.registry import IdGen, renderer_for


@renderer_for(Slide)
def render_slide(block: Slide, idgen: IdGen) -> str:
    """A slide: its title (a section slide when it has no blocks), then its blocks, top to bottom."""
    section = "" if block.blocks else " bf-slide--section"
    title = f'<h2 class="bf-slide__title">{inline_markdown(block.title)}</h2>' if block.title else ""
    body = "\n".join(render_block(child, idgen) for child in block.blocks)
    body = f'<div class="bf-slide__body">{body}</div>' if body else ""
    return f'<section class="bf-slide{section}">{title}{body}</section>'


__all__ = ["render_slide"]
