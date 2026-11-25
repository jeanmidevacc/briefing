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


# ── facets and buckets= ─────────────────────────────────────────────────────────


def test_facet_columns_split_the_dots_into_panels(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", color="team", facet_col="team")))
    dive = _dive(page)
    assert _shown(dive) == 40
    xs = {team: [_dot(dive, i)["x"] for i in range(40) if _DF["team"][i] == team] for team in ("blue", "green", "red")}
    # One panel per team, in natural order, side by side: every blue dot left of every green one, and so on.
    assert max(xs["blue"]) < min(xs["green"]) and max(xs["green"]) < min(xs["red"])
    heads = dive.locator(".bf-dd__axes .bf-dd__head").all_text_contents()
    assert heads == ["blue", "green", "red"]
    # Shared scales: across every panel, a dot's height is one linear function of its b.
    ys, bs = [_dot(dive, i)["y"] for i in range(40)], list(_DF["b"])
    slope = (ys[1] - ys[0]) / (bs[1] - bs[0])
    assert all(abs(ys[i] - ys[0] - slope * (bs[i] - bs[0])) < 0.5 for i in range(40))
    page.locator('select[data-axis="fcol"]').select_option("")
    expect(dive.locator(".bf-dd__axes .bf-dd__head")).to_have_count(0)


def test_facet_rows_stack_panels_and_the_legend_still_filters(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", color="team", facet_row="team")))
    dive = _dive(page)
    ys = {team: [_dot(dive, i)["y"] for i in range(40) if _DF["team"][i] == team] for team in ("blue", "green", "red")}
    assert max(ys["blue"]) < min(ys["green"]) and max(ys["green"]) < min(ys["red"])
    dive.get_by_role("button", name="red 20").click()
    assert _shown(dive) == 20


def test_numbers_split_into_round_buckets(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", facet_col="score", buckets={"score": 4})))
    dive = _dive(page)
    assert dive.locator(".bf-dd__axes .bf-dd__head").all_text_contents() == ["0–10", "10–20", "20–30", "30–40"]


def test_a_category_keeps_its_most_frequent_values_and_an_other(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b", facet_col="team", buckets=2)))
    dive = _dive(page)
    assert dive.locator(".bf-dd__axes .bf-dd__head").all_text_contents() == ["blue", "red", "other"]
    others = [_dot(dive, i)["x"] for i in range(35, 40)]  # the five green rows
    reds = [_dot(dive, i)["x"] for i in range(20)]
    assert min(others) > max(reds)


def test_tiles_split_into_facets_with_one_dot_size(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="team", color="team", layout="tile", facet_col="score",
                                                   buckets={"score": 2})))
    dive = _dive(page)
    assert _shown(dive) == 40
    assert dive.locator(".bf-dd__axes .bf-dd__head").all_text_contents() == ["0–20", "20–40"]
    low = [_dot(dive, i)["x"] for i in range(20)]
    high = [_dot(dive, i)["x"] for i in range(20, 40)]
    assert max(low) < min(high)


# ── record cards and title= ─────────────────────────────────────────────────────

_NAMED = _DF.assign(name=[f"Player {i}" for i in range(40)],
                    page=[f"https://example.org/p/{i}" if i % 2 == 0 else "not a link" for i in range(40)])


def _click_dot(page: Page, dive: Locator, i: int) -> None:
    box = dive.locator("canvas").bounding_box()
    assert box is not None
    dot, unit = _dot(dive, i), box["width"] / dive.evaluate("d => d.briefingDive.width()")
    page.mouse.click(box["x"] + dot["x"] * unit, box["y"] + dot["y"] * unit)


def _cards(dive: Locator) -> list[dict[str, t.Any]]:
    cards: list[dict[str, t.Any]] = dive.evaluate("d => d.briefingDive.cards()")
    return cards


def test_clicking_a_dot_opens_its_card_with_every_column(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_NAMED, x="a", y="b", color="team", title="name")))
    dive = _dive(page)
    _click_dot(page, dive, 8)
    card = dive.locator(".bf-dd__card")
    expect(card).to_have_count(1)
    expect(card.locator(".bf-dd__card-title")).to_have_text("Player 8")
    assert card.locator("dt").all_inner_texts() == ["a", "b", "team", "score", "name", "page"]
    assert card.locator("dd").all_inner_texts()[:3] == ["8", "16", "red"]
    link = card.locator("dd a")
    expect(link).to_have_attribute("href", "https://example.org/p/8")
    expect(link).to_have_attribute("rel", "noopener noreferrer")
    expect(dive.locator(".bf-dd__picked")).to_have_count(1)  # its dot is ringed
    _click_dot(page, dive, 9)  # another dot replaces an unpinned card
    expect(card.locator(".bf-dd__card-title")).to_have_text("Player 9")
    expect(card.locator("dd a")).to_have_count(0)  # "not a link" stays text


