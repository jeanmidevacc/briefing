"""Linked selection (#21): selects= on DataProfile and DataCompare, resolved and checked like a link."""
from __future__ import annotations

import json
import typing as t

import pandas as pd
import pytest

import briefing as bf
from tests.golden import static_files
from tests.html_helpers import attr, find_one, parse

_DF = pd.DataFrame({"n": [1.0, 2.0, 3.0, 4.0], "team": ["a", "b", "a", "c"], "day": pd.to_datetime(["2026-01-01"] * 4)})
_SELECT_JS = static_files()["lab/static/select.js"]
_SELECT_CSS = static_files()["lab/static/select.css"]


def _dive(**kwargs: t.Any) -> bf.lab.DataDive:
    return bf.lab.DataDive(_DF, name="dive", **kwargs)


def _html(*blocks: t.Any) -> str:
    return bf.stringify(bf.Briefing(*blocks))


# ── checks ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("selects", ["", "1dive", ["ok", 3], [], {"dive": 1}])
def test_selects_takes_names(selects: object) -> None:
    with pytest.raises(bf.BriefingError, match="'selects'"):
        bf.lab.DataProfile(_DF, selects=selects)  # type: ignore[arg-type]
    with pytest.raises(bf.BriefingError, match="'selects'"):
        bf.lab.DataCompare([_DF, _DF], selects=selects)  # type: ignore[arg-type]


def test_a_missing_target_lists_the_dives_of_its_page() -> None:
    report = bf.Briefing(
        bf.Page(bf.lab.DataProfile(_DF, selects="dive"), bf.lab.DataDive(_DF, name="other"), title="A", name="a"),
        bf.Page(_dive(), title="B", name="b"),  # another page: not reachable
    )
    message = "no block named 'dive' in page 'a'. The DataDive or DataTable blocks there: 'other'"
    with pytest.raises(bf.BriefingError, match=message):
        bf.stringify(report)


def test_a_target_must_be_a_datadive_or_a_datatable() -> None:
    with pytest.raises(bf.BriefingError,
                       match="is a Text, not a DataDive or DataTable. There is no named DataDive or DataTable there"):
        _html(bf.lab.DataProfile(_DF, selects="t"), bf.Text("x", name="t"))


def test_the_target_is_its_link_id_in_the_senders_page() -> None:
    report = bf.Briefing(
        bf.Page(bf.lab.DataProfile(_DF, selects=["dive", "more"]), _dive(), bf.lab.DataDive(_DF, name="more"),
                title="Detail", name="detail"),
        bf.Page(bf.Text("x"), title="Other"),
    )
    profile = find_one(parse(bf.stringify(report)), ".bf-profile")
    assert json.loads(attr(profile, "data-bf-selects")) == ["detail/dive", "detail/more"]
    assert attr(profile, "data-bf-from") == "profile"


def test_validate_reports_a_missing_target_at_its_block() -> None:
    report = bf.Briefing(bf.Text("x"), bf.lab.DataProfile(_DF, selects="dive"))
    [error] = [d for d in bf.validate(report) if d.severity == "error"]
    assert (error.code, error.path) == ("unknown-target", "/blocks/1")
    assert bf.validate(bf.Briefing(bf.lab.DataProfile(_DF, selects="dive"), _dive())) == []


def test_selects_round_trips_through_the_json_form() -> None:
    report = bf.Briefing(bf.lab.DataCompare([_DF, _DF], selects=["dive"]), _dive())
    spec, data = bf.to_spec(report)
    assert spec["blocks"][0]["selects"] == ["dive"]
    assert bf.stringify(bf.from_spec(json.dumps(spec), data)) == bf.stringify(report)


# ── assets ────────────────────────────────────────────────────────────────────


def test_the_script_and_styles_ship_only_with_a_sender() -> None:
    plain = _html(bf.lab.DataProfile(_DF), bf.lab.DataCompare([_DF, _DF]), _dive())
    assert _SELECT_JS not in plain and _SELECT_CSS not in plain
    assert parse(plain).select(".bf-sel__hit, [data-bf-selects], [data-bf-column]") == []
    linked = _html(bf.lab.DataProfile(_DF, selects="dive"), bf.lab.DataCompare([_DF, _DF], selects="dive"), _dive())
    assert linked.count(_SELECT_JS) == 1 and linked.count(_SELECT_CSS) == 1


# ── the bars ──────────────────────────────────────────────────────────────────


def test_a_histogram_gets_a_target_per_bin_with_its_range() -> None:
    soup = parse(_html(bf.lab.DataProfile(_DF, selects="dive"), _dive()))
    chart = find_one(soup, '.bf-profile__chart[data-bf-column="n"]')
    test = json.loads(attr(chart, "data-bf-test"))
    assert test == {"kind": "bins", "min": 1.0, "max": 4.0, "scale": 1.0, "bins": 20, "unit": 1}
    hits = chart.select(".bf-sel__hit")
    assert [attr(h, "data-bf-pick") for h in hits] == [str(i) for i in range(20)]
    assert attr(hits[0], "data-bf-label") == "1–1.15" and attr(hits[-1], "data-bf-label") == "3.85–4"
    assert attr(hits[0], "aria-label") == "Select n 1–1.15 in dive"


