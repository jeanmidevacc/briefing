"""Colour helpers for palettes (#175): OKLab conversions and ramps, in plain Python.

OKLab (Björn Ottosson, 2020) is a perceptual colour space: equal distances look like
equal differences, and its ``L`` is perceived lightness. Mixing colours there, rather
than in sRGB, gives ramps without muddy middles or uneven steps.

Example::

    bf.color.ramp(["#1b2c80", "#f5479a", "#ffc46b"], 5)  # five colours from blue to amber
"""
from __future__ import annotations

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


__all__ = ["along", "check_hex", "from_oklab", "lightness", "mix", "ramp", "to_oklab"]
