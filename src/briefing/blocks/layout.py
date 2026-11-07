"""Layout and container blocks: Group, Select, Toggle, Page, Briefing."""
from __future__ import annotations

import math
import numbers
import typing as t
import warnings
from collections.abc import Sequence
from enum import StrEnum

from briefing._error import BriefingError
from briefing.blocks.base import _MAX_CAPTION_LEN, BlockId, BlockOrPrimitive, ContainerBlock, _truncate

# ── enums ─────────────────────────────────────────────────────────────────────


class SelectType(StrEnum):
    """How a :class:`Select` shows its panels: a row of tabs or a dropdown.

    Example::

        bf.Select(a, b, type=bf.SelectType.DROPDOWN)  # or type="dropdown"
    """

    TABS = "tabs"
    DROPDOWN = "dropdown"


class VAlign(StrEnum):
    """Vertical alignment of the cells of a :class:`Group`.

    Example::

        bf.Group(chart, note, columns=2, valign=bf.VAlign.CENTER)  # or valign="center"
    """

    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


def _is_positive_number(value: object, *, whole: bool = False) -> bool:
    """Whether *value* is a finite number above zero; ``True`` and ``False`` don't count."""
    kind = numbers.Integral if whole else numbers.Real
    return isinstance(value, kind) and not isinstance(value, bool) and 0 < float(value) < math.inf


# ── layout blocks ─────────────────────────────────────────────────────────────


class Group(ContainerBlock):
    """Grid layout container.

    Lays out child blocks in *n* columns. Use ``widths`` to control the
    relative proportion of each column.

    Args:
        *arg_blocks: The child blocks; strings become ``Text`` and dataframes ``DataTable``.
        blocks: The children as a list, instead of positional arguments.
        columns: Number of grid columns, a whole number of 1 or more.
        widths: Relative column widths, positive numbers, one per column (e.g. ``[2, 1]``).
        valign: Vertical alignment of the cells: ``"top"``, ``"center"`` or ``"bottom"``.
        name: Stable block id (letters, digits, ``_`` and ``-``), for referencing the block.
        label: Tab or dropdown label when the block is inside a ``Select``.

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
        if not _is_positive_number(columns, whole=True):
            raise BriefingError(f"Group 'columns' must be a whole number of 1 or more, not {columns!r}.")
        if widths is not None:
            if len(widths) != columns:
                raise BriefingError(
                    f"Group 'widths' length ({len(widths)}) must match 'columns' ({columns})."
                )
            for width in widths:
                if not _is_positive_number(width):
                    raise BriefingError(f"Group 'widths' must be positive numbers such as [2, 1], not {width!r}.")
        super().__init__(*arg_blocks, blocks=blocks, name=name, label=label)
        self.columns = int(columns)
        self.widths = widths
        self.valign = VAlign(valign)


class Select(ContainerBlock):
    """Tab or dropdown selector — shows one child block at a time.

    Each child block should have a ``label`` set, which becomes the tab/option
    title. A minimum of 2 children is expected.

    Args:
        *arg_blocks: The panels; each child's ``label`` is its tab or option title.
        blocks: The panels as a list, instead of positional arguments.
        type: ``"tabs"`` (default) or ``"dropdown"`` (or a :class:`SelectType`).
        name: Stable block id (letters, digits, ``_`` and ``-``), for referencing the block.
        label: Tab or dropdown label when the block is inside a ``Select``.

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

    Args:
        *arg_blocks: The hidden content; several blocks are wrapped in a ``Group``.
        blocks: The content as a list, instead of positional arguments.
        name: Stable block id (letters, digits, ``_`` and ``-``), for referencing the block.
        label: The clickable title (``"Details"`` when omitted).

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

    Args:
        *arg_blocks: The page's blocks.
        blocks: The blocks as a list, instead of positional arguments.
        title: The page's tab title.
        name: Stable block id; ``save_image`` / ``save_pdf`` accept it as ``page=``.

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

    Args:
        *arg_blocks: The report's blocks, in order.
        blocks: The blocks as a list, instead of positional arguments.
        export: Opt-in export menu in the report header: ``"png"`` adds "Save as
            PNG" (the open page, drawn in the reader's browser at 2×) and ``"pdf"``
            adds "Print" (the print dialog, which can save a PDF). Reports without
            it contain no export code. "Save as PNG" is best effort: charts
            drawn in iframes (Bokeh) and WebGL Plotly traces come out blank, and
            fonts are whatever the reader's machine has. For exact, reproducible
            files use :func:`~briefing.save_image` / :func:`~briefing.save_pdf`.
        footer: Text to put before the report's footer line, such as a team name. Every
            report ends with "Made with briefing" and its version; that line can't be
            turned off.

    Example::

        report = bf.Briefing(
            bf.Text("# My report"),
            bf.Plot(fig),
            export=("png", "pdf"),
            footer="Analytics team",  # "Analytics team · Made with briefing 0.3.0"
        )
        bf.save(report, "report.html")
    """

    min_blocks: t.ClassVar[int] = 1

    #: The actions export= accepts, in menu order.
    EXPORTS: t.ClassVar[tuple[str, ...]] = ("png", "pdf")
    export: tuple[str, ...]
    footer: str | None

    def __init__(
        self,
        *arg_blocks: BlockOrPrimitive,
        blocks: Sequence[BlockOrPrimitive] | None = None,
        export: str | Sequence[str] = (),
        footer: str | None = None,
    ) -> None:
        # Unwrap if a single Briefing is passed directly (avoids double-wrapping).
        if len(arg_blocks) == 1 and isinstance(arg_blocks[0], Briefing):
            export = export or arg_blocks[0].export
            footer = footer or arg_blocks[0].footer
            arg_blocks = tuple(arg_blocks[0].blocks)
        if footer is not None and not isinstance(footer, str):
            raise BriefingError(f"Briefing 'footer' must be text such as 'Analytics team', not {footer!r}.")
        super().__init__(*arg_blocks, blocks=blocks)
        self.export = self._check_export(export)
        self.footer = _truncate(footer, _MAX_CAPTION_LEN) if footer else None

    @classmethod
    def _check_export(cls, export: object) -> tuple[str, ...]:
        actions = (export,) if isinstance(export, str) else export
        if not isinstance(actions, Sequence) or any(a not in cls.EXPORTS for a in actions):
            raise BriefingError(
                f"export accepts 'png' and/or 'pdf', for example export=('png', 'pdf'); got {export!r}."
            )
        return tuple(dict.fromkeys(t.cast("Sequence[str]", actions)))

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
