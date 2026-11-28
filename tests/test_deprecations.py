"""Deprecated and removed names and features: the 0.2 aliases (gone in 0.3.0), the calendar hour view, export="pdf"."""
from __future__ import annotations

import typing as t
import warnings

import pytest

import briefing as bf

#: Names deprecated in 0.2 and removed in 0.3.0, with what to use instead.
REMOVED = [
    ("Blocks", "Briefing"),
    ("BaseBlock", "Block"),
    ("save_report", "save"),
    ("stringify_report", "stringify"),
    ("DataProfile", "lab.DataProfile"),
    ("DataDive", "lab.DataDive"),
]


@pytest.mark.parametrize(("old", "new"), REMOVED)
def test_a_removed_name_says_what_to_use_instead(old: str, new: str) -> None:
    with pytest.raises(AttributeError, match=rf"briefing\.{old} was removed in 0\.3\.0: use briefing\.{new}\."):
        getattr(bf, old)
    assert not hasattr(bf, old)


@pytest.mark.parametrize(("old", "new"), REMOVED)
def test_the_replacement_works_without_a_warning(old: str, new: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        obj: t.Any = bf
        for part in new.split("."):
            obj = getattr(obj, part)


def test_unknown_attribute_still_raises_attributeerror() -> None:
    with pytest.raises(AttributeError, match="has no attribute 'DefinitelyNotAThing'"):
        bf.DefinitelyNotAThing


# ── Plot(scale=...) (#7): deprecated in 0.1.1, removed in 0.3.0 ──────────────


def test_plot_scale_is_gone() -> None:
    import inspect

    assert "scale" not in inspect.signature(bf.Plot).parameters
    with pytest.raises(TypeError, match="scale"):
        bf.Plot(object(), scale=2.0)  # type: ignore[call-arg]


# ── CalendarHeatmap's hour view (#111): deprecated in 0.2.2, removed in 0.5.0 ──────


@pytest.mark.parametrize("views", [("hours",), ("days", "hours"), ["hours", "days"]])
def test_the_calendar_hour_view_was_removed_and_says_what_to_use(views: t.Any, df_pipeline_log: t.Any) -> None:
    expected = r"hour view .* was removed in briefing 0\.5\.0\. Use bf\.lab\.TimeHeatmap\(df, date=\.\.\., rows="
    with pytest.raises(bf.BriefingError, match=expected):
        bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", views=views)


def test_the_day_calendar_still_takes_views_days(df_pipeline_log: t.Any) -> None:
    # The deprecation told users to pass views=('days',): it keeps working, without a warning.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at")
        bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", views=("days",))


# ── Briefing(export="pdf"): the "Print" button, removed in 0.4.0 ──────────────────────────


@pytest.mark.parametrize("export", ["pdf", ("png", "pdf"), ["pdf", "png", "pdf"]])
def test_export_pdf_was_removed_in_0_4_and_says_what_to_use(export: t.Any) -> None:
    assert "pdf" not in bf.Briefing.DEPRECATED_EXPORTS
    with pytest.raises(bf.BriefingError, match=r"export='pdf'\) was removed in 0\.4\.0.*Ctrl\+P.*bf\.save_pdf"):
        bf.Briefing(bf.Text("x"), export=export)


def test_export_png_alone_does_not_warn() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bf.Briefing(bf.Text("x"), export="png")


# ── the heatmaps' center= (#175): deprecated in 0.6.0, removed in 0.8.0 (#196) ──────


@pytest.mark.parametrize("block", ["CalendarHeatmap", "TimeHeatmap"])
def test_heatmap_center_is_removed_for_a_scale(block: str, df_pipeline_log: t.Any) -> None:
    extra = {"rows": "weekday", "columns": "hour"} if block == "TimeHeatmap" else {}
    expected = (rf"{block}: center= was removed in briefing 0\.8\.0 \(deprecated since 0\.6\.0\)\. "
                r"Pass colors=bf\.Scale\(\[below, at, above\], center=\.\.\.\)")
    with pytest.raises(bf.BriefingError, match=expected):
        getattr(bf.lab, block)(df_pipeline_log, date="run_at", value="rows", center=500,
                               colors=["#d73027", "#f7f7f7", "#1a9850"], **extra)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        getattr(bf.lab, block)(df_pipeline_log, date="run_at", value="rows",
                               colors=bf.Scale(["#d73027", "#f7f7f7", "#1a9850"], center=500), **extra)


@pytest.mark.parametrize("block", ["CalendarHeatmap", "TimeHeatmap"])
def test_heatmap_center_is_out_of_the_json_form(block: str) -> None:
    assert "center" not in bf.schema()["$defs"][f"lab.{block}"]["properties"]
