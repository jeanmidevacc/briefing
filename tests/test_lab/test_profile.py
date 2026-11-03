"""Tests for DataProfile rendering (Phase 5)."""
from __future__ import annotations

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from briefing.blocks.layout import Briefing
from briefing.lab import DataProfile
from briefing.lab._render_profile import (
    _bar_chart_svg,
    _detect_kind,
    _histogram_svg,
    render_profile,
)
from briefing.renderers.html import render_report
from tests.html_helpers import find_one

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def numeric_df():
    return pd.DataFrame({"score": [1.0, 2.0, 3.0, 4.0, 5.0, None]})


@pytest.fixture()
def categorical_df():
    return pd.DataFrame({"color": ["red", "blue", "red", "green", "blue", "blue"]})


@pytest.fixture()
def datetime_df():
    return pd.DataFrame(
        {"ts": pd.date_range("2024-01-01", periods=5, freq="D")}
    )


@pytest.fixture()
def mixed_df():
    return pd.DataFrame(
        {
            "n": [1.0, 2.0, 3.0],
            "c": ["a", "b", "a"],
            "d": pd.date_range("2024-01-01", periods=3, freq="D"),
        }
    )


# ── _detect_kind ──────────────────────────────────────────────────────────────


class TestDetectKind:
    def test_integer_column(self):
        assert _detect_kind(pd.Series([1, 2, 3])) == "numeric"

    def test_float_column(self):
        assert _detect_kind(pd.Series([1.1, 2.2, 3.3])) == "numeric"

    def test_object_column(self):
        assert _detect_kind(pd.Series(["a", "b"])) == "categorical"

    def test_bool_column(self):
        assert _detect_kind(pd.Series([True, False, True])) == "categorical"

    def test_datetime_column(self):
        s = pd.Series(pd.date_range("2024-01-01", periods=3))
        assert _detect_kind(s) == "datetime"

    def test_category_dtype(self):
        s = pd.Series(["a", "b", "a"], dtype="category")
        assert _detect_kind(s) == "categorical"


# ── SVG generators ────────────────────────────────────────────────────────────


class TestHistogramSvg:
    def test_returns_svg_tag(self):
        s = pd.Series([1, 2, 3, 4, 5])
        svg = _histogram_svg(s)
        assert svg.startswith("<svg")
        assert "rect" in svg

    def test_empty_series_returns_empty_svg(self):
        svg = _histogram_svg(pd.Series([], dtype=float))
        assert "<svg" in svg
        assert "rect" not in svg

    def test_all_same_value_single_bar(self):
        svg = _histogram_svg(pd.Series([5.0, 5.0, 5.0]))
        assert "rect" in svg

    def test_nan_only_returns_svg(self):
        svg = _histogram_svg(pd.Series([float("nan"), float("nan")]))
        assert "<svg" in svg

    def test_no_external_resources(self):
        svg = _histogram_svg(pd.Series(range(100)))
        # xmlns URI is expected; no external src= links
        assert 'src="http' not in svg
        assert 'href="http' not in svg


class TestBarChartSvg:
    def test_returns_svg_tag(self):
        svg = _bar_chart_svg([("a", 5), ("b", 3)])
        assert svg.startswith("<svg")
        assert "rect" in svg

    def test_empty_list_returns_svg(self):
        svg = _bar_chart_svg([])
        assert "<svg" in svg

    def test_single_bar(self):
        svg = _bar_chart_svg([("only", 10)])
        assert "rect" in svg


# ── render_profile ────────────────────────────────────────────────────────────


