"""Every report the suite builds follows the HTML contract in ``tests/contract.py``.

Scenarios cover every block type, alone, nested and over each shared dataframe
fixture. Each rule runs against each scenario. Cases that fail on purpose today
are ``xfail(strict=True)`` and name the issue that fixes them, so the fix turns
them into an XPASS failure until the mark is removed.
"""
from __future__ import annotations

import typing as t
from collections.abc import Callable

import pandas as pd
import pytest
from bs4 import BeautifulSoup

import briefing as bf
from briefing.blocks.base import Block
from briefing.renderers.registry import iter_blocks
from tests.banner_images import RED_SVG
from tests.contract import (
    MARKER,
    PAYLOAD,
    RULES,
    check_deterministic,
    check_user_text_escaped,
    parse_report,
)

# The "calendar" scenario keeps the deprecated hour view (#111) so the contract still covers it.
pytestmark = pytest.mark.filterwarnings("ignore:CalendarHeatmap. the hour view:DeprecationWarning")

Frames = Callable[[str], pd.DataFrame]
Build = Callable[[Frames], bf.Briefing]

#: Shared dataframes from ``conftest.py`` that the data blocks are rendered over.
FRAME_FIXTURES = ["df_mixed", "df_empty", "df_single_row", "df_all_null", "df_constant"]
REPORT_NAME = "Contract report"


# ── figures (imported lazily, skipped when the library is missing) ────────────


def _matplotlib_figure(kind: str = "line") -> t.Any:
    figure = pytest.importorskip("matplotlib.figure")
    fig = figure.Figure(figsize=(4, 3))
    ax = fig.add_subplot()
    if kind == "line":
        ax.plot([1, 2, 3], [3, 1, 2], marker="o")
    else:
        ax.bar(["a", "b"], [2, 5])
    return fig


def _plotly_figure() -> t.Any:
    go = pytest.importorskip("plotly.graph_objects")
    return go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2]))


def _altair_chart() -> t.Any:
    alt = pytest.importorskip("altair")
    return alt.Chart(pd.DataFrame({"x": [1, 2, 3], "y": [3, 1, 2]})).mark_point().encode(x="x", y="y")


# ── scenarios ─────────────────────────────────────────────────────────────────


def _tabs(*blocks: Block) -> bf.Select:
    return bf.Select(*blocks)


#: Data blocks, each rendered over every fixture in FRAME_FIXTURES.
FRAME_BLOCKS: dict[str, Callable[[pd.DataFrame], Block]] = {
    "table": lambda frame: bf.Table(frame, caption="Table"),
    "datatable": lambda frame: bf.DataTable(frame, caption="DataTable"),
    "dataprofile": lambda frame: bf.lab.DataProfile(frame),
    "datadive": lambda frame: bf.lab.DataDive(frame),
}


def _over_frame(make: Callable[[pd.DataFrame], Block], fixture: str) -> Build:
    return lambda df: bf.Briefing(make(df(fixture)))


def _infinite_frame() -> pd.DataFrame:
    return pd.DataFrame({"x": [1.0, float("inf"), float("-inf"), None, 2.5], "n": [1, 2, 3, 4, 5]})


def _over_infinite(make: Callable[[pd.DataFrame], Block]) -> Build:
    return lambda _: bf.Briefing(make(_infinite_frame()))


