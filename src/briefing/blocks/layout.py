"""Layout and container blocks: Group, Select, Toggle, Page, Briefing."""
from __future__ import annotations

import dataclasses
import math
import numbers
import re
import typing as t
import warnings
from collections.abc import Mapping, Sequence
from enum import StrEnum

from briefing._error import BriefingError
from briefing.blocks.base import _MAX_CAPTION_LEN, BlockId, BlockOrPrimitive, ContainerBlock, _truncate
from briefing.blocks.header import Header

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


@dataclasses.dataclass(frozen=True)
class TabStyle:
    """How a row of tabs looks: page tabs (``Briefing(tabs=)``) or a ``Select``'s (``Select(style=)``).

    The defaults are the usual look; a report that sets no style renders exactly as before.

    Args:
        layout: ``"start"`` (tabs from the left), ``"center"``, or ``"stretch"``
            (each tab takes an equal share of the line).
        full_width: Run the tab line edge to edge across the window; the tabs stay
            aligned with the content.
        sticky: Keep the tab bar at the top of the window while scrolling.
        size: ``"sm"``, ``"md"`` or ``"lg"``.
        variant: ``"underline"`` (a line under the active tab), ``"pills"`` (a tinted
            pill) or ``"boxed"`` (folder tabs that join their panel).

    Example::

        report = bf.Briefing(page_1, page_2, tabs=bf.TabStyle(layout="stretch", sticky=True))
        bf.Select(chart, table, style=bf.TabStyle(variant="pills", size="sm"))
    """

    layout: str = "start"
    full_width: bool = False
    sticky: bool = False
    size: str = "md"
    variant: str = "underline"

    LAYOUTS: t.ClassVar[tuple[str, ...]] = ("start", "center", "stretch")
    SIZES: t.ClassVar[tuple[str, ...]] = ("sm", "md", "lg")
    VARIANTS: t.ClassVar[tuple[str, ...]] = ("underline", "pills", "boxed")

    def __post_init__(self) -> None:
        for option, choices in (("layout", self.LAYOUTS), ("size", self.SIZES), ("variant", self.VARIANTS)):
            value = getattr(self, option)
            if value not in choices:
                raise BriefingError(
                    f"TabStyle: {option} must be one of {', '.join(map(repr, choices))}, not {value!r}."
                )
        for option in ("full_width", "sticky"):
            if not isinstance(getattr(self, option), bool):
                raise BriefingError(f"TabStyle: {option} must be True or False, not {getattr(self, option)!r}.")

    @classmethod
    def of(cls, value: TabStyle | Mapping[str, t.Any] | None, where: str) -> TabStyle | None:
        """*value* as a TabStyle: a TabStyle, a dict of its options (the JSON form) or ``None``."""
        if value is None or isinstance(value, TabStyle):
            return value
        if isinstance(value, Mapping):
            fields = [f.name for f in dataclasses.fields(cls)]
            unknown = [k for k in value if k not in fields]
            if unknown:
                raise BriefingError(f"{where}: TabStyle has no option {unknown[0]!r}; it takes {', '.join(fields)}.")
            return cls(**value)
        raise BriefingError(f"{where} takes a bf.TabStyle(...) or a dict of its options, not {value!r}.")

    def to_dict(self) -> dict[str, t.Any]:
        """The options that differ from the defaults: the JSON form."""
        default = TabStyle()
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)
                if getattr(self, f.name) != getattr(default, f.name)}

    def classes(self) -> str:
        """The ``bf-tabs--*`` classes for this style: none for the defaults."""
        default = TabStyle()
        names = [self.layout, self.size, self.variant]
        names = [n for n, d in zip(names, [default.layout, default.size, default.variant], strict=True) if n != d]
        names += ["full"] * self.full_width + ["sticky"] * self.sticky
        return "".join(f" bf-tabs--{n}" for n in names)


