"""``from_spec``: a report from JSON written by hand, or by an agent (#31)."""
from __future__ import annotations

import base64
import json
import typing as t
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from tests.banner_images import RED_SVG
from tests.contract import RULES, parse_report

#: The example of issue #31: pages, a group, a chart and two tables, one of them by reference.
EXAMPLE: dict[str, t.Any] = {
    "briefing": 1,
    "footer": "Analytics team",
    "export": ["png"],
    "blocks": [
        {"type": "Page", "title": "Summary", "name": "summary", "blocks": [
            {"type": "Text", "text": "# Q1\n\nRevenue grew."},
            {"type": "Group", "columns": 2, "blocks": [
                {"type": "BigNumber", "heading": "Revenue", "value": "$4.2M", "change": "+12%",
                 "is_upward_change": True},
                {"type": "Alert", "message": "Margins are a week late.", "level": "warning"},
            ]},
            {"type": "Plot", "figure": {"ref": "trend"}, "caption": "Weekly revenue"},
        ]},
        {"type": "Page", "title": "Detail", "name": "detail", "blocks": [
            {"type": "DataTable", "df": {"ref": "sales"}},
            {"type": "lab.DataProfile", "df": {"columns": ["n"], "dtypes": ["int64"], "rows": [[1], [2]]}},
        ]},
    ],
}


def _data() -> dict[str, t.Any]:
    from tests.scenarios import matplotlib_figure

    return {"trend": matplotlib_figure(), "sales": pd.DataFrame({"region": ["North", "South"], "sales": [3, 4]})}


def _one(block: dict[str, t.Any], data: dict[str, t.Any] | None = None) -> t.Any:
    return bf.from_spec({"briefing": 1, "blocks": [block]}, data).blocks[0]


def test_the_issues_example_renders_like_its_python() -> None:
    data = _data()
    report = bf.from_spec(EXAMPLE, data)
    python = bf.Briefing(
        bf.Page(
            bf.Text("# Q1\n\nRevenue grew."),
            bf.Group(bf.BigNumber("Revenue", "$4.2M", change="+12%", is_upward_change=True),
                     bf.Alert("Margins are a week late.", level="warning"), columns=2),
            bf.Plot(data["trend"], caption="Weekly revenue"),
            title="Summary", name="summary",
        ),
        bf.Page(bf.DataTable(data["sales"]), bf.lab.DataProfile(pd.DataFrame({"n": [1, 2]})), title="Detail",
                name="detail"),
        export="png", footer="Analytics team",
    )
    html = bf.stringify(report, now=_now())
    assert html == bf.stringify(python, now=_now())
    soup = parse_report(html)
    for rule in RULES.values():
        rule(soup)


def _now() -> t.Any:
    from tests.golden import NOW

    return NOW


def test_it_reads_a_dict_json_text_or_a_file(tmp_path: Path) -> None:
    spec = {"briefing": 1, "blocks": [{"type": "Text", "text": "# Hi"}]}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    reports = [bf.from_spec(spec), bf.from_spec(json.dumps(spec)), bf.from_spec(path), bf.from_spec(str(path))]
    assert {bf.stringify(r, now=_now()) for r in reports} == {bf.stringify(bf.Text("# Hi"), now=_now())}


def test_a_select_takes_its_type_as_select_type() -> None:
    select = _one({"type": "Select", "select_type": "dropdown", "blocks": [
        {"type": "Text", "text": "a", "label": "A"}, {"type": "Text", "text": "b", "label": "B"}]})
    assert select.type == bf.SelectType.DROPDOWN


# ── tables ────────────────────────────────────────────────────────────────────


def test_a_table_without_dtypes_lets_pandas_infer_them() -> None:
    table = _one({"type": "DataTable", "df": {"columns": ["n", "x", "w"], "rows": [[1, 0.5, "a"], [2, None, "b"]]}})
    assert [str(d) for d in table.df.dtypes[:2]] == ["int64", "float64"]
    assert table.df["x"].isna().tolist() == [False, True]


def test_a_tables_dtypes_read_dates_infinities_and_missing_values() -> None:
    table = _one({"type": "Table", "data": {
        "columns": ["day", "x", "n"], "dtypes": ["datetime64[ns]", "float64", "Int64"],
        "rows": [["2026-01-01T00:00:00", "Infinity", 1], [None, None, None]],
    }})
    frame = table.data
    assert frame["day"].iloc[0] == pd.Timestamp("2026-01-01") and frame["day"].isna().iloc[1]
    assert frame["x"].iloc[0] == float("inf") and frame["n"].isna().iloc[1]
    assert str(frame["n"].dtype) == "Int64"


