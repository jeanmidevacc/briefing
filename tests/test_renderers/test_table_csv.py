"""DataTable's CSV button (#34), from Python's side; the download itself is in tests/test_browser/test_table_csv.py."""
from __future__ import annotations

import typing as t

import pandas as pd
import pytest

import briefing as bf
from tests.html_helpers import attr, find_one, parse

_DF = pd.DataFrame({"n": [1, 2]})


def test_without_download_a_table_has_no_button() -> None:
    assert parse(bf.stringify(bf.DataTable(_DF))).select(".bf-dt__csv, .bf-dt__csv-note") == []


@pytest.mark.parametrize(
    ("kwargs", "filename"),
    [({"name": "orders"}, "orders.csv"), ({"caption": "Orders, January–February"}, "orders-january-february.csv"),
     ({}, "table.csv"), ({"caption": "€€€"}, "table.csv")],
)
def test_the_button_names_the_file_after_the_table(kwargs: dict[str, t.Any], filename: str) -> None:
    soup = parse(bf.stringify(bf.DataTable(_DF, download=True, **kwargs)))
    button = find_one(soup, ".bf-dt__toolbar button.bf-dt__csv")
    assert button.get_text() == "CSV" and attr(button, "data-bf-filename") == filename
    assert attr(find_one(soup, ".bf-dt__csv-note"), "aria-live") == "polite"


def test_download_is_true_or_false() -> None:
    with pytest.raises(bf.BriefingError, match="download is True or False, not 'yes'"):
        bf.DataTable(_DF, download="yes")  # type: ignore[arg-type]


def test_it_has_a_json_form() -> None:
    spec, data = bf.to_spec(bf.DataTable(_DF, download=True))
    assert spec["blocks"][0]["download"] is True
    assert "download" not in bf.to_spec(bf.DataTable(_DF))[0]["blocks"][0]
