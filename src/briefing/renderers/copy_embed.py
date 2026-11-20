"""The copy-embed button (#124): which blocks get one, and what each one says.

A report built with ``export=("embed",)`` puts a ``</>`` button on its pages, labelled
groups, charts, tables, texts, numbers, alerts, banners and lab blocks: the block types
whose ``embed_noun`` is set. The button copies that block as an embed fragment (#122),
cut by ``static/copy-embed.js`` from an untouched copy of the report that the report
carries (``renderers/fragment.py``, :func:`~briefing.renderers.fragment.copy_data`).
"""
from __future__ import annotations

import re

from briefing.blocks.base import Block
from briefing.blocks.layout import Group

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
    if noun is None or (isinstance(block, Group) and not block.label):
        return None
    for text in (block.label, *(getattr(block, a, None) for a in ("caption", "heading", "title"))):
        if isinstance(text, str) and text.strip():
            return text.strip()
    markdown = getattr(block, "content", None) or getattr(block, "text", None)
    heading = _FIRST_HEADING.match(markdown) if isinstance(markdown, str) else None
    return heading.group(1) if heading else f"this {noun}"
