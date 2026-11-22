"""Pre-render normalization pass.

Transforms the block tree before HTML rendering:
- Converts top-level ``Page`` blocks into a ``Select(TABS)`` of ``Group`` blocks.
- Validates that the root ``Briefing`` container is not empty.
"""
from __future__ import annotations

import copy

from briefing._error import BriefingError
from briefing.blocks.layout import Briefing, Group, Page, Select, SelectType


def normalize(blocks: Briefing) -> Briefing:
    """Return a normalized copy of *blocks*, ready for rendering.

    Mutations applied (in order):

    1. **Empty root check** — raises :class:`~briefing.BriefingError` if the root
       ``Briefing`` has zero children.
    2. **Page → Select conversion** — if *all* top-level children are
       :class:`~briefing.Page` blocks they are converted to a single
       ``Select(type=TABS)`` whose children are labelled ``Group`` blocks,
       one per page.  Mixed roots (some Pages, some non-Pages) raise an error.
    """
    root = copy.copy(blocks)
    root.blocks = list(blocks.blocks)  # shallow-copy the list

    if len(root.blocks) == 0:
        raise BriefingError(
            "Cannot render an empty Briefing container — add at least one block."
        )

    has_pages = [isinstance(b, Page) for b in root.blocks]

    if any(has_pages) and not all(has_pages):
        raise BriefingError(
            "Cannot mix Page blocks with other block types at the top level. "
            "Either wrap all content in Page blocks, or use none."
        )

    if all(has_pages):
        pages = [b for b in root.blocks if isinstance(b, Page)]
        root.blocks = [
            Select(
                blocks=[
                    Group(blocks=page.blocks, label=page.title, name=page.name)
                    for page in pages
                ],
                type=SelectType.TABS,
                style=blocks.tabs,
            )
        ]

    return root
