"""Every report the suite builds follows the HTML contract in ``tests/contract.py``.

Scenarios (``tests/scenarios.py``) cover every block type, alone, nested and over
each shared dataframe fixture. Each rule runs against each scenario. Cases that
fail on purpose today are ``xfail(strict=True)`` and name the issue that fixes
them, so the fix turns them into an XPASS failure until the mark is removed.
"""
from __future__ import annotations

import typing as t

import pytest
from bs4 import BeautifulSoup

import briefing as bf
from briefing.blocks.base import Block
from briefing.renderers.registry import iter_blocks
from tests.contract import (
    MARKER,
    RULES,
    check_deterministic,
    check_user_text_escaped,
    parse_report,
)
from tests.scenarios import ESCAPE_SCENARIOS, HOUR_VIEW_WARNING, REPORT_NAME, SCENARIOS, Frames

pytestmark = pytest.mark.filterwarnings(HOUR_VIEW_WARNING)


#: Cases expected to fail today, as {(rule, scenario): reason}. Remove an entry
#: when its issue is fixed; strict xfail makes a stale entry fail.
KNOWN_FAILURES: dict[tuple[str, str], str] = {}


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
    # Rebuild the report for each render: the promise is same input, same bytes. Rendering one
    # object twice would miss randomness picked when a block or its data is created (#101).
    check_deterministic(lambda: bf.stringify(SCENARIOS[scenario](frames), name=REPORT_NAME))


def _all_block_types() -> set[type]:
    exported = [getattr(bf, n) for n in bf.__all__] + [getattr(bf.lab, n) for n in bf.lab.__all__]
    return {obj for obj in exported if isinstance(obj, type) and issubclass(obj, Block) and obj is not Block}


def test_every_block_type_is_covered(frames: Frames) -> None:
    covered = {type(b) for build in SCENARIOS.values() for b in iter_blocks(build(frames))}
    assert _all_block_types() - covered == set()


# ── user text stays escaped ───────────────────────────────────────────────────


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
