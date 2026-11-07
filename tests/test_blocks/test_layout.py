"""Tests for layout blocks: Group, Select, Toggle, Page, Briefing."""
from __future__ import annotations

import typing as t
import warnings

import numpy as np
import pytest

from briefing._error import BriefingError
from briefing.blocks.layout import Briefing, Group, Page, Select, SelectType, Toggle, VAlign
from briefing.blocks.text import Text

# ── helpers ───────────────────────────────────────────────────────────────────


def make_texts(n: int) -> list[Text]:
    return [Text(f"Block {i}", label=f"Tab {i}") for i in range(n)]


# ── Group ─────────────────────────────────────────────────────────────────────


class TestBriefingFooter:
    def test_defaults_to_no_prefix(self):
        assert Briefing(Text("a")).footer is None

    @pytest.mark.parametrize("footer", [1, True, ["team"]])
    def test_must_be_text(self, footer):
        with pytest.raises(BriefingError, match="'footer' must be text"):
            Briefing(Text("a"), footer=footer)

    def test_long_text_is_shortened_like_a_caption(self):
        assert len(t.cast(str, Briefing(Text("a"), footer="x" * 600).footer)) == 512

    def test_wrapping_a_briefing_keeps_its_footer(self):
        assert Briefing(Briefing(Text("a"), footer="Team")).footer == "Team"

    def test_an_explicit_footer_replaces_the_wrapped_one(self):
        assert Briefing(Briefing(Text("a"), footer="Team"), footer="Other").footer == "Other"


class TestGroup:
    def test_single_column_default(self):
        g = Group(*make_texts(2))
        assert g.columns == 1

    def test_multi_column(self):
        g = Group(*make_texts(3), columns=3)
        assert g.columns == 3
        assert len(g) == 3

    def test_blocks_kwarg(self):
        items = make_texts(2)
        g = Group(blocks=items, columns=2)
        assert len(g) == 2

    @pytest.mark.parametrize("columns", [0, -1, 1.5, 2.0, True, "2", None])
    def test_columns_must_be_a_whole_number_of_one_or_more(self, columns):
        with pytest.raises(BriefingError, match="'columns' must be a whole number of 1 or more"):
            Group(*make_texts(2), columns=columns)

    @pytest.mark.parametrize("width", [0, -1, float("nan"), float("inf"), True, "1", None])
    def test_widths_must_be_positive_numbers(self, width):
        with pytest.raises(BriefingError, match="'widths' must be positive numbers"):
            Group(*make_texts(2), columns=2, widths=[1, width])

    @pytest.mark.parametrize(("columns", "widths"), [(np.int64(2), [np.int64(2), np.float64(1.5)])])
    def test_numpy_numbers_work_like_python_ones(self, columns, widths):
        g = Group(*make_texts(2), columns=columns, widths=widths)
        assert g.columns == 2
        assert type(g.columns) is int

    def test_widths_correct_length(self):
        g = Group(*make_texts(2), columns=2, widths=[2, 1])
        assert g.widths == [2, 1]

    def test_widths_wrong_length_raises(self):
        with pytest.raises(BriefingError, match="widths"):
            Group(*make_texts(2), columns=2, widths=[1, 2, 3])

    def test_valign_default(self):
        g = Group(*make_texts(2))
        assert g.valign == VAlign.TOP

    def test_valign_set(self):
        g = Group(*make_texts(2), valign=VAlign.CENTER)
        assert g.valign == VAlign.CENTER

    def test_valign_string_coerced(self):
        g = Group(*make_texts(2), valign="bottom")
        assert g.valign == VAlign.BOTTOM

    def test_empty_group_allowed(self):
        g = Group()
        assert len(g) == 0

    def test_string_auto_wrapped(self):
        g = Group("# Title", Text("body"), columns=2)
        assert len(g) == 2
        # The string should be wrapped into a Text block
        from briefing.blocks.text import Text as T
        assert isinstance(g.blocks[0], T)

    def test_name_and_label(self):
        g = Group(*make_texts(2), name="grid-1", label="Grid")
        assert g.name == "grid-1"
        assert g.label == "Grid"


