"""Tests for DataDive rendering (Phase 6)."""
from __future__ import annotations

import json
import typing as t

import pandas as pd
import pytest
from bs4 import BeautifulSoup

import briefing as bf
from briefing.blocks.layout import Briefing
from briefing.lab import DataDive
from briefing.lab._render_datadive import MAX_TEXT, _col_kind, _pick_defaults, _serialise, render_datadive
from briefing.renderers.html import render_report
from briefing.renderers.pack import unpack
from tests.html_helpers import attr, classes, find_one

# ── fixtures ──────────────────────────────────────────────────────────────────


def _data(html: str) -> dict[str, t.Any]:
    """The columns a rendered DataDive carries: {"rows", "columns": [{"name", "kind", ...}]}."""
    script = find_one(BeautifulSoup(html, "html.parser"), "script.bf-dd__data")
    data: dict[str, t.Any] = json.loads(unpack(json.loads(script.get_text()), int(attr(script, "data-size"))))
    return data


def _column(html: str, name: str) -> dict[str, t.Any]:
    return next(c for c in _data(html)["columns"] if c["name"] == name)


def _cells(column: dict[str, t.Any]) -> list[t.Any]:
    """A column's values as the page reads them: a category's level, or the number (None when missing)."""
    if column["kind"] == "categorical":
        return [None if k < 0 else column["levels"][k] for k in column["codes"]]
    return list(column["values"])


@pytest.fixture()
def simple_df():
    return pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [4.0, 5.0, 6.0], "cat": ["a", "b", "c"]})


@pytest.fixture()
def numeric_only_df():
    return pd.DataFrame({"a": [1, 2, 3], "b": [10, 20, 30], "c": [100, 200, 300]})


# ── _col_kind ─────────────────────────────────────────────────────────────────


class TestColKind:
    def test_numeric(self):
        assert _col_kind(pd.Series([1.0, 2.0])) == "numeric"

    def test_bool_is_categorical(self):
        assert _col_kind(pd.Series([True, False])) == "categorical"

    def test_string_is_categorical(self):
        assert _col_kind(pd.Series(["a", "b"])) == "categorical"

    def test_datetime_is_datetime(self):
        assert _col_kind(pd.Series(pd.date_range("2024-01-01", periods=3))) == "datetime"


# ── _pick_defaults ────────────────────────────────────────────────────────────


class TestPickDefaults:
    def test_picks_first_two_numerics_as_x_y(self, numeric_only_df):
        x, y, _ = _pick_defaults(numeric_only_df, None, None, None)
        assert x == "a"
        assert y == "b"

    def test_explicit_hints_respected(self, numeric_only_df):
        x, y, _ = _pick_defaults(numeric_only_df, "c", "b", None)
        assert x == "c"
        assert y == "b"

    def test_color_defaults_to_categorical(self, simple_df):
        _, _, color = _pick_defaults(simple_df, None, None, None)
        assert color == "cat"


# ── render_datadive ───────────────────────────────────────────────────────────


