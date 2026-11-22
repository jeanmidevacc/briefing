"""bf.deck.to_html and bf.deck.save (#197): one self-contained page of slides, in the report's theme."""
from __future__ import annotations

import typing as t
import warnings
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from briefing.deck._render import MAX_WORDS
from briefing.renderers.plot import get_runtime_scripts
from tests.golden import static_files
from tests.html_helpers import attr, classes, find_one, parse


def _deck(**kwargs: t.Any) -> bf.deck.Deck:
    return bf.deck.Deck(
        bf.deck.Slide(title="Part one"),
        bf.deck.Slide(bf.Text("Revenue grew."), bf.BigNumber("Revenue", 42), title="**Summary**", name="summary"),
        bf.deck.Slide(bf.DataTable(pd.DataFrame({"a": [1, 2]}), name="rows"), title="Detail"),
        **kwargs,
    )


def test_a_deck_is_one_page_with_a_section_per_slide() -> None:
    soup = parse(bf.deck.to_html(_deck(footer="Team"), name="Q3 <review>"))
    assert find_one(soup, "title").get_text() == "Q3 <review>"
    assert attr(find_one(soup, 'meta[name="viewport"]'), "content") == "width=1280"
    assert attr(find_one(soup, 'meta[name="generator"]'), "content") == f"briefing {bf.__version__}"
    slides = soup.select(".bf-deck__stage > section.bf-slide")
    assert [attr(s, "data-bf-slide") for s in slides] == ["1", "2", "3"]
    assert [attr(s, "aria-label") for s in slides] == [
        "Slide 1 of 3: Part one", "Slide 2 of 3: Summary", "Slide 3 of 3: Detail",
    ]
    footer = find_one(slides[1], ".bf-slide__footer")
    assert find_one(footer, ".bf-slide__made").get_text() == f"Team · Made with briefing {bf.__version__}"
    assert find_one(footer, ".bf-slide__number").get_text() == "2 / 3"


def test_a_slide_title_takes_inline_markdown_and_is_escaped() -> None:
    soup = parse(bf.deck.to_html(bf.deck.Deck(bf.deck.Slide("a", title="**Q3** <b>x</b>"))))
    title = find_one(soup, ".bf-slide__title")
    assert title.select_one("strong") is not None and title.select_one("b") is None
    assert "<b>x</b>" in title.get_text()


def test_section_and_title_slides_get_their_own_class() -> None:
    from tests.banner_images import RED_SVG

    deck = bf.deck.Deck(
        bf.deck.Slide(bf.Banner("# Q3", image=RED_SVG)),
        bf.deck.Slide(title="Part two"),
        bf.deck.Slide(bf.Banner("# Q3", image=RED_SVG), title="A banner under a title"),
    )
    slides = parse(bf.deck.to_html(deck)).select("section.bf-slide")
    assert "bf-slide--banner" in classes(slides[0])
    assert "bf-slide--section" in classes(slides[1])
    assert not {"bf-slide--banner", "bf-slide--section"} & set(classes(slides[2]))


def test_named_slides_and_blocks_get_their_link() -> None:
    deck = _deck()
    deck.slides[1].blocks.append(bf.Text("## Notes {#notes}", name="more"))
    soup = parse(bf.deck.to_html(deck))
    summary = find_one(soup, "#summary")
    assert summary.name == "section" and summary.has_attr("data-bf-link")
    assert find_one(soup, '[id="summary/more"]').find_parent("section") is summary
    assert soup.select_one('[id="summary/notes"]') is not None
    assert find_one(soup, "#rows").find_parent("section") is soup.select("section.bf-slide")[2]


def test_a_name_used_twice_outside_named_slides_is_refused() -> None:
    deck = bf.deck.Deck(bf.deck.Slide("a", name="kpis"), bf.deck.Slide(bf.Text("b", name="kpis")))
    with pytest.raises(bf.BriefingError, match="named 'kpis'"):
        bf.deck.to_html(deck)


def test_the_page_carries_report_css_deck_css_the_theme_and_the_scripts() -> None:
    html = bf.deck.to_html(_deck(), formatting=bf.Formatting.from_accent("#0f766e"))
    for path in ("static/report.css", "static/deck.css", "static/report.js", "static/deck.js"):
        assert static_files()[path] in html, path
    assert "--bf-accent:     #0f766e;" in html
    assert html.count("briefing.init(document);") == 1
    assert "lab/static/lab.js" not in html and static_files()["lab/static/lab.js"] not in html


def test_lab_scripts_and_chart_runtimes_come_only_with_their_blocks() -> None:
    import plotly.express as px

    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    plain = bf.deck.to_html(bf.deck.Deck(bf.deck.Slide("a")))
    html = bf.deck.to_html(bf.deck.Deck(bf.deck.Slide(bf.Plot(px.line(df, x="x", y="y")), bf.lab.DataDive(df))))
    assert static_files()["lab/static/lab.js"] in html and static_files()["lab/static/lab.js"] not in plain
    runtime = get_runtime_scripts({"plotly"})
    assert runtime and runtime in html and runtime not in plain


def test_the_same_deck_renders_the_same_bytes() -> None:
    assert bf.deck.to_html(_deck()) == bf.deck.to_html(_deck())


def test_save_writes_the_page(tmp_path: Path) -> None:
    path = tmp_path / "deck.html"
    bf.deck.save(_deck(), path, name="Q3")
    assert path.read_text(encoding="utf-8") == bf.deck.to_html(_deck(), name="Q3")


def test_a_slide_with_too_much_text_warns_at_the_callers_line() -> None:
    deck = bf.deck.Deck(bf.deck.Slide(title="fine"), bf.deck.Slide(" ".join(["word"] * (MAX_WORDS + 1)), title="Long"))
    with pytest.warns(UserWarning, match=r"Slide 2 \('Long'\) holds 121 words") as caught:
        bf.deck.to_html(deck)
    assert caught[0].filename == __file__


def test_text_within_the_limit_does_not_warn() -> None:
    deck = bf.deck.Deck(bf.deck.Slide(bf.Group(bf.Text(" ".join(["word"] * 60)), bf.Text(" ".join(["w"] * 60)))))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bf.deck.to_html(deck)


def test_a_deck_over_max_size_names_its_largest_slide_blocks() -> None:
    deck = bf.deck.Deck(bf.deck.Slide(title="a"), bf.deck.Slide(bf.DataTable(pd.DataFrame({"a": range(500)}))))
    with pytest.warns(UserWarning, match=r"over max_size .*DataTable at /slides/1/blocks/0") as caught:
        bf.deck.to_html(deck, max_size=2_000)
    assert caught[0].filename == __file__


def test_a_report_given_to_bf_deck_says_what_to_use() -> None:
    with pytest.raises(bf.BriefingError, match=r"not Briefing\. For a report, use bf\.save"):
        bf.deck.to_html(t.cast(t.Any, bf.Briefing(bf.Text("a"))))


def test_slides_changed_after_the_deck_was_built_are_checked_again() -> None:
    deck = _deck()
    deck.slides.append(t.cast(t.Any, bf.Text("loose")))
    with pytest.raises(bf.BriefingError, match="slide 4 is a Text"):
        bf.deck.to_html(deck)


def test_validate_reports_long_text_and_size_at_their_slide() -> None:
    spec = {"briefing": 1, "slides": [{"title": "a"}, {"blocks": [{"type": "Text", "text": "word " * 130}]}]}
    found = [(d.code, d.path) for d in bf.validate(spec)]
    assert found == [("block-warning", "/slides/1")]
    assert ("too-big", "") in [(d.code, d.path) for d in bf.validate(spec, max_size=1_000)]
