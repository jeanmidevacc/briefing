"""Every scenario renders to the bytes stored in its golden snapshot (#45).

Each scenario in ``tests/scenarios.py`` has ``tests/snapshots/golden/<scenario>.html``:
the report rendered with a fixed date, then masked by ``tests/golden.py`` (briefing's
static files become a hash; chart libraries' output and the version become markers).

Any change to a report's HTML fails here until it is accepted with::

    pytest tests/test_golden.py --snapshot-update

which rewrites the snapshots, so the change shows up as a diff in the pull request.
"""
from __future__ import annotations

import typing as t
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from tests.golden import NOW, mask, static_files, static_marker
from tests.scenarios import REPORT_NAME, SCENARIOS, Frames

GOLDEN = Path(__file__).parent / "snapshots" / "golden"

#: DataProfile prints pandas' dtype names, which pandas 3 changed (``object`` → ``str``,
#: ``datetime64[ns]`` → ``datetime64[us]``). These snapshots hold the pandas 3 names.
PANDAS_3_ONLY = {"dataprofile-df_constant", "dataprofile-df_mixed", "dataprofile-df_single_row", "everything"}


def _pandas_major() -> int:
    return int(pd.__version__.split(".")[0])


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_report_matches_golden_snapshot(scenario: str, frames: Frames, snapshot: t.Any) -> None:
    if scenario in PANDAS_3_ONLY and _pandas_major() < 3:
        pytest.skip("its snapshot shows the dtype names of pandas 3")
    html = bf.stringify(SCENARIOS[scenario](frames), name=REPORT_NAME, now=NOW)
    snapshot.snapshot_dir = GOLDEN
    snapshot.assert_match(mask(html), f"{scenario}.html")


def test_every_snapshot_has_a_scenario() -> None:
    stale = sorted({p.name for p in GOLDEN.iterdir()} - {f"{s}.html" for s in SCENARIOS})
    assert stale == [], f"delete the snapshots of scenarios that no longer exist: {stale}"


# ── the mask hides only what it should ────────────────────────────────────────


def test_mask_replaces_each_inlined_file_with_its_hash() -> None:
    masked = mask(bf.stringify(bf.Briefing(bf.Text("x")), now=NOW))
    for path in ("static/report.css", "static/report.js"):
        assert static_marker(path, static_files()[path]) in masked
    assert static_files()["static/report.js"] not in masked
    assert "lab/static/lab.js" not in masked


def test_mask_keeps_a_file_that_was_changed_on_the_way_in() -> None:
    js = static_files()["static/report.js"]
    html = bf.stringify(bf.Briefing(bf.Text("x")), now=NOW).replace(js, js.replace("function", "function ", 1))
    assert "golden: static/report.js" not in mask(html)


def test_mask_shows_svg_ids_briefing_left_unscoped() -> None:
    figure = '<figure class="bf-block bf-plot"><svg><g id="mpl-1-a"></g><g id="axes_1"></g></svg>\n</figure>'
    assert mask(figure) == (
        '<figure class="bf-block bf-plot"><!-- golden: SVG from Matplotlib, ids id="axes_1" mpl-1- --></figure>'
    )


def test_mask_replaces_the_version() -> None:
    masked = mask(bf.stringify(bf.Briefing(bf.Text("x")), now=NOW))
    assert bf.__version__ not in masked
    assert '<meta name="generator" content="briefing {version}" />' in masked
