"""lab.CalendarHeatmap as a reader sees it (#19)."""
from __future__ import annotations

import typing as t

import pandas as pd
import pytest
from playwright.sync_api import Page

import briefing as bf
from tests.test_browser.conftest import Viewer


@pytest.mark.parametrize("theme", ["default", "dark"])
def test_zero_no_data_and_below_target_are_visibly_different(viewer: Viewer, df_pipeline_log: pd.DataFrame,
                                                             theme: str) -> None:
    formatting = bf.Formatting.dark() if theme == "dark" else bf.Formatting()
    block = bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", value="rows", expected=500)
    page = viewer.open(bf.Briefing(block), formatting=formatting)

    def look(day: str) -> dict[str, str]:
        style: dict[str, str] = page.locator(f'rect[data-date="{day}"]').evaluate(
            "e => { const s = getComputedStyle(e); return {fill: s.fill, stroke: s.stroke, dash: s.strokeDasharray}; }")
        return style

    background = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    zero, empty, ok = look("2025-12-04"), look("2026-01-17"), look("2025-11-18")
    assert zero["fill"] not in ("none", background)  # a zero is a filled grey cell
    assert empty["fill"] == "none"  # no data is an outline only
    assert look("2026-01-03")["stroke"] == "rgb(220, 38, 38)"  # a failed run is flagged red
    assert ok["stroke"] in ("none", "")  # a normal day has no outline


def _year() -> pd.DataFrame:
    """One run a day through 2025: 53 week columns, a calendar 774 px wide at its natural size."""
    days = pd.date_range("2025-01-01", "2025-12-31", freq="D")
    return pd.DataFrame({"run_at": days, "rows": range(len(days))})


def _width(page: Page, selector: str) -> float:
    box = page.locator(selector).first.bounding_box()
    assert box is not None
    return float(box["width"])


def test_a_year_fills_the_width_of_its_block(viewer: Viewer) -> None:
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(_year(), date="run_at")))
    assert _width(page, "svg.bf-cal__days") == pytest.approx(_width(page, ".bf-cal__scroll"), abs=1)
    assert _width(page, 'rect[data-date="2025-06-02"]') > 14  # cells grew from their natural 11 px


