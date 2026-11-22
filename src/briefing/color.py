"""Colour helpers for palettes (#175): OKLab conversions and ramps, in plain Python.

OKLab (Björn Ottosson, 2020) is a perceptual colour space: equal distances look like
equal differences, and its ``L`` is perceived lightness. Mixing colours there, rather
than in sRGB, gives ramps without muddy middles or uneven steps.

Example::

    bf.color.ramp(["#1b2c80", "#f5479a", "#ffc46b"], 5)  # five colours from blue to amber
"""
from __future__ import annotations

import dataclasses
import itertools
import math
import re
from collections.abc import Sequence

from briefing._error import BriefingError

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

OKLab = tuple[float, float, float]


def _to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def check_hex(color: object, where: str = "colour") -> str:
    """*color* as ``#rrggbb`` (lower case) if it is a hex colour; else an error naming *where*."""
    if not isinstance(color, str) or not _HEX.match(color.strip()):
        raise BriefingError(f"{where} must be a hex colour such as '#f5479a', not {color!r}.")
    c = color.strip().lstrip("#").lower()
    return "#" + ("".join(ch * 2 for ch in c) if len(c) == 3 else c)


def to_oklab(color: str) -> OKLab:
    """A hex colour as OKLab ``(L, a, b)``.

    Args:
        color: A hex colour such as ``"#f5479a"`` or ``"#fff"``.

    Example::

        bf.color.to_oklab("#ffffff")  # (1.0, 0.0, 0.0), near enough
    """
    h = check_hex(color).lstrip("#")
    r, g, b = (_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def from_oklab(lab: OKLab) -> str:
    """An OKLab ``(L, a, b)`` as a hex colour, clipped to sRGB.

    Args:
        lab: The colour's lightness ``L`` (0 to 1) and its ``a`` and ``b`` axes.

    Example::

        bf.color.from_oklab((0.5, 0.0, 0.0))  # '#636363'
    """
    lightness, a, b = lab
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    return "#" + "".join(f"{round(_to_srgb(c) * 255):02x}" for c in rgb)


def mix(a: str, b: str, t: float) -> str:
    """The colour a fraction *t* of the way from *a* to *b*, mixed in OKLab.

    Args:
        a: The colour at ``t=0`` (hex).
        b: The colour at ``t=1`` (hex).
        t: How far along, from 0 to 1 (clamped).

    Example::

        bf.color.mix("#1b2c80", "#ffc46b", 0.5)
    """
    t = min(1.0, max(0.0, float(t)))
    pa, pb = to_oklab(a), to_oklab(b)
    return from_oklab((pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t, pa[2] + (pb[2] - pa[2]) * t))


def along(anchors: Sequence[str], t: float) -> str:
    """The colour at *t* (0 to 1) on a ramp through *anchors*, evenly spaced, mixed in OKLab."""
    t = min(1.0, max(0.0, float(t)))
    n = len(anchors) - 1
    i = min(n - 1, int(t * n))
    return mix(anchors[i], anchors[i + 1], t * n - i)


def ramp(anchors: Sequence[str], n: int) -> list[str]:
    """*n* colours evenly along a ramp through *anchors* (low to high), mixed in OKLab.

    Args:
        anchors: Two or more hex colours, low to high.
        n: How many colours to return, 2 or more.

    Example::

        bf.color.ramp(["#1b2c80", "#f5479a", "#ffc46b"], 5)
    """
    colors = [check_hex(c, "bf.color.ramp: an anchor") for c in anchors]
    if len(colors) < 2:
        raise BriefingError("bf.color.ramp needs at least two anchors.")
    if not isinstance(n, int) or isinstance(n, bool) or n < 2:
        raise BriefingError(f"bf.color.ramp: n is a whole number of 2 or more, not {n!r}.")
    return [along(colors, i / (n - 1)) for i in range(n)]


def lightness(color: str) -> float:
    """The perceived lightness of a hex colour, OKLab's ``L``, from 0 (black) to 1 (white).

    Args:
        color: A hex colour.

    Example::

        bf.color.lightness("#f5479a")  # about 0.67
    """
    return to_oklab(color)[0]


# ── checks (#179) ─────────────────────────────────────────────────────────────


def _linear_rgb(color: str) -> tuple[float, float, float]:
    h = check_hex(color).lstrip("#")
    r, g, b = (_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return r, g, b


def contrast(a: str, b: str) -> float:
    """The WCAG contrast ratio of two hex colours, from 1 (the same) to 21 (black on white).

    Args:
        a: A hex colour.
        b: Another hex colour.

    Example::

        bf.color.contrast("#767676", "#ffffff")  # 4.54: just enough for text
    """
    def luminance(color: str) -> float:
        r, g, b = _linear_rgb(color)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


#: Machado, Oliveira and Fernandes (2009), full severity, on linear RGB.
_CVD: dict[str, tuple[tuple[float, float, float], ...]] = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216),
                   (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413),
                     (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602),
                   (0.004733, 0.691367, 0.303900)),
}


