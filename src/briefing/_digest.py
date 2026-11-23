"""``bf.email.from_report`` (#199, experimental): a first draft of an email digest from a report.

A digest is short, so it takes one page. Blocks an email shows stay; interactive ones
become what a reader would see first (a DataTable's first rows, a Select's first panel);
the rest is left out, and one warning names it.
"""
from __future__ import annotations

import copy
import re
import typing as t
import warnings

from briefing._error import BriefingError
from briefing._experimental import experimental
from briefing.blocks.asset import DataTable, Plot, Table
from briefing.blocks.banner import Banner
from briefing.blocks.base import Block
from briefing.blocks.chips import Chips
from briefing.blocks.layout import Briefing, Card, Group, Page, Select
from briefing.blocks.text import Alert, BigNumber, Text

if t.TYPE_CHECKING:
    import pandas as pd

    from briefing.email import Digest

#: Rows a table keeps in an email (``bf.email.MAX_TABLE_ROWS``).
ROWS = 30
#: A Markdown link into the report itself: ``[words](#page/name)``.
_INNER_LINK = re.compile(r"\[([^\]]+)\]\(#[^)\s]*\)")


def _unlinked(block: Block) -> Block:
    """*block* with its links into the report turned into their words (a digest without ``link=``)."""
    if isinstance(block, Text) and _INNER_LINK.search(block.content):
        return Text(_INNER_LINK.sub(r"\1", block.content), name=block.name, label=block.label)
    if isinstance(block, Group):
        group = copy.copy(block)
        group.blocks = [_unlinked(child) for child in block.blocks]
        return group
    return block


def _what(block: Block) -> str:
    from briefing.spec._model import type_name

    kind = type_name(block) or type(block).__name__
    return f'{kind} "{block.name}"' if block.name else kind


def _rows(frame: pd.DataFrame, caption: str | None) -> list[Block]:
    """A Table of *frame*'s first rows, and a line saying so when it was cut."""
    table: list[Block] = [Table(frame.head(ROWS).reset_index(drop=True), caption=caption)]
    if len(frame) > ROWS:
        table.append(Text(f"First {ROWS} of {len(frame):,} rows: see the full report."))
    return table


def _datatable(block: DataTable) -> list[Block]:
    """A DataTable as the Table of its first rows, its ``formats=`` applied."""
    from briefing.renderers.table import _formatted

    frame = block.df.head(ROWS).copy()
    for column, how in (block.formats or {}).items():
        if column in frame.columns:
            frame[column] = _formatted(how, column, frame[column].tolist())
    rows: list[Block] = [Table(frame.reset_index(drop=True), caption=block.caption)]
    if len(block.df) > ROWS:
        rows.append(Text(f"First {ROWS} of {len(block.df):,} rows: see the full report."))
    return rows


def convert(block: Block, left: list[str]) -> list[Block]:
    """What *block* becomes in an email; what can't go in one is added to *left*."""
    if isinstance(block, Text | BigNumber | Alert | Plot):
        return [block]
    if isinstance(block, Group):
        children = [child for b in block.blocks for child in convert(b, left)]
        if not children:
            return []
        group = copy.copy(block)
        group.blocks = children
        return [group]
    if isinstance(block, DataTable):
        return _datatable(block)
    if isinstance(block, Table):
        frame = t.cast("pd.DataFrame", getattr(block.data, "data", block.data))  # a Styler keeps its frame in .data
        return [block] if len(frame) <= ROWS else _rows(frame, block.caption)
    if isinstance(block, Select):
        return convert(block.blocks[0], left) if block.blocks else []
    if isinstance(block, Card):
        title = [Text(f"**{block.title}**")] if block.title else []
        return title + [child for b in block.blocks for child in convert(b, left)]
    if isinstance(block, Banner):
        return [Text(block.text)]
    if isinstance(block, Chips):
        return [Text(" · ".join(chip.text for chip in block.items))] if block.items else []
    left.append(_what(block))
    return []


def _page(root: Briefing, page: int | str) -> list[Block]:
    """The blocks of the page *page* picks: an index, a page's title or its name."""
    pages = [b for b in root.blocks if isinstance(b, Page)] if all(isinstance(b, Page) for b in root.blocks) else []
    if not pages:
        if page not in (0, "0"):
            raise BriefingError(f"bf.email.from_report: page={page!r}, but the report has no Page blocks; "
                                "leave page out to take the whole report.")
        return list(root.blocks)
    if isinstance(page, int) and not isinstance(page, bool):
        if 0 <= page < len(pages):
            return list(pages[page].blocks)
        raise BriefingError(f"bf.email.from_report: page={page} is out of range: the report has "
                            f"{len(pages)} pages, from 0.")
    found = [p for p in pages if p.name == page] or [p for p in pages if p.title == page]
    if not found:
        titles = ", ".join(repr(p.title) for p in pages)
        raise BriefingError(f"bf.email.from_report: no page named {page!r}. Pages: {titles}. Pass an index, "
                            "a title or a name.")
    return list(found[0].blocks)


def from_report(report: object, link: str | None = None, page: int | str = 0) -> Digest:
    """*Experimental.* A first draft of an email digest from a report, to adjust before sending.

    A digest is short, so it takes one page of the report (the whole report when it has no
    pages). Text, numbers, alerts and charts stay. A ``DataTable`` becomes a ``Table`` of
    its first 30 rows, its formats applied; a ``Select`` its first panel; a ``Card`` its
    title in bold, then its blocks; a ``Banner`` and ``Chips`` their text. Toggles, images,
    files, code, formulas, raw HTML and lab blocks are left out, and one warning names them.
    Without ``link=``, links into the report (``[detail](#detail/rows)``) keep only their words.

    The result is an ordinary :class:`Digest`. What it returns may change in any release;
    it warns :class:`~briefing.ExperimentalWarning` once per session.

    Args:
        report: A :class:`~briefing.Briefing`, a block or a list of blocks.
        link: The full report's address: the digest's "Open the full report" button.
        page: The page to take: an index (0 for the first), a page's title or its ``name``.

    Returns:
        The digest.

    Raises:
        BriefingError: For an unknown page, or a page with nothing an email can show.

    Example::

        digest = bf.email.from_report(report, link="https://example.com/q3.html")
        message = bf.email.to_message(digest, subject="Q3 review", to="team@example.com")
    """
    from briefing.email import Digest

    experimental("bf.email.from_report")
    root = Briefing.wrap(t.cast(t.Any, report))
    left: list[str] = []
    blocks = [out for block in _page(root, page) for out in convert(block, left)]
    if left:
        hint = "The digest's button leads to the full report." if link else "link= adds a button to the full report."
        warnings.warn(f"bf.email.from_report left out {len(left)} block{'s' if len(left) != 1 else ''} an email "
                      f"can't show: {', '.join(left)}. {hint}", UserWarning, stacklevel=2)
    if link is None:
        blocks = [_unlinked(block) for block in blocks]
    if not blocks:
        raise BriefingError("bf.email.from_report: this page holds nothing an email can show "
                            f"(only {', '.join(left)}). Pick another page with page=, or write the digest yourself.")
    return Digest(*blocks, link=link, footer=root.footer)


__all__ = ["ROWS", "convert", "from_report"]
