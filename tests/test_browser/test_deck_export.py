"""A deck printed, as a PDF and as images (#197): one slide per page, each the size of a 16:9 slide."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from playwright.sync_api import expect

import briefing as bf
from tests.image_helpers import png_size
from tests.pdf_reader import read_pdf
from tests.test_browser.conftest import Viewer


def _deck() -> bf.deck.Deck:
    return bf.deck.Deck(
        bf.deck.Slide(title="Q3 review"),
        bf.deck.Slide(bf.Text("Revenue grew."), title="Summary", name="summary"),
        bf.deck.Slide(bf.Select(bf.Text("alpha panel", label="A"), bf.Text("bravo panel", label="B")), title="Detail"),
        bf.deck.Slide(bf.DataTable(pd.DataFrame({"row": [f"r{i}" for i in range(30)]})), title="Rows"),
        footer="Team",
    )


def _saved(tmp_path: Path) -> Path:
    path = tmp_path / "q3.html"
    bf.deck.save(_deck(), path)
    return path


def _pages(path: Path) -> list[str]:
    return read_pdf(path.read_bytes()).pages


def test_the_pdf_has_one_slide_per_page_at_slide_size(tmp_path: Path) -> None:
    path = bf.deck.save_pdf(_deck(), tmp_path / "q3.pdf")
    pages = _pages(path)
    assert [p.split("\n", 1)[0] for p in pages] == ["Q3 review", "Summary", "Detail", "Rows"]
    boxes = re.findall(rb"/MediaBox\s*\[([^\]]*)\]", path.read_bytes())
    assert {tuple(float(v) for v in box.split()) for box in boxes} == {(0, 0, 960, 540)}  # 1280 x 720 px


def test_a_slide_prints_as_it_shows(tmp_path: Path) -> None:
    pages = _pages(bf.deck.save_pdf(_deck(), tmp_path / "q3.pdf"))
    assert "alpha panel" in pages[2] and "bravo panel" not in pages[2]  # its chosen tab only


def test_a_table_on_a_slide_prints_the_page_it_shows(viewer: Viewer) -> None:
    # Checked in the page: the test PDF reader can't read text inside a slide shrunk to fit.
    page = viewer.open(bf.deck.to_html(_deck()))
    page.emulate_media(media="print")
    page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    expect(page.locator(".bf-slide").nth(3).locator("tbody tr")).to_have_count(10)
    expect(page.locator(".bf-slide").nth(2).locator(".bf-print-label")).to_have_count(0)


def test_one_slide_by_name_or_number(tmp_path: Path) -> None:
    assert _pages(bf.deck.save_pdf(_deck(), tmp_path / "a.pdf", slide="summary"))[0].startswith("Summary")
    pages = _pages(bf.deck.save_pdf(_saved(tmp_path), tmp_path / "b.pdf", slide=3))
    assert len(pages) == 1 and pages[0].startswith("Detail")


def test_an_unknown_slide_says_which_there_are(tmp_path: Path) -> None:
    with pytest.raises(bf.BriefingError, match=r"slide=5 is out of range: the deck has 4 slides"):
        bf.deck.save_pdf(_deck(), tmp_path / "x.pdf", slide=5)
    with pytest.raises(bf.BriefingError, match=r"No slide named 'nope'\. Named slides: 'summary'"):
        bf.deck.save_image(_deck(), tmp_path / "x.png", slide="nope")


def test_images_are_one_per_slide_numbered(tmp_path: Path) -> None:
    written = bf.deck.save_image(_deck(), tmp_path / "q3.png", scale=1)
    assert [p.name for p in written] == ["q3_01.png", "q3_02.png", "q3_03.png", "q3_04.png"]
    assert {png_size(p) for p in written} == {(1280, 720)}


def test_one_image_goes_to_the_path_given(tmp_path: Path) -> None:
    written = bf.deck.save_image(_saved(tmp_path), tmp_path / "cover.webp", slide=1, scale=0.5)
    assert written == [tmp_path / "cover.webp"]
    assert (tmp_path / "cover.webp").read_bytes()[8:12] == b"WEBP"


def test_reports_and_decks_go_to_their_own_exports(tmp_path: Path) -> None:
    with pytest.raises(bf.BriefingError, match=r"slide deck: export it with bf\.deck\.save_pdf"):
        bf.save_pdf(_saved(tmp_path), tmp_path / "x.pdf")
    with pytest.raises(bf.BriefingError, match=r"slide deck: export it with bf\.deck\.save_pdf"):
        bf.save_image(_deck(), tmp_path / "x.png")
    report = tmp_path / "report.html"
    bf.save(bf.Text("a"), str(report))
    with pytest.raises(bf.BriefingError, match=r"a report, not a slide deck: export it with bf\.save_pdf"):
        bf.deck.save_pdf(report, tmp_path / "x.pdf")


def test_printing_shows_every_slide_and_no_controls(viewer: Viewer) -> None:
    page = viewer.open(bf.deck.to_html(_deck()))
    page.keyboard.press("o")
    page.emulate_media(media="print")
    page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    for i in range(4):
        assert page.locator(".bf-slide").nth(i).evaluate("el => getComputedStyle(el).visibility") == "visible"
    expect(page.locator(".bf-deck__controls")).to_be_hidden()
    expect(page.locator(".bf-deck")).not_to_have_class(re.compile("bf-deck--overview"))
    page.evaluate("() => window.dispatchEvent(new Event('afterprint'))")
    page.emulate_media(media="screen")
    expect(page.locator(".bf-deck")).to_have_class(re.compile("bf-deck--overview"))  # back as it was


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "briefing", *args], capture_output=True, text=True)


def test_the_command_line_exports_a_saved_deck(tmp_path: Path) -> None:
    saved = _saved(tmp_path)
    run = _cli("pdf", str(saved))
    assert run.returncode == 0, run.stderr
    assert len(_pages(tmp_path / "q3.pdf")) == 4
    run = _cli("image", str(saved), "--slide", "summary", "-o", str(tmp_path / "s.png"), "--scale", "1")
    assert run.returncode == 0, run.stderr
    assert png_size(tmp_path / "s.png") == (1280, 720)


def test_the_command_line_keeps_report_options_for_reports(tmp_path: Path) -> None:
    saved = _saved(tmp_path)
    assert "pick a slide with --slide" in _cli("pdf", str(saved), "--page", "1").stderr
    assert "--paper and --landscape are for reports" in _cli("pdf", str(saved), "--paper", "letter").stderr
    assert "--size and --width are for reports" in _cli("image", str(saved), "--size", "og").stderr
    report = tmp_path / "report.html"
    bf.save(bf.Text("a"), str(report))
    assert "is a report: use --page" in _cli("pdf", str(report), "--slide", "2").stderr
