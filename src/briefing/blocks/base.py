"""Core block primitives: Block, ContainerBlock, and wrap_block."""
from __future__ import annotations

import re
import typing as t
from collections.abc import Sequence

from briefing._error import BriefingError

_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")
_MAX_LABEL_LEN = 256
_MAX_CAPTION_LEN = 512

BlockId = str
BlockOrPrimitive = t.Union["Block", t.Any]


class Block:
    """Base class for all briefing blocks.

    All blocks carry an optional ``name`` (a stable ID for referencing the
    block) and an optional ``label`` (a human-readable display string used
    e.g. as a tab title inside a Select).

    Args:
        name: Stable block id (letters, digits, ``_`` and ``-``), for referencing the block.
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.Text("Revenue grew 12 %", name="summary", label="Summary")
    """

    def __init__(
        self,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        if name is not None and not _NAME_RE.match(name):
            raise BriefingError(
                f"Invalid block name {name!r}: must start with a letter and contain "
                "only letters, digits, underscores, or hyphens."
            )
        self.name = name
        self.label = _truncate(label, _MAX_LABEL_LEN) if label else label

    def _repr_html_(self) -> str:
        """Notebook preview: this block as a complete report, isolated in its own iframe."""
        from briefing._preview import preview_html

        return preview_html(self)

    def __repr__(self) -> str:
        parts = []
        if self.name:
            parts.append(f"name={self.name!r}")
        if self.label:
            parts.append(f"label={self.label!r}")
        return f"{self.__class__.__name__}({', '.join(parts)})"


class ContainerBlock(Block):
    """Block that holds a list of child blocks (forms a subtree)."""

    #: Subclasses can raise the bar; checked during rendering, not construction.
    min_blocks: t.ClassVar[int] = 1

    def __init__(
        self,
        *arg_blocks: BlockOrPrimitive,
        blocks: Sequence[BlockOrPrimitive] | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        resolved = list(blocks if blocks is not None else arg_blocks)
        self.blocks: list[Block] = [wrap_block(b) for b in resolved]

    def __iter__(self) -> t.Iterator[Block]:
        return iter(self.blocks)

    def __len__(self) -> int:
        return len(self.blocks)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"{len(self.blocks)} block(s)"
            + (f", name={self.name!r}" if self.name else "")
            + ")"
        )


def wrap_block(b: BlockOrPrimitive) -> Block:
    """Auto-wrap primitives into appropriate blocks.

    Containers call this on their children, so ``bf.Group("# Title", df)``
    works without spelling out ``Text`` and ``DataTable``.

    Args:
        b: A block (returned as-is), a string (becomes :class:`~briefing.Text`)
            or a dataframe — pandas, polars, pyarrow or any dataframe-interchange
            object (becomes :class:`~briefing.DataTable`).

    Returns:
        The block.

    Raises:
        BriefingError: For any other type; the message names the supported ones.

    Example::

        bf.wrap_block("**Note**: figures are provisional")  # a Text block
    """
    if isinstance(b, Block):
        return b

    if isinstance(b, str):
        from briefing.blocks.text import Text

        return Text(text=b)

    from briefing._frames import looks_like_dataframe

    if looks_like_dataframe(b):
        from briefing.blocks.asset import DataTable

        return DataTable(b)

    raise BriefingError(
        f"Cannot auto-wrap {type(b).__name__!r} into a briefing block. "
        "Pass a briefing block, a string, or a dataframe."
    )


# ── helpers ──────────────────────────────────────────────────────────────────


def _truncate(s: str, max_len: int) -> str:
    return s[: max_len - 3] + "..." if len(s) > max_len else s
