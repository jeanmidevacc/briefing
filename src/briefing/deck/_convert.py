"""``bf.deck.from_report`` (#199, experimental): a report's first draft as a deck.

Each page starts a slide; in a ``Text``, a ``# Heading`` becomes a section slide, a
``## Heading`` starts a slide, and a ``---`` line starts a slide that keeps the title.
Every other block stays whole, in order. The result is an ordinary :class:`Deck`.
"""
from __future__ import annotations

import re
import typing as t
from dataclasses import dataclass, field

from briefing._experimental import experimental
from briefing._prose import slug
from briefing.blocks.banner import Banner
from briefing.blocks.base import Block
from briefing.blocks.layout import Briefing, Page
from briefing.blocks.text import Text
from briefing.deck._blocks import Deck, Slide

_FENCE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
_HEADING = re.compile(r"^[ ]{0,3}(#{1,2})[ \t]+(.*?)(?:[ \t]+\{#([A-Za-z][\w-]*)\})?[ \t#]*$")
_BREAK = re.compile(r"^[ ]{0,3}(?:-[ \t]*){3,}$")


@dataclass
class _Draft:
    """A slide being filled: its title, name and blocks; *explicit* when a heading made it."""

    title: str | None = None
    name: str | None = None
    blocks: list[Block] = field(default_factory=list)
    explicit: bool = False


class _Builder:
    def __init__(self) -> None:
        self.slides: list[Slide] = []
        self.names: set[str] = set()
        self.draft = _Draft()
        self.page_name: str | None = None  # a page that opens with a heading lends that slide its name

    def unique(self, name: str | None) -> str | None:
        """*name*, or *name* with a number after it when another slide has it."""
        if name is None:
            return None
        found, n = name, 1
        while found in self.names:
            n += 1
            found = f"{name}-{n}"
        self.names.add(found)
        return found

    def flush(self) -> None:
        draft = self.draft
        if draft.blocks or (draft.explicit and draft.title):
            self.slides.append(Slide(*draft.blocks, title=draft.title, name=draft.name))
        elif draft.name is not None:
            self.names.discard(draft.name)  # an empty slide gives its name back
        self.draft = _Draft()

    def _name(self, name: str | None, page: str | None) -> str | None:
        """*name*, else (in a named page) the page's name and the slide's number, made unique."""
        return self.unique(name or (f"{page}-{len(self.slides) + 1}" if page else None))

    def start(self, title: str | None, name: str | None, explicit: bool, page: str | None = None) -> None:
        self.flush()
        self.draft = _Draft(title=title, name=self._name(name, page), explicit=explicit)

    def section(self, title: str, name: str | None, page: str | None = None) -> None:
        self.flush()
        self.slides.append(Slide(title=title, name=self._name(name, page)))

    def text(self, block: Text, page: str | None) -> None:
        """Split a Text at its ``#`` and ``##`` headings and ``---`` lines, outside code fences."""
        lines: list[str] = []
        named = block.name  # the Text's own link goes on its first piece
        fence: str | None = None

        def keep() -> None:
            nonlocal lines, named
            body = "\n".join(lines).strip("\n")
            if body.strip():
                self.draft.blocks.append(Text(body, name=named))
                named = None
            lines = []

        for line in block.content.splitlines():
            if fence is not None:
                lines.append(line)
                if line.strip().startswith(fence):
                    fence = None
                continue
            if (opened := _FENCE.match(line)) is not None:
                fence = opened.group(1)
                lines.append(line)
                continue
            if (heading := _HEADING.match(line)) is not None:
                keep()
                level, title, name = len(heading.group(1)), heading.group(2).strip(), heading.group(3)
                if name == "auto":
                    name = slug(title)
                name, self.page_name = name or self.page_name, None
                if level == 1:
                    self.section(title, name, page)
                    self.draft = _Draft(name=self._name(None, page))
                else:
                    self.start(title, name, explicit=True, page=page)
                continue
            if _BREAK.match(line):
                keep()
                self.start(self.draft.title, None, explicit=False, page=page)
                continue
            lines.append(line)
        keep()


def _starts_with_heading(block: Block) -> bool:
    if not isinstance(block, Text):
        return False
    first = next((line for line in block.content.splitlines() if line.strip()), "")
    return _HEADING.match(first) is not None


def from_report(report: object, title: str | None = None) -> Deck:
    """*Experimental.* A first draft of a deck from a report, to adjust before saving.

    Each ``Page`` starts a slide titled with the page's title. In a ``Text``, a ``# Heading``
    becomes a section slide, a ``## Heading`` starts a slide with that title (its ``{#name}``
    names the slide), and a ``---`` line starts a slide that keeps the title. Every other
    block stays whole, in order: groups, tabs, tables, charts and lab blocks. A ``Banner``
    that opens the report becomes the title slide. The report's footer is the deck's.

    The result is an ordinary :class:`Deck`: reorder, drop or retitle its slides before
    saving. What it returns may change in any release; it warns
    :class:`~briefing.ExperimentalWarning` once per session.

    Args:
        report: A :class:`~briefing.Briefing`, a block or a list of blocks.
        title: A first section slide with this title (a report's name isn't part of it).

    Returns:
        The deck.

    Example::

        deck = bf.deck.from_report(report, title="Q3 review")
        del deck.slides[4]
        bf.deck.save(deck, "q3-deck.html")
    """
    experimental("bf.deck.from_report")
    root = Briefing.wrap(t.cast(t.Any, report))
    pages = [b for b in root.blocks if isinstance(b, Page)] if all(isinstance(b, Page) for b in root.blocks) else []
    builder = _Builder()
    if title:
        builder.section(title, None)
    groups: list[tuple[Page | None, list[Block]]] = [(p, list(p.blocks)) for p in pages] or [(None, list(root.blocks))]
    for index, (page, blocks) in enumerate(groups):
        if index == 0 and blocks and isinstance(blocks[0], Banner):
            builder.slides.append(Slide(blocks[0]))  # the title slide
            blocks = blocks[1:]
        name = page.name if page is not None else None
        heading_first = bool(blocks) and _starts_with_heading(blocks[0])
        builder.start(None if heading_first or page is None else page.title,
                      None if heading_first else name, explicit=False)
        builder.page_name = name if heading_first else None
        for block in blocks:
            if isinstance(block, Text):
                builder.text(block, name)
            else:
                builder.draft.blocks.append(block)
        builder.flush()
    if not builder.slides:
        builder.slides.append(Slide(title=title or "Untitled"))
    return Deck(*builder.slides, footer=root.footer)


__all__ = ["from_report"]
