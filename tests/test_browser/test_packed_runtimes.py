"""Chart runtimes packed in the report (#38): they unpack as the page opens, before the charts draw.

Charts drawing in reports, fragments, copy-embed copies, print and PNG/PDF exports are
covered by those features' own browser tests; these check what packing itself could break.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import expect

import briefing as bf
from tests.scenarios import altair_chart, plotly_figure
from tests.test_browser.conftest import Viewer

_HOST = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Host</title>{head}</head>'
    "<body>{body}</body></html>"
)


def test_the_runtime_unpacked_is_the_installed_one(viewer: Viewer) -> None:
    from plotly.offline import get_plotlyjs_version

    page = viewer.open(bf.Plot(plotly_figure()))
    expect(page.locator(".js-plotly-plot .main-svg").first).to_be_visible()
    assert page.evaluate("window.Plotly.version") == get_plotlyjs_version()


def test_a_vega_chart_draws_from_its_packed_runtime(viewer: Viewer) -> None:
    pytest.importorskip("vl_convert")
    page = viewer.open(bf.Plot(altair_chart()))
    expect(page.locator(".bf-altair svg").first).to_be_visible()


def test_a_page_that_loads_requirejs_still_gets_plotly(viewer: Viewer) -> None:
    # RequireJS defines define.amd: an unshielded UMD bundle would register a module instead of window.Plotly.
    fragment = bf.stringify(bf.Plot(plotly_figure(), name="chart"), full_html=False)
    page = viewer.open(_HOST.format(head="<script>window.define = function () {}; window.define.amd = {};</script>",
                                    body=fragment))
    expect(page.locator("#chart .js-plotly-plot .main-svg").first).to_be_visible()


def test_scripts_run_again_one_by_one_as_a_notebook_does(viewer: Viewer) -> None:
    # Jupyter inserts HTML output, then recreates each <script> so it runs: each runs as it is inserted.
    fragment = bf.stringify(bf.Plot(plotly_figure(), name="chart"), full_html=False)
    page = viewer.open(_HOST.format(head="", body='<div id="out"></div>'))
    page.evaluate("""html => {
        const out = document.getElementById('out');
        out.innerHTML = html;
        for (const old of Array.from(out.querySelectorAll('script'))) {
            const fresh = document.createElement('script');
            fresh.text = old.text;
            old.replaceWith(fresh);
        }
    }""", fragment)
    expect(page.locator("#chart .js-plotly-plot .main-svg").first).to_be_visible()


def test_two_fragments_unpack_the_runtime_once(viewer: Viewer) -> None:
    parts = [bf.stringify(bf.Plot(plotly_figure(), name=n), full_html=False) for n in ("one", "two")]
    page = viewer.open(_HOST.format(
        head="<script>window.__unpacked = 0; Object.defineProperty(window, 'briefingUnpack', {"
             "configurable: true, set(f) { Object.defineProperty(window, 'briefingUnpack', {value: function () {"
             "window.__unpacked++; return f.apply(this, arguments); }}); }});</script>",
        body="".join(parts),
    ))
    for name in ("one", "two"):
        expect(page.locator(f"#{name} .js-plotly-plot .main-svg").first).to_be_visible()
    assert page.evaluate("window.__unpacked") == 1

