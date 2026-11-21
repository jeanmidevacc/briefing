"""Big DataTables keep their first page in the HTML and their rows packed as JSON (#38).

The browser side (paging, sorting, search, print, no JavaScript) is in
``tests/test_browser/test_big_tables.py``.
"""
from __future__ import annotations

import json
import typing as t

import numpy as np
import pandas as pd
import pytest

import briefing as bf
from briefing.renderers.pack import pack, unpack
from tests.golden import static_files
from tests.html_helpers import attr, find_one, parse
from tests.scenarios import big_frame

UNPACK_JS = static_files()["static/unpack.js"]


def _rows(html: str) -> dict[str, t.Any]:
    data = find_one(parse(html), "script.bf-dt__data")
    rows: dict[str, t.Any] = json.loads(unpack(json.loads(data.get_text()), int(attr(data, "data-size"))))
    return rows


def test_up_to_html_rows_every_row_stays_in_the_html() -> None:
    html = bf.stringify(bf.DataTable(big_frame(bf.DataTable.HTML_ROWS)))
    soup = parse(html)
    assert len(soup.select(".bf-dt__table tbody tr")) == bf.DataTable.HTML_ROWS
    assert soup.select("script.bf-dt__data, noscript") == [] and UNPACK_JS not in html


def test_above_it_the_html_keeps_the_first_page_and_a_note() -> None:
    html = bf.stringify(bf.DataTable(big_frame(1_001)))
    soup = parse(html)
    assert len(soup.select(".bf-dt__table tbody tr")) == 25
    assert find_one(soup, "noscript").get_text() == "The first 25 of 1,001 rows: the others need JavaScript."
    assert html.count(UNPACK_JS) == 1


def test_the_packed_rows_are_each_cells_text_and_where_needed_its_sort_key() -> None:
    frame = big_frame(1_200)
    rows = _rows(bf.stringify(bf.DataTable(frame)))
    assert rows["rows"] == 1_200 and len(rows["text"]) == 4
    assert rows["text"][2][:2] == ["word 0", "word 1"]
    assert set(rows["keys"]) == {"1", "3"}  # x (decimals) and day (ISO keys); id and word sort by their text
    assert rows["keys"]["1"][1] == repr(float(frame["x"][1])) and rows["text"][1][1] == f"{frame['x'][1]:g}"
    assert rows["keys"]["3"][0] == "2025-01-01T00:00:00"


def test_its_first_page_is_the_first_rows_of_the_packed_ones() -> None:
    html = bf.stringify(bf.DataTable(big_frame(1_200)))
    first = [td.get_text() for td in parse(html).select(".bf-dt__table tbody tr:first-child td")]
    rows = _rows(html)
    assert first == [column[0] for column in rows["text"]]


def test_a_named_index_is_a_packed_column_too() -> None:
    frame = big_frame(1_100).set_index("id")
    rows = _rows(bf.stringify(bf.DataTable(frame)))
    assert len(rows["text"]) == 4 and rows["text"][0][:3] == ["0", "1", "2"]


def test_the_unpacker_ships_once_and_only_with_a_big_table() -> None:
    two = bf.stringify(bf.Briefing(bf.DataTable(big_frame(1_100)), bf.DataTable(big_frame(1_200))))
    assert two.count(UNPACK_JS) == 1
    fragment = bf.stringify(bf.DataTable(big_frame(1_100)), full_html=False)
    assert fragment.count(UNPACK_JS) == 1
    assert UNPACK_JS not in bf.stringify(bf.DataTable(big_frame(10)), full_html=False)


def test_packed_rows_are_the_same_bytes_every_time() -> None:
    assert bf.stringify(bf.DataTable(big_frame(1_100))) == bf.stringify(bf.DataTable(big_frame(1_100)))


def test_pack_round_trips() -> None:
    for text in ("", "x", "héllo ✓" * 1000):
        assert unpack(*pack(text)) == text
    with pytest.raises(ValueError, match="unpacked"):
        unpack(pack("abc")[0], 4)


@pytest.mark.parametrize(
    ("make", "budget"),
    [  # the sizes #38's spec promised, within 10 %
        (lambda rng: pd.DataFrame(rng.normal(size=(10_000, 10))), 1.8e6 * 1.1),
        (lambda rng: pd.DataFrame(rng.integers(0, 1000, size=(10_000, 10))), 0.3e6 * 1.1),
    ],
    ids=["decimals", "whole-numbers"],
)
def test_ten_thousand_rows_weigh_what_the_spec_said(make: t.Any, budget: float) -> None:
    html = bf.stringify(bf.DataTable(make(np.random.default_rng(0))))
    assert len(html.encode()) < budget
