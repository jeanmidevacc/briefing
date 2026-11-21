"""DataTable formats and links (#33): cells show formatted text or links, and sort by their raw value.

The browser side (sorting formatted columns, links in big tables) is in
``tests/test_browser/test_table_cells.py``.
"""
from __future__ import annotations

import json
import typing as t
import warnings

import pandas as pd
import pytest

import briefing as bf
from briefing.renderers.pack import unpack
from tests.html_helpers import attr, find_one, parse
from tests.scenarios import big_frame


def _papers() -> pd.DataFrame:
    return pd.DataFrame({
        "title": ["Graphs", "Ranking", "Bandits"],
        "url": ["https://example.org/a", "mailto:team@example.org", None],
        "doi": ["10.1000/a", None, "10.1000/c?x=1&y=\"2\""],
        "citations": [12345, 678, 9],
        "share": [0.1234, 0.5, None],
        "published": pd.to_datetime(pd.Series(["2024-01-05", "2023-11-30", None])),
    })


def _cells(block: bf.DataTable) -> list[list[t.Any]]:
    """Each cell of each row: its text, its sort key and the link it holds."""
    soup = parse(bf.stringify(block))
    rows = []
    for tr in soup.select(".bf-dt__table tbody tr"):
        row = []
        for td in tr.find_all("td"):
            a = td.find("a")
            row.append([td.get_text(), td.get("data-sort"), attr(a, "href") if a is not None else None])
        rows.append(row)
    return rows


def test_formats_change_the_text_and_keep_the_raw_value_for_sorting() -> None:
    cells = _cells(bf.DataTable(_papers()[["citations", "share", "published"]],
                                formats={"citations": "{:,}", "share": "{:.1%}", "published": "{:%d %b %Y}"}))
    assert cells[0] == [["12,345", "12345", None], ["12.3%", "0.1234", None],
                        ["05 Jan 2024", "2024-01-05T00:00:00", None]]
    assert cells[2][1:] == [["", None, None], ["", None, None]]  # missing values stay empty, and sort last


def test_a_format_can_be_a_function() -> None:
    cells = _cells(bf.DataTable(pd.DataFrame({"n": [1, 2]}), formats={"n": lambda v: f"#{v}"}))
    assert [row[0][:2] for row in cells] == [["#1", "1"], ["#2", "2"]]


def test_values_a_format_doesnt_fit_show_as_they_are_with_a_warning() -> None:
    frame = pd.DataFrame({"n": [1.5, "n/a", 2.0]}, dtype=object)
    with pytest.warns(UserWarning, match=r"the format '\{:\.1f\}' of column 'n' doesn't fit 1 of its values "
                                         r"\(such as 'n/a'\)"):
        cells = _cells(bf.DataTable(frame, formats={"n": "{:.1f}"}))
    assert [row[0][0] for row in cells] == ["1.5", "n/a", "2.0"]


def test_links_from_the_cell_or_another_column() -> None:
    cells = _cells(bf.DataTable(_papers()[["title", "url", "doi"]],
                                links={"doi": "https://doi.org/{}", "title": "{url}"}))
    assert [row[0] for row in cells] == [
        ["Graphs", None, "https://example.org/a"],
        ["Ranking", None, "mailto:team@example.org"],
        ["Bandits", None, None],  # no url: no link
    ]
    assert [row[2][2] for row in cells] == ["https://doi.org/10.1000/a", None, 'https://doi.org/10.1000/c?x=1&y="2"']


def test_a_link_opens_in_a_new_tab_and_its_url_is_escaped() -> None:
    html = bf.stringify(bf.DataTable(_papers()[["doi"]], links={"doi": "https://doi.org/{}"}))
    a = parse(html).select(".bf-dt__table a")[1]
    assert attr(a, "target") == "_blank" and attr(a, "rel") == "noopener noreferrer"
    assert 'href="https://doi.org/10.1000/c?x=1&amp;y=&quot;2&quot;"' in html


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "ftp://example.org", "/relative"])
def test_other_schemes_stay_text_with_a_warning(url: str) -> None:
    with pytest.warns(UserWarning, match=r"column 'u' links only to http\(s\):// and mailto: URLs"):
        cells = _cells(bf.DataTable(pd.DataFrame({"u": [url]}), links={"u": "{}"}))
    assert cells == [[[url, None, None]]]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"formats": {"nope": "{}"}}, r"formats names the column 'nope', which the table doesn't have\. "
                                     r"Its columns: title, url, doi, citations, share, published\."),
        ({"links": {"nope": "{}"}}, r"links names the column 'nope'"),
        ({"links": {"title": "{link}"}}, r"the link of 'title' names the column 'link'"),
        ({"formats": {"citations": "{:,"}}, r"isn't a valid template"),
        ({"formats": {"citations": "no field"}}, r"must be a format string with one \{\} for the value"),
        ({"formats": {"citations": "{name}"}}, r"must be a format string with one \{\} for the value"),
        ({"formats": {"citations": 3}}, r"must be a format string"),
        ({"links": {"title": 3}}, r"must be a URL template"),
        ({"formats": ["citations"]}, r"formats is a dict of columns"),
        ({"links": "doi"}, r"links is a dict of columns"),
    ],
)
def test_options_that_dont_fit_the_table_say_what_to_pass(kwargs: dict[str, t.Any], message: str) -> None:
    with pytest.raises(bf.BriefingError, match=message):
        bf.DataTable(_papers(), **kwargs)


def test_without_them_a_table_is_as_before() -> None:
    plain = bf.DataTable(_papers())
    assert plain.formats is None and plain.links is None
    assert parse(bf.stringify(plain)).select(".bf-dt__table a") == []


def test_a_big_table_packs_its_formatted_text_and_links() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        html = bf.stringify(bf.DataTable(big_frame(1_100), formats={"x": "{:.2f}"},
                                         links={"id": "https://example.org/rows/{}"}))
    data = find_one(parse(html), "script.bf-dt__data")
    rows = json.loads(unpack(json.loads(data.get_text()), int(attr(data, "data-size"))))
    x = float(big_frame(2)["x"][1])
    assert rows["text"][1][1] == f"{x:.2f}" and rows["keys"]["1"][1] == repr(x)
    assert rows["links"] == {"0": [f"https://example.org/rows/{i}" for i in range(1_100)]}
    first = parse(html).select(".bf-dt__table tbody tr")[0].find("a")
    assert first is not None and attr(first, "href") == "https://example.org/rows/0"


def test_both_have_a_json_form() -> None:
    table = bf.DataTable(pd.DataFrame({"n": [1]}), formats={"n": "{:,}"}, links={"n": "https://x.org/{}"})
    spec, data = bf.to_spec(table)
    assert spec["blocks"][0]["formats"] == {"n": "{:,}"} and spec["blocks"][0]["links"] == {"n": "https://x.org/{}"}
    assert bf.stringify(bf.from_spec(json.dumps(spec), data)) == bf.stringify(table)
    with_function, data = bf.to_spec(bf.DataTable(pd.DataFrame({"n": [1]}), formats={"n": str}))
    assert with_function["blocks"][0]["formats"] == {"ref": "datatable-1-formats"}  # a function goes by reference
    assert bf.validate({"briefing": 1, "blocks": [{"type": "DataTable", "df": {"columns": ["n"], "rows": [[1]]},
                                                   "formats": {"n": 3}}]})[0].message.startswith(
        'DataTable "formats" must be null or an object {"<column>": text}, not {"n": 3}.')
