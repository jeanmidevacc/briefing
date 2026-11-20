"""``to_spec``: what the JSON form of a report holds (#31)."""
from __future__ import annotations

import base64
import json
import typing as t
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from tests.banner_images import RED_SVG
from tests.scenarios import altair_chart, matplotlib_figure, plotly_figure


def _blocks(*blocks: t.Any, inline: bool = False) -> tuple[list[dict[str, t.Any]], dict[str, t.Any]]:
    spec, data = bf.to_spec(bf.Briefing(*blocks), inline=inline)
    return spec["blocks"], data


# ── options ───────────────────────────────────────────────────────────────────


def test_options_follow_the_signature_and_defaults_are_left_out() -> None:
    spec, data = bf.to_spec(bf.Briefing(bf.Group(bf.Text("a"), "b", columns=2, valign="center", name="g")))
    assert spec == {
        "briefing": 1,
        "blocks": [{
            "type": "Group", "columns": 2, "valign": "center", "name": "g",
            "blocks": [{"type": "Text", "text": "a"}, {"type": "Text", "text": "b"}],
        }],
    }
    assert data == {}


def test_the_reports_options_sit_at_the_top() -> None:
    spec, _ = bf.to_spec(bf.Briefing(bf.Text("a"), export=("embed", "png"), footer="Team"))
    assert list(spec) == ["briefing", "export", "footer", "blocks"]
    assert spec["export"] == ["embed", "png"] and spec["footer"] == "Team"


def test_a_block_or_a_list_of_blocks_is_a_report() -> None:
    assert bf.to_spec(bf.Text("a")) == bf.to_spec([bf.Text("a")]) == bf.to_spec(bf.Briefing(bf.Text("a")))


