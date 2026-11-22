"""bf.diff (#30): what changed between two runs of a report, as a report of its own.

Blocks are matched by their link names (#24); unnamed blocks aren't compared.
"""
from __future__ import annotations

import difflib
import json
import math
import numbers
import typing as t
from collections.abc import Mapping, Sequence
from pathlib import Path

from briefing._error import BriefingError
from briefing.blocks.asset import DataTable, Table
from briefing.blocks.base import Block, ContainerBlock
from briefing.blocks.layout import Briefing, Group
from briefing.blocks.text import BigNumber, Code, Text

if t.TYPE_CHECKING:
    import pandas as pd

#: What a table diff shows in a cell that changed.
ARROW = " → "


# ── reading the two runs ──────────────────────────────────────────────────────


def _report(run: object, which: str) -> Briefing:
    """*run* as a Briefing: a Briefing, a block, a JSON form (dict or path) or a (spec, data) pair."""
    from briefing.spec import from_spec

    if isinstance(run, Briefing):
        return run
    if isinstance(run, Block):
        return Briefing(run)
    if isinstance(run, tuple) and len(run) == 2 and isinstance(run[0], Mapping):
        return from_spec(run[0], run[1])
    if isinstance(run, Mapping):
        return from_spec(run)
    if isinstance(run, str | Path):
        path = Path(run).expanduser()
        if not path.is_file():
            raise BriefingError(f"bf.diff: {which} file not found: {path}")
        return from_spec(json.loads(path.read_text(encoding="utf-8")))
    raise BriefingError(f"bf.diff: {which} is a Briefing, a block, a JSON form (a dict or a path) or a "
                        f"(spec, data) pair from bf.to_spec, not {type(run).__name__}.")


def _named(report: Briefing) -> tuple[dict[str, Block], int]:
    """Each named block (not containers: their blocks) by its link name, and how many have no name."""
    from briefing.renderers.links import claim_links
    from briefing.renderers.normalize import normalize
    from briefing.renderers.registry import IdGen

    root = normalize(report)
    idgen = IdGen()
    claim_links(root, idgen)
    named: dict[str, Block] = {}
    unnamed = 0

    def walk(block: Block) -> None:
        nonlocal unnamed
        if isinstance(block, ContainerBlock):  # pages, groups, tabs: their blocks are compared one by one
            for child in block.blocks:
                walk(child)
        elif (link := idgen.link(block)) is not None:
            named[link] = block
        else:
            unnamed += 1

    for block in root.blocks:
        walk(block)
    return named, unnamed


# ── comparing blocks ──────────────────────────────────────────────────────────


def _form(block: Block) -> tuple[t.Any, list[t.Any]]:
    """A block's JSON form, and the objects it refers to (charts that only go by reference)."""
    from briefing.spec import to_spec

    spec, data = to_spec(Briefing(block), inline=True)
    return spec["blocks"][0], list(data.values())


def _same_objects(a: list[t.Any], b: list[t.Any]) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b, strict=True):
        if hasattr(x, "equals") and type(x) is type(y):
            if not x.equals(y):
                return False
        elif x is not y:
            return False
    return True


def _same(a: Block, b: Block) -> bool:
    if type(a) is not type(b):
        return False
    try:
        (spec_a, refs_a), (spec_b, refs_b) = _form(a), _form(b)
    except BriefingError:
        return False
    return bool(spec_a == spec_b) and _same_objects(refs_a, refs_b)


def _frame(block: Block) -> pd.DataFrame | None:
    if isinstance(block, DataTable):
        return block.df
    if isinstance(block, Table):
        data = block.data
        return t.cast("pd.DataFrame", getattr(data, "data", data))  # a Styler keeps its frame in .data
    return None


def _number(value: object) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(float(value))


# ── what changed, block by block ──────────────────────────────────────────────


def _bignumber(old: BigNumber, new: BigNumber) -> BigNumber:
    if _number(old.value) and _number(new.value):
        return BigNumber(new.heading, t.cast(float, new.value), prev_value=t.cast(float, old.value),
                         format=new.format)
    return BigNumber(new.heading, new.value, change=f"was {old.value}")


def _cell(value: object) -> str:
    from briefing.renderers.table import _fmt

    return str(_fmt(value))