def test_a_single_value_is_one_bar_found_by_equality() -> None:
    soup = parse(_html(bf.lab.DataProfile(pd.DataFrame({"n": [7, 7]}), selects="dive"),
                       bf.lab.DataDive(pd.DataFrame({"n": [7, 7]}), name="dive")))
    chart = find_one(soup, '[data-bf-column="n"]')
    assert json.loads(attr(chart, "data-bf-test"))["bins"] == 1
    assert [attr(h, "data-bf-label") for h in chart.select(".bf-sel__hit")] == ["7"]


def test_category_bars_select_their_value_as_the_dive_shows_it() -> None:
    chart = find_one(parse(_html(bf.lab.DataProfile(_DF, selects="dive"), _dive())), '[data-bf-column="team"]')
    assert json.loads(attr(chart, "data-bf-test")) == {"kind": "values"}
    assert [attr(h, "data-bf-pick") for h in chart.select(".bf-sel__hit")] == ["a", "b", "c"]


def test_a_column_the_dive_holds_as_another_kind_selects_nothing() -> None:
    other = _DF.assign(n=["x", "y", "z", "w"])
    soup = parse(_html(bf.lab.DataProfile(_DF, selects="dive"), bf.lab.DataDive(other, name="dive")))
    chart = find_one(soup, ".bf-profile__chart[data-bf-unselectable]")
    assert attr(chart, "title") == "In the DataDive 'dive', 'n' holds categories, not numbers."
    assert chart.select(".bf-sel__hit") == []


def test_a_comparisons_dates_are_tested_in_nanoseconds_from_the_dives_milliseconds() -> None:
    later = _DF.assign(day=pd.to_datetime(["2026-02-01"] * 4))
    soup = parse(_html(bf.lab.DataCompare([_DF, later], selects="dive"), _dive()))
    test = json.loads(attr(find_one(soup, '.bf-cmp__chart[data-bf-column="day"]'), "data-bf-test"))
    assert test["unit"] == 1_000_000 and test["min"] == pd.Timestamp("2026-01-01").value


def test_curves_and_the_other_bar_select_nothing() -> None:
    many = pd.DataFrame({"v": [f"v{i}" for i in range(30)]})
    soup = parse(_html(bf.lab.DataCompare([many, many], selects="dive"), bf.lab.DataDive(many, name="dive")))
    assert soup.select(".bf-sel__hit") == []  # 30 values: a cumulative curve
    some = pd.DataFrame({"v": [f"v{i}" for i in range(15)]})
    soup = parse(_html(bf.lab.DataCompare([some, some], selects="dive"), bf.lab.DataDive(some, name="dive")))
    assert len(soup.select(".bf-sel__hit")) == 10  # the top 10 bars, not "other"


def test_a_deck_resolves_targets_in_the_senders_slide() -> None:
    deck = bf.deck.Deck(bf.deck.Slide(bf.lab.DataProfile(_DF, selects="dive"), _dive(), title="S", name="s"))
    profile = find_one(parse(bf.deck.to_html(deck)), ".bf-profile")
    assert json.loads(attr(profile, "data-bf-selects")) == ["s/dive"]


# ── a DataTable as a receiver (#238) ──────────────────────────────────────────


def test_a_table_carries_its_values_only_when_it_receives() -> None:
    soup = parse(_html(bf.lab.DataProfile(_DF, selects="rows"), bf.DataTable(_DF, name="rows")))
    values = json.loads(find_one(soup, '.bf-datatable script.bf-dt__values').get_text())
    assert values["columns"]["team"] == {"name": "team", "kind": "categorical", "levels": ["a", "b", "c"],
                                         "codes": [0, 1, 0, 2]}
    assert values["columns"]["day"]["values"] == [pd.Timestamp("2026-01-01").value // 1_000_000] * 4
    alone = parse(_html(bf.lab.DataProfile(_DF, selects="dive"), _dive(), bf.DataTable(_DF, name="rows")))
    assert alone.select("script.bf-dt__values") == []


def test_a_big_tables_values_are_packed() -> None:
    big = pd.DataFrame({"n": range(1500)})
    soup = parse(_html(bf.lab.DataProfile(big, selects="rows"), bf.DataTable(big, name="rows")))
    script = find_one(soup, "script.bf-dt__values")
    packed = json.loads(script.get_text())  # a packed string (#38), not the columns themselves
    assert script.has_attr("data-size") and isinstance(packed, str) and '"columns"' not in packed


def test_a_column_the_table_lacks_is_not_clickable_and_says_why() -> None:
    soup = parse(_html(bf.lab.DataProfile(_DF, selects="rows"), bf.DataTable(_DF.drop(columns="team"), name="rows")))
    chart = find_one(soup, ".bf-profile__chart[data-bf-unselectable]")
    assert attr(chart, "title") == "The DataTable 'rows' has no column 'team'."


def test_a_table_target_validates_and_round_trips() -> None:
    report = bf.Briefing(bf.lab.DataCompare([_DF, _DF], selects="rows"), bf.DataTable(_DF, name="rows"))
    assert bf.validate(report) == []
    spec, data = bf.to_spec(report)
    assert bf.stringify(bf.from_spec(json.dumps(spec), data)) == bf.stringify(report)


def test_a_table_in_another_page_is_not_reachable() -> None:
    report = bf.Briefing(
        bf.Page(bf.lab.DataProfile(_DF, selects="rows"), title="A", name="a"),
        bf.Page(bf.DataTable(_DF, name="rows"), title="B", name="b"),
    )
    with pytest.raises(bf.BriefingError, match="no block named 'rows' in page 'a'"):
        bf.stringify(report)
