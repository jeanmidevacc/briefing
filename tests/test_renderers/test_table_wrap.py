"""DataTable(wrap=…): long text wraps instead of widening the table (#151)."""
from __future__ import annotations

import json
import typing as t

import pandas as pd
import pytest

import briefing as bf
from briefing.renderers.pack import unpack
from tests.html_helpers import attr, find_one, parse
from tests.scenarios import big_frame

_NOTES = pd.DataFrame({"term": ["a", "b"], "note": ["a long note " * 20, "short"]})


def _wrapped(block: bf.DataTable) -> list[bool]:
    cells = parse(bf.stringify(block)).select(".bf-dt__table tbody tr:first-child td")
    return ["bf-dt__wrap" in (cell.get("class") or []) for cell in cells]


def test_listed_columns_wrap_and_others_dont() -> None:
    assert _wrapped(bf.DataTable(_NOTES, wrap=["note"])) == [False, True]
    assert _wrapped(bf.DataTable(_NOTES, wrap=True)) == [True, True]
    assert _wrapped(bf.DataTable(_NOTES)) == [False, False]


def test_an_index_column_never_wraps() -> None:
    assert _wrapped(bf.DataTable(_NOTES.set_index("term"), wrap=True)) == [False, True]


@pytest.mark.parametrize(("wrap", "message"), [(["nope"], "wrap names the column 'nope'"),
                                               ("note", "wrap is True, False or a list"), ([1], "wrap is True")])
def test_a_wrong_wrap_says_what_to_pass(wrap: t.Any, message: str) -> None:
    with pytest.raises(bf.BriefingError, match=message):
        bf.DataTable(_NOTES, wrap=wrap)


def test_a_big_table_packs_which_columns_wrap() -> None:
    html = bf.stringify(bf.DataTable(big_frame(1_100), wrap=["word"]))
    data = find_one(parse(html), "script.bf-dt__data")
    rows = json.loads(unpack(json.loads(data.get_text()), int(attr(data, "data-size"))))
    assert rows["wrap"] == [2]


def test_it_has_a_json_form() -> None:
    spec, data = bf.to_spec(bf.DataTable(_NOTES, wrap=["note"]))
    assert spec["blocks"][0]["wrap"] == ["note"]
    assert bf.stringify(bf.from_spec(json.dumps(spec), data)) == bf.stringify(bf.DataTable(_NOTES, wrap=["note"]))
