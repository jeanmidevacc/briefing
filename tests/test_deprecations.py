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


# ── CalendarHeatmap's hour view (#111) ────────────────────────────────────────


@pytest.mark.parametrize("views", [("hours",), ("days", "hours"), ["hours", "days"]])
def test_the_calendar_hour_view_warns_and_still_renders(views: tuple[str, ...], df_pipeline_log: t.Any) -> None:
    expected = r"hour view .* deprecated since briefing 0\.2\.2.*issues/111"
    with pytest.warns(DeprecationWarning, match=expected) as caught:
        block = bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", views=views)
    assert caught[0].filename == __file__  # points at the caller's line (stacklevel=2)
    assert "bf-cal__hours" in bf.stringify(bf.Briefing(block))


def test_the_day_calendar_alone_does_not_warn(df_pipeline_log: t.Any) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at")
        bf.lab.CalendarHeatmap(df_pipeline_log, date="run_at", views=("days",))


# ── Briefing(export="pdf"): the "Print" button ────────────────────────────────


@pytest.mark.parametrize("export", ["pdf", ("png", "pdf"), ["pdf", "png", "pdf"]])
def test_export_pdf_warns_once_and_adds_no_button(export: t.Any) -> None:
    expected = r"export='pdf'.*deprecated.*Ctrl\+P.*bf\.save_pdf.*0\.4\.0"
    with pytest.warns(DeprecationWarning, match=expected) as caught:
        report = bf.Briefing(bf.Text("x"), export=export)
    assert len(caught) == 1
    assert caught[0].filename == __file__  # points at the caller's line (stacklevel=3)
    assert "pdf" not in report.export


def test_export_png_alone_does_not_warn() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bf.Briefing(bf.Text("x"), export="png")


def test_export_pdf_is_rejected_from_0_4() -> None:
    # Fails from 0.4 on until "pdf" leaves Briefing.DEPRECATED_EXPORTS and raises BriefingError.
    version = tuple(int(part) for part in bf.__version__.split(".")[:2])
    if version >= (0, 4):
        assert "pdf" not in bf.Briefing.DEPRECATED_EXPORTS
