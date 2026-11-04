"""Headless Chromium renderer shared by :func:`~briefing.save_image` and :func:`~briefing.save_pdf`.

A report is written to a temporary file and opened in headless Chromium with
every network request blocked, so exports obey the same offline rule as the
report itself. Playwright is imported here, inside the functions, so
``import briefing`` never loads it.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import os
import re
import tempfile
import typing as t
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from briefing._error import BriefingError

if t.TYPE_CHECKING:
    from playwright.sync_api import Page, Route

    from briefing.renderers.formatting import Formatting

INSTALL_HINT = 'pip install "briefing[image]"'
BROWSER_HINT = "playwright install chromium"

#: A Briefing, a block, a list of blocks, or the path to a saved report.html.
ReportSource = t.Any

# True once every chart and lab block on the page has drawn.
_DRAWN_JS = """() =>
  [...document.querySelectorAll('.js-plotly-plot')].every(e => e.querySelector('.main-svg')) &&
  [...document.querySelectorAll('.bf-altair')].every(e => e.querySelector('svg, canvas')) &&
  [...document.querySelectorAll('.bf-datadive')].every(e => {
    const data = e.querySelector('.bf-dd__data');
    return !data || JSON.parse(data.textContent).length === 0 || e.querySelector('.bf-dd__dot');
  }) &&
  document.fonts.status === 'loaded'
"""

# Top-level pages render as one tabbed Select at the root of the report.
_PAGES_JS = """() => {
  const sel = document.querySelector('.bf-blocks > .bf-select:only-child:not(.bf-select--dropdown)');
  return sel ? [...sel.querySelectorAll(':scope > .bf-select__tablist > .bf-select__tab')].map(t => t.textContent) : [];
}"""

# While exporting one page, the root tab bar is noise.
_EXPORT_CSS = ".bf-blocks > .bf-select:only-child > .bf-select__tablist { display: none !important; }"


@dataclass(frozen=True)
class ReportPage:
    """One top-level page of a report: its position, tab title and block ``name``."""

    index: int
    title: str
    name: str | None


def _playwright() -> t.Any:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BriefingError(f"Exporting images and PDFs needs Playwright. Install it with: {INSTALL_HINT}") from exc
    return sync_playwright


def browser_error(exc: BaseException) -> BriefingError | None:
    """The error to raise when Playwright is installed but its Chromium is not, else ``None``."""
    message = str(exc)
    if "Executable doesn't exist" in message or "playwright install" in message:
        return BriefingError(f"Playwright's Chromium browser isn't installed. Run: {BROWSER_HINT}")
    return None


def _report_html(
    report: ReportSource, name: str, formatting: Formatting | None
) -> tuple[str, list[str | None]]:
    """The report's HTML and the ``name`` of each top-level page (empty for a saved file)."""
    if isinstance(report, str | os.PathLike):
        path = Path(report)
        if not path.is_file():
            raise BriefingError(f"No saved report at {path}. Pass a Briefing, a block, or the path to a .html file.")
        return path.read_text(encoding="utf-8"), []
    from briefing.blocks.layout import Briefing, Page
    from briefing.renderers.html import render_report

    wrapped = Briefing.wrap(report)
    names = [b.name for b in wrapped.blocks] if all(isinstance(b, Page) for b in wrapped.blocks) else []
    return render_report(wrapped, name=name, formatting=formatting), names


def _block_network(route: Route) -> None:
    if route.request.url.startswith(("http:", "https:", "ws:", "wss:")):
        route.abort()
    else:
        route.continue_()


class Session:
    """A report open in headless Chromium, ready to show a page and capture it."""

    def __init__(self, page: Page, names: list[str | None]) -> None:
        self.page = page
        titles: list[str] = page.evaluate(_PAGES_JS)
        self.pages = [
            ReportPage(i, title, names[i] if len(names) == len(titles) else None) for i, title in enumerate(titles)
        ]
        page.add_style_tag(content=_EXPORT_CSS)

    def resolve(self, page: str | int) -> list[ReportPage | None]:
        """The pages a ``page=`` argument selects; ``[None]`` is the whole report when it has no pages."""
        if page == "all":
            return list(self.pages) or [None]
        if isinstance(page, int):
            if not self.pages and page == 0:
                return [None]
            if 0 <= page < len(self.pages):
                return [self.pages[page]]
            raise BriefingError(f"page={page} is out of range: the report has {len(self.pages) or 1} page(s).")
        # A page's block name wins over a title that happens to match.
        found: list[ReportPage | None] = [p for p in self.pages if p.name == page]
        found = found or [p for p in self.pages if p.title == page]
        if found:
            return found[:1]
        titles = ", ".join(repr(p.title) for p in self.pages) or "none (the report has no Page blocks)"
        raise BriefingError(f"No page named {page!r}. Pages: {titles}. Pass a title, a block name or an index.")

    def show(self, target: ReportPage | None) -> None:
        """Show one top-level page (by clicking its tab, so charts resize), or leave the report as is."""
        if target is not None:
            self.page.evaluate(
                """i => document.querySelector('.bf-blocks > .bf-select:only-child')
                     .querySelectorAll(':scope > .bf-select__tablist > .bf-select__tab')[i].click()""",
                target.index,
            )
        self.wait_drawn()

    def expand(self) -> None:
        """Open every toggle, outer ones first, so hidden content is captured."""
        self.page.evaluate(
            """() => document.querySelectorAll('.bf-toggle__header[aria-expanded="false"]')
                   .forEach(h => h.click())"""
        )
        self.wait_drawn()

    def wait_drawn(self) -> None:
        self.page.wait_for_function(_DRAWN_JS, timeout=30_000)
        # Let charts that just became visible finish resizing.
        self.page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    def background(self) -> str:
        """The report's background colour, to pad preset images with."""
        colour: str = self.page.evaluate("() => getComputedStyle(document.body).backgroundColor")
        return colour


@contextlib.contextmanager
def open_report(
    report: ReportSource,
    *,
    width: int,
    scale: float,
    name: str = "Report",
    formatting: Formatting | None = None,
) -> Iterator[Session]:
    """Open *report* in headless Chromium at *width* CSS pixels and *scale* device pixels per pixel."""
    sync_playwright = _playwright()
    html, names = _report_html(report, name, formatting)
    with tempfile.TemporaryDirectory(prefix="briefing-export-") as tmp, sync_playwright() as pw:
        source = Path(tmp) / "report.html"
        source.write_text(html, encoding="utf-8")
        try:
            browser = pw.chromium.launch()
        except Exception as exc:  # Playwright raises its own Error type
            error = browser_error(exc)
            if error is not None:
                raise error from exc
            raise
        try:
            # A short viewport: a full-page capture is never shorter than it, so the
            # content alone sets the image height.
            context = browser.new_context(viewport={"width": width, "height": 100}, device_scale_factor=scale)
            context.route("**/*", _block_network)
            page = context.new_page()
            page.goto(source.as_uri())
            page.wait_for_load_state("load")
            session = Session(page, names)
            session.wait_drawn()
            yield session
        finally:
            browser.close()


_T = t.TypeVar("_T")


def outside_event_loop(fn: t.Callable[[], _T]) -> _T:
    """Run *fn* here, or in a worker thread when this thread runs an asyncio loop.

    Playwright's sync API refuses to run inside an event loop, and a Jupyter
    notebook always has one running; a fresh thread has none.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return fn()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="briefing-export") as pool:
        return pool.submit(fn).result()


def slug(title: str, index: int) -> str:
    """A file-name-safe version of a page title."""
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or f"page_{index + 1}"
