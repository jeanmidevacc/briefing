"""bf.Scale (#175): a colour scale with a fixed meaning, interpolated in OKLab."""
from __future__ import annotations

import dataclasses
import math
import numbers
import typing as t
from collections.abc import Mapping, Sequence

from briefing import color as _color
from briefing._error import BriefingError


def _number(value: object) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(float(value))


@dataclasses.dataclass(frozen=True)
class Scale:
    """A colour scale: which colour a value gets, the same in every block that uses it.

    Colours are spaced evenly along the domain and mixed in OKLab, so equal steps in value
    look like equal steps in colour. Pass a scale as ``colors=`` to the heatmaps, or call it
    with a value to colour anything else.

    Args:
        colors: Two or more hex colours, low to high. With ``center``, an odd number:
            the middle one sits at the centre.
        domain: ``(low, high)``: the values the first and last colours stand for, so a
            colour means the same value everywhere; values outside are clamped. Without
            it, each block spreads the colours over its own data.
        center: A midpoint for a diverging scale, such as ``0`` for a balance.
        steps: Show that many flat classes instead of a continuous ramp.

    Example::

        interest = bf.Scale(["#1b2c80", "#9a3fc4", "#f5479a", "#ffc46b"], domain=(0, 100))
        bf.lab.CalendarHeatmap(df, date="day", value="interest", colors=interest)
        interest(42)  # the hex colour of 42
        balance = bf.Scale(["#d73027", "#f7f7f7", "#1a9850"], center=0)
    """

    colors: Sequence[str]
    domain: tuple[float, float] | None = None
    center: float | None = None
    steps: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.colors, str) or not isinstance(self.colors, Sequence) or len(self.colors) < 2:
            raise BriefingError(f"Scale: colors is a list of two or more hex colours, not {self.colors!r}.")
        object.__setattr__(self, "colors", tuple(_color.check_hex(c, "Scale: each colour") for c in self.colors))
        if self.domain is not None:
            if (isinstance(self.domain, str) or not isinstance(self.domain, Sequence) or len(self.domain) != 2
                    or not all(_number(v) for v in self.domain) or not self.domain[0] < self.domain[1]):
                raise BriefingError(f"Scale: domain is (low, high), two numbers with low below high, "
                                    f"not {self.domain!r}.")
            object.__setattr__(self, "domain", (float(self.domain[0]), float(self.domain[1])))
        if self.center is not None:
            if not _number(self.center):
                raise BriefingError(f"Scale: center is a number, not {self.center!r}.")
            if len(self.colors) % 2 == 0:
                raise BriefingError("Scale: with center, colors has an odd number of colours (3, 5…): "
                                    "the middle one sits at the centre.")
            if self.domain is not None and not self.domain[0] < self.center < self.domain[1]:
                raise BriefingError(f"Scale: center {self.center} must be inside the domain {self.domain}.")
            object.__setattr__(self, "center", float(self.center))
        if self.steps is not None and (not isinstance(self.steps, int) or isinstance(self.steps, bool)
                                       or self.steps < 2):
            raise BriefingError(f"Scale: steps is a whole number of 2 or more, not {self.steps!r}.")

    # ── the scale ────────────────────────────────────────────────────────────

    def bounds(self, values: Sequence[float] = ()) -> tuple[float, float]:
        """The low and high ends: the domain, else the range of *values* (symmetric around a centre)."""
        if self.domain is not None:
            return self.domain
        if not values:
            raise BriefingError("Scale: this scale has no domain and no values to spread over: "
                                "pass domain=(low, high).")
        lo, hi = float(min(values)), float(max(values))
        if self.center is not None:
            reach = max(abs(lo - self.center), abs(hi - self.center)) or 1.0
            return self.center - reach, self.center + reach
        return lo, hi

    def position(self, value: float, lo: float, hi: float) -> float:
        """Where *value* falls between *lo* and *hi*, from 0 to 1 (the centre, if any, at 0.5)."""
        v = min(hi, max(lo, float(value)))
        if self.center is None:
            where = 1.0 if hi == lo else (v - lo) / (hi - lo)
        elif v <= self.center:
            where = 0.5 * (v - lo) / (self.center - lo) if self.center > lo else 0.5
        else:
            where = 0.5 + 0.5 * (v - self.center) / (hi - self.center) if hi > self.center else 0.5
        if self.steps is not None:
            where = min(self.steps - 1, math.floor(where * self.steps)) / (self.steps - 1)
        return where

    def at(self, value: float, lo: float, hi: float) -> str:
        """The colour of *value* between *lo* and *hi*."""
        return _color.along(self.colors, self.position(value, lo, hi))

    def __call__(self, value: float) -> str:
        """The hex colour of *value* on this scale's domain."""
        lo, hi = self.bounds()
        return self.at(value, lo, hi)

    def gradient(self, lo: float, hi: float) -> str:
        """A CSS ``linear-gradient`` of the scale from *lo* to *hi*, left to right."""
        if self.steps is not None:
            stops = []
            for k in range(self.steps):
                c = _color.along(self.colors, k / (self.steps - 1))
                stops.append(f"{c} {k / self.steps * 100:.4g}% {(k + 1) / self.steps * 100:.4g}%")
            return f"linear-gradient(to right, {', '.join(stops)})"
        samples = [self.at(lo + (hi - lo) * i / 16, lo, hi) for i in range(17)]
        return f"linear-gradient(to right, {', '.join(samples)})"

    # ── the JSON form ────────────────────────────────────────────────────────

    @classmethod
    def of(cls, value: Scale | Mapping[str, t.Any]) -> Scale:
        """*value* as a Scale: a Scale or a dict of its fields (the JSON form)."""
        if isinstance(value, Scale):
            return value
        fields = [f.name for f in dataclasses.fields(cls)]
        unknown = [k for k in value if k not in fields]
        if unknown:
            raise BriefingError(f"Scale has no field {unknown[0]!r}; it takes {', '.join(fields)}.")
        if "colors" not in value:
            raise BriefingError("Scale: colors is required.")
        return cls(**value)

    def to_dict(self) -> dict[str, t.Any]:
        """The fields that are set, as JSON."""
        out: dict[str, t.Any] = {"colors": list(self.colors)}
        if self.domain is not None:
            out["domain"] = list(self.domain)
        if self.center is not None:
            out["center"] = self.center
        if self.steps is not None:
            out["steps"] = self.steps
        return out


__all__ = ["Scale"]