class TestRenderDataDive:
    def test_returns_datadive_div(self, simple_df):
        html = render_datadive(DataDive(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("div", class_="bf-datadive") is not None

    def test_fl_block_class(self, simple_df):
        html = render_datadive(DataDive(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        assert "bf-block" in classes(find_one(soup, "div.bf-datadive"))

    def test_controls_present(self, simple_df):
        html = render_datadive(DataDive(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("div", class_="bf-dd__controls") is not None
        selects = soup.find_all("select", class_="bf-dd__sel")
        assert len(selects) >= 2  # at minimum X and Y

    def test_canvas_and_axes_present(self, simple_df):
        soup = BeautifulSoup(render_datadive(DataDive(simple_df)), "html.parser")
        assert attr(find_one(soup, "canvas.bf-dd__canvas"), "role") == "img"
        assert soup.find("svg", class_="bf-dd__axes") is not None
        assert soup.find("div", class_="bf-dd__legend") is not None

    def test_data_travels_by_column(self, simple_df):
        data = _data(render_datadive(DataDive(simple_df)))
        assert data["rows"] == 3
        assert [(c["name"], c["kind"]) for c in data["columns"]] == [
            ("x", "numeric"), ("y", "numeric"), ("cat", "categorical")]
        assert _cells(data["columns"][0]) == [1, 2, 3]
        assert data["columns"][2] == {"name": "cat", "kind": "categorical", "levels": ["a", "b", "c"],
                                      "codes": [0, 1, 2]}

    def test_all_columns_in_selects(self, simple_df):
        html = render_datadive(DataDive(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        x_select = find_one(soup, 'select[data-axis="x"]')
        opts = [o["value"] for o in x_select.find_all("option") if o.get("value")]
        for col in simple_df.columns:
            assert col in opts

    def test_default_x_selected(self, simple_df):
        html = render_datadive(DataDive(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        x_select = find_one(soup, 'select[data-axis="x"]')
        selected = x_select.find("option", selected=True)
        assert selected is not None

    def test_hint_x_pre_selected(self, simple_df):
        html = render_datadive(DataDive(simple_df, x="y"))
        soup = BeautifulSoup(html, "html.parser")
        selected = find_one(soup, 'select[data-axis="x"] option[selected]')
        assert attr(selected, "value") == "y"

    def test_row_count_in_footer(self, simple_df):
        html = render_datadive(DataDive(simple_df))
        assert "3" in html  # 3 rows

    def test_nan_serialised_as_null(self):
        df = pd.DataFrame({"a": [1.5, float("nan"), 3.0], "b": ["x", None, "y"]})
        html = render_datadive(DataDive(df))
        assert _cells(_column(html, "a")) == [1.5, None, 3]
        assert _cells(_column(html, "b")) == ["x", None, "y"]

    def test_datetime_serialised_as_epoch_milliseconds(self):
        stamps = [pd.Timestamp("2024-01-01"), pd.NaT, pd.Timestamp("2024-01-03 12:00")]
        df = pd.DataFrame({"ts": stamps, "v": [1, 2, 3]})
        column = _column(render_datadive(DataDive(df)), "ts")
        assert column["kind"] == "datetime"
        assert column["values"] == [1704067200000, None, 1704283200000]

    def test_time_zones_become_utc(self):
        ts = pd.Series(pd.to_datetime(["2024-01-01 09:00"]).tz_localize("America/Montreal"))
        column = _column(render_datadive(DataDive(pd.DataFrame({"ts": ts, "v": [1]}))), "ts")
        assert column["values"] == [int(pd.Timestamp("2024-01-01 14:00", tz="UTC").timestamp() * 1000)]

    def test_booleans_are_categories(self):
        column = _column(render_datadive(DataDive(pd.DataFrame({"ok": [True, False, True], "v": [1, 2, 3]}))), "ok")
        assert column["kind"] == "categorical" and _cells(column) == ["True", "False", "True"]

    def test_no_external_resources(self, simple_df):
        html = render_datadive(DataDive(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(src=True):
            assert not str(tag.get("src", "")).startswith("http")

    def test_column_names_escaped(self):
        df = pd.DataFrame({'<script>': [1, 2], 'y': [3, 4]})
        html = render_datadive(DataDive(df))
        # The raw <script> tag from column name should NOT appear as HTML
        # (it would be escaped in option text/values)
        soup = BeautifulSoup(html, "html.parser")
        scripts = [s for s in soup.find_all("script") if s.get("class") not in [["bf-dd__data"], ["bf-dd__scale"]]]
        # No extra injected script tags
        assert len(scripts) == 0

    def test_sampling_warns_on_large_df(self):
        big = pd.DataFrame({"a": range(200), "b": range(200)})
        with pytest.warns(UserWarning, match="sampling"):
            block = DataDive(big, max_rows=50)
        assert _data(render_datadive(block))["rows"] == 50

    def test_the_default_limit_is_100_000_rows(self):
        assert DataDive.MAX_ROWS == 100_000


# ── _serialise ────────────────────────────────────────────────────────────────


class TestSerialise:
    # None → pandas' default inference: object on pandas 2, str on pandas 3.
    @pytest.mark.parametrize("dtype", [None, object, "string"])
    def test_long_strings_are_cut(self, dtype):
        df = pd.DataFrame({"s": pd.Series(["x" * 300, "short", None], dtype=dtype), "v": [1.0, 2.0, 3.0]})
        columns = json.loads(_serialise(df))["columns"]
        assert _cells(columns[0]) == ["x" * (MAX_TEXT - 1) + "…", "short", None]
        assert _cells(columns[1]) == [1, 2, 3]

    def test_infinities_are_missing(self):
        df = pd.DataFrame({"v": [1.0, float("inf"), float("-inf")]})
        assert _cells(json.loads(_serialise(df))["columns"][0]) == [1, None, None]

    def test_nullable_integers(self):
        df = pd.DataFrame({"n": pd.array([1, None, 3], dtype="Int64")})
        assert _cells(json.loads(_serialise(df))["columns"][0]) == [1, None, 3]

    def test_the_data_is_deterministic(self, simple_df):
        assert render_datadive(DataDive(simple_df)) == render_datadive(DataDive(simple_df))


# ── colors=: a bf.Scale (#16) ─────────────────────────────────────────────────


class TestColors:
    def _scale(self, block: DataDive) -> dict[str, t.Any] | None:
        tag = BeautifulSoup(render_datadive(block), "html.parser").select_one("script.bf-dd__scale")
        return None if tag is None else json.loads(tag.get_text())

    def test_no_scale_by_default(self, simple_df):
        assert self._scale(DataDive(simple_df)) is None

    def test_a_categorical_scale_names_its_colours(self, simple_df):
        scale = bf.Scale(["#d71920", "#1a4782"], domain=["a", "b"])
        assert self._scale(DataDive(simple_df, colors=scale)) == {"categories": {"a": "#d71920", "b": "#1a4782"}}

    def test_a_numeric_scale_travels_as_a_ramp(self, simple_df):
        scale = bf.Scale(["#000000", "#ffffff"], domain=(0, 10))
        sent = self._scale(DataDive(simple_df, colors=scale))
        assert sent is not None
        assert len(sent["ramp"]) == 64 and sent["ramp"][0] == "#000000" and sent["ramp"][-1] == "#ffffff"
        assert sent["domain"] == [0, 10] and sent["center"] is None

    def test_steps_and_centre(self, simple_df):
        scale = bf.Scale(["#d73027", "#f7f7f7", "#1a9850"], center=0, steps=5)
        sent = self._scale(DataDive(simple_df, colors=scale))
        assert sent is not None
        assert len(sent["ramp"]) == 5 and sent["center"] == 0 and sent["domain"] is None

    def test_a_dict_is_read_as_a_scale(self, simple_df):
        block = DataDive(simple_df, colors={"colors": ["#000000", "#ffffff"]})
        assert isinstance(block.colors, bf.Scale)

    def test_anything_else_is_refused(self, simple_df):
        with pytest.raises(bf.BriefingError, match="colors must be a bf.Scale"):
            DataDive(simple_df, colors=["#000000", "#ffffff"])  # type: ignore[arg-type]

    def test_category_names_cant_end_the_script(self, simple_df):
        scale = bf.Scale(["#d71920", "#1a4782"], domain=["</script><img src=x>", "b"])
        soup = BeautifulSoup(render_datadive(DataDive(simple_df, colors=scale)), "html.parser")
        assert soup.find("img") is None and "<" not in find_one(soup, "script.bf-dd__scale").get_text()


# ── integration ───────────────────────────────────────────────────────────────


class TestDataDiveInReport:
    def test_datadive_in_report(self, simple_df):
        html = render_report(Briefing(DataDive(simple_df)))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("div", class_="bf-datadive") is not None

    def test_self_contained(self, simple_df):
        html = render_report(Briefing(DataDive(simple_df)))
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(src=True):
            assert not str(tag.get("src", "")).startswith("http")
        for tag in soup.find_all("link", href=True):
            assert not str(tag.get("href", "")).startswith("http")


# ── facets are not drawn yet (#6) ─────────────────────────────────────────────


class TestFacetParameters:
    @pytest.mark.parametrize("param", ["facet_row", "facet_col"])
    def test_passing_a_facet_warns_and_points_to_v2(self, simple_df, param):
        with pytest.warns(UserWarning, match=rf"{param}.*not drawn.*DataDive v2.*issues/16"):
            if param == "facet_row":
                DataDive(simple_df, facet_row="cat")
            else:
                DataDive(simple_df, facet_col="cat")

    def test_both_facets_warn_once(self, simple_df):
        with pytest.warns(UserWarning, match="facet_row and facet_col") as record:
            DataDive(simple_df, facet_row="cat", facet_col="cat")
        assert len([w for w in record if "facet" in str(w.message)]) == 1

    def test_no_warning_without_facets(self, simple_df):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            DataDive(simple_df)

    def test_unknown_facet_column_still_raises(self, simple_df):
        from briefing import BriefingError

        with pytest.raises(BriefingError, match="facet_row"):
            DataDive(simple_df, facet_row="nope")


# ── embedded JSON can't be closed by the data (#55) ───────────────────────────


class TestEmbeddedJsonIsSafe:
    HOSTILE = ["</script><img src=x onerror=alert(1)>", "<!--<script>", "a & b > c"]

    @pytest.mark.parametrize("text", HOSTILE)
    def test_column_names_round_trip(self, text):
        html = render_datadive(DataDive(pd.DataFrame({text: [1, 2], "y": [3, 4]})))
        assert _cells(_column(html, text)) == [1, 2]
        assert BeautifulSoup(html, "html.parser").find("img") is None

    @pytest.mark.parametrize("text", HOSTILE)
    def test_cell_values_round_trip(self, text):
        html = render_datadive(DataDive(pd.DataFrame({"label": [text, "plain"], "y": [3, 4]})))
        assert _cells(_column(html, "label")) == [text, "plain"]
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("img") is None
        assert len(soup.find_all("script")) == 1  # the data only

    def test_payloads_have_no_raw_angle_brackets(self):
        html = render_datadive(DataDive(pd.DataFrame({"</script>": ["<!--"], "y": [1]})))
        text = find_one(BeautifulSoup(html, "html.parser"), "script.bf-dd__data").get_text()
        assert "<" not in text and ">" not in text
