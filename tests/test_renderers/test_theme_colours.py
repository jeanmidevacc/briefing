"""Tables (#150) and alerts (#167) take their colours from the theme, so dark themes read."""
from __future__ import annotations

import re

from tests.golden import static_files

_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_TABLE = re.compile(r"\b(?:tr|td|th|table)\b|\.bf-dt__|\.bf-table__")


def test_table_rules_use_no_hard_coded_colour() -> None:
    css = re.sub(r"/\*.*?\*/", "", static_files()["static/report.css"], flags=re.S)
    offenders = [f"{selector.strip()} {{{body.strip()}}}" for selector, body in _RULE.findall(css)
                 if _TABLE.search(selector) and _HEX.search(body)]
    assert offenders == []


def test_alert_backgrounds_and_text_come_from_the_theme() -> None:
    # #167: a level sets only its hue (--bf-alert); its background and text mix it with the theme.
    css = re.sub(r"/\*.*?\*/", "", static_files()["static/report.css"], flags=re.S)
    for selector, body in _RULE.findall(css):
        if ".bf-alert" in selector:
            for declaration in body.split(";"):
                prop, _, value = declaration.partition(":")
                if prop.strip() in ("background", "background-color", "color"):
                    assert not _HEX.search(value), f"{selector.strip()}: {declaration.strip()}"
