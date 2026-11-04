"""bf.save_image renders report pages to PNG/JPEG/WebP in headless Chromium (#49)."""
from __future__ import annotations

import typing as t
import warnings
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from briefing.export._render import open_report, outside_event_loop
from tests.image_helpers import image_kind, png_size


def _pages() -> bf.Briefing:
    return bf.Briefing(
        bf.Page(bf.Text("# Summary\n\nShort page."), title="Summary", name="summary"),
        bf.Page(bf.Text("# Detail"), bf.Toggle(bf.Text("hidden " * 400), label="More"), title="Detail view"),
    )


def _long() -> bf.Briefing:
    return bf.Briefing(*[bf.Text(f"## Section {i}\n\n" + "Lorem ipsum dolor sit amet. " * 30) for i in range(12)])


def test_page_all_writes_one_image_per_page_named_after_it(tmp_path: Path) -> None:
    paths = bf.save_image(_pages(), tmp_path / "q1.png", page="all", width=800, scale=2)
    assert [p.name for p in paths] == ["q1_summary.png", "q1_detail_view.png"]
    assert all(png_size(p)[0] == 1600 for p in paths)


def test_report_without_pages_writes_one_image(tmp_path: Path) -> None:
    paths = bf.save_image(bf.Briefing(bf.Text("# One")), tmp_path / "one.png", width=600, scale=1)
    assert paths == [tmp_path / "one.png"]
    assert png_size(paths[0])[0] == 600


def test_a_page_by_title_name_or_index(tmp_path: Path) -> None:
    by_title = bf.save_image(_pages(), tmp_path / "t.png", page="Detail view", scale=1)
    by_index = bf.save_image(_pages(), tmp_path / "i.png", page=1, scale=1)
    by_name = bf.save_image(_pages(), tmp_path / "n.png", page="summary", scale=1)
    assert [p.name for p in by_title + by_index + by_name] == ["t.png", "i.png", "n.png"]
    # the same page either way (image bytes may vary, sizes don't); "summary" is the short page
    assert png_size(by_title[0]) == png_size(by_index[0])
    assert png_size(by_name[0])[1] < png_size(by_index[0])[1]


def test_unknown_page_lists_the_pages(tmp_path: Path) -> None:
    with pytest.raises(bf.BriefingError, match="Summary.*Detail view"):
        bf.save_image(_pages(), tmp_path / "x.png", page="Nope")


@pytest.mark.parametrize(("size", "expected"), [("og", (1200, 630)), ("square", (1080, 1080)),
                                                ("portrait", (1080, 1350))])
@pytest.mark.parametrize("scale", [1, 2])
def test_presets_have_their_exact_size(tmp_path: Path, size: str, expected: tuple[int, int], scale: int) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        (path,) = bf.save_image(_pages(), tmp_path / "card.png", page=0, size=size, scale=scale)
    assert png_size(path) == (expected[0] * scale, expected[1] * scale)


def test_preset_warns_when_the_page_shrinks_below_half(tmp_path: Path) -> None:
    with pytest.warns(UserWarning, match="shrunk to .*% to fit 'og'"):
        bf.save_image(_long(), tmp_path / "long.png", size="og", scale=1)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bf.save_image(bf.Briefing(bf.Text("# Short")), tmp_path / "short.png", size="og", scale=1)


def test_expand_opens_toggles(tmp_path: Path) -> None:
    (open_,) = bf.save_image(_pages(), tmp_path / "open.png", page=1, scale=1, expand=True)
    (closed,) = bf.save_image(_pages(), tmp_path / "closed.png", page=1, scale=1, expand=False)
    assert png_size(open_)[1] > png_size(closed)[1] + 200


def test_saved_html_file_as_input(tmp_path: Path) -> None:
    saved = tmp_path / "report.html"
    bf.save(_pages(), str(saved))
    paths = bf.save_image(saved, tmp_path / "from_file.png", page="all", scale=1)
    assert [p.name for p in paths] == ["from_file_summary.png", "from_file_detail_view.png"]


@pytest.mark.parametrize(("suffix", "kind"), [(".png", "png"), (".jpg", "jpeg"), (".jpeg", "jpeg"), (".webp", "webp")])
def test_format_follows_the_suffix(tmp_path: Path, suffix: str, kind: str) -> None:
    (path,) = bf.save_image(bf.Briefing(bf.Text("# Hi")), tmp_path / f"x{suffix}", scale=1)
    assert image_kind(path) == kind


def test_charts_and_lab_blocks_are_drawn_before_capture() -> None:
    go = pytest.importorskip("plotly.graph_objects")
    df = pd.DataFrame({"x": range(30), "y": [(i * 7) % 30 for i in range(30)], "c": [i % 3 for i in range(30)]})
    report = bf.Briefing(
        bf.Page(bf.Text("first"), title="One"),
        bf.Page(bf.Plot(go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))), bf.lab.DataDive(df), bf.lab.DataProfile(df),
                title="Charts"),
    )

    def drawn_state() -> dict[str, t.Any]:
        with open_report(report, width=1000, scale=1) as session:
            session.show(session.resolve(1)[0])
            return session.page.evaluate(STATE_JS)  # type: ignore[no-any-return]

    state = outside_event_loop(drawn_state)
    assert state["plotly"] and state["dots"] == 30 and state["profile"] >= 3
    assert state["chartWidth"] > 800  # drawn at the layout width, not Plotly's 700 px default


STATE_JS = """() => ({
          plotly: document.querySelectorAll('.js-plotly-plot .main-svg').length > 0,
          dots: document.querySelectorAll('.bf-dd__dot').length,
          profile: document.querySelectorAll('.bf-profile__card svg').length,
          chartWidth: document.querySelector('.js-plotly-plot .main-svg').getBoundingClientRect().width,
        })"""


def test_no_network_request_while_rendering(tmp_path: Path, counting_server: tuple[str, list[str]]) -> None:
    url, hits = counting_server
    report = bf.Briefing(bf.HTML(f'<img src="{url}/tracker.png"><link rel="stylesheet" href="{url}/x.css">'))
    bf.save_image(report, tmp_path / "x.png", scale=1)
    bf.save_image(report, tmp_path / "card.png", size="og", scale=1)
    assert hits == []


def test_works_inside_a_running_event_loop(tmp_path: Path) -> None:
    # A Jupyter notebook always runs an asyncio loop; Playwright's sync API refuses one.
    import asyncio

    async def notebook_cell() -> list[Path]:
        return bf.save_image(bf.Briefing(bf.Text("# From a notebook")), tmp_path / "nb.png", scale=1)

    # Run the "notebook" in its own thread, so its loop doesn't clash with pytest-playwright's.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        (path,) = pool.submit(asyncio.run, notebook_cell()).result()
    assert png_size(path)[0] == 1200
