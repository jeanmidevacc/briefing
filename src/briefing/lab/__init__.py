"""``briefing.lab`` — custom-visualisation blocks.

These are richer, more opinionated visualisations kept out of the core grammar
so it stays small and dependency-free:

* :class:`DataProfile` — per-column statistics with inline SVG mini-charts.
* :class:`DataCompare` — datasets compared column by column (train and test…).
* :class:`DataDive` — Facets Dive-style interactive dot explorer.
* :class:`CalendarHeatmap` — GitHub-style calendar of daily activity.
* :class:`TimeHeatmap` — when something usually happens: weekday by hour, month by year…

Install with ``pip install briefing[lab]``. Importing this module registers the
blocks with the renderer, so ``briefing.stringify``/``briefing.save`` can render
them once it has been imported (``briefing`` imports it automatically when it is
importable).

Usage::

    import briefing as bf

    bf.save(
        bf.Briefing(
            bf.lab.DataProfile(df),
            bf.lab.DataDive(df, x="revenue", y="margin", color="region"),
        ),
        "report.html",
    )
"""
from __future__ import annotations

from importlib.resources import files

from briefing.lab._blocks import CalendarHeatmap, DataCompare, DataDive, DataProfile, Legend, TimeHeatmap
from briefing.lab._render_calendar import render_calendar, render_legend
from briefing.lab._render_compare import render_compare
from briefing.lab._render_datadive import render_datadive
from briefing.lab._render_profile import render_profile
from briefing.lab._render_timeheatmap import render_timeheatmap
from briefing.renderers.registry import IdGen, register_renderer

_LAB_JS = (files("briefing.lab") / "static" / "lab.js").read_text(encoding="utf-8")


def _render_profile_block(block: DataProfile, _: IdGen) -> str:
    return render_profile(block)


def _render_datadive_block(block: DataDive, _: IdGen) -> str:
    return render_datadive(block)


register_renderer(DataProfile, _render_profile_block)


def _render_compare_block(block: DataCompare, _: IdGen) -> str:
    return render_compare(block)


_COMPARE_CSS = (files("briefing.lab") / "static" / "compare.css").read_text(encoding="utf-8")
_COMPARE_JS = (files("briefing.lab") / "static" / "compare.js").read_text(encoding="utf-8")
register_renderer(DataCompare, _render_compare_block, js_asset=_COMPARE_JS, css_asset=_COMPARE_CSS)
register_renderer(DataDive, _render_datadive_block, js_asset=_LAB_JS)


def _render_calendar_block(block: CalendarHeatmap, idgen: IdGen) -> str:
    return render_calendar(block, idgen)


_CALENDAR_JS = (files("briefing.lab") / "static" / "calendar.js").read_text(encoding="utf-8")
register_renderer(CalendarHeatmap, _render_calendar_block, js_asset=_CALENDAR_JS)


def _render_timeheatmap_block(block: TimeHeatmap, _: IdGen) -> str:
    return render_timeheatmap(block)


# The time-pattern grid shares the calendar's script: sizing, tooltips, the rows panel (#111).
register_renderer(TimeHeatmap, _render_timeheatmap_block, js_asset=_CALENDAR_JS)

def _render_legend_block(block: Legend, _: IdGen) -> str:
    return render_legend(block)


register_renderer(Legend, _render_legend_block)  # no script: a legend is static (#177)

__all__ = ["CalendarHeatmap", "DataCompare", "DataDive", "DataProfile", "Legend", "TimeHeatmap"]