class TestRenderProfile:
    def test_outer_div_class(self, numeric_df):
        html = render_profile(DataProfile(numeric_df))
        soup = BeautifulSoup(html, "html.parser")
        outer = soup.find("div", class_="bf-profile")
        assert outer is not None
        assert "bf-block" in outer["class"]

    def test_one_card_per_column(self, mixed_df):
        html = render_profile(DataProfile(mixed_df))
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", class_="bf-profile__card")
        assert len(cards) == 3  # n, c, d

    def test_column_name_shown(self, numeric_df):
        html = render_profile(DataProfile(numeric_df))
        assert "score" in html

    def test_dtype_badge_present(self, numeric_df):
        html = render_profile(DataProfile(numeric_df))
        soup = BeautifulSoup(html, "html.parser")
        badges = soup.find_all("span", class_="bf-profile__dtype")
        assert len(badges) == 1

    def test_numeric_stats_present(self, numeric_df):
        html = render_profile(DataProfile(numeric_df))
        assert "mean" in html
        assert "std" in html
        assert "median" in html

    def test_categorical_stats_present(self, categorical_df):
        html = render_profile(DataProfile(categorical_df))
        assert "unique" in html
        assert "top" in html

    def test_top_values_shown(self, categorical_df):
        html = render_profile(DataProfile(categorical_df))
        assert "blue" in html  # most frequent

    def test_datetime_stats_shown(self, datetime_df):
        html = render_profile(DataProfile(datetime_df))
        assert "min" in html
        assert "max" in html

    def test_missing_shown(self, numeric_df):
        html = render_profile(DataProfile(numeric_df))
        assert "missing" in html

    def test_high_missing_highlighted(self):
        df = pd.DataFrame({"x": [None] * 9 + [1.0]})  # 90% missing
        html = render_profile(DataProfile(df, missing_threshold=0.20))
        soup = BeautifulSoup(html, "html.parser")
        high = soup.find(class_="bf-profile__missing--high")
        assert high is not None

    def test_low_missing_not_highlighted(self, numeric_df):
        # numeric_df has 1/6 ≈ 16.7% missing, threshold=0.20 → no highlight
        html = render_profile(DataProfile(numeric_df, missing_threshold=0.20))
        soup = BeautifulSoup(html, "html.parser")
        high = soup.find(class_="bf-profile__missing--high")
        assert high is None

    def test_numeric_chart_svg_present(self, numeric_df):
        html = render_profile(DataProfile(numeric_df))
        soup = BeautifulSoup(html, "html.parser")
        svgs = soup.find_all("svg")
        assert len(svgs) >= 1

    def test_categorical_chart_svg_present(self, categorical_df):
        html = render_profile(DataProfile(categorical_df))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("svg") is not None

    def test_column_name_escaped(self):
        df = pd.DataFrame({'<script>alert(1)</script>': [1, 2]})
        html = render_profile(DataProfile(df))
        assert "<script>" not in html

    def test_max_categories_respected(self):
        vals = [str(i) for i in range(50)]
        df = pd.DataFrame({"c": vals})
        html = render_profile(DataProfile(df, max_categories=5))
        soup = BeautifulSoup(html, "html.parser")
        # only 5 values' bars should appear in SVG (SVG rect count = 5)
        card = find_one(soup, "div.bf-profile__card")
        rects = card.find_all("rect")
        assert len(rects) <= 5

    def test_no_external_resources(self, mixed_df):
        html = render_profile(DataProfile(mixed_df))
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(src=True):
            assert not str(tag.get("src", "")).startswith("http")


# ── integration — full render_report ─────────────────────────────────────────


class TestProfileInReport:
    def test_profile_in_report(self, mixed_df):
        html = render_report(Briefing(DataProfile(mixed_df)))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("div", class_="bf-profile") is not None

    def test_self_contained(self, numeric_df):
        html = render_report(Briefing(DataProfile(numeric_df)))
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(src=True):
            assert not str(tag.get("src", "")).startswith("http")
        for tag in soup.find_all("link", href=True):
            assert not str(tag.get("href", "")).startswith("http")

    def test_empty_df_renders(self):
        df = pd.DataFrame({"a": pd.Series([], dtype=float)})
        html = render_report(Briefing(DataProfile(df)))
        assert "bf-profile" in html
