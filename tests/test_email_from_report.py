"""bf.email.from_report (#199, experimental): a first draft of an email digest from a report."""
from __future__ import annotations

import typing as t
import warnings
from collections.abc import Iterator

import pandas as pd
import pytest

import briefing as bf
from briefing import _experimental
from tests.banner_images import RED_SVG
from tests.scenarios import SCENARIOS, Frames


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    _experimental._warned.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", bf.ExperimentalWarning)
        yield


def _kinds(digest: bf.email.Digest) -> list[str]:
    return [type(b).__name__ for b in digest.blocks]


def _texts(digest: bf.email.Digest) -> list[str]:
    return [b.content for b in digest.blocks if isinstance(b, bf.Text)]


def test_it_warns_that_it_is_experimental_once_at_the_callers_line() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        bf.email.from_report(bf.Text("a"))
        bf.email.from_report(bf.Text("b"))
    found = [w for w in caught if issubclass(w.category, bf.ExperimentalWarning)]
    assert len(found) == 1 and "bf.email.from_report is experimental" in str(found[0].message)
    assert found[0].filename == __file__


def test_what_an_email_shows_stays_as_it_is() -> None:
    blocks = [bf.Text("# Q3"), bf.BigNumber("Revenue", 42), bf.Alert("Late data.", level="warning"),
              bf.Table(pd.DataFrame({"a": [1, 2]}))]
    digest = bf.email.from_report(bf.Briefing(*blocks, footer="Team"), link="https://example.com/q3.html")
    assert digest.blocks == blocks
    assert (digest.footer, digest.link) == ("Team", "https://example.com/q3.html")


def test_it_takes_one_page_by_index_title_or_name() -> None:
    report = bf.Briefing(bf.Page("first page", title="Summary", name="summary"),
                         bf.Page("second page", title="Detail", name="detail"))
    assert _texts(bf.email.from_report(report)) == ["first page"]
    assert _texts(bf.email.from_report(report, page=1)) == ["second page"]
    assert _texts(bf.email.from_report(report, page="Detail")) == ["second page"]
    assert _texts(bf.email.from_report(report, page="detail")) == ["second page"]
    with pytest.raises(bf.BriefingError, match=r"no page named 'x'\. Pages: 'Summary', 'Detail'"):
        bf.email.from_report(report, page="x")
    with pytest.raises(bf.BriefingError, match="page=5 is out of range"):
        bf.email.from_report(report, page=5)
    with pytest.raises(bf.BriefingError, match="the report has no Page blocks"):
        bf.email.from_report(bf.Text("a"), page=1)


def test_a_datatable_becomes_its_first_30_rows_with_its_formats() -> None:
    frame = pd.DataFrame({"n": range(45), "share": [i / 100 for i in range(45)]})
    digest = bf.email.from_report(bf.DataTable(frame, formats={"share": "{:.0%}"}, caption="Rows"))
    assert _kinds(digest) == ["Table", "Text"]  # the table, then the line saying it was cut
    table = t.cast(bf.Table, digest.blocks[0])
    data = t.cast(pd.DataFrame, table.data)
    assert len(data) == 30 and data["share"].tolist()[:2] == ["0%", "1%"]
    assert table.caption == "Rows"
    assert _texts(digest) == ["First 30 of 45 rows: see the full report."]


def test_a_short_datatable_has_no_note() -> None:
    assert _kinds(bf.email.from_report(bf.DataTable(pd.DataFrame({"a": [1, 2]})))) == ["Table"]


def test_a_long_table_is_cut_too() -> None:
    digest = bf.email.from_report(bf.Table(pd.DataFrame({"a": range(31)})))
    assert _kinds(digest) == ["Table", "Text"]
    assert len(t.cast(pd.DataFrame, t.cast(bf.Table, digest.blocks[0]).data)) == 30


def test_interactive_and_framed_blocks_become_what_a_reader_sees_first() -> None:
    report = bf.Briefing(
        bf.Select(bf.Text("first tab", label="A"), bf.Text("second tab", label="B")),
        bf.Card(bf.BigNumber("Orders", 7), title="A card"),
        bf.Banner("# Q3 review", image=RED_SVG),
        bf.Chips(["North", bf.Chip("South", tooltip="down")]),
    )
    digest = bf.email.from_report(report)
    assert _kinds(digest) == ["Text", "Text", "BigNumber", "Text", "Text"]
    assert _texts(digest) == ["first tab", "**A card**", "# Q3 review", "North · South"]