def _table(link: str, old: pd.DataFrame, new: pd.DataFrame, key: str | Sequence[str] | None) -> list[Block]:
    """A sentence and a DataTable of the rows that changed between *old* and *new*."""
    import pandas as pd

    gone = [c for c in old.columns if c not in new.columns]
    came = [c for c in new.columns if c not in old.columns]
    shared = [c for c in new.columns if c in old.columns]
    notes = []
    if came:
        notes.append(f"columns added: {', '.join(map(str, came))}")
    if gone:
        notes.append(f"columns removed: {', '.join(map(str, gone))}")
    columns = [str(c) for c in shared]
    rows: list[list[str]] = []
    if key is not None:
        keys = [key] if isinstance(key, str) else list(key)
        missing = [k for k in keys if k not in shared]
        if missing:
            raise BriefingError(f"bf.diff: the key {missing!r} of {link!r} isn't a column of both runs.")
        before = {tuple(r[k] for k in keys): r for _, r in old.iterrows()}
        after = {tuple(r[k] for k in keys): r for _, r in new.iterrows()}
        added = [k for k in after if k not in before]
        removed = [k for k in before if k not in after]
        changed = [k for k in after if k in before and any(
            _cell(after[k][c]) != _cell(before[k][c]) for c in shared)]
        for k in added:
            rows.append(["added", *(_cell(after[k][c]) for c in shared)])
        for k in removed:
            rows.append(["removed", *(_cell(before[k][c]) for c in shared)])
        for k in changed:
            rows.append(["changed", *(_cell(after[k][c]) if _cell(after[k][c]) == _cell(before[k][c])
                                       else _cell(before[k][c]) + ARROW + _cell(after[k][c]) for c in shared)])
        counts = [f"{len(added)} added", f"{len(removed)} removed", f"{len(changed)} changed"]
    else:
        def lines(frame: pd.DataFrame) -> list[tuple[str, ...]]:
            return [tuple(_cell(v) for v in row) for row in frame[shared].itertuples(index=False, name=None)]

        before_rows, after_rows = lines(old), lines(new)
        pool = list(before_rows)
        added_rows = []
        for row in after_rows:
            if row in pool:
                pool.remove(row)
            else:
                added_rows.append(row)
        rows = [["added", *r] for r in added_rows] + [["removed", *r] for r in pool]
        counts = [f"{len(added_rows)} rows added", f"{len(pool)} removed"]
    sentence = f"**`{link}`**: {', '.join(counts)}" + (f"; {'; '.join(notes)}" if notes else "") + "."
    blocks: list[Block] = [Text(sentence)]
    if rows:
        frame = pd.DataFrame(rows, columns=["change", *columns])
        blocks.append(DataTable(frame, caption=f"Rows of {link} that changed"))
    return blocks


def _text(link: str, old: Text, new: Text) -> list[Block]:
    lines = difflib.unified_diff(old.content.splitlines(), new.content.splitlines(),
                                 fromfile=f"{link} (before)", tofile=f"{link} (now)", lineterm="")
    return [Code("\n".join(lines), language="diff", caption=f"{link}: text changed")]


# ── the diff ──────────────────────────────────────────────────────────────────


def diff(old: object, new: object, keys: Mapping[str, str | Sequence[str]] | None = None) -> Briefing:
    """What changed between two runs of a report, as a report of its own.

    Blocks are matched by their link names (``name=``, see the links guide); unnamed
    blocks aren't compared. Changed numbers show their change, changed tables the rows
    added, removed and changed, changed text a line-by-line diff.

    Args:
        old: The earlier run: a ``Briefing`` or block, a JSON form (a dict, or the path
            of a ``.json`` file written from ``bf.to_spec(report, inline=True)``), or the
            ``(spec, data)`` pair ``bf.to_spec`` returns.
        new: The later run, in any of the same forms.
        keys: For tables, the column (or columns) that identify a row, by the table's
            link name, such as ``{"detail/regions": "region"}``. A table without a key
            is compared row by row: rows added and removed.

    Example::

        changes = bf.diff("yesterday.json", today, keys={"detail/ridings": "riding"})
        bf.save(changes, "what-changed.html", name="What changed since yesterday")
    """
    before_report, after_report = _report(old, "old"), _report(new, "new")
    before, unnamed_before = _named(before_report)
    after, unnamed_after = _named(after_report)
    keys = dict(keys or {})
    unknown = [k for k in keys if k not in after or _frame(after[k]) is None]
    if unknown:
        raise BriefingError(f"bf.diff: keys names {unknown!r}, which aren't tables of the new run.")

    added = [link for link in after if link not in before]
    removed = [link for link in before if link not in after]
    common = [link for link in after if link in before]
    changed = [link for link in common if not _same(before[link], after[link])]

    numbers_: list[Block] = []
    tables: list[Block] = []
    texts: list[Block] = []
    others: list[str] = []
    for link in changed:
        a, b = before[link], after[link]
        if isinstance(a, BigNumber) and isinstance(b, BigNumber):
            numbers_.append(_bignumber(a, b))
        elif (fa := _frame(a)) is not None and (fb := _frame(b)) is not None and type(a) is type(b):
            tables += _table(link, fa, fb, keys.get(link))
        elif isinstance(a, Text) and isinstance(b, Text):
            texts += _text(link, a, b)
        else:
            others.append(f"- `{link}` ({type(b).__name__})")

    def plural(n: int, word: str) -> str:
        return f"{n} {word}{'' if n == 1 else 's'}"

    if changed or added or removed:
        summary = (f"{plural(len(changed), 'block')} changed, {len(added)} added, {len(removed)} removed, "
                   f"{len(common) - len(changed)} unchanged.")
    else:
        summary = "Nothing changed: every named block is the same in both runs."
    unnamed = max(unnamed_before, unnamed_after)
    if unnamed:
        summary += (f" {plural(unnamed, 'unnamed block')} {'wasn' if unnamed == 1 else 'weren'}'t compared: "
                    "give a block `name=` to compare it from run to run.")
    blocks: list[Block] = [Text(f"## What changed\n\n{summary}")]
    if numbers_:
        blocks += [Text("### Numbers"), Group(*numbers_, min_width="12rem")]
    if tables:
        blocks += [Text("### Tables"), *tables]
    if texts:
        blocks += [Text("### Text"), *texts]
    if others:
        blocks.append(Text("### Other blocks that changed\n\n" + "\n".join(others)))
    for title, links, run in (("Added", added, after), ("Removed", removed, before)):
        if links:
            items = "\n".join(f"- `{link}` ({type(run[link]).__name__})" for link in links)
            blocks.append(Text(f"### {title}\n\n{items}"))
    return Briefing(*blocks)


__all__ = ["diff"]