def test_a_short_range_grows_to_twice_its_natural_size(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    calendar = bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", label="Calendar")
    page = viewer.open(bf.Briefing(bf.Select(bf.Text("first", label="Text"), calendar)))
    page.get_by_role("tab", name="Calendar").click()  # a calendar in a hidden tab is measured once shown
    natural = float(page.locator("svg.bf-cal__days").get_attribute("width") or 0)
    assert _width(page, "svg.bf-cal__days") == pytest.approx(2 * natural, abs=1)
    assert _width(page, 'rect[data-date="2026-01-05"]') == pytest.approx(22, abs=0.5)


def test_labels_grow_at_half_the_rate_and_swatches_match_cells(viewer: Viewer,
                                                                 df_pipeline_log: pd.DataFrame) -> None:
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at")))
    label = page.locator("svg.bf-cal__days text.bf-cal__weekday").first.bounding_box()
    assert label is not None and label["height"] < 20  # 9 px text at 2x would be about 24 px tall
    cell = _width(page, 'rect[data-date="2026-01-05"]')
    assert _width(page, ".bf-cal__swatch:not(.bf-cal__swatch--event-day)") == pytest.approx(cell, abs=0.5)


def test_a_calendar_in_a_group_fits_its_column(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    year = bf.lab.CalendarHeatmap(_year(), date="run_at")
    page = viewer.open(bf.Briefing(bf.Group(year, bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at"), columns=2)))
    columns = page.locator(".bf-group > .bf-calendar")
    first, second = columns.nth(0).bounding_box(), columns.nth(1).bounding_box()
    assert first is not None and second is not None
    assert first["width"] == pytest.approx(second["width"], abs=1)  # the year no longer widens its column
    assert _width(page, "svg.bf-cal__days") == pytest.approx(first["width"], abs=1)
    assert _width(page, 'rect[data-date="2025-06-02"]') < 11  # shrunk to fit
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")


def test_a_narrow_screen_shrinks_then_scrolls(viewer: Viewer) -> None:
    viewer.page.set_viewport_size({"width": 375, "height": 800})
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(_year(), date="run_at")))
    assert _width(page, 'rect[data-date="2025-06-02"]') == pytest.approx(0.6 * 11, abs=0.3)  # the floor
    overflow = page.locator(".bf-cal__scroll").evaluate("e => e.scrollWidth > e.clientWidth")
    assert overflow
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")  # inside the block
    label = page.locator("svg.bf-cal__days text.bf-cal__weekday").first.bounding_box()
    assert label is not None and label["height"] > 6  # labels shrink at half the rate


def test_a_year_prints_without_clipping(viewer: Viewer) -> None:
    viewer.page.set_viewport_size({"width": 794, "height": 1123})  # A4 at 96 dpi
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(_year(), date="run_at")))
    page.emulate_media(media="print")
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    scroll = page.locator(".bf-cal__scroll").bounding_box()
    last = page.locator('rect[data-date="2025-12-31"]').bounding_box()
    assert scroll is not None and last is not None
    assert last["x"] + last["width"] <= scroll["x"] + scroll["width"] + 0.5


def test_clicking_a_day_lists_its_rows(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", on_click="rows")))
    panel = page.locator(".bf-cal__panel")
    assert not panel.is_visible()
    page.locator('rect[data-date="2025-12-07"]').click()
    assert panel.is_visible()
    assert "2025-12-07" in panel.locator(".bf-cal__panel-title").inner_text()
    assert panel.locator("tbody tr").count() == 2
    assert panel.locator("thead th").all_inner_texts() == ["run_at", "team", "rows"]
    panel.get_by_role("button", name="Close").click()
    assert not panel.is_visible()


def test_keyboard_opens_the_rows_of_a_day(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    block = bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", on_click="rows")
    page = viewer.open(bf.Briefing(block))
    page.locator('rect[data-date="2025-12-07"]').focus()
    page.keyboard.press("Enter")
    assert "2025-12-07" in page.locator(".bf-cal__panel-title").inner_text()


def test_capped_cells_say_so_and_values_stay_text(viewer: Viewer) -> None:
    df = pd.DataFrame({"run_at": [pd.Timestamp("2026-01-05 09:00")] * 120,
                       "note": ["<img src=x onerror=window.__hit=1>"] * 120})
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df, date="run_at", on_click="rows")))
    page.locator('rect[data-date="2026-01-05"]').click()
    panel = page.locator(".bf-cal__panel")
    assert panel.locator("tbody tr").count() == 50
    assert "first 50 of 120 rows" in panel.inner_text()
    assert panel.locator("img").count() == 0 and page.evaluate("() => window.__hit") is None


# ── hover tooltip (#109) ──────────────────────────────────────────────────────


def _tip_box(page: Page) -> dict[str, float]:
    tip = page.locator(".bf-cal__tip")
    assert tip.is_visible()
    box = tip.bounding_box()
    assert box is not None
    return {"x": box["x"], "y": box["y"], "width": box["width"], "height": box["height"]}


def test_hovering_a_day_shows_its_exact_value_at_once(viewer: Viewer) -> None:
    df = pd.DataFrame({"day": pd.to_datetime(["2026-01-05", "2026-01-06"]), "amount": [12345.67, 3.0]})
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df, date="day", value="amount")))
    tip = page.locator(".bf-cal__tip")
    assert not tip.is_visible()
    cell = page.locator('rect[data-date="2026-01-05"]')
    cell.hover()
    assert tip.is_visible()  # no delay: visible as soon as the pointer is over the cell
    assert tip.locator("strong").inner_text() == "Mon 2026-01-05"
    assert "12,345.67 amount" in tip.inner_text()
    cell_box, box = cell.bounding_box(), _tip_box(page)
    assert cell_box is not None and box["y"] + box["height"] <= cell_box["y"]  # above the cell
    page.mouse.move(0, 0)
    assert not tip.is_visible()