# ── Select ────────────────────────────────────────────────────────────────────


class TestSelect:
    def test_default_type_is_tabs(self):
        s = Select(*make_texts(2))
        assert s.type == SelectType.TABS

    def test_dropdown_type(self):
        s = Select(*make_texts(2), type=SelectType.DROPDOWN)
        assert s.type == SelectType.DROPDOWN

    def test_string_type_coerced(self):
        s = Select(*make_texts(2), type="dropdown")
        assert s.type == SelectType.DROPDOWN

    def test_fewer_than_2_blocks_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            Select(Text("only one"))
        assert any("at least 2" in str(w.message) for w in caught)

    def test_exactly_2_blocks_no_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            Select(*make_texts(2))
        assert not any("at least 2" in str(w.message) for w in caught)

    def test_many_blocks_accepted(self):
        s = Select(*make_texts(5))
        assert len(s) == 5

    def test_blocks_kwarg(self):
        items = make_texts(3)
        s = Select(blocks=items)
        assert len(s) == 3


# ── Toggle ────────────────────────────────────────────────────────────────────


class TestToggle:
    def test_single_block(self):
        t = Toggle(Text("content"), label="Show details")
        assert len(t) == 1
        assert t.label == "Show details"

    def test_multiple_blocks_wrapped_in_group(self):
        t = Toggle(*make_texts(3))
        # Multiple blocks should be wrapped into a single Group.
        assert len(t) == 1
        assert isinstance(t.blocks[0], Group)

    def test_single_block_not_wrapped(self):
        inner = Text("only one")
        t = Toggle(inner)
        assert t.blocks[0] is inner

    def test_name_stored(self):
        t = Toggle(Text("x"), name="toggle-1")
        assert t.name == "toggle-1"


# ── Page ──────────────────────────────────────────────────────────────────────


class TestPage:
    def test_title_stored_as_label(self):
        p = Page(Text("content"), title="Overview")
        assert p.title == "Overview"
        assert p.label == "Overview"

    def test_no_title_is_none(self):
        p = Page(Text("content"))
        assert p.title is None
        assert p.label is None

    def test_nested_page_raises(self):
        with pytest.raises(BriefingError, match="Nested Page"):
            Page(Page(Text("inner")))

    def test_blocks_kwarg(self):
        items = make_texts(2)
        p = Page(blocks=items, title="My Page")
        assert len(p) == 2

    def test_name_stored(self):
        p = Page(Text("x"), name="page-1")
        assert p.name == "page-1"


# ── Briefing ────────────────────────────────────────────────────────────────────


class TestBlocks:
    def test_basic(self):
        b = Briefing(*make_texts(3))
        assert len(b) == 3

    def test_single_blocks_unwrapped(self):
        inner = Briefing(Text("a"), Text("b"))
        outer = Briefing(inner)
        # Passing a single Briefing into Briefing should flatten it.
        assert len(outer) == 2

    def test_string_auto_wrapped(self):
        b = Briefing("# Hello", Text("world"))
        assert len(b) == 2

    def test_wrap_from_blocks_instance(self):
        original = Briefing(*make_texts(2))
        wrapped = Briefing.wrap(original)
        assert wrapped is original

    def test_wrap_from_list(self):
        items = make_texts(3)
        wrapped = Briefing.wrap(items)
        assert isinstance(wrapped, Briefing)
        assert len(wrapped) == 3

    def test_wrap_from_single_block(self):
        t = Text("only")
        wrapped = Briefing.wrap(t)
        assert isinstance(wrapped, Briefing)
        assert len(wrapped) == 1

    def test_blocks_kwarg(self):
        items = make_texts(2)
        b = Briefing(blocks=items)
        assert len(b) == 2

    def test_iteration(self):
        items = make_texts(3)
        b = Briefing(*items)
        assert list(b) == items
