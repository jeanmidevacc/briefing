"""The objects of a slide deck (#197): :class:`Deck`, a list of :class:`Slide`, each holding blocks."""
from __future__ import annotations

import typing as t
from collections.abc import Sequence

from briefing._error import BriefingError
from briefing.blocks.base import _MAX_CAPTION_LEN, BlockId, BlockOrPrimitive, ContainerBlock, _truncate
from briefing.blocks.layout import Page

#: What to say when a slide is put where a report's blocks go.
SLIDE_IN_REPORT = ("bf.deck.Slide goes in a bf.deck.Deck, saved with bf.deck.save; in a report, use bf.Page "
                   "for a page or bf.Group to keep blocks together.")


class Slide(ContainerBlock):
    """One slide of a deck: a title over blocks stacked top to bottom, as in a report.

    Lay blocks out with the blocks that already do it: :class:`~briefing.Group` for columns,
    :class:`~briefing.Select` for tabs, :class:`~briefing.Card` for a framed box. A slide with
    a title and no blocks is a section slide, its title shown large.

    Args:
        *arg_blocks: The slide's blocks, in order; strings become ``Text``, dataframes ``DataTable``.
        blocks: The blocks as a list, instead of positional arguments.
        title: The slide's heading, with inline Markdown as in captions.
        name: Stable slide id (letters, digits, ``_`` and ``-``): its link in the deck (``#name``).

    Example::

        bf.deck.Slide(
            bf.Text("Revenue grew in **every** region."),
            bf.Group(bf.BigNumber("Revenue", 4.2e6, prev_value=3.9e6, format="${:,.0f}"),
                     bf.BigNumber("Margin", 0.31, format="{:.0%}"), columns=2),
            title="Summary",
            name="summary",
        )
    """

    min_blocks: t.ClassVar[int] = 0

    def __init__(
        self,
        *arg_blocks: BlockOrPrimitive,
        blocks: Sequence[BlockOrPrimitive] | None = None,
        title: str | None = None,
        name: BlockId | None = None,
    ) -> None:
        if title is not None and not isinstance(title, str):
            raise BriefingError(f"Slide 'title' must be text such as 'Summary', not {title!r}.")
        super().__init__(*arg_blocks, blocks=blocks, name=name)
        self.title = _truncate(title.strip(), _MAX_CAPTION_LEN) if title and title.strip() else None
        for child in self.blocks:
            if isinstance(child, Slide):
                raise BriefingError("A Slide can't hold another Slide: put both in the Deck, one after the other.")
            if isinstance(child, Page):
                raise BriefingError("A Slide can't hold a Page: in a deck, each page is a Slide of its own.")
        if not self.blocks and self.title is None:
            raise BriefingError("This Slide is empty: give it blocks, or a title for a section slide.")

    def __repr__(self) -> str:
        title = f", title={self.title!r}" if self.title else ""
        name = f", name={self.name!r}" if self.name else ""
        return f"Slide({len(self.blocks)} block(s){title}{name})"


class Deck:
    """A slide deck: briefing's blocks on slides, saved as one HTML file in the report's theme.

    A deck runs in the browser like a report, so every block keeps what it does there:
    charts stay interactive, tables sort. It is shared as that file, or printed to PDF.

    Args:
        *arg_slides: The deck's slides, in order: :class:`Slide` objects.
        slides: The slides as a list, instead of positional arguments.
        footer: Text before the "Made with briefing" line at the foot of every slide, such
            as a team name.

    Example::

        deck = bf.deck.Deck(
            bf.deck.Slide(bf.Banner("# Q3 review", image="cover.jpg")),
            bf.deck.Slide(bf.Plot(fig), title="Revenue by month"),
            footer="Sales analytics",
        )
    """

    def __init__(
        self,
        *arg_slides: Slide,
        slides: Sequence[Slide] | None = None,
        footer: str | None = None,
    ) -> None:
        resolved = list(slides if slides is not None else arg_slides)
        if not resolved:
            raise BriefingError("This Deck has no slides: pass at least one bf.deck.Slide(...).")
        for i, slide in enumerate(resolved):
            if not isinstance(slide, Slide):
                raise BriefingError(
                    f"A Deck holds bf.deck.Slide objects; slide {i + 1} is a {type(slide).__name__}. "
                    "Wrap it: bf.deck.Slide(block, title=...)."
                )
        if footer is not None and not isinstance(footer, str):
            raise BriefingError(f"Deck 'footer' must be text such as 'Analytics team', not {footer!r}.")
        self.slides: list[Slide] = resolved
        self.footer = _truncate(footer, _MAX_CAPTION_LEN) if footer else None

    def __iter__(self) -> t.Iterator[Slide]:
        return iter(self.slides)

    def __len__(self) -> int:
        return len(self.slides)

    def __repr__(self) -> str:
        footer = f", footer={self.footer!r}" if self.footer else ""
        return f"Deck({len(self.slides)} slide(s){footer})"


__all__ = ["SLIDE_IN_REPORT", "Deck", "Slide"]
