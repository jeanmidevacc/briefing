"""The briefing.lab boundary: registration + on-demand asset injection."""
from __future__ import annotations

import datetime

import pandas as pd
import pytest

import briefing as bf
from briefing.renderers.registry import asset_js_for, lookup_renderer

_NOW = datetime.datetime(2020, 1, 1)
_LAB_JS_MARKER = "briefing.lab — DataDive interactive dot explorer"


@pytest.fixture()
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {"a": [1, 2, 3, 4], "b": [4.0, 3.0, 2.0, 1.0], "g": ["x", "y", "x", "y"]}
    )


def test_lab_blocks_have_registered_renderers(df: pd.DataFrame) -> None:
    assert lookup_renderer(bf.lab.DataProfile(df)) is not None
    assert lookup_renderer(bf.lab.DataDive(df)) is not None


def test_only_datadive_carries_a_js_asset(df: pd.DataFrame) -> None:
    assert asset_js_for(bf.lab.DataDive(df)) is not None
    assert asset_js_for(bf.lab.DataProfile(df)) is None
    assert asset_js_for(bf.Text("# plain")) is None


def test_core_report_does_not_inline_the_lab_engine(df: pd.DataFrame) -> None:
    html = bf.stringify(bf.Briefing(bf.Text("# hi"), bf.Table(df)), now=_NOW)
    assert _LAB_JS_MARKER not in html


def test_profile_only_report_does_not_inline_the_lab_engine(df: pd.DataFrame) -> None:
    html = bf.stringify(bf.Briefing(bf.lab.DataProfile(df)), now=_NOW)
    assert _LAB_JS_MARKER not in html


def test_datadive_report_inlines_the_lab_engine_exactly_once(df: pd.DataFrame) -> None:
    html = bf.stringify(
        bf.Briefing(bf.lab.DataDive(df, x="a", y="b"), bf.lab.DataDive(df, x="a", y="b")),
        now=_NOW,
    )
    assert html.count(_LAB_JS_MARKER) == 1


def test_datadive_nested_in_a_container_still_triggers_injection(df: pd.DataFrame) -> None:
    html = bf.stringify(
        bf.Briefing(bf.Group(bf.Text("# g"), bf.lab.DataDive(df, x="a", y="b"))),
        now=_NOW,
    )
    assert _LAB_JS_MARKER in html


def test_output_is_still_byte_reproducible_with_lab_blocks(df: pd.DataFrame) -> None:
    report = bf.Briefing(bf.lab.DataProfile(df), bf.lab.DataDive(df, x="a", y="b"))
    assert bf.stringify(report, now=_NOW) == bf.stringify(report, now=_NOW)


# ── a lab block's own stylesheet (#17): DataCompare's ships only with a DataCompare ──

_COMPARE_CSS_MARKER = "briefing lab: DataCompare (#17). Inlined only"


def _compare(df: pd.DataFrame) -> bf.lab.DataCompare:
    return bf.lab.DataCompare({"a": df, "b": df})


def test_a_report_without_a_comparison_carries_none_of_its_css(df: pd.DataFrame) -> None:
    html = bf.stringify(bf.Briefing(bf.lab.DataProfile(df), bf.lab.DataDive(df)), now=_NOW)
    assert _COMPARE_CSS_MARKER not in html and ".bf-cmp__row" not in html


def test_a_comparison_brings_its_css_once_after_report_css(df: pd.DataFrame) -> None:
    html = bf.stringify(bf.Briefing(bf.Group(_compare(df)), _compare(df)), now=_NOW)
    assert html.count(_COMPARE_CSS_MARKER) == 1
    assert html.index(".bf-report {") < html.index(_COMPARE_CSS_MARKER)  # so it can build on report.css


def test_fragments_and_their_assets_scope_the_comparisons_css(df: pd.DataFrame) -> None:
    fragment = bf.stringify(bf.Briefing(_compare(df)), full_html=False, now=_NOW)
    assert ".bf-embed .bf-cmp__row" in fragment
    assert ".bf-cmp__row" not in bf.stringify(bf.Briefing(bf.Text("x")), full_html=False, now=_NOW)
    assets = bf.embed_assets([bf.Text("x"), _compare(df)])
    assert ".bf-embed .bf-cmp__row" in assets


def test_a_copy_embed_copy_carries_the_comparisons_css(df: pd.DataFrame) -> None:
    import base64
    import gzip
    import json

    from tests.html_helpers import find_one, parse

    html = bf.stringify(bf.Briefing(_compare(df), export="embed"), now=_NOW)
    script = find_one(parse(html), "script.bf-copy-data")
    data = json.loads(gzip.decompress(base64.b64decode(json.loads(script.get_text()))))
    assert ".bf-embed .bf-cmp__row" in data["css"]


def test_a_deck_with_a_comparison_carries_its_css(df: pd.DataFrame) -> None:
    deck = bf.deck.Deck(bf.deck.Slide(_compare(df), title="Drift"))
    assert _COMPARE_CSS_MARKER in bf.deck.to_html(deck)
    assert _COMPARE_CSS_MARKER not in bf.deck.to_html(bf.deck.Deck(bf.deck.Slide("x", title="T")))
