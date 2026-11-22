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
    with a value to colour anything else. A domain of category names makes it categorical:
    a named palette, one colour per category (#39).

    Args:
        colors: Two or more hex colours, low to high. With ``center``, an odd number:
            the middle one sits at the centre.
        domain: ``(low, high)``: the values the first and last colours stand for, so a
            colour means the same value everywhere; values outside are clamped. Without
            it, each block spreads the colours over its own data. Or a list of category
            names, one per colour, for a categorical scale.
        center: A midpoint for a diverging scale, such as ``0`` for a balance.
        steps: Show that many flat classes instead of a continuous ramp.

    Example::

        interest = bf.Scale(["#1b2c80", "#9a3fc4", "#f5479a", "#ffc46b"], domain=(0, 100))
        bf.lab.CalendarHeatmap(df, date="day", value="interest", colors=interest)
        interest(42)  # the hex colour of 42
        balance = bf.Scale(["#d73027", "#f7f7f7", "#1a9850"], center=0)
        parties = bf.Scale(["#d71920", "#1a4782"], domain=["Liberal", "Conservative"])
        parties("Liberal")  # '#d71920'; parties.mapping for Plotly's color_discrete_map
    """

    colors: Sequence[str]
    domain: tuple[float, float] | Sequence[str] | None = None
    center: float | None = None
    steps: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.colors, str) or not isinstance(self.colors, Sequence) or len(self.colors) < 2:
            raise BriefingError(f"Scale: colors is a list of two or more hex colours, not {self.colors!r}.")
        object.__setattr__(self, "colors", tuple(_color.check_hex(c, "Scale: each colour") for c in self.colors))
        if self.domain is not None and self.domain and not isinstance(self.domain, str) and all(
                isinstance(v, str) for v in self.domain):
            self._categorical()
            return
        if self.domain is not None:
            ends: t.Any = self.domain
            if (isinstance(ends, str) or not isinstance(ends, Sequence) or len(ends) != 2
                    or not all(_number(v) for v in ends) or not ends[0] < ends[1]):
                raise BriefingError(f"Scale: domain is (low, high), two numbers with low below high, "
                                    f"not {self.domain!r}.")
            object.__setattr__(self, "domain", (float(ends[0]), float(ends[1])))
        if self.center is not None:
            if not _number(self.center):
                raise BriefingError(f"Scale: center is a number, not {self.center!r}.")
            if len(self.colors) % 2 == 0:
                raise BriefingError("Scale: with center, colors has an odd number of colours (3, 5…): "
                                    "the middle one sits at the centre.")
            lo, hi = t.cast("tuple[float, float]", self.domain) if self.domain is not None else (-math.inf, math.inf)
            if not lo < self.center < hi:
                raise BriefingError(f"Scale: center {self.center} must be inside the domain {self.domain}.")
            object.__setattr__(self, "center", float(self.center))
        if self.steps is not None and (not isinstance(self.steps, int) or isinstance(self.steps, bool)
                                       or self.steps < 2):
            raise BriefingError(f"Scale: steps is a whole number of 2 or more, not {self.steps!r}.")

    def _categorical(self) -> None:
        names = list(t.cast("Sequence[str]", self.domain))
        if len(names) != len(self.colors):
            raise BriefingError(f"Scale: a categorical scale has one colour per category: {len(self.colors)} "
                                f"colours for {len(names)} categories.")
        if len(set(names)) != len(names):
            raise BriefingError(f"Scale: a category is named twice in {names!r}.")
        if self.center is not None or self.steps is not None:
            raise BriefingError("Scale: center and steps are for numbers, not categories.")
        object.__setattr__(self, "domain", tuple(names))

    @property
    def categorical(self) -> bool:
        """Whether the domain names categories (a named palette) rather than a range of numbers."""
        return self.domain is not None and all(isinstance(v, str) for v in self.domain)

    @property
    def mapping(self) -> dict[str, str]:
        """Category → colour, for a categorical scale (Plotly's ``color_discrete_map``)."""
        if not self.categorical:
            raise BriefingError("Scale: mapping is for a categorical scale, whose domain names categories.")
        return dict(zip(t.cast("Sequence[str]", self.domain), self.colors, strict=True))

    # ── the scale ────────────────────────────────────────────────────────────

    def bounds(self, values: Sequence[float] = ()) -> tuple[float, float]:
        """The low and high ends: the domain, else the range of *values* (symmetric around a centre)."""
        if self.categorical:
            raise BriefingError("Scale: a categorical scale colours categories, not a range of numbers.")
        if self.domain is not None:
            return t.cast("tuple[float, float]", self.domain)
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

    def __call__(self, value: float | str) -> str:
        """The hex colour of *value* on this scale's domain (or of a category)."""
        if self.categorical:
            mapping = self.mapping
            if value not in mapping:
                raise BriefingError(f"Scale: {value!r} isn't one of its categories: {list(mapping)!r}.")
            return mapping[str(value)]
        lo, hi = self.bounds()
        return self.at(t.cast(float, value), lo, hi)

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
            out["domain"] = list(self.domain)  # numbers, or category names
        if self.center is not None:
            out["center"] = self.center
        if self.steps is not None:
            out["steps"] = self.steps
        return out


__all__ = ["Scale"]
