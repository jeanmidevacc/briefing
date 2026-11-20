"""Link ids for named blocks (#24), claimed before rendering.

Anchors come only from ``name=``, never from titles. The panels of a report's only
top-level ``Select`` (which top-level ``Page`` blocks become) are its pages:

- a page named ``detail`` links as ``#detail``;
- a block named ``by-region`` inside it as ``#detail/by-region``;
- a heading ``## Methodology {#methodology}`` in a ``Text`` there as ``#detail/methodology``.

Outside a named page, a name links as itself (``#by-region``). A name must be unique
within its page; :meth:`IdGen.claim` raises otherwise.
"""
from __future__ import annotations

from briefing.blocks.base import Block, ContainerBlock
from briefing.blocks.layout import Briefing, Select
from briefing.renderers.registry import IdGen


def claim_links(root: Briefing, idgen: IdGen) -> None:
    """Give every named block under *root* its link id, and every block its page."""
    pages = root.blocks[0] if len(root.blocks) == 1 and isinstance(root.blocks[0], Select) else None
    for block in root.blocks:
        if block is pages:
            _claim(block, None, idgen)
            for page in block.blocks:
                _claim(page, None, idgen, what="a page")
                idgen.place(page, page.name)  # a page's own headings (a Text page) sit in it
                for child in _children(page):
                    _walk(child, page.name, idgen)
        else:
            _walk(block, None, idgen)


def _walk(block: Block, page: str | None, idgen: IdGen) -> None:
    _claim(block, page, idgen)
    for child in _children(block):
        _walk(child, page, idgen)


def _claim(block: Block, page: str | None, idgen: IdGen, what: str | None = None) -> None:
    idgen.place(block, page)
    idgen.name(block, what or f"a {type(block).__name__} block")


def _children(block: Block) -> list[Block]:
    return list(block.blocks) if isinstance(block, ContainerBlock) else []
