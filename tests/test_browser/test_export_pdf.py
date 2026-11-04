"""bf.save_pdf writes a report as one PDF, laid out like the print dialog (#49, #37)."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from tests.pdf_reader import read_pdf
from tests.test_browser.conftest import Viewer


def _three_pages() -> bf.Briefing:
    return bf.Briefing(
        bf.Page(bf.Text("# Summary\n\nRead the [full data](https://example.com/data) online."), title="Summary"),
        bf.Page(bf.DataTable(pd.DataFrame({"label": [f"item {i}" for i in range(40)]})), title="Data"),
        bf.Page(bf.Toggle(bf.Text("Methodology body."), label="Methodology"), title="Notes", name="notes"),
    )


def _sheet_starts(pdf_path: Path) -> list[str]:
    return [text.split("\n", 1)[0].strip() for text in read_pdf(pdf_path.read_bytes()).pages]


def test_page_all_is_one_pdf_with_each_page_on_a_new_sheet(tmp_path: Path) -> None:
    path = bf.save_pdf(_three_pages(), tmp_path / "q1.pdf")
    assert path == tmp_path / "q1.pdf"
    starts = _sheet_starts(path)
    assert "Data" in starts and "Notes" in starts
    text = "\n".join(read_pdf(path.read_bytes()).pages)
    assert "Methodology body." in text  # toggles print open


def test_one_page_by_title_or_name(tmp_path: Path) -> None:
    for page in ("Data", 1):
        text = "\n".join(read_pdf(bf.save_pdf(_three_pages(), tmp_path / "d.pdf", page=page).read_bytes()).pages)
        assert "item 39" in text and "Methodology body." not in text and "Read the" not in text
    notes = "\n".join(read_pdf(bf.save_pdf(_three_pages(), tmp_path / "n.pdf", page="notes").read_bytes()).pages)
    assert "Methodology body." in notes and "item 0" not in notes


def test_text_is_selectable_and_links_work(tmp_path: Path) -> None:
    pdf = read_pdf(bf.save_pdf(_three_pages(), tmp_path / "q1.pdf").read_bytes())
    assert "full data" in pdf.pages[0]
    assert "https://example.com/data" in pdf.links


def test_charts_are_drawn_and_stay_vector(tmp_path: Path) -> None:
    go = pytest.importorskip("plotly.graph_objects")
    figure = pytest.importorskip("matplotlib.figure")
    mpl = figure.Figure(figsize=(4, 3))
    mpl.add_subplot().plot([1, 2, 3])
    mpl.axes[0].set_title("Matplotlib title")
    df = pd.DataFrame({"x": range(20), "y": [(i * 3) % 7 for i in range(20)]})
    report = bf.Briefing(
        bf.Plot(go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2])).update_layout(title="Plotly title")),
        bf.Plot(mpl),
        bf.lab.DataProfile(df),
        bf.lab.DataDive(df),
    )
    raw = bf.save_pdf(report, tmp_path / "charts.pdf").read_bytes()
    text = "\n".join(read_pdf(raw).pages)
    assert "Plotly title" in text  # Plotly's chart text stays real text (Matplotlib draws text as paths)
    assert "mean" in text  # DataProfile stats
    assert re.search(rb"/Subtype\s*/Image", raw) is None  # nothing rasterised: charts are vector


def test_same_layout_as_the_print_dialog(viewer: Viewer, tmp_path: Path) -> None:
    printed = read_pdf(viewer.open(_three_pages()).pdf(format="A4", print_background=True))
    saved = read_pdf(bf.save_pdf(_three_pages(), tmp_path / "q1.pdf", paper="a4").read_bytes())
    # The headers differ only by their timestamp, so compare everything after it.
    assert len(saved.pages) == len(printed.pages)
    assert saved.pages[1:] == printed.pages[1:]


@pytest.mark.parametrize(
    ("paper", "landscape", "points"),
    [("a4", False, (595, 842)), ("letter", False, (612, 792)), ("letter", True, (792, 612)), ("a3", True, (1191, 842))],
)
def test_paper_and_orientation(tmp_path: Path, paper: str, landscape: bool, points: tuple[int, int]) -> None:
    raw = bf.save_pdf(_three_pages(), tmp_path / "x.pdf", paper=paper, landscape=landscape).read_bytes()
    box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", raw)
    assert box is not None
    # Chromium sizes paper via pixels, so A4 comes out as 595.92 x 842.88 pt.
    assert float(box.group(1)) == pytest.approx(points[0], abs=1)
    assert float(box.group(2)) == pytest.approx(points[1], abs=1)


def test_landscape_uses_the_wider_line(tmp_path: Path) -> None:
    long_line = bf.Text(" ".join(f"word{i}" for i in range(120)))
    portrait = read_pdf(bf.save_pdf(bf.Briefing(long_line), tmp_path / "p.pdf").read_bytes())
    landscape = read_pdf(bf.save_pdf(bf.Briefing(long_line), tmp_path / "l.pdf", landscape=True).read_bytes())
    assert landscape.pages[0].count("\n") < portrait.pages[0].count("\n")


def test_no_network_request(tmp_path: Path, counting_server: tuple[str, list[str]]) -> None:
    url, hits = counting_server
    bf.save_pdf(bf.Briefing(bf.HTML(f'<img src="{url}/tracker.png">')), tmp_path / "x.pdf")
    assert hits == []
