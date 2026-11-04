"""Browser-test fixtures: open rendered reports in headless Chromium, offline.

Every test here is marked ``browser`` automatically. Run them with
``pytest -m browser`` after a one-time ``playwright install chromium``.
"""
from __future__ import annotations

import http.server
import threading
import typing as t
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route

import briefing as bf

_NOW = datetime(2024, 1, 2, 3, 4, tzinfo=UTC)

#: WCAG 2 contrast ratio between two CSS colours, computed in the page: page.evaluate(CONTRAST_JS, [fg, bg]).
CONTRAST_JS = """([fg, bg]) => {
  const ctx = document.createElement('canvas').getContext('2d');
  const rgb = c => { ctx.fillStyle = '#000'; ctx.fillStyle = c; ctx.fillRect(0, 0, 1, 1);
    return Array.from(ctx.getImageData(0, 0, 1, 1).data).slice(0, 3); };
  const lin = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  const lum = c => { const [r, g, b] = rgb(c).map(lin);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
}"""
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


@pytest.fixture
def counting_server() -> Iterator[tuple[str, list[str]]]:
    hits: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            hits.append(self.path)
            self.send_response(404)
            self.end_headers()

        def log_message(self, *args: object) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", hits
    server.shutdown()
