"""The copy-embed button (#124): which blocks get one, and what each one says.

A report built with ``export=("embed",)`` puts a ``</>`` button on its pages, labelled
groups, rows (a Group of blocks side by side, #226), charts, tables, texts, numbers,
alerts, banners and lab blocks: the block types whose ``embed_noun`` is set. The button
copies that block as an embed fragment (#122), cut by ``static/copy-embed.js`` from an
untouched copy of the report that the report carries (``renderers/fragment.py``,
:func:`~briefing.renderers.fragment.copy_data`).
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from briefing.blocks.base import Block
from briefing.blocks.layout import Group
from briefing.blocks.text import Text
from briefing.renderers.inline import inline_plain

#: A markdown heading on the first line, without its ``{#name}``.
_FIRST_HEADING = re.compile(r"\s*#{1,6}[ \t]+([^\n]+?)(?:[ \t]*\{#[\w-]+\})?[ \t]*(?:\n|$)")

#: The global each chart library's runtime defines (``renderers/plot.py``).
RUNTIME_GLOBALS = {"plotly": "Plotly", "altair": "vegaEmbed"}


def embed_label(block: Block, page: bool = False) -> str | None:
    """What the button of *block* names (``Copy embed code for <label>``), or ``None``: no button.

    A page is "the <title> page". Other blocks: their label, caption, heading or title,
    or the heading their markdown starts with, else "this chart", "this table"…
    """
    noun = type(block).embed_noun
    if page:
        return f"the {block.label} page" if block.label else "this page"
    if isinstance(block, Group) and not block.label:  # a row of blocks has a button, a plain stack doesn't (#226)
        return "this row" if is_row(block) else None
    if noun is None:
        return None
    for text in (block.label, *(getattr(block, a, None) for a in ("caption", "heading", "title"))):
        if isinstance(text, str) and inline_plain(text):
            return inline_plain(text)
    markdown = getattr(block, "content", None) or getattr(block, "text", None)
    heading = _FIRST_HEADING.match(markdown) if isinstance(markdown, str) else None
    return heading.group(1) if heading else f"this {noun}"


def is_row(block: Group) -> bool:
    """Whether *block* lays two or more blocks side by side: a row, which gets a button unlabelled (#226)."""
    return len(block.blocks) >= 2 and (block.columns > 1 or block.min_width is not None)


#: The ``#`` of a markdown heading on the first line.
_HEADING_LEVEL = re.compile(r"\s*(#{1,6})[ \t]+\S")


def heading_level(block: Block) -> int | None:
    """The level of the heading a :class:`Text` starts with (``## A`` is 2), or ``None``."""
    if not isinstance(block, Text):
        return None
    match = _HEADING_LEVEL.match(block.content)
    return len(match.group(1)) if match else None


def sections(blocks: Sequence[Block]) -> dict[int, int]:
    """The heading sections of a one-column flow of *blocks* (#226): ``id(text) -> blocks after it``.

    A section is a Text that starts with a heading and the blocks after it, up to the next
    Text that starts with a heading of the same or a higher level (fewer ``#``). A heading
    with nothing after it isn't one.
    """
    found: dict[int, int] = {}
    for i, block in enumerate(blocks):
        level = heading_level(block)
        if level is None:
            continue
        size = 0
        for after in blocks[i + 1:]:
            other = heading_level(after)
            if other is not None and other <= level:
                break
            size += 1
        if size:
            found[id(block)] = size
    return found
