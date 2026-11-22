"""Chips (#27): a wrapping row of labelled pills, such as the searches that rose or fell."""
from __future__ import annotations

import dataclasses
import typing as t
from collections.abc import Mapping, Sequence

from briefing._colors import check_color
from briefing._error import BriefingError
from briefing.blocks.base import _MAX_CAPTION_LEN, Block, BlockId, _truncate


@dataclasses.dataclass(frozen=True)
class Chip:
    """One pill of a :class:`Chips` row: its text, and an optional tooltip and colour.

    Args:
        text: What the pill says, as plain text.
        tooltip: Shown when the reader hovers the pill.
        color: ``"up"``, ``"down"`` or ``"accent"`` (the theme's colours) or a CSS colour;
            the pill is tinted with it. Without it the pill is neutral.

    Example::

        bf.Chip("Steam +41%", tooltip="Usual level 31, since the release 44", color="up")
    """

    text: str
    tooltip: str | None = None
    color: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise BriefingError(f"Chip: text is a short line such as 'Steam +41%', not {self.text!r}.")
        if self.tooltip is not None and not isinstance(self.tooltip, str):
            raise BriefingError(f"Chip: tooltip is text, not {self.tooltip!r}.")
        object.__setattr__(self, "text", _truncate(self.text.strip(), _MAX_CAPTION_LEN))
        object.__setattr__(self, "tooltip", self.tooltip.strip() or None if self.tooltip else None)
        object.__setattr__(self, "color", check_color(self.color, "Chip: color"))

    @classmethod
    def of(cls, item: object) -> Chip:
        """*item* as a Chip: a Chip, its text, or a dict of its fields (the JSON form)."""
        if isinstance(item, Chip):
            return item
        if isinstance(item, str):
            return cls(item)
        if isinstance(item, Mapping):
            fields = [f.name for f in dataclasses.fields(cls)]
            unknown = [k for k in item if k not in fields]
            if unknown:
                raise BriefingError(f"Chip has no field {unknown[0]!r}; it takes {', '.join(fields)}.")
            return cls(**item)
        raise BriefingError(f"Chips: an item is text, a bf.Chip(...) or a dict of its fields, not {item!r}.")

    def to_json(self) -> str | dict[str, str]:
        """The JSON form: the text alone, or an object when there is more."""
        if self.tooltip is None and self.color is None:
            return self.text
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}


class Chips(Block):
    """A wrapping row of pills: labels, tags, or values that rose or fell.

    Args:
        items: The pills: text, or :class:`Chip` for a tooltip or a colour.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.Chips(["Pizza", "Uber Eats", "DoorDash"])
        bf.Chips([bf.Chip("Steam +41%", color="up"), bf.Chip("Netflix -12%", color="down")])
    """

    def __init__(
        self,
        items: Sequence[str | Chip | Mapping[str, t.Any]],
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        if isinstance(items, str | bytes | Mapping) or not isinstance(items, Sequence):
            raise BriefingError(f"Chips: items is a list of texts or bf.Chip(...), not {type(items).__name__}.")
        if not items:
            raise BriefingError("Chips: items holds at least one pill.")
        self.items = [Chip.of(item) for item in items]


__all__ = ["Chip", "Chips"]
