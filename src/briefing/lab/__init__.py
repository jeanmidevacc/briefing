"""``briefing.lab`` — custom-visualisation blocks.

These are richer, more opinionated visualisations kept out of the core grammar
so it stays small and dependency-free:

* :class:`DataProfile` — per-column statistics with inline SVG mini-charts.
* :class:`DataDive` — Facets Dive-style interactive dot explorer.
* :class:`CalendarHeatmap` — GitHub-style calendar of daily activity.

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

from briefing.lab._blocks import CalendarHeatmap, DataDive, DataProfile
from briefing.lab._render_calendar import render_calendar
from briefing.lab._render_datadive import render_datadive
from briefing.lab._render_profile import render_profile
from briefing.renderers.registry import IdGen, register_renderer

_LAB_JS = (files("briefing.lab") / "static" / "lab.js").read_text(encoding="utf-8")


def _render_profile_block(block: DataProfile, _: IdGen) -> str:
    return render_profile(block)


def _render_datadive_block(block: DataDive, _: IdGen) -> str:
    return render_datadive(block)


register_renderer(DataProfile, _render_profile_block)
register_renderer(DataDive, _render_datadive_block, js_asset=_LAB_JS)


def _render_calendar_block(block: CalendarHeatmap, idgen: IdGen) -> str:
    return render_calendar(block, idgen)


register_renderer(CalendarHeatmap, _render_calendar_block)

__all__ = ["CalendarHeatmap", "DataDive", "DataProfile"]
