"""Reports render the same <body> as 0.1.2: only shared CSS/JS and theme variables may grow."""
from __future__ import annotations

from pathlib import Path

import pytest

import briefing as bf
from tests.compat_reports import NOW, body_markup, reports

GOLDEN = Path(__file__).parent / "snapshots" / "compat_0_1_2"


@pytest.mark.parametrize("name", list(reports()))
def test_body_markup_matches_0_1_2(name: str) -> None:
    html = bf.stringify(reports()[name], name="Reference", now=NOW)
    assert body_markup(html) == (GOLDEN / f"{name}.body.html").read_text()
