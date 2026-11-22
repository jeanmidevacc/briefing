"""Colours a block may take from its author (#27): a theme token or a plain CSS colour.

``"up"``, ``"down"`` and ``"accent"`` name the theme's colours (``--bf-up``, ``--bf-down``,
``--bf-accent``), so a dark theme sets them once; anything else must be a CSS colour made of
plain characters, so it can't break out of the ``style`` attribute it lands in.
"""
from __future__ import annotations

import re

from briefing._error import BriefingError

#: A CSS colour: a hex, a name, or rgb()/hsl()/oklch()/oklab() with plain numbers.
CSS_COLOR = re.compile(
    r"^(?:#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})"  # #rgb, #rgba, #rrggbb, #rrggbbaa
    r"|[a-zA-Z]+"  # a named colour
    r"|(?:rgb|rgba|hsl|hsla|oklch|oklab)\([0-9.,%\s/-]+\))$"  # a colour function of plain numbers
)

#: The theme's colours, by the name an author uses.
TOKENS = {"up": "var(--bf-up)", "down": "var(--bf-down)", "accent": "var(--bf-accent)"}


def check_color(value: object, where: str) -> str | None:
    """*value* if it is a theme token or a CSS colour (``None`` stays ``None``); else an error."""
    if value is None:
        return None
    if isinstance(value, str) and (value in TOKENS or CSS_COLOR.match(value.strip())):
        return value.strip()
    raise BriefingError(f"{where} is 'up', 'down', 'accent' or a CSS colour such as '#2dd4bf' or 'teal', "
                        f"not {value!r}.")


def css_color(value: str) -> str:
    """The CSS for a checked colour: a theme token becomes its variable."""
    return TOKENS.get(value, value)


__all__ = ["CSS_COLOR", "TOKENS", "check_color", "css_color"]
