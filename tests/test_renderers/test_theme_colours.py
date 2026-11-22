"""Tables take their colours from the theme, so a dark theme's tables read (#150)."""
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