#: A CSS length for Group(min_width=): a positive number in rem, em or px.
_LENGTH = re.compile(r"^(?:\d+(?:\.\d+)?|\.\d+)(?:rem|em|px)$")


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
        min_width: The narrowest a cell may be, such as ``"16rem"`` (or a number of
            pixels): as many cells per row as fit, up to ``columns`` when it is above 1.
            Not with ``widths``.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    On phones every Group is one column; on tablets (up to 960 px wide) a Group of
    three or more columns shows two per row.

    Example::

        bf.Group(plot, table, columns=2)
        bf.Group(a, b, c, columns=3, widths=[2, 1, 1])
        bf.Group(*cards, min_width="16rem")  # as many per row as fit
    """

    embed_noun: t.ClassVar[str | None] = "section"

    min_blocks: t.ClassVar[int] = 0

    def __init__(
        self,
        *arg_blocks: BlockOrPrimitive,
        blocks: Sequence[BlockOrPrimitive] | None = None,
        columns: int = 1,
        widths: list[int | float] | None = None,
        valign: VAlign | str = VAlign.TOP,
        min_width: str | int | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        if min_width is not None:
            css = f"{min_width}px" if _is_positive_number(min_width, whole=True) else min_width
            if not isinstance(css, str) or not _LENGTH.match(css):
                raise BriefingError(f"Group 'min_width' must be a CSS length such as '16rem' or a number of pixels, "
                                    f"not {min_width!r}.")
            if widths is not None:
                raise BriefingError("Group takes 'widths' or 'min_width', not both: min_width lets the cells "
                                    "share each row equally.")
            min_width = css
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
        self.min_width = min_width


class Select(ContainerBlock):
    """Tab or dropdown selector — shows one child block at a time.

    Each child block should have a ``label`` set, which becomes the tab/option
    title. A minimum of 2 children is expected.

    Args:
        *arg_blocks: The panels; each child's ``label`` is its tab or option title.
        blocks: The panels as a list, instead of positional arguments.
        type: ``"tabs"`` (default) or ``"dropdown"`` (or a :class:`SelectType`).
        style: How the tabs look: a :class:`TabStyle` (layout, size, variant…). Tabs only.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
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
        style: TabStyle | Mapping[str, t.Any] | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(*arg_blocks, blocks=blocks, name=name, label=label)
        self.type = SelectType(type)
        self.style = TabStyle.of(style, "Select style=")
        if self.style is not None and self.type == SelectType.DROPDOWN:
            raise BriefingError("Select: style= styles tabs, and this Select is a dropdown. "
                                "Drop style=, or use type='tabs'.")
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
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
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


EXPORT_PDF_REMOVED = (
    "Briefing(export='pdf') was removed in 0.4.0 (deprecated since 0.2.4): the 'Print' button only opened the "
    "browser's print dialog, which Ctrl+P (Cmd+P on a Mac) opens with the same print layout. For a PDF file, use "
    "bf.save_pdf(report, 'report.pdf'). Pass export='png' for the 'Save as PNG' button, or leave export out."
)


