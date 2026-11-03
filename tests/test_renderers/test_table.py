"""Tests for Table and DataTable rendering (Phase 4)."""
from __future__ import annotations

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from briefing.blocks.asset import DataTable, Table
from briefing.blocks.layout import Briefing
from briefing.renderers.html import render_report
from briefing.renderers.table import render_datatable, render_table
from tests.html_helpers import attr, classes, find_one

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def simple_df():
    return pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


@pytest.fixture()
def named_index_df():
    df = pd.DataFrame({"val": [10, 20]}, index=pd.Index(["r1", "r2"], name="row"))
    return df


# ── Table (static) ────────────────────────────────────────────────────────────


class TestRenderTable:
    def test_returns_table_html(self, simple_df):
        html = render_table(Table(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("table") is not None

    def test_outer_div_classes(self, simple_df):
        html = render_table(Table(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        outer = classes(find_one(soup, "div"))
        assert "bf-block" in outer
        assert "bf-table" in outer

    def test_scroll_wrapper_present(self, simple_df):
        html = render_table(Table(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("div", class_="bf-table__scroll") is not None

    def test_column_headers(self, simple_df):
        html = render_table(Table(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        headers = [th.get_text(strip=True) for th in soup.find_all("th")]
        assert "a" in headers
        assert "b" in headers

    def test_row_data_present(self, simple_df):
        html = render_table(Table(simple_df))
        assert "x" in html
        assert "y" in html

    def test_caption_rendered(self, simple_df):
        html = render_table(Table(simple_df, caption="My Table"))
        soup = BeautifulSoup(html, "html.parser")
        cap = soup.find("div", class_="bf-table__caption")
        assert cap is not None
        assert "My Table" in cap.text

    def test_no_caption_when_empty(self, simple_df):
        html = render_table(Table(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("div", class_="bf-table__caption") is None

    def test_caption_escaped(self, simple_df):
        html = render_table(Table(simple_df, caption="<script>alert(1)</script>"))
        assert "<script>" not in html

    def test_accepts_styler(self, simple_df):
        styler = simple_df.style.highlight_max(color="yellow")
        html = render_table(Table(styler))
        assert "<table" in html

    def test_rangeindex_hidden_by_default(self, simple_df):
        # Default RangeIndex should not appear as a column
        html = render_table(Table(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        # The first header should be 'a' not '0'
        assert find_one(soup, "th").get_text(strip=True) == "a"

    def test_named_index_shown(self, named_index_df):
        html = render_table(Table(named_index_df))
        assert "row" in html


# ── DataTable (interactive) ───────────────────────────────────────────────────


class TestRenderDataTable:
    def test_returns_datatable_div(self, simple_df):
        html = render_datatable(DataTable(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        outer = soup.find("div", class_="bf-datatable")
        assert outer is not None

    def test_fl_block_class(self, simple_df):
        html = render_datatable(DataTable(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        assert "bf-block" in classes(find_one(soup, "div.bf-datatable"))

    def test_search_input_present(self, simple_df):
        html = render_datatable(DataTable(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("input", class_="bf-dt__search") is not None

    def test_pagination_buttons_present(self, simple_df):
        html = render_datatable(DataTable(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        btns = soup.find_all("button", class_="bf-dt__page-btn")
        assert len(btns) == 2

    def test_column_headers_with_data_col(self, simple_df):
        html = render_datatable(DataTable(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        ths = soup.find_all("th", class_="bf-dt__th")
        assert len(ths) == 2  # no named index → 2 columns
        cols = [int(attr(th, "data-col")) for th in ths]
        assert cols == [0, 1]

    def test_all_rows_rendered(self, simple_df):
        html = render_datatable(DataTable(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        rows = find_one(soup, "tbody").find_all("tr")
        assert len(rows) == 3

    def test_cell_data_present(self, simple_df):
        html = render_datatable(DataTable(simple_df))
        assert "x" in html
        assert "y" in html

    def test_caption_rendered(self, simple_df):
        html = render_datatable(DataTable(simple_df, caption="Interactive!"))
        soup = BeautifulSoup(html, "html.parser")
        cap = soup.find("div", class_="bf-dt__caption")
        assert cap is not None
        assert "Interactive!" in cap.text

    def test_no_caption_when_empty(self, simple_df):
        html = render_datatable(DataTable(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("div", class_="bf-dt__caption") is None

    def test_caption_escaped(self, simple_df):
        html = render_datatable(DataTable(simple_df, caption='<img src="x" onerror="alert(1)">'))
        # The tag must NOT appear as a real HTML element — it must be entity-encoded
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("img") is None  # not injected as a real tag

    def test_named_index_shown(self, named_index_df):
        html = render_datatable(DataTable(named_index_df))
        soup = BeautifulSoup(html, "html.parser")
        ths = soup.find_all("th", class_="bf-dt__th")
        assert len(ths) == 2  # index + 'val'
        assert ths[0].get_text(strip=True) == "row"

    def test_rangeindex_hidden(self, simple_df):
        html = render_datatable(DataTable(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        ths = soup.find_all("th", class_="bf-dt__th")
        labels = [th.get_text(strip=True) for th in ths]
        assert "a" in labels
        assert "b" in labels
        assert len(ths) == 2  # not 3 (no extra index col)

    def test_nan_rendered_as_empty(self):

        df = pd.DataFrame({"x": [1.0, float("nan"), 3.0]})
        html = render_datatable(DataTable(df))
        soup = BeautifulSoup(html, "html.parser")
        cells = find_one(soup, "tbody").find_all("td")
        texts = [c.get_text() for c in cells]
        assert "" in texts

    def test_float_integer_displayed_without_decimal(self):
        df = pd.DataFrame({"v": [1.0, 2.0, 3.0]})
        html = render_datatable(DataTable(df))
        assert "1.0" not in html
        assert ">1<" in html or ">1\n" in html or "td>1<" in html

    def test_row_truncation_at_max_rows(self):
        big = pd.DataFrame({"n": range(150)})
        with pytest.warns(UserWarning, match="truncating"):
            dt = DataTable(big, max_rows=100)
        html = render_datatable(dt)
        soup = BeautifulSoup(html, "html.parser")
        rows = find_one(soup, "tbody").find_all("tr")
        assert len(rows) == 100

    def test_sort_icon_span_present(self, simple_df):
        html = render_datatable(DataTable(simple_df))
        soup = BeautifulSoup(html, "html.parser")
        icons = soup.find_all("span", class_="bf-dt__sort-icon")
        assert len(icons) == 2

    def test_xss_in_cell_data(self):
        df = pd.DataFrame({"col": ['<script>alert("xss")</script>']})
        html = render_datatable(DataTable(df))
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ── integration — full render_report ─────────────────────────────────────────


class TestTableInReport:
    def test_datatable_in_report(self, simple_df):
        html = render_report(Briefing(DataTable(simple_df)))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("div", class_="bf-datatable") is not None

    def test_table_in_report(self, simple_df):
        html = render_report(Briefing(Table(simple_df)))
        soup = BeautifulSoup(html, "html.parser")
        assert soup.find("div", class_="bf-table") is not None

    def test_no_external_resources(self, simple_df):
        html = render_report(Briefing(DataTable(simple_df)))
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(src=True):
            assert not str(tag.get("src", "")).startswith("http")
        for tag in soup.find_all("link", href=True):
            assert not str(tag.get("href", "")).startswith("http")