SCENARIOS: dict[str, Build] = {
    "text": lambda _: bf.Briefing(bf.Text("# Title\n\nSome *markdown* with a [link](https://example.com).")),
    "text-markdown-table": lambda _: bf.Briefing(bf.Text("| a | b |\n| --- | --- |\n| 1 | 2 |")),
    "html": lambda _: bf.Briefing(bf.HTML("<p>Raw <b>HTML</b></p><ul><li>item</li></ul>")),
    "code": lambda _: bf.Briefing(bf.Code("SELECT 1 FROM t", language="sql", caption="Query")),
    "formula": lambda _: bf.Briefing(bf.Formula(r"\frac{a}{b}", caption="Ratio")),
    "bignumber": lambda _: bf.Briefing(
        bf.Group(
            bf.BigNumber("Revenue", "$4.2M", change="+3%", is_upward_change=True),
            bf.BigNumber("Churn", 0.12, change="-1%", is_upward_change=False),
            bf.BigNumber("Users", 1200),
            columns=3,
        )
    ),
    "alert": lambda _: bf.Briefing(bf.Alert("Drift detected.", level="warning", title="Heads up")),
    "group-widths": lambda _: bf.Briefing(bf.Group(bf.Text("a"), bf.Text("b"), columns=2, widths=[3, 1])),
    "select-tabs": lambda _: bf.Briefing(_tabs(bf.Text("a", label="A"), bf.Text("b", label="B"))),
    "select-dropdown": lambda _: bf.Briefing(
        bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B"), type="dropdown")
    ),
    "toggle": lambda _: bf.Briefing(bf.Toggle(bf.Text("hidden"), bf.Text("more"), label="More")),
    "pages": lambda _: bf.Briefing(bf.Page(bf.Text("one"), title="One"), bf.Page(bf.Text("two"), title="Two")),
    "nested-layout": lambda _: bf.Briefing(
        _tabs(
            bf.Group(
                bf.Toggle(bf.Text("x"), label="T1"),
                _tabs(bf.Text("a", label="A"), bf.Text("b", label="B")),
                label="Outer",
            ),
            bf.Toggle(_tabs(bf.Text("c", label="C"), bf.Text("d", label="D")), label="T2"),
        ),
        bf.Toggle(bf.Toggle(bf.Text("deep"), label="Inner"), label="Outer toggle"),
    ),
    "plot-matplotlib": lambda _: bf.Briefing(bf.Plot(_matplotlib_figure(), caption="Line")),
    "plot-plotly": lambda _: bf.Briefing(bf.Plot(_plotly_figure(), caption="Scatter")),
    "plot-altair": lambda _: bf.Briefing(bf.Plot(_altair_chart(), caption="Points")),
    "two-matplotlib-plots": lambda _: bf.Briefing(
        bf.Plot(_matplotlib_figure("line")), bf.Plot(_matplotlib_figure("bar"))
    ),
    "table-styler": lambda df: bf.Briefing(bf.Table(df("df_constant").style.highlight_max(), caption="Styled")),
    **{
        f"{kind}-{fixture}": _over_frame(make, fixture)
        for kind, make in FRAME_BLOCKS.items()
        for fixture in FRAME_FIXTURES
    },
    **{f"{kind}-infinite": _over_infinite(make) for kind, make in FRAME_BLOCKS.items()},
    "calendar": lambda df: bf.Briefing(bf.lab.CalendarHeatmap(
        df("df_pipeline_log"), date="run_at", value="rows", group="team", expected=500, events=df("df_events"),
        views=("days", "hours"), tz="America/Montreal", on_click="rows")),
    "calendar-diverging": lambda df: bf.Briefing(
        bf.lab.CalendarHeatmap(df("df_signed"), date="day", value="balance", center=0,
                               colors=["#d73027", "#f7f7f7", "#1a9850"], week_start="sunday")),
    "banner": lambda _: bf.Briefing(
        bf.Banner("# Cover\n\nA **subtitle**.", image=RED_SVG, text_position=55, opacity=80),
        bf.Banner("## Left", image=RED_SVG, side="left", text_position=40, focus=(20, 80), alt="A red field"),
    ),
    "export-menu": lambda _: bf.Briefing(
        bf.Page(bf.Text("# One"), title="One"), bf.Page(bf.Text("# Two"), title="Two"), export=("png", "pdf")
    ),
    "everything": lambda df: bf.Briefing(
        bf.Text("# Everything"),
        bf.Group(bf.BigNumber("A", 1), bf.Alert("note"), columns=2),
        _tabs(
            bf.Group(bf.HTML("<i>raw</i>"), bf.Code("x = 1"), bf.Formula("x^2"), label="Text"),
            bf.Group(bf.Plot(_matplotlib_figure()), bf.Plot(_plotly_figure()), label="Plots"),
            bf.Group(bf.Table(df("df_mixed")), bf.DataTable(df("df_mixed")), label="Tables"),
            bf.Group(bf.lab.DataProfile(df("df_mixed")), bf.lab.DataDive(df("df_mixed")), label="Lab"),
        ),
        bf.Toggle(bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B"), type="dropdown"), label="More"),
    ),
}

#: Cases expected to fail today, as {(rule, scenario): reason}. Remove an entry
#: when its issue is fixed; strict xfail makes a stale entry fail.
KNOWN_FAILURES: dict[tuple[str, str], str] = {
    **{("generator_meta", s): "#23: no generator meta tag yet" for s in SCENARIOS},
}


@pytest.fixture
def frames(request: pytest.FixtureRequest) -> Frames:
    return t.cast(Frames, request.getfixturevalue)


_parsed: dict[str, BeautifulSoup] = {}


def _render(scenario: str, frames: Frames) -> BeautifulSoup:
    """Render and parse *scenario* once per session; rules only read the result."""
    if scenario not in _parsed:
        report = SCENARIOS[scenario](frames)
        _parsed[scenario] = parse_report(bf.stringify(report, name=REPORT_NAME))
    return _parsed[scenario]


def _cases(rules: list[str], scenarios: list[str]) -> list[t.Any]:
    cases = []
    for rule in rules:
        for scenario in scenarios:
            reason = KNOWN_FAILURES.get((rule, scenario))
            marks = [pytest.mark.xfail(reason=reason, strict=True)] if reason else []
            cases.append(pytest.param(rule, scenario, marks=marks, id=f"{rule}:{scenario}"))
    return cases


# ── every rule × every scenario ───────────────────────────────────────────────


@pytest.mark.parametrize(("rule", "scenario"), _cases(list(RULES), list(SCENARIOS)))
def test_report_follows_rule(rule: str, scenario: str, frames: Frames) -> None:
    RULES[rule](_render(scenario, frames))


@pytest.mark.parametrize(("rule", "scenario"), _cases(["deterministic"], list(SCENARIOS)))
def test_report_is_deterministic(
    rule: str, scenario: str, frames: Frames, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    report = SCENARIOS[scenario](frames)
    check_deterministic(lambda: bf.stringify(report, name=REPORT_NAME))


def _all_block_types() -> set[type]:
    exported = [getattr(bf, n) for n in bf.__all__] + [getattr(bf.lab, n) for n in bf.lab.__all__]
    return {obj for obj in exported if isinstance(obj, type) and issubclass(obj, Block) and obj is not Block}


def test_every_block_type_is_covered(frames: Frames) -> None:
    covered = {type(b) for build in SCENARIOS.values() for b in iter_blocks(build(frames))}
    assert _all_block_types() - covered == set()


# ── user text stays escaped ───────────────────────────────────────────────────


def _payload_frame() -> pd.DataFrame:
    return pd.DataFrame({PAYLOAD: [PAYLOAD, "plain"], "n": [1, 2]})


#: Every user-supplied string set to PAYLOAD. ``Text`` and ``HTML`` content is
#: raw markup by design (see CLAUDE.md), so only their labels are tested.
ESCAPE_SCENARIOS: dict[str, Callable[[], tuple[bf.Briefing, str]]] = {
    "report-name": lambda: (bf.Briefing(bf.Text("x")), PAYLOAD),
    "select-tab-labels": lambda: (bf.Briefing(_tabs(bf.Text("a", label=PAYLOAD), bf.Text("b", label=PAYLOAD))), "R"),
    "select-dropdown-labels": lambda: (
        bf.Briefing(bf.Select(bf.Text("a", label=PAYLOAD), bf.HTML("<b>b</b>", label=PAYLOAD), type="dropdown")),
        "R",
    ),
    "toggle-label": lambda: (bf.Briefing(bf.Toggle(bf.Text("a"), label=PAYLOAD)), "R"),
    "page-titles": lambda: (bf.Briefing(bf.Page(bf.Text("a"), title=PAYLOAD), bf.Page(bf.Text("b"), title="2")), "R"),
    "code": lambda: (bf.Briefing(bf.Code(PAYLOAD, language=PAYLOAD, caption=PAYLOAD)), "R"),
    "formula": lambda: (bf.Briefing(bf.Formula(PAYLOAD, caption=PAYLOAD)), "R"),
    "bignumber": lambda: (bf.Briefing(bf.BigNumber(PAYLOAD, PAYLOAD, change=PAYLOAD, is_upward_change=True)), "R"),
    "alert": lambda: (bf.Briefing(bf.Alert(PAYLOAD, title=PAYLOAD)), "R"),
    "plot-caption": lambda: (bf.Briefing(bf.Plot(_matplotlib_figure(), caption=PAYLOAD)), "R"),
    "table": lambda: (bf.Briefing(bf.Table(_payload_frame(), caption=PAYLOAD)), "R"),
    "datatable": lambda: (bf.Briefing(bf.DataTable(_payload_frame(), caption=PAYLOAD)), "R"),
    "dataprofile": lambda: (bf.Briefing(bf.lab.DataProfile(_payload_frame())), "R"),
    "datadive": lambda: (bf.Briefing(bf.lab.DataDive(_payload_frame(), color=PAYLOAD)), "R"),
    "banner-alt": lambda: (bf.Briefing(_tabs(bf.Banner("x", image=RED_SVG, alt=PAYLOAD, label=PAYLOAD),
                                             bf.Text("b", label="B"))), "R"),
    "calendar": lambda: (bf.Briefing(bf.lab.CalendarHeatmap(
        pd.DataFrame({"day": pd.to_datetime(["2026-01-05", "2026-01-06"]), "who": [PAYLOAD, "b"]}),
        date="day", group="who", events=pd.DataFrame({"start": ["2026-01-05"], "label": [PAYLOAD]}),
        on_click="rows")), "R"),
}


@pytest.mark.parametrize(("rule", "scenario"), _cases(["user_text_escaped"], list(ESCAPE_SCENARIOS)))
def test_user_text_escaped(rule: str, scenario: str) -> None:
    report, name = ESCAPE_SCENARIOS[scenario]()
    soup = parse_report(bf.stringify(report, name=name))
    check_user_text_escaped(soup)
    # The payload's text must survive somewhere visible, not just vanish.
    assert MARKER in soup.get_text()


# ── the rules reject bad reports ──────────────────────────────────────────────

_GOOD = (
    '<!DOCTYPE html><html lang="en"><head><title>R</title>'
    f'<meta name="generator" content="briefing {bf.__version__}"><style>.a {{ color: red }}</style></head>'
    '<body><a href="https://example.com">a link is fine</a><img src="data:image/png;base64,AAAA">'
    '<button aria-controls="p">x</button><div id="p" class="bf-text"><p>| not a table</p></div>'
    '<script type="application/json">{"a": 1}</script></body></html>'
)


def _data_iframe(html: str) -> str:
    import base64

    return f'<iframe src="data:text/html;base64,{base64.b64encode(html.encode()).decode()}"></iframe>'


BAD_REPORTS: list[t.Any] = [
    pytest.param("no_external_urls", '<script src="https://cdn.example.com/x.js"></script>', id="script-src"),
    pytest.param("no_external_urls", '<link rel="stylesheet" href="//cdn.example.com/x.css">', id="link-href"),
    pytest.param("no_external_urls", '<div style="background: url(https://x.example/y.png)"></div>', id="css-url"),
    pytest.param("no_external_urls", '<style>@import "https://x.example/a.css";</style>', id="css-import"),
    pytest.param("no_external_urls", _data_iframe('<script src="https://cdn.example.com/v.js"></script>'),
                 id="data-iframe"),
    pytest.param("no_external_urls", '<iframe srcdoc="<img src=&quot;http://x.example/a.png&quot;>"></iframe>',
                 id="srcdoc-iframe"),
    pytest.param("unique_ids", '<div id="a"></div><span id="a"></span>', id="duplicate-id"),
    pytest.param("aria_references", '<button aria-controls="missing">x</button>', id="aria-controls"),
    pytest.param("aria_references", '<div id="a" aria-labelledby="a missing"></div>', id="aria-labelledby"),
    pytest.param("json_scripts_parse", '<script type="application/json">{"a": </script>', id="bad-json"),
    pytest.param("markdown_rendered", '<div class="bf-text"><p>| a | b |\n| --- | --- |</p></div>', id="raw-table"),
    pytest.param("document_head", "<html><head></head><body></body></html>", id="no-title-no-lang"),
    pytest.param("document_head", '<html lang="en"><head><title>a</title><title>b</title></head></html>',
                 id="two-titles"),
    pytest.param("generator_meta", '<html lang="en"><head><title>a</title></head></html>', id="no-generator"),
    pytest.param("user_text_escaped", f'<img src="x" onerror="{MARKER}()">', id="event-handler"),
    pytest.param("user_text_escaped", f"<script>{MARKER}()</script>", id="script"),
]


def test_rules_accept_a_good_report() -> None:
    soup = parse_report(_GOOD)
    for rule in RULES.values():
        rule(soup)
    check_user_text_escaped(soup)


@pytest.mark.parametrize(("rule", "html"), BAD_REPORTS)
def test_rule_rejects_bad_report(rule: str, html: str) -> None:
    check = check_user_text_escaped if rule == "user_text_escaped" else RULES[rule]
    with pytest.raises(AssertionError):
        check(parse_report(html))


def test_deterministic_rejects_changing_output() -> None:
    renders = iter(["<p>1</p>", "<p>2</p>"])
    with pytest.raises(AssertionError, match="differ"):
        check_deterministic(lambda: next(renders))