def simulate(color: str, condition: str) -> str:
    """How *color* looks with a colour-vision deficiency, at full severity.

    Args:
        color: A hex colour.
        condition: ``"protanopia"``, ``"deuteranopia"`` or ``"tritanopia"``.

    Example::

        bf.color.simulate("#ff0000", "deuteranopia")
    """
    if condition not in _CVD:
        raise BriefingError(f"bf.color.simulate: condition is one of {', '.join(_CVD)}, not {condition!r}.")
    rgb = _linear_rgb(color)
    out = [sum(m * c for m, c in zip(row, rgb, strict=True)) for row in _CVD[condition]]
    return "#" + "".join(f"{round(_to_srgb(c) * 255):02x}" for c in out)


def distance(a: str, b: str) -> float:
    """How different two colours look: their distance in OKLab, times 100 (about 2 is barely visible).

    Args:
        a: A hex colour.
        b: Another hex colour.

    Example::

        bf.color.distance("#1b2c80", "#1f40be")
    """
    return math.dist(to_oklab(a), to_oklab(b)) * 100


@dataclasses.dataclass(frozen=True)
class Finding:
    """One thing :func:`check` found about a palette."""

    level: str  # "warning", or "info" for what few readers meet (tritanopia)
    code: str  # "low-contrast", "too-close", "colour-blind", "lightness-not-monotonic"
    message: str
    colors: tuple[str, ...]


#: Below this OKLab distance (×100), two colours are hard to tell apart.
MIN_DISTANCE = 10.0
#: WCAG's minimum contrast for graphics against their background.
MIN_GRAPHIC_CONTRAST = 3.0


def check(colors: Sequence[str], background: str = "#ffffff", kind: str = "categorical") -> list[Finding]:
    """What makes a palette hard to read, as a list of findings (empty: nothing found).

    Args:
        colors: The palette, as hex colours (low to high for a sequential or diverging one).
        background: The colour they're drawn on, such as the theme's background.
        kind: ``"categorical"`` (each colour a category: they must stay apart, for
            colour-blind readers too), ``"sequential"`` (lightness must rise or fall all
            the way) or ``"diverging"`` (lightness must peak or dip at the middle colour).

    Example::

        for finding in bf.color.check(["#1b2c80", "#f5479a", "#ffc46b"], background="#1a1a1a"):
            print(finding.message)
    """
    palette = [check_hex(c, "bf.color.check: a colour") for c in colors]
    bg = check_hex(background, "bf.color.check: background")
    if kind not in ("categorical", "sequential", "diverging"):
        raise BriefingError(f"bf.color.check: kind is 'categorical', 'sequential' or 'diverging', not {kind!r}.")
    findings: list[Finding] = []
    for c in palette:
        ratio = contrast(c, bg)
        if ratio < MIN_GRAPHIC_CONTRAST:
            findings.append(Finding("warning", "low-contrast", f"{c} has a contrast of {ratio:.2f}:1 against {bg}; "
                                    f"graphics need {MIN_GRAPHIC_CONTRAST:g}:1.", (c, bg)))
    if kind == "categorical":
        for a, b in itertools.combinations(palette, 2):
            if distance(a, b) < MIN_DISTANCE:
                findings.append(Finding("warning", "too-close", f"{a} and {b} are hard to tell apart "
                                        f"(OKLab distance {distance(a, b):.1f}).", (a, b)))
                continue
            for condition in _CVD:
                d = distance(simulate(a, condition), simulate(b, condition))
                if d < MIN_DISTANCE:
                    # Tritanopia is rare (about 1 in 10,000): worth knowing, not a warning.
                    level = "info" if condition == "tritanopia" else "warning"
                    findings.append(Finding(level, "colour-blind", f"{a} and {b} look alike with {condition} "
                                            f"(OKLab distance {d:.1f}).", (a, b)))
                    break
    else:
        light = [lightness(c) for c in palette]
        if kind == "sequential":
            steps = [b - a for a, b in zip(light, light[1:], strict=False)]
            if not (all(d > 0 for d in steps) or all(d < 0 for d in steps)):
                findings.append(Finding("warning", "lightness-not-monotonic", "The lightness doesn't rise (or fall) "
                                        "all the way, so a lighter colour doesn't always mean more.", tuple(palette)))
        else:
            mid = len(light) // 2
            left, right = light[:mid + 1], light[mid:]
            peak = all(a < b for a, b in zip(left, left[1:], strict=False)) and all(
                a > b for a, b in zip(right, right[1:], strict=False))
            dip = all(a > b for a, b in zip(left, left[1:], strict=False)) and all(
                a < b for a, b in zip(right, right[1:], strict=False))
            if len(palette) % 2 == 0 or not (peak or dip):
                findings.append(Finding("warning", "lightness-not-monotonic", "A diverging palette needs an odd number "
                                        "of colours whose lightness peaks or dips at the middle one.", tuple(palette)))
    return findings


__all__ = ["Finding", "along", "check", "check_hex", "contrast", "distance", "from_oklab", "lightness", "mix",
           "ramp", "simulate", "to_oklab"]