def test_an_empty_table_keeps_its_columns() -> None:
    table = _one({"type": "DataTable", "df": {"columns": ["a", "b"], "rows": []}})
    assert list(table.df.columns) == ["a", "b"] and len(table.df) == 0


# ── charts and images ─────────────────────────────────────────────────────────


def test_a_plotly_figure_written_by_hand() -> None:
    pytest.importorskip("plotly")
    plot = _one({"type": "Plot", "figure": {"plotly": {"data": [{"type": "bar", "x": ["a", "b"], "y": [1, 2]}],
                                                        "layout": {"title": {"text": "Sales"}}}}})
    assert type(plot.figure).__module__.startswith("plotly")
    assert plot.figure.layout.title.text == "Sales"
    assert 'class="plotly-graph-div"' in bf.stringify(bf.Briefing(plot))


def test_a_vega_lite_chart_written_by_hand() -> None:
    pytest.importorskip("altair")
    plot = _one({"type": "Plot", "figure": {"vega-lite": {
        "data": {"values": [{"x": 1, "y": 2}, {"x": 2, "y": 1}]},
        "mark": "line",
        "encoding": {"x": {"field": "x", "type": "quantitative"}, "y": {"field": "y", "type": "quantitative"}},
    }}})
    assert type(plot.figure).__module__.startswith("altair")
    assert 'class="bf-altair"' in bf.stringify(bf.Briefing(plot))


def test_an_unreadable_vega_lite_chart_says_why() -> None:
    pytest.importorskip("altair")
    with pytest.raises(bf.BriefingError, match="Altair can't read this Vega-Lite"):
        _one({"type": "Plot", "figure": {"vega-lite": {"mark": "no-such-mark"}}})


def test_a_banner_image_from_a_data_uri_or_a_path(tmp_path: Path) -> None:
    path = tmp_path / "cover.svg"
    path.write_bytes(RED_SVG)
    uri = "data:image/svg+xml;base64," + base64.b64encode(RED_SVG).decode()
    for image in (uri, str(path), "data:image/svg+xml," + RED_SVG.decode().replace("#", "%23")):
        assert _one({"type": "Banner", "text": "# Cover", "image": image}).image == RED_SVG


def test_calendar_events_as_date_strings(df_pipeline_log: pd.DataFrame) -> None:
    calendar = _one({"type": "lab.CalendarHeatmap", "df": {"ref": "log"}, "date": "run_at",
                     "events": ["2025-12-25", "2026-01-01"]}, {"log": df_pipeline_log})
    assert calendar.events["start"].dt.strftime("%m-%d").tolist() == ["12-25", "01-01"]


# ── problems ──────────────────────────────────────────────────────────────────


def test_it_raises_every_problem_with_its_place() -> None:
    spec = {"briefing": 1, "blocks": [
        {"type": "Group", "colums": 2, "blocks": [{"type": "Txt", "text": "a"}]},
        {"type": "DataTable", "df": {"ref": "sales"}},
    ]}
    with pytest.raises(bf.BriefingError) as caught:
        bf.from_spec(spec)
    message = str(caught.value)
    assert 'at /blocks/0/colums: Group has no option "colums". Did you mean "columns"?' in message
    assert "at /blocks/0/blocks/0/type: There is no block type \"Txt\"" in message
    assert "at /blocks/1/df: No object named 'sales' was passed in data." in message
    assert "bf.validate(spec, data) lists every problem." in message


def test_a_constructors_own_check_is_raised_with_the_blocks_place() -> None:
    with pytest.raises(bf.BriefingError, match=r"at /blocks/0: Group 'widths' length \(1\) must match"):
        _one({"type": "Group", "columns": 2, "widths": [1], "blocks": [{"type": "Text", "text": "a"}]})


def test_a_newer_format_says_to_upgrade() -> None:
    with pytest.raises(bf.BriefingError, match="This JSON is in format 2; briefing .* reads format 1.*pip install -U"):
        bf.from_spec({"briefing": 2, "blocks": [{"type": "Hologram"}]})


def test_a_block_still_warns_as_in_python() -> None:
    with pytest.warns(UserWarning, match="truncating to 1"):
        _one({"type": "DataTable", "df": {"columns": ["n"], "rows": [[1], [2]]}, "max_rows": 1})


def test_data_must_be_a_dict() -> None:
    with pytest.raises(bf.BriefingError, match="data must be a dict"):
        bf.from_spec(EXAMPLE, data=[1, 2])  # type: ignore[arg-type]