class Briefing(ContainerBlock):
    """Root document container.

    This is the top-level object passed to ``save`` and ``stringify``.

    Args:
        *arg_blocks: The report's blocks, in order.
        blocks: The blocks as a list, instead of positional arguments.
        export: Opt-in export menu in the report header: ``"png"`` adds "Save as
            PNG" (the open page with a margin around it, drawn in the reader's
            browser at 2×). Reports without it contain no export code. "Save as
            PNG" is best effort: charts drawn in iframes (Bokeh) and WebGL Plotly
            traces come out blank, and fonts are whatever the reader's machine
            has. For exact, reproducible files use :func:`~briefing.save_image` /
            :func:`~briefing.save_pdf`. To print, use the browser's own print
            (Ctrl+P or ⌘P): it gets the same print layout. ``"embed"`` puts a
            ``</>`` button on each page, labelled group, chart, table, text,
            number, alert and banner: it copies that part as an embed fragment, as
            :func:`~briefing.stringify` makes with ``full_html=False``, to paste
            into another page. ``"pdf"`` (the "Print" button) was removed in 0.4.0:
            print with Ctrl+P, or save a file with :func:`~briefing.save_pdf`.
        footer: Text to put before the report's footer line, such as a team name. Every
            report ends with "Made with briefing" and its version; that line can't be
            turned off.
        tabs: How the page tabs look, for a report made of :class:`Page` blocks: a
            :class:`TabStyle` such as ``bf.TabStyle(layout="stretch", sticky=True)``.
        header: What the header shows besides the name and render time: a
            :class:`Header` with a subtitle, author, logo, "data as of" date and time zone.

    Example::

        report = bf.Briefing(
            bf.Text("# My report"),
            bf.Plot(fig),
            export="png",
            footer="Analytics team",  # "Analytics team · Made with briefing 0.4.1"
        )
        bf.save(report, "report.html")
    """

    min_blocks: t.ClassVar[int] = 1

    #: The actions export= accepts, in menu order.
    EXPORTS: t.ClassVar[tuple[str, ...]] = ("png", "embed")
    #: Accepted with a DeprecationWarning, and dropped: they add no button.
    DEPRECATED_EXPORTS: t.ClassVar[dict[str, str]] = {}
    #: Rejected with what to use instead.
    REMOVED_EXPORTS: t.ClassVar[dict[str, str]] = {"pdf": EXPORT_PDF_REMOVED}
    export: tuple[str, ...]
    footer: str | None
    tabs: TabStyle | None
    header: Header | None

    def __init__(
        self,
        *arg_blocks: BlockOrPrimitive,
        blocks: Sequence[BlockOrPrimitive] | None = None,
        export: str | Sequence[str] = (),
        footer: str | None = None,
        tabs: TabStyle | Mapping[str, t.Any] | None = None,
        header: Header | Mapping[str, t.Any] | None = None,
    ) -> None:
        # Unwrap if a single Briefing is passed directly (avoids double-wrapping).
        if len(arg_blocks) == 1 and isinstance(arg_blocks[0], Briefing):
            export = export or arg_blocks[0].export
            footer = footer or arg_blocks[0].footer
            tabs = tabs or arg_blocks[0].tabs
            header = header or arg_blocks[0].header
            arg_blocks = tuple(arg_blocks[0].blocks)
        if footer is not None and not isinstance(footer, str):
            raise BriefingError(f"Briefing 'footer' must be text such as 'Analytics team', not {footer!r}.")
        super().__init__(*arg_blocks, blocks=blocks)
        self.export = self._check_export(export)
        self.footer = _truncate(footer, _MAX_CAPTION_LEN) if footer else None
        self.tabs = TabStyle.of(tabs, "Briefing tabs=")
        self.header = Header.of(header)
        if self.tabs is not None and not any(isinstance(b, Page) for b in self.blocks):
            raise BriefingError("Briefing: tabs= styles the page tabs, and this report has no Page. "
                                "Put its blocks in bf.Page(...)s, or style a Select with Select(style=...).")

    @classmethod
    def _check_export(cls, export: object) -> tuple[str, ...]:
        actions = (export,) if isinstance(export, str) else export
        if isinstance(actions, Sequence):
            removed = next((a for a in actions if a in cls.REMOVED_EXPORTS), None)
            if removed is not None:
                raise BriefingError(cls.REMOVED_EXPORTS[removed])
        if not isinstance(actions, Sequence) or any(
            a not in cls.EXPORTS and a not in cls.DEPRECATED_EXPORTS for a in actions
        ):
            raise BriefingError(
                f"export accepts 'png' and 'embed', for example export=('png', 'embed'); got {export!r}."
            )
        unique = tuple(dict.fromkeys(t.cast("Sequence[str]", actions)))
        for action in unique:
            if action in cls.DEPRECATED_EXPORTS:
                # stacklevel 3: _check_export <- __init__ <- the caller's bf.Briefing(...)
                warnings.warn(cls.DEPRECATED_EXPORTS[action], DeprecationWarning, stacklevel=3)
        return tuple(a for a in unique if a in cls.EXPORTS)

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
    "TabStyle",
    "Toggle",
    "VAlign",
]
