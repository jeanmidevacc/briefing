"""DataDive as a reader uses it: dots on a canvas, a legend that filters, a tooltip (#16)."""
from __future__ import annotations

import time
import typing as t

import pandas as pd
from playwright.sync_api import Locator, Page, expect

import briefing as bf
from tests.test_browser.conftest import Viewer

_DF = pd.DataFrame({
    "a": range(40),
    "b": [(i * 7) % 40 for i in range(40)],
    "team": ["red"] * 20 + ["blue"] * 15 + ["green"] * 5,
    "score": [float(i) for i in range(40)],
})


def _dive(page: Page, nth: int = 0) -> Locator:
    return page.locator(".bf-datadive").nth(nth)


def _shown(dive: Locator) -> int:
    count: int = dive.evaluate("d => d.briefingDive.shown()")
    return count


def _dot(dive: Locator, i: int) -> dict[str, t.Any]:
    dot: dict[str, t.Any] = dive.evaluate("(d, i) => d.briefingDive.dot(i)", i)
    return dot


def test_one_dot_per_row_and_redraw_on_axis_change(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", color="team")))
    dive = _dive(page)
    assert _shown(dive) == 40
    before = [_dot(dive, i)["x"] for i in range(40)]
    page.locator('select[data-axis="x"]').select_option("b")
    after = [_dot(dive, i)["x"] for i in range(40)]
    assert _shown(dive) == 40 and before != after
    expect(dive.locator(".bf-dd__footer")).to_have_text("40 rows")
    expect(dive.locator("canvas")).to_have_attribute(
        "aria-label", "DataDive scatter plot of b against b, coloured by team: 40 of 40 dots")


def test_the_legend_hides_and_shows_a_category(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", color="team")))
    dive = _dive(page)
    keys = dive.locator(".bf-dd__key")
    expect(keys).to_have_count(3)
    assert keys.all_inner_texts() == ["red\n20", "blue\n15", "green\n5"]  # most frequent first
    blue = dive.get_by_role("button", name="blue 15")
    blue.click()
    expect(blue).to_have_attribute("aria-pressed", "false")
    assert _shown(dive) == 25
    expect(dive.locator(".bf-dd__footer")).to_have_text("25 of 40 shown")
    assert not _dot(dive, 25)["shown"] and _dot(dive, 0)["shown"]
    blue.click()
    assert _shown(dive) == 40


def test_alt_click_shows_one_category_alone_and_again_shows_all(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", color="team")))
    dive = _dive(page)
    green = dive.get_by_role("button", name="green 5")
    green.click(modifiers=["Alt"])
    assert _shown(dive) == 5
    assert dive.locator('.bf-dd__key[aria-pressed="true"]').all_inner_texts() == ["green\n5"]
    green.click(modifiers=["Alt"])
    assert _shown(dive) == 40


def test_changing_the_colour_column_resets_the_legend(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", color="team")))
    dive = _dive(page)
    dive.get_by_role("button", name="red 20").click()
    assert _shown(dive) == 20
    page.locator('select[data-axis="color"]').select_option("score")
    assert _shown(dive) == 40
    expect(dive.locator(".bf-dd__key")).to_have_count(0)
    expect(dive.locator(".bf-dd__ramp")).to_be_visible()
    assert dive.locator(".bf-dd__ramp-end").all_inner_texts() == ["0", "39"]
    page.locator('select[data-axis="color"]').select_option("")
    expect(dive.locator(".bf-dd__legend")).to_be_hidden()


def test_a_categorical_scale_colours_its_categories(viewer: Viewer) -> None:
    scale = bf.Scale(["#d71920", "#1a4782"], domain=["blue", "red"])
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", color="team", colors=scale)))
    dive = _dive(page)
    assert _dot(dive, 0)["colour"] == "#1a4782"  # red
    assert _dot(dive, 20)["colour"] == "#d71920"  # blue
    green = _dot(dive, 39)["colour"]
    assert green not in ("#1a4782", "#d71920")  # not in the scale: the theme's palette


def test_a_numeric_scale_places_values_on_its_domain(viewer: Viewer) -> None:
    scale = bf.Scale(["#000000", "#ffffff"], domain=(0, 78))
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", color="score", colors=scale)))
    dive = _dive(page)
    assert _dot(dive, 0)["colour"] == "#000000"
    # 39 is half way to 78: the colour Scale gives it, to within the page's 64-step ramp.
    got, want = (int(c.lstrip("#")[:2], 16) for c in (_dot(dive, 39)["colour"], scale(39)))
    assert abs(got - want) <= 3


def test_hovering_a_dot_shows_its_row(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", color="team")))
    dive = _dive(page)
    canvas = dive.locator("canvas")
    box = canvas.bounding_box()
    assert box is not None
    dot, width = _dot(dive, 7), dive.evaluate("d => d.briefingDive.width()")
    unit = box["width"] / width
    page.mouse.move(box["x"] + dot["x"] * unit, box["y"] + dot["y"] * unit)
    tip = dive.locator(".bf-dd__tooltip")
    expect(tip).to_be_visible()
    expect(tip).to_contain_text("a: 7")
    expect(tip).to_contain_text("team: red")
    page.mouse.move(box["x"] - 20, box["y"] - 20)
    expect(tip).to_be_hidden()


def test_tiles_pack_every_dot_into_its_cell(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="team", color="team", layout="tile")))
    dive = _dive(page)
    page.locator('select[data-axis="y"]').select_option("")  # "— none —": one row of tiles
    assert _shown(dive) == 40
    xs = {team: sorted({round(_dot(dive, i)["x"]) for i in range(40) if _DF["team"][i] == team})
          for team in ("blue", "green", "red")}
    assert max(xs["blue"]) < min(xs["green"]) and max(xs["green"]) < min(xs["red"])  # columns in natural order
    dive.get_by_role("button", name="red 20").click()
    assert _shown(dive) == 20


def test_a_dive_in_a_hidden_tab_draws_when_shown(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(
        bf.Page(bf.Text("First"), title="First"),
        bf.Page(bf.lab.DataDive(_DF, x="a", y="b"), title="Dive"),
    ))
    page.get_by_role("tab", name="Dive").click()
    dive = _dive(page)
    expect(dive.locator("canvas")).to_be_visible()
    box = dive.locator("canvas").bounding_box()
    assert box is not None
    page.wait_for_function("() => { const d = document.querySelector('.bf-datadive');"
                           " return Math.abs(d.briefingDive.width() - d.querySelector('canvas').clientWidth) <= 1; }")


def test_100_000_rows_stay_responsive(viewer: Viewer) -> None:
    sales = bf.datasets.load("sales", n=100_000)
    started = time.perf_counter()
    page = viewer.open(bf.Briefing(bf.lab.DataDive(sales, x="ordered_at", y="revenue", color="region")))
    dive = _dive(page)
    assert _shown(dive) == 100_000
    opened = time.perf_counter() - started
    redraw = dive.evaluate("""d => {
        const sel = d.querySelector('select[data-axis="color"]'), t = performance.now();
        sel.value = 'channel'; sel.dispatchEvent(new Event('change'));
        return performance.now() - t; }""")
    # Measured at 0.3 s to open and 40-80 ms to redraw on a laptop; CI machines are slower.
    assert opened < 10 and redraw < 1000, (opened, redraw)


def test_a_small_dive_prints_as_vector_circles(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", color="team")))
    dive = _dive(page)
    dive.get_by_role("button", name="green 5").click()
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    expect(dive.locator(".bf-dd__print circle")).to_have_count(35)  # the dots shown, not the hidden ones
    expect(dive.locator("canvas")).to_have_css("visibility", "hidden")
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    expect(dive.locator(".bf-dd__print")).to_have_count(0)
    expect(dive.locator("canvas")).to_have_css("visibility", "visible")


def test_a_big_dive_prints_as_its_canvas(viewer: Viewer) -> None:
    sales = bf.datasets.load("sales", n=6_000)
    page = viewer.open(bf.Briefing(bf.lab.DataDive(sales, x="ordered_at", y="revenue")))
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    dive = _dive(page)
    expect(dive.locator(".bf-dd__print")).to_have_count(0)
    expect(dive.locator("canvas")).to_have_css("visibility", "visible")
