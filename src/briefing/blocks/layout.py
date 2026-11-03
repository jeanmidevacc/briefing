"""Layout and container blocks: Group, Select, Toggle, Page, Briefing."""
from __future__ import annotations

import typing as t
import warnings
from collections.abc import Sequence
from enum import StrEnum

from briefing._error import BriefingError
from briefing.blocks.base import BlockId, BlockOrPrimitive, ContainerBlock

# ── enums ─────────────────────────────────────────────────────────────────────


class SelectType(StrEnum):
    TABS = "tabs"
    DROPDOWN = "dropdown"


class VAlign(StrEnum):
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


# ── layout blocks ─────────────────────────────────────────────────────────────


class Group(ContainerBlock):
    """Grid layout container.

    Lays out child blocks in *n* columns. Use ``widths`` to control the
    relative proportion of each column.

    Example::

        bf.Group(plot, table, columns=2)
        bf.Group(a, b, c, columns=3, widths=[2, 1, 1])
    """

    min_blocks: t.ClassVar[int] = 0

    def __init__(
        self,
        *arg_blocks: BlockOrPrimitive,
        blocks: Sequence[BlockOrPrimitive] | None = None,
        columns: int = 1,
        widths: list[int | float] | None = None,
        valign: VAlign | str = VAlign.TOP,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        if widths is not None and len(widths) != columns:
            raise BriefingError(
                f"Group 'widths' length ({len(widths)}) must match 'columns' ({columns})."
            )
        super().__init__(*arg_blocks, blocks=blocks, name=name, label=label)
        self.columns = columns
        self.widths = widths
        self.valign = VAlign(valign)


class Select(ContainerBlock):
    """Tab or dropdown selector — shows one child block at a time.

    Each child block should have a ``label`` set, which becomes the tab/option
    title. A minimum of 2 children is expected.

    Example::

        bf.Select(
            bf.Plot(fig, label="Chart"),
            bf.DataTable(df, label="Data"),
            type=bf.SelectType.TABS,
        )
    """

    min_blocks: t.ClassVar[int] = 2

    def __init__(
        self,
        *arg_blocks: BlockOrPrimitive,
        blocks: Sequence[BlockOrPrimitive] | None = None,
        type: SelectType | str = SelectType.TABS,  # noqa: A002
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(*arg_blocks, blocks=blocks, name=name, label=label)
        self.type = SelectType(type)
        if len(self.blocks) < 2:
            warnings.warn(
                f"Select has {len(self.blocks)} block(s) — at least 2 are expected.",
                stacklevel=2,
            )


class Toggle(ContainerBlock):
    """Collapsible container — hidden by default, expanded on click.

    Example::

        bf.Toggle(bf.DataTable(df), label="Show raw data")
    """

    min_blocks: t.ClassVar[int] = 1

    def __init__(
        self,
        *arg_blocks: BlockOrPrimitive,
        blocks: Sequence[BlockOrPrimitive] | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(*arg_blocks, blocks=blocks, name=name, label=label)
        # Multiple top-level children are wrapped in a Group for clean rendering.
        if len(self.blocks) > 1:
            self.blocks = [Group(blocks=self.blocks)]


class Page(ContainerBlock):
    """Top-level page tab.

    Pages are converted to a ``Select(type=TABS)`` wrapping ``Group`` blocks
    during the pre-render normalisation pass — they cannot be nested.

    Example::

        bf.Briefing(
            bf.Page(summary_group, title="Summary"),
            bf.Page(detail_group, title="Detail"),
        )
    """

    min_blocks: t.ClassVar[int] = 1

    def __init__(
        self,
        *arg_blocks: BlockOrPrimitive,
        blocks: Sequence[BlockOrPrimitive] | None = None,
        title: str | None = None,
        name: BlockId | None = None,
    ) -> None:
        resolved = list(blocks if blocks is not None else arg_blocks)
        if any(isinstance(b, Page) for b in resolved):
            raise BriefingError("Nested Page blocks are not supported — use Select and Group instead.")
        # label carries the title so the renderer can use it generically.
        super().__init__(*arg_blocks, blocks=blocks, name=name, label=title)
        self.title = title


class Briefing(ContainerBlock):
    """Root document container.

    This is the top-level object passed to ``save`` and ``stringify``.

    Example::

        report = bf.Briefing(
            bf.Text("# My report"),
            bf.Plot(fig),
        )
        bf.save(report, "report.html")
    """

    min_blocks: t.ClassVar[int] = 1

    def __init__(
        self,
        *arg_blocks: BlockOrPrimitive,
        blocks: Sequence[BlockOrPrimitive] | None = None,
    ) -> None:
        # Unwrap if a single Briefing is passed directly (avoids double-wrapping).
        if len(arg_blocks) == 1 and isinstance(arg_blocks[0], Briefing):
            arg_blocks = tuple(arg_blocks[0].blocks)
        super().__init__(*arg_blocks, blocks=blocks)

    @classmethod
    def wrap(
        cls,
        x: Briefing | list[BlockOrPrimitive] | BlockOrPrimitive,
    ) -> Briefing:
        """Coerce *x* into a ``Briefing`` instance.

        - Already a ``Briefing`` → returned unchanged.
        - A ``list`` → unpacked into ``Briefing(*x)``.
        - Anything else → wrapped as ``Briefing(x)``.
        """
        if isinstance(x, Briefing):
            return x
        if isinstance(x, list):
            return cls(*x)
        return cls(x)


# ── public re-exports ─────────────────────────────────────────────────────────

__all__: list[str] = [
    "Briefing",
    "Group",
    "Page",
    "Select",
    "SelectType",
    "Toggle",
    "VAlign",
]
