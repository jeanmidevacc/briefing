"""Browser-test fixtures: open rendered reports in headless Chromium, offline.

Every test here is marked ``browser`` automatically. Run them with
``pytest -m browser`` after a one-time ``playwright install chromium``.
"""
from __future__ import annotations

import typing as t
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route

import briefing as bf

_NOW = datetime(2024, 1, 2, 3, 4, tzinfo=UTC)
_HERE = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if _HERE in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.browser)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, t.Any]) -> dict[str, t.Any]:
    # Wide enough that a chart drawn at Plotly's 700 px default is visibly too narrow.
    return {**browser_context_args, "viewport": {"width": 1366, "height": 900}}


class Viewer:
    """Opens reports in the test's page and records what must not happen."""

    def __init__(self, page: Page, tmp_path: Path) -> None:
        self.page = page
        self._tmp_path = tmp_path
        self.external_requests: list[str] = []
        self.errors: list[str] = []
        page.context.route("**/*", self._route)
        page.on("pageerror", lambda exc: self.errors.append(str(exc)))

    def _route(self, route: Route) -> None:
        url = route.request.url
        if url.startswith(("http:", "https:", "ws:", "wss:")):
            self.external_requests.append(url)
            route.abort()
        else:
            route.continue_()

    def open(self, report: bf.Block | str, **kwargs: t.Any) -> Page:
        """Render *report* (or take a ready HTML string), save it, and load it from disk."""
        html = report if isinstance(report, str) else bf.stringify(report, now=_NOW, **kwargs)
        path = self._tmp_path / "report.html"
        path.write_text(html, encoding="utf-8")
        self.page.goto(path.as_uri())
        self.page.wait_for_load_state("load")
        return self.page


@pytest.fixture
def viewer(page: Page, tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[Viewer]:
    v = Viewer(page, tmp_path)
    yield v
    # An xfail test reports its own failure; don't turn it into a teardown error.
    if request.node.get_closest_marker("xfail") is None:
        assert v.external_requests == [], f"the report made network requests: {v.external_requests}"
        assert v.errors == [], f"JavaScript errors: {v.errors}"