def test_the_native_tooltip_no_longer_doubles_up(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at")))
    assert page.locator(".bf-calendar svg title").count() == 0
    assert page.locator("rect.bf-cal__day[data-tip]").count() == page.locator("rect.bf-cal__day").count()


def test_event_bands_have_tooltips(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    events = pd.DataFrame({"start": ["2025-12-22"], "end": ["2026-01-02"], "label": ["Freeze"]})
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", events=events)))
    page.locator("g.bf-cal__event").first.hover()
    assert "Freeze" in page.locator(".bf-cal__tip").inner_text()


def test_keyboard_focus_and_tap_show_the_tooltip(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", on_click="rows")))
    cell = page.locator('rect[data-date="2025-12-07"]')
    cell.focus()
    assert page.locator(".bf-cal__tip strong").inner_text() == "Sun 2025-12-07"
    assert cell.get_attribute("aria-label") is not None  # clickable cells keep their name
    page.keyboard.press("Escape")
    assert not page.locator(".bf-cal__tip").is_visible()
    other = page.locator('rect[data-date="2025-12-08"]')
    other.dispatch_event("pointerdown", {"pointerType": "touch", "bubbles": True})
    assert page.locator(".bf-cal__tip strong").inner_text() == "Mon 2025-12-08"
    cell.click()  # the rows panel still opens, titled from the same text
    assert "2025-12-07" in page.locator(".bf-cal__panel-title").inner_text()


def test_the_tooltip_stays_inside_the_window(viewer: Viewer) -> None:
    viewer.page.set_viewport_size({"width": 375, "height": 800})
    days = pd.date_range("2025-01-01", "2025-12-31", freq="D")
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(pd.DataFrame({"run_at": days}), date="run_at")))
    page.locator('rect[data-date="2025-01-06"]').scroll_into_view_if_needed()
    page.evaluate("() => window.scrollTo(0, document.querySelector('svg.bf-cal__days').getBoundingClientRect().top"
                  " + window.scrollY - 30)")  # the first row sits right under the top of the window
    cell = page.locator('rect[data-date="2025-01-06"]')
    cell.hover()
    cell_box, box = cell.bounding_box(), _tip_box(page)
    assert cell_box is not None and box["y"] >= cell_box["y"] + cell_box["height"]  # flipped below the cell
    assert box["x"] >= 0 and box["x"] + box["width"] <= 375


def test_the_tooltip_never_prints(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at")))
    page.locator('rect[data-date="2025-12-07"]').hover()
    page.emulate_media(media="print")
    assert not page.locator(".bf-cal__tip").is_visible()


def test_weekday_labels_do_not_overlap_when_shrunk(viewer: Viewer) -> None:
    viewer.page.set_viewport_size({"width": 375, "height": 800})  # a year at the 0.6x floor (#113)
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(_year(), date="run_at")))
    boxes = page.locator("svg.bf-cal__days text.bf-cal__weekday").evaluate_all(
        "els => els.map(e => { const b = e.getBoundingClientRect(); return [b.top, b.height]; })")
    assert len(boxes) == 7
    boxes.sort()
    # A text box includes line spacing (about 1.25x the glyphs); the glyphs stay apart when the
    # rows are at least 0.8 of a box apart.
    assert all(below[0] - above[0] >= 0.8 * above[1] for above, below in zip(boxes, boxes[1:], strict=False))


def _rgb(page: Page, selector: str, prop: str) -> list[int]:
    """A computed colour of the first match, read back as RGB through a canvas (it may be oklab())."""
    return t.cast("list[int]", page.locator(selector).first.evaluate(f"""el => {{
        const c = document.createElement('canvas').getContext('2d');
        c.fillStyle = getComputedStyle(el).{prop}; c.fillRect(0, 0, 1, 1);
        return Array.from(c.getImageData(0, 0, 1, 1).data.slice(0, 3)); }}"""))


def test_events_take_their_own_colour(viewer: Viewer, df_pipeline_log: pd.DataFrame) -> None:
    events = pd.DataFrame({"start": ["2026-02-03", "2026-01-05"], "end": [None, None],
                           "label": ["Incident", "Plain"], "color": ["#00ff00", None]})
    page = viewer.open(bf.Briefing(bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", events=events)),
                       formatting=bf.Formatting(accent_color="#ff0000"))
    assert _rgb(page, ".bf-cal__event--day[style] circle", "fill") == [0, 255, 0]
    assert _rgb(page, ".bf-cal__event--day:not([style]) circle", "fill") == [255, 0, 0]
    assert _rgb(page, 'rect[data-date="2026-02-03"]', "stroke") == [0, 255, 0]
    assert _rgb(page, ".bf-cal__swatch--event-day[style]", "backgroundColor") == [0, 255, 0]