def test_the_tooltip_is_headed_by_the_title(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_NAMED, x="a", y="b", title="name")))
    dive = _dive(page)
    box = dive.locator("canvas").bounding_box()
    assert box is not None
    dot, unit = _dot(dive, 3), box["width"] / dive.evaluate("d => d.briefingDive.width()")
    page.mouse.move(box["x"] + dot["x"] * unit, box["y"] + dot["y"] * unit)
    expect(dive.locator(".bf-dd__tip-title")).to_have_text("Player 3")


def test_two_pinned_cards_sit_side_by_side(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_NAMED, x="a", y="b", title="name")))
    dive = _dive(page)
    _click_dot(page, dive, 1)
    dive.get_by_role("button", name="Pin", exact=True).click()
    _click_dot(page, dive, 2)
    assert _cards(dive) == [{"row": 1, "pinned": True}, {"row": 2, "pinned": False}]
    dive.get_by_role("button", name="Pin", exact=True).click()
    _click_dot(page, dive, 3)
    assert _cards(dive) == [{"row": 1, "pinned": True}, {"row": 2, "pinned": True}, {"row": 3, "pinned": False}]
    boxes = [dive.locator(".bf-dd__card").nth(k).bounding_box() for k in range(2)]
    assert boxes[0] and boxes[1] and abs(boxes[0]["y"] - boxes[1]["y"]) < 1  # side by side
    dive.get_by_role("button", name="Pin", exact=True).click()  # a third pin: the oldest pinned card goes
    assert _cards(dive) == [{"row": 2, "pinned": True}, {"row": 3, "pinned": True}]
    expect(dive.locator(".bf-dd__picked--pinned")).to_have_count(2)


def test_cards_close_with_their_button_or_escape(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_NAMED, x="a", y="b", title="name")))
    dive = _dive(page)
    _click_dot(page, dive, 4)
    dive.get_by_role("button", name="Close the card of Player 4").click()
    expect(dive.locator(".bf-dd__card")).to_have_count(0)
    _click_dot(page, dive, 5)
    dive.get_by_role("button", name="Pin", exact=True).click()
    _click_dot(page, dive, 6)
    page.keyboard.press("Escape")
    expect(dive.locator(".bf-dd__card")).to_have_count(0)
    expect(dive.locator(".bf-dd__picked")).to_have_count(0)


def test_without_a_title_a_card_is_headed_by_its_row(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b")))
    dive = _dive(page)
    _click_dot(page, dive, 11)
    expect(dive.locator(".bf-dd__card-title")).to_have_text("Row 12")


# ── search and filters ──────────────────────────────────────────────────────────


def _search(page: Page, dive: Locator, text: str) -> None:
    """Type *text* in the search box, and wait for the pause in typing that applies it."""
    dive.locator(".bf-dd__search").fill(text)
    page.wait_for_function("(t) => document.querySelector('.bf-datadive').briefingDive.searched() === t", arg=text)


def _matches(dive: Locator) -> int:
    count: int = dive.evaluate("d => d.briefingDive.matches()")
    return count


def test_search_highlights_the_matching_dots(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_NAMED, x="a", y="b", color="team", title="name")))
    dive = _dive(page)
    _search(page, dive, "player 1")  # Player 1 and Player 10–19
    assert _matches(dive) == 11
    assert _shown(dive) == 40  # Highlight: the others stay, dimmed
    expect(dive.locator(".bf-dd__footer")).to_have_text("11 of 40 match")
    results = dive.locator(".bf-dd__result")
    expect(results).to_have_count(8)
    expect(results.first).to_have_text("Player 1")
    expect(dive.locator(".bf-dd__result-more")).to_have_text("11 rows match")
    dive.locator(".bf-dd__search").press("Enter")  # opens the first match's card
    expect(dive.locator(".bf-dd__card-title")).to_have_text("Player 1")
    dive.get_by_role("button", name="Filter", exact=True).click()
    assert _shown(dive) == 11
    expect(dive.locator(".bf-dd__footer")).to_have_text("11 of 40 shown")
    _search(page, dive, "")
    assert _shown(dive) == 40
    expect(dive.locator(".bf-dd__results")).to_be_hidden()