def test_a_group_keeps_only_what_an_email_shows() -> None:
    report = bf.Briefing(bf.Group(bf.BigNumber("A", 1), bf.Code("x = 1"), columns=2),
                         bf.Group(bf.Code("y = 2")))
    with pytest.warns(UserWarning, match="left out 2 blocks"):
        digest = bf.email.from_report(report)
    group = t.cast(bf.Group, digest.blocks[0])
    assert _kinds(digest) == ["Group"] and [type(b).__name__ for b in group.blocks] == ["BigNumber"]
    assert [type(b).__name__ for b in t.cast(bf.Group, report.blocks[0]).blocks] == ["BigNumber", "Code"]  # unchanged


def test_one_warning_names_what_was_left_out() -> None:
    report = bf.Briefing(bf.Text("a"), bf.Toggle(bf.Text("b"), label="More"),
                         bf.lab.DataDive(pd.DataFrame({"x": [1, 2]}), name="dive"))
    with pytest.warns(UserWarning, match=r'left out 2 blocks an email can\'t show: Toggle, lab\.DataDive "dive"\. '
                                          r"link= adds a button") as caught:
        bf.email.from_report(report)
    assert [w.filename for w in caught if "left out" in str(w.message)] == [__file__]


def test_links_into_the_report_need_its_address_or_keep_only_their_words() -> None:
    report = bf.Briefing(bf.Text("See [the rows](#detail/rows) and [the site](https://example.com)."),
                         bf.Group(bf.Text("[Method](#method)")))
    plain = bf.email.from_report(report)
    assert _texts(plain) == ["See the rows and [the site](https://example.com)."]
    assert t.cast(bf.Text, t.cast(bf.Group, plain.blocks[1]).blocks[0]).content == "Method"
    bf.email.to_html(plain)  # renders: no link left that needs the report's address
    linked = bf.email.from_report(report, link="https://example.com/q3.html")
    assert 'href="https://example.com/q3.html#detail/rows"' in bf.email.to_html(linked)[0]


def test_a_page_with_nothing_an_email_shows_says_so() -> None:
    with pytest.raises(bf.BriefingError, match="holds nothing an email can show"), pytest.warns(UserWarning):
        bf.email.from_report(bf.Code("x = 1"))


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_every_scenario_converts_to_a_digest_or_says_why_not(scenario: str, frames: Frames) -> None:
    try:
        digest = bf.email.from_report(SCENARIOS[scenario](frames))
    except bf.BriefingError as exc:
        assert "nothing an email can show" in str(exc)
        return
    if any(isinstance(b, bf.Plot) for b in digest.blocks):
        return  # drawing charts as PNG needs their export libraries; bf.email's own tests cover it
    html, _ = bf.email.to_html(digest)
    assert "Made with briefing" in html


def test_a_converted_digest_matches_its_golden_snapshot(snapshot: t.Any) -> None:
    from pathlib import Path

    report = bf.Briefing(
        bf.Page(
            bf.Text("# Q3 review\n\nRevenue grew in **every** region; see [the detail](#detail/regions)."),
            bf.Group(bf.BigNumber("Revenue", 4.2e6, prev_value=3.9e6, format="${:,.0f}"),
                     bf.BigNumber("Margin", 0.31, prev_value=0.33, format="{:.0%}"), columns=2),
            bf.Select(bf.DataTable(pd.DataFrame({"region": ["North", "South"], "revenue": [1.42, 0.96]}),
                                   formats={"revenue": "${:.2f}M"}, label="Regions"),
                      bf.Text("Notes", label="Notes")),
            bf.Toggle(bf.Text("Method"), label="Method"),
            title="Summary", name="summary",
        ),
        bf.Page(bf.Text("Detail"), title="Detail", name="detail"),
        footer="Sales analytics",
    )
    with pytest.warns(UserWarning, match="left out 1 block"):
        digest = bf.email.from_report(report, link="https://example.com/q3.html")
    html, pictures = bf.email.to_html(digest)
    assert pictures == []
    snapshot.snapshot_dir = Path(__file__).parent / "snapshots" / "golden_email"
    snapshot.assert_match(html.replace(bf.__version__, "{version}"), "from-report.html")
