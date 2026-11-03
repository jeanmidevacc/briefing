"""Tests for DataDive rendering (Phase 6)."""
from __future__ import annotations

import json

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from briefing.blocks.layout import Briefing
from briefing.lab import DataDive
from briefing.lab._render_datadive import _col_kind, _pick_defaults, _serialise, render_datadive
from briefing.renderers.html import render_report
from tests.html_helpers import attr, classes, find_one

# ── fixtures ──────────────────────────────────────────────────────────────────


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

    def test_svg_present(self, simple_df):
        html = render_datadive(DataDive(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("svg", class_="bf-dd__plot") is not None

    def test_data_json_embedded(self, simple_df):
        html = render_datadive(DataDive(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        records = json.loads(find_one(soup, "script.bf-dd__data").get_text())
        assert len(records) == 3

    def test_meta_json_embedded(self, simple_df):
        html = render_datadive(DataDive(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        meta = json.loads(find_one(soup, "script.bf-dd__meta").get_text())
        assert meta["x"] == "numeric"
        assert meta["cat"] == "categorical"

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
        df = pd.DataFrame({"a": [1.0, float("nan"), 3.0], "b": [4.0, 5.0, 6.0]})
        html = render_datadive(DataDive(df))
        soup = BeautifulSoup(html, "html.parser")
        records = json.loads(find_one(soup, "script.bf-dd__data").get_text())
        assert records[1]["a"] is None

    def test_datetime_serialised_as_string(self):
        df = pd.DataFrame({
            "ts": pd.date_range("2024-01-01", periods=3, freq="D"),
            "v": [1.0, 2.0, 3.0],
        })
        html = render_datadive(DataDive(df))
        soup = BeautifulSoup(html, "html.parser")
        records = json.loads(find_one(soup, "script.bf-dd__data").get_text())
        assert isinstance(records[0]["ts"], str)

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
        scripts = [s for s in soup.find_all("script") if s.get("class") not in [["bf-dd__data"], ["bf-dd__meta"]]]
        # No extra injected script tags
        assert len(scripts) == 0

    def test_sampling_warns_on_large_df(self):
        big = pd.DataFrame({"a": range(200), "b": range(200)})
        with pytest.warns(UserWarning, match="sampling"):
            block = DataDive(big, max_rows=50)
        html = render_datadive(block)
        soup = BeautifulSoup(html, "html.parser")
        records = json.loads(find_one(soup, "script.bf-dd__data").get_text())
        assert len(records) == 50


# ── _serialise ────────────────────────────────────────────────────────────────


class TestSerialise:
    # None → pandas' default inference: object on pandas 2, str on pandas 3.
    @pytest.mark.parametrize("dtype", [None, object, "string"])
    def test_long_strings_trimmed_to_64_chars(self, dtype):
        df = pd.DataFrame({"s": pd.Series(["x" * 100, "short", None], dtype=dtype), "v": [1.0, 2.0, 3.0]})
        records = json.loads(_serialise(df))
        assert records[0]["s"] == "x" * 64
        assert records[1]["s"] == "short"
        assert records[2]["s"] is None
        assert records[0]["v"] == 1.0


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