def test_a_selects_type_is_written_as_select_type() -> None:
    blocks, _ = _blocks(bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B"), type="dropdown"))
    assert blocks[0]["type"] == "Select" and blocks[0]["select_type"] == "dropdown"


def test_lab_blocks_are_named_with_their_prefix(df_constant: pd.DataFrame) -> None:
    blocks, _ = _blocks(bf.lab.DataProfile(df_constant), bf.lab.DataDive(df_constant, layout="tile"))
    assert [b["type"] for b in blocks] == ["lab.DataProfile", "lab.DataDive"]
    assert blocks[1]["layout"] == "tile"


def test_pages_keep_their_title_and_a_text_read_from_a_file_its_text(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text("# Notes\n\nFrom a file.\n", encoding="utf-8")
    blocks, _ = _blocks(bf.Page(bf.Text(file=notes), title="One", name="one"))
    assert blocks == [{"type": "Page", "title": "One", "name": "one",
                       "blocks": [{"type": "Text", "text": "# Notes\n\nFrom a file."}]}]


def test_numpy_numbers_become_json_numbers() -> None:
    np = pytest.importorskip("numpy")
    blocks, data = _blocks(bf.BigNumber("Users", np.int64(1200)), bf.BigNumber("Rate", np.float64(0.25)))
    assert [b["value"] for b in blocks] == [1200, 0.25] and data == {}
    assert type(blocks[0]["value"]) is int


def test_a_value_json_cant_hold_goes_by_reference() -> None:
    blocks, data = _blocks(bf.BigNumber("Ratio", float("nan")))
    assert blocks[0]["value"] == {"ref": "bignumber-1"}
    assert data["bignumber-1"] != data["bignumber-1"]  # NaN
    json.dumps(blocks, allow_nan=False)


def test_a_block_class_briefing_doesnt_define_has_no_json_form() -> None:
    class Note(bf.Text):
        pass

    with pytest.raises(bf.BriefingError, match="Note isn't one of briefing's blocks"):
        bf.to_spec(bf.Briefing(Note("a")))


# ── references ────────────────────────────────────────────────────────────────


def test_data_goes_by_reference_named_after_its_block(df_constant: pd.DataFrame, df_mixed: pd.DataFrame) -> None:
    figure = matplotlib_figure()
    blocks, data = _blocks(bf.DataTable(df_constant, name="rows"), bf.Plot(figure), bf.DataTable(df_mixed))
    assert [b.get("df", b.get("figure")) for b in blocks] == [
        {"ref": "rows"}, {"ref": "plot-1"}, {"ref": "datatable-2"},  # the second DataTable
    ]
    assert data["plot-1"] is figure
    assert data["rows"].equals(df_constant) and data["datatable-2"].equals(df_mixed)


def test_an_object_two_blocks_share_is_passed_once(df_constant: pd.DataFrame) -> None:
    blocks, data = _blocks(bf.Table(df_constant), bf.Table(df_constant))
    assert blocks[0]["data"] == blocks[1]["data"] == {"ref": "table-1"}
    assert list(data) == ["table-1"]


def test_a_blocks_second_reference_is_named_after_its_option(
    df_pipeline_log: pd.DataFrame, df_events: pd.DataFrame
) -> None:
    calendar = bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", events=df_events, name="runs")
    blocks, data = _blocks(calendar)
    assert blocks[0]["df"] == {"ref": "runs"} and blocks[0]["events"] == {"ref": "runs-events"}
    assert set(data) == {"runs", "runs-events"}


def test_two_names_alike_in_two_pages_get_two_references(df_constant: pd.DataFrame) -> None:
    _, data = _blocks(
        bf.Page(bf.DataTable(df_constant, name="rows"), title="A", name="a"),
        bf.Page(bf.DataTable(df_constant.head(1), name="rows"), title="B", name="b"),
    )
    assert list(data) == ["rows", "rows-2"]


# ── inline ────────────────────────────────────────────────────────────────────


def test_an_inline_table_has_its_columns_dtypes_and_rows() -> None:
    frame = pd.DataFrame({
        "n": [1, 2], "x": [0.5, float("inf")], "word": ["a", None], "ok": [True, False],
        "day": pd.to_datetime(pd.Series(["2026-01-01", None])),
    })
    blocks, data = _blocks(bf.DataTable(frame), inline=True)
    table = blocks[0]["df"]
    assert data == {}
    assert table["columns"] == ["n", "x", "word", "ok", "day"]
    assert table["dtypes"][:2] == ["int64", "float64"] and table["dtypes"][3] == "bool"
    assert table["rows"] == [[1, 0.5, "a", True, "2026-01-01T00:00:00"], [2, "Infinity", None, False, None]]


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"n": [1, 2]}, index=["a", "b"]),  # an index of its own
        pd.DataFrame({1: [1, 2]}),  # a column name that isn't text
        pd.DataFrame({"t": pd.to_timedelta([1, 2], unit="s")}),  # durations
        pd.DataFrame({"o": ["a", float("nan")]}, dtype=object),  # NaN in text: it would come back None
        pd.DataFrame({"c": pd.Categorical(["b"], categories=["b", "a"])}),  # an order JSON doesn't keep
    ],
    ids=["index", "int-column", "timedelta", "object-nan", "category-order"],
)
def test_a_table_that_wouldnt_come_back_the_same_stays_a_reference(frame: pd.DataFrame) -> None:
    blocks, data = _blocks(bf.Table(frame), inline=True)
    assert blocks[0]["data"] == {"ref": "table-1"} and data["table-1"] is frame


def test_a_styled_table_and_a_matplotlib_figure_stay_references(df_constant: pd.DataFrame) -> None:
    blocks, data = _blocks(bf.Table(df_constant.style.highlight_max()), bf.Plot(matplotlib_figure()), inline=True)
    assert [b.get("data", b.get("figure")) for b in blocks] == [{"ref": "table-1"}, {"ref": "plot-1"}]


def test_an_inline_plotly_figure_leaves_out_the_default_template() -> None:
    blocks, _ = _blocks(bf.Plot(plotly_figure()), inline=True)
    figure = blocks[0]["figure"]["plotly"]
    assert "template" not in figure.get("layout", {})
    assert figure["data"][0]["type"] == "scatter"


def test_an_inline_plotly_figure_names_another_registered_template() -> None:
    go = pytest.importorskip("plotly.graph_objects")
    figure = go.Figure(go.Bar(x=["a"], y=[1]), layout={"template": "plotly_white"})
    blocks, _ = _blocks(bf.Plot(figure), inline=True)
    assert blocks[0]["figure"]["plotly"]["layout"]["template"] == "plotly_white"


def test_an_inline_altair_chart_is_its_vega_lite() -> None:
    chart = altair_chart()
    blocks, _ = _blocks(bf.Plot(chart), inline=True)
    assert blocks[0]["figure"] == {"vega-lite": chart.to_dict()}


def test_an_inline_image_is_a_data_uri() -> None:
    blocks, _ = _blocks(bf.Banner("# Cover", image=RED_SVG), inline=True)
    assert blocks[0]["image"] == "data:image/svg+xml;base64," + base64.b64encode(RED_SVG).decode()
