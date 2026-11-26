"""Linked selection (#21): a bar of a DataProfile or a DataCompare selects rows in a DataDive.

``selects="dive"`` names a DataDive in the sender's page. At render time:

- :func:`sender_attrs` puts the target's link id (resolved like a link, #24, and checked
  once every name is claimed, see :meth:`IdGen.target`) and a made-up id for the sender
  on its outer element;
- :func:`chart_attrs` says, on each chart, which column it counts and how a bar's rows are
  told apart: on bins (the bar's index, computed in the browser exactly as Python binned
  the values: same minimum, maximum, scale and number of bins) or on values (the text the
  DataDive shows);
- :func:`hits` draws an invisible target over each bar, which ``lab/static/select.js``
  makes clickable. A column the DataDive doesn't have (or holds as another kind) gets none,
  and its chart says why.

The DataDive (``lab.js``) listens for ``bf:select`` on the report's root and adds the
selection as a filter chip; nothing crosses into another report on the same page.
"""
from __future__ import annotations

import html as _html
import json
import typing as t
from collections.abc import Sequence

from briefing._error import BriefingError
from briefing.blocks.base import _NAME_RE, Block

if t.TYPE_CHECKING:
    from briefing.renderers.registry import IdGen


def check_selects(selects: object, block: str) -> tuple[str, ...]:
    """The names *selects* gives (one or a list), each a valid block name."""
    if selects is None:
        return ()
    names = [selects] if isinstance(selects, str) else selects
    if not isinstance(names, Sequence) or isinstance(names, str) or not names:
        raise BriefingError(f"{block} 'selects' is the name of a DataDive, or a list of names; not {selects!r}.")
    for name in names:
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise BriefingError(
                f"{block} 'selects' names a DataDive by its name= (letters, digits, '_' and '-'), not {name!r}."
            )
    return tuple(dict.fromkeys(names))


class Targets:
    """The DataDives a sender selects rows in, and the kind of each of their columns where known."""

    def __init__(self, sender: Block, names: tuple[str, ...], idgen: IdGen) -> None:
        from briefing.lab._blocks import DataDive
        from briefing.lab._render_datadive import _col_kind

        self.links = [idgen.target(sender, name, DataDive) for name in names]
        self.source = idgen.next("sel")
        self.known = True
        self.kinds: dict[str, str] = {}
        for link in self.links:
            dive = idgen.named(link)
            if not isinstance(dive, DataDive):
                self.known = False  # drawn alone (validate): checked when the report renders
                continue
            for column in dive.df.columns:
                if str(column) != dive.thumbnails:
                    self.kinds.setdefault(str(column), _col_kind(dive.df[column]))
        self.names = names

    def why_not(self, column: str, kind: str) -> str | None:
        """Why *column*'s bars select nothing, or ``None`` when they can."""
        if not self.known:
            return None
        have = self.kinds.get(column)
        if have == kind:
            return None
        dives = " or ".join(repr(n) for n in self.names)
        if have is None:
            return f"The DataDive {dives} has no column {column!r}."
        return f"In the DataDive {dives}, {column!r} holds {_KINDS[have]}, not {_KINDS[kind]}."


_KINDS = {"numeric": "numbers", "datetime": "dates", "categorical": "categories"}


def sender_attrs(targets: Targets | None, noun: str, block: Block) -> str:
    """The attributes of a sender's outer element: where its selections go, and who sends them."""
    if targets is None:
        return ""
    source = block.name or noun
    return (
        f' data-bf-selects="{_html.escape(json.dumps(targets.links))}" data-bf-source="{targets.source}"'
        f' data-bf-from="{_html.escape(source)}"'
    )


def bins_test(low: float, high: float, scale: float, bins: int, unit: float = 1) -> dict[str, t.Any]:
    """How the browser finds a value's bar, exactly as Python binned it; *unit* turns the dive's values into these."""
    return {"kind": "bins", "min": low, "max": high, "scale": scale, "bins": bins, "unit": unit}


def chart_attrs(targets: Targets | None, column: str, kind: str, test: dict[str, t.Any]) -> tuple[str, bool]:
    """The attributes of one chart, and whether its bars select rows."""
    if targets is None:
        return "", False
    why = targets.why_not(column, kind)
    if why is not None:
        return f' title="{_html.escape(why)}" data-bf-unselectable', False
    return (
        f' data-bf-column="{_html.escape(column)}" data-bf-test="{_html.escape(json.dumps(test, allow_nan=False))}"',
        True,
    )


def hits(column: str, boxes: Sequence[tuple[float, float, float, float, str, str]], dive: str) -> str:
    """An invisible, focusable target over each bar: ``(x, y, width, height, pick, label)``."""
    out = "".join(
        f'<rect class="bf-sel__hit" x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'data-bf-pick="{_html.escape(pick)}" data-bf-label="{_html.escape(label)}" tabindex="0" role="button" '
        f'aria-pressed="false" aria-label="{_html.escape(f"Select {column} {label} in {dive}")}"/>'
        for x, y, w, h, pick, label in boxes
    )
    return f'<g class="bf-sel__hits">{out}</g>'


__all__ = ["Targets", "bins_test", "chart_attrs", "check_selects", "hits", "sender_attrs"]
