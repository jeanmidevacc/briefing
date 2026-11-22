"""Markdown-first reports (#191): the prose in a ``.md`` file, Python supplying values and blocks.

A slot is a MyST-style colon fence, ``::: block <name>`` … ``:::``; what it holds is a note for
the author, not shown. With ``pages=True`` each ``# Heading`` starts a page.
"""
from __future__ import annotations

import re
import typing as t
from collections.abc import Mapping
from pathlib import Path

from briefing._error import BriefingError
from briefing._prose import fill, slug
from briefing.blocks.base import Block, wrap_block
from briefing.blocks.layout import Briefing, Page
from briefing.blocks.text import Text

_SLOT = re.compile(r"^:::[ \t]*block[ \t]+([A-Za-z][A-Za-z0-9_-]*)[ \t]*$")
_CLOSE = re.compile(r"^:::[ \t]*$")
_FENCE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
_PAGE = re.compile(r"^#[ \t]+(.*?)(?:[ \t]+\{#([A-Za-z][A-Za-z0-9_-]*)\})?[ \t]*$")
_MISSING = re.compile(r"no value for \{(\w+)\}")


def _source(markdown: str | Path) -> tuple[str, str]:
    """The Markdown and the name its errors use: a file's name, or ``<markdown>``."""
    if isinstance(markdown, Path) or (isinstance(markdown, str) and "\n" not in markdown
                                       and markdown.strip().endswith((".md", ".markdown"))):
        path = Path(markdown).expanduser()
        if not path.is_file():
            raise BriefingError(f"bf.from_markdown: file not found: {path}")
        return path.read_text(encoding="utf-8"), path.name
    if not isinstance(markdown, str):
        raise BriefingError(f"bf.from_markdown takes a .md path or Markdown text, not {type(markdown).__name__}.")
    return markdown, "<markdown>"


def _fill(text: str, first_line: int, values: Mapping[str, t.Any], where: str) -> str:
    try:
        return fill(text, values)
    except BriefingError as exc:
        found = _MISSING.search(str(exc))
        line = first_line
        if found:
            hit = next((i for i, row in enumerate(text.splitlines()) if "{" + found.group(1) in row), 0)
            line = first_line + hit
        raise BriefingError(f"{where}:{line}: {str(exc).removeprefix('Text: ')}") from exc


def _as_blocks(value: object, name: str) -> list[Block]:
    items = list(value) if isinstance(value, list | tuple) else [value]
    try:
        return [wrap_block(t.cast(t.Any, item)) for item in items]
    except BriefingError as exc:
        raise BriefingError(f"bf.from_markdown: the block for the slot {name!r}: {exc}") from exc


def from_markdown(
    markdown: str | Path,
    values: Mapping[str, t.Any] | None = None,
    blocks: Mapping[str, t.Any] | None = None,
    pages: bool = False,
    **options: t.Any,
) -> Briefing:
    """A report written in Markdown, with Python supplying its values and its blocks.

    The prose is Markdown, as in :class:`~briefing.Text`, filled from ``values`` as
    ``Text(values=)`` fills it. A slot, a ``::: block <name>`` line closed by ``:::``,
    takes ``blocks[name]``; what the fence holds is a note for the author, not shown.

    Args:
        markdown: The path of a ``.md`` file, or the Markdown itself.
        values: Fills ``{name}`` and ``{name:spec}`` in the prose; each value shows as written.
        blocks: What each slot holds: a block, a list of blocks, a string (``Text``) or a
            dataframe (``DataTable``).
        pages: Start a ``Page`` at each ``# Heading``; ``{#name}`` or ``{#auto}`` names it.
        **options: The report's options, as :class:`~briefing.Briefing` takes them:
            ``export``, ``footer``, ``header``, ``tabs``.

    Example::

        report = bf.from_markdown("report.md", values={"searches": 241},
                                  blocks={"families": cards, "calendars": calendars})
        bf.save(report, "report.html", name="GTA VI and the internet")
    """
    text, where = _source(markdown)
    values = dict(values or {})
    slots = dict(blocks or {})
    used: set[str] = set()

    # (title, name, blocks) per page; one unnamed "page" when pages=False
    sections: list[tuple[str | None, str | None, list[Block]]] = [(None, None, [])]
    chunk: list[str] = []
    chunk_start = 1
    fence: str | None = None
    slot: tuple[str, int] | None = None

    def flush(line: int) -> None:
        nonlocal chunk, chunk_start
        body = "\n".join(chunk).strip("\n")
        if body.strip():
            if pages and sections[-1][0] is None:
                raise BriefingError(f"{where}:{chunk_start}: with pages=True, the report starts with a "
                                    "'# Page title' heading.")
            sections[-1][2].append(Text(_fill(body, chunk_start, values, where)))
        chunk, chunk_start = [], line + 1

    for number, line in enumerate(text.splitlines(), start=1):
        if slot is not None:  # inside a slot: the author's note
            if _CLOSE.match(line):
                slot = None
                chunk_start = number + 1
            continue
        if fence is not None:  # inside a code block: as written
            chunk.append(line)
            if line.strip().startswith(fence):
                fence = None
            continue
        if (opened := _FENCE.match(line)) is not None:
            fence = opened.group(1)
            chunk.append(line)
            continue
        if (found := _SLOT.match(line)) is not None:
            flush(number - 1)
            name = found.group(1)
            if name not in slots:
                raise BriefingError(f"{where}:{number}: no block for the slot {name!r}; blocks has "
                                    f"{sorted(slots)!r}.")
            if pages and sections[-1][0] is None:
                raise BriefingError(f"{where}:{number}: with pages=True, the report starts with a "
                                    "'# Page title' heading.")
            sections[-1][2].extend(_as_blocks(slots[name], name))
            used.add(name)
            slot = (name, number)
            continue
        if line.startswith(":::"):
            raise BriefingError(f"{where}:{number}: the only fence here is a slot, '::: block <name>' closed "
                                f"by ':::'; not {line.strip()!r}.")
        if pages and (heading := _PAGE.match(line)) is not None:
            flush(number - 1)
            title = _fill(heading.group(1), number, values, where).replace("\\", "")
            name = heading.group(2)
            if name == "auto":
                name = slug(title)
            sections.append((title, name, []))
            chunk_start = number + 1
            continue
        chunk.append(line)
    if slot is not None:
        raise BriefingError(f"{where}:{slot[1]}: the slot {slot[0]!r} isn't closed: end it with a ':::' line.")
    flush(len(text.splitlines()))

    unused = sorted(set(slots) - used)
    if unused:
        raise BriefingError(f"bf.from_markdown: blocks {unused!r} have no slot in {where}: add "
                            f"'::: block {unused[0]}' where they go, or drop them.")
    if pages:
        built = [Page(*content, title=title, name=name) for title, name, content in sections[1:]]
        if not built:
            raise BriefingError(f"{where}: pages=True, but there is no '# Page title' heading.")
        return Briefing(*built, **options)
    content = sections[0][2]
    if not content:
        raise BriefingError(f"{where}: the report is empty.")
    return Briefing(*content, **options)


__all__ = ["from_markdown"]