def test_a_category_filter(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b")))
    dive = _dive(page)
    dive.locator(".bf-dd__add").select_option("team")
    chip = dive.locator(".bf-dd__chip")
    assert chip.locator(".bf-dd__chip-option").all_inner_texts() == ["red\n20", "blue\n15", "green\n5"]
    chip.locator(".bf-dd__chip-option", has_text="red").locator("input").uncheck()
    expect(chip.locator(".bf-dd__chip-count")).to_have_text("2 of 3")
    assert _matches(dive) == 20
    dive.get_by_role("button", name="Filter", exact=True).click()
    assert _shown(dive) == 20 and not _dot(dive, 0)["shown"]
    dive.get_by_role("button", name="Remove the filter on team").click()
    assert _shown(dive) == 40


def test_a_number_range_filter(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b")))
    dive = _dive(page)
    dive.locator(".bf-dd__add").select_option("score")
    dive.get_by_label("score at least").fill("10")
    dive.get_by_label("score at least").press("Tab")
    dive.get_by_label("score at most").fill("19.5")
    dive.get_by_label("score at most").press("Tab")
    assert _matches(dive) == 10  # 10 to 19


def test_a_date_range_filter(viewer: Viewer) -> None:
    days = pd.DataFrame({"day": pd.date_range("2026-01-01", periods=30, freq="D"), "v": range(30)})
    page = viewer.open(bf.Briefing(bf.lab.DataDive(days, x="day", y="v")))
    dive = _dive(page)
    dive.locator(".bf-dd__add").select_option("day")
    dive.get_by_label("day at least").fill("2026-01-10")
    dive.get_by_label("day at least").press("Tab")
    dive.get_by_label("day at most").fill("2026-01-12")
    dive.get_by_label("day at most").press("Tab")
    assert _matches(dive) == 3  # the 10th, 11th and 12th, the last day whole


def test_an_embedding_map_finds_its_articles(viewer: Viewer) -> None:
    points = bf.datasets.load("embeddings")
    page = viewer.open(bf.Briefing(bf.lab.DataDive(points, x="x", y="y", color="cluster", title="title")))
    dive = _dive(page)
    _search(page, dive, "music article 7")  # Music article 7, 70–79
    assert _matches(dive) == 11
    dive.locator(".bf-dd__result", has_text="Music article 7").first.click()
    expect(dive.locator(".bf-dd__card-title")).to_have_text("Music article 7")
    row = dive.evaluate("d => d.briefingDive.cards()[0].row")
    assert points["title"][row] == "Music article 7" and points["cluster"][row] == "music"


# ── motion and zoom ─────────────────────────────────────────────────────────────


def _view(dive: Locator) -> dict[str, float]:
    view: dict[str, float] = dive.evaluate("d => d.briefingDive.view()")
    return view


def _ctrl_wheel(page: Page, dive: Locator, times: int, at: tuple[float, float] = (0.5, 0.5)) -> None:
    box = dive.locator("canvas").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] * at[0], box["y"] + box["height"] * at[1])
    page.keyboard.down("Control")
    for _ in range(times):
        page.mouse.wheel(0, -120)
    page.keyboard.up("Control")


