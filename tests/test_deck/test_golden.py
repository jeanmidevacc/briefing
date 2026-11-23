"""A few decks render to the bytes stored in their golden snapshots (#197), as reports do (#45).

Accept a change to a deck's HTML with ``pytest tests/test_deck/test_golden.py --snapshot-update``.
"""
from __future__ import annotations

import typing as t
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from tests.banner_images import RED_SVG
from tests.golden import mask
from tests.scenarios import plotly_figure

GOLDEN = Path(__file__).parents[1] / "snapshots" / "golden_deck"


def _basic() -> bf.deck.Deck:
    return bf.deck.Deck(
        bf.deck.Slide(bf.Banner("# Q3 review\n\nSales and operations", image=RED_SVG)),
        bf.deck.Slide(title="Part one: the numbers"),
        bf.deck.Slide(
            bf.Text("Revenue grew in **every** region."),
            bf.Group(bf.BigNumber("Revenue", 4.2e6, prev_value=3.9e6, format="${:,.0f}"),
                     bf.BigNumber("Margin", 0.31, format="{:.0%}", name="margin"), columns=2),
            title="Summary",
            name="summary",
        ),
        bf.deck.Slide(bf.DataTable(pd.DataFrame({"region": ["North", "South"], "revenue": [412000, 287500]})),
                      title="By region"),
        footer="Sales analytics",
    )


def _from_report() -> bf.deck.Deck:
    import warnings

    report = bf.Briefing(
        bf.Page(bf.Text("## Overview\n\nRevenue grew.\n\n## Numbers {#numbers}"),
                bf.Group(bf.BigNumber("Revenue", 42), bf.BigNumber("Orders", 7), columns=2),
                title="Summary", name="summary"),
        bf.Page(bf.Text("# Detail\n\nBy region.\n\n---\n\nContinued."), title="Detail", name="detail"),
        footer="Team",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", bf.ExperimentalWarning)
        return bf.deck.from_report(report, title="Q3 review")


DECKS: dict[str, tuple[Callable[[], bf.deck.Deck], bf.Formatting | None]] = {
    "basic": (_basic, None),
    "from-report": (_from_report, None),
    "dark-theme": (_basic, bf.Formatting.dark()),
    "plotly": (lambda: bf.deck.Deck(bf.deck.Slide(bf.Plot(plotly_figure()), title="A chart")), None),
    "tabs": (lambda: bf.deck.Deck(bf.deck.Slide(bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B")))), None),
}


@pytest.mark.parametrize("name", list(DECKS))
def test_deck_matches_golden_snapshot(name: str, snapshot: t.Any) -> None:
    build, formatting = DECKS[name]
    snapshot.snapshot_dir = GOLDEN
    snapshot.assert_match(mask(bf.deck.to_html(build(), name="Golden deck", formatting=formatting)), f"{name}.html")


def test_every_snapshot_has_a_deck() -> None:
    stale = sorted({p.name for p in GOLDEN.iterdir()} - {f"{name}.html" for name in DECKS})
    assert stale == [], f"delete the snapshots of decks that no longer exist: {stale}"