def test_changing_an_axis_moves_the_dots_to_their_new_places(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b")))
    dive = _dive(page)
    page.locator('select[data-axis="y"]').select_option("score")
    assert dive.evaluate("d => d.briefingDive.moving()")
    page.wait_for_function("() => !document.querySelector('.bf-datadive').briefingDive.moving()", timeout=2000)


def test_no_motion_when_the_reader_asks_for_less(viewer: Viewer) -> None:
    viewer.page.emulate_media(reduced_motion="reduce")
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b")))
    dive = _dive(page)
    page.locator('select[data-axis="y"]').select_option("score")
    assert not dive.evaluate("d => d.briefingDive.moving()")


_GRID = pd.DataFrame({"gx": [i % 20 for i in range(400)], "gy": [i // 20 for i in range(400)],
                      "name": [f"Point {i}" for i in range(400)]})


def test_ctrl_wheel_zooms_and_a_plain_wheel_scrolls(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_GRID, x="gx", y="gy", title="name")))
    dive = _dive(page)
    zoom_out = dive.get_by_role("button", name="Zoom out")
    expect(zoom_out).to_be_disabled()
    box = dive.locator("canvas").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -120)  # a plain wheel: the page scrolls, and a hint says how to zoom
    expect(dive.locator(".bf-dd__hint")).to_be_visible()
    assert _view(dive) == {"x0": 0, "x1": 1, "y0": 0, "y1": 1}
    _ctrl_wheel(page, dive, 8)
    view = _view(dive)
    assert view["x1"] - view["x0"] < 0.2 and view["y1"] - view["y0"] < 0.2
    assert 0.3 < (view["x0"] + view["x1"]) / 2 < 0.7  # around the pointer, here the middle
    expect(zoom_out).to_be_enabled()
    expect(dive.locator(".bf-dd__label").first).to_be_visible()  # close up, dots carry their title
    in_view = dive.evaluate("d => { let k = 0; for (let i = 0; i < 400; i++) { const x = d.briefingDive.dot(i).x;"
                            " if (x === x) k++; } return k; }")
    assert 0 < in_view < 40  # the others are out of view
    expect(dive.locator(".bf-dd__label")).to_have_count(in_view)
    dive.locator("canvas").dblclick()
    assert _view(dive) == {"x0": 0, "x1": 1, "y0": 0, "y1": 1}
    expect(dive.locator(".bf-dd__label")).to_have_count(0)


def test_the_zoom_buttons(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b")))
    dive = _dive(page)
    dive.get_by_role("button", name="Zoom in").click()
    assert _view(dive) == {"x0": 0.25, "x1": 0.75, "y0": 0.25, "y1": 0.75}
    dive.get_by_role("button", name="Zoom out").click()
    assert _view(dive) == {"x0": 0, "x1": 1, "y0": 0, "y1": 1}
    dive.get_by_role("button", name="Zoom in").click()
    dive.get_by_role("button", name="Show all the data again").click()
    assert _view(dive) == {"x0": 0, "x1": 1, "y0": 0, "y1": 1}


def test_dragging_pans_and_is_not_a_click(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="a", y="b")))
    dive = _dive(page)
    dive.get_by_role("button", name="Zoom in").click()
    box = dive.locator("canvas").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 + 80, box["y"] + box["height"] / 2 + 40, steps=6)
    page.mouse.up()
    view = _view(dive)
    assert view["x0"] < 0.25 and view["y0"] > 0.25  # dragged right and down: further left and up
    assert view["x1"] - view["x0"] == 0.5
    assert dive.evaluate("d => d.briefingDive.cards()") == []


def test_a_click_on_a_zoomed_dot_opens_its_card(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_NAMED, x="a", y="b", title="name")))
    dive = _dive(page)
    dive.get_by_role("button", name="Zoom in").click()
    in_view = "(d, i) => d.briefingDive.dot(i).x === d.briefingDive.dot(i).x"
    row = next(i for i in range(40) if dive.evaluate(in_view, i))
    _click_dot(page, dive, row)
    expect(dive.locator(".bf-dd__card-title")).to_have_text(f"Player {row}")


def test_tiles_do_not_zoom(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.DataDive(_DF, x="team", layout="tile")))
    expect(_dive(page).locator(".bf-dd__zoom")).to_be_hidden()
