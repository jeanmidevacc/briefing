"""``bf.save_pdf``: a report as one PDF, laid out like the browser's print dialog."""
from __future__ import annotations

import typing as t
from pathlib import Path

from briefing._error import BriefingError
from briefing.export._render import ReportSource, open_report, outside_event_loop

if t.TYPE_CHECKING:
    from briefing.renderers.formatting import Formatting

#: Paper sizes in millimetres (portrait), by the names save_pdf accepts.
PAPERS: dict[str, tuple[float, float]] = {
    "a3": (297, 420), "a4": (210, 297), "a5": (148, 210), "letter": (215.9, 279.4), "legal": (215.9, 355.6),
}
_MARGIN_MM = 12  # report.css: @page { margin: 12mm }

# Print only the chosen top-level page (and its label) instead of all of them.
_ONE_PAGE_CSS = """
html.bf-printing .bf-blocks > .bf-select:only-child > .bf-select__panel:not([data-bf-export]),
html.bf-printing .bf-blocks > .bf-select:only-child > .bf-print-label:has(+ .bf-select__panel:not([data-bf-export])) {
  display: none !important;
}
"""


def save_pdf(
    report: ReportSource,
    path: str | Path,
    *,
    page: str | int = "all",
    paper: str = "a4",
    landscape: bool = False,
    name: str = "Report",
    formatting: Formatting | None = None,
) -> Path:
    """Save a report as a PDF, rendered in headless Chromium with the print stylesheet.

    The layout is the one the browser's print dialog gives: every tab printed
    under its label, toggles open, controls hidden, each top-level ``Page`` on a
    new sheet. Text stays selectable, links clickable and charts vector. Needs
    ``pip install "briefing[image]"`` and, once, ``playwright install chromium``;
    rendering is offline.

    Args:
        report: A :class:`~briefing.Briefing`, a block or a list of blocks, or the
            path to a saved report ``.html``.
        path: Destination ``.pdf`` file.
        page: ``"all"`` for every page in one PDF, or one page by title, ``name``
            or 0-based index.
        paper: ``"a4"`` (default), ``"letter"``, ``"legal"``, ``"a3"`` or ``"a5"``.
        landscape: Turn the paper sideways; the report uses the wider line.
        name: Report title, when ``report`` is a block (as in :func:`~briefing.save`).
        formatting: Theme, when ``report`` is a block (as in :func:`~briefing.save`).

    Returns:
        The path written.

    Raises:
        BriefingError: For an unknown paper, page or suffix, or when Playwright or
            its Chromium isn't installed (the message says how to install it).

    Example::

        bf.save_pdf(report, "q1.pdf")                          # every page
        bf.save_pdf(report, "summary.pdf", page="Summary", paper="letter")
    """
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        raise BriefingError(f"save_pdf writes .pdf files, not {path.suffix or 'no suffix'!r}.")
    if paper.lower() not in PAPERS:
        raise BriefingError(f"Unknown paper {paper!r}: use one of {', '.join(PAPERS)}.")
    width_mm, height_mm = PAPERS[paper.lower()]
    line_mm = (height_mm if landscape else width_mm) - 2 * _MARGIN_MM

    def render() -> Path:
        with open_report(report, width=1200, scale=1, name=name, formatting=formatting) as session:
            (target,) = session.resolve(page) if page != "all" else [None]
            if target is not None:
                session.page.evaluate(
                    """i => document.querySelector('.bf-blocks > .bf-select:only-child')
                         .querySelectorAll(':scope > .bf-select__panel')[i].setAttribute('data-bf-export', '')""",
                    target.index,
                )
                session.page.add_style_tag(content=_ONE_PAGE_CSS)
            session.page.evaluate(
                "w => document.documentElement.style.setProperty('--bf-print-width', w)", f"{line_mm}mm"
            )
            # Lay the print layout out and let charts resize before Chromium takes the PDF
            # (page.pdf fires beforeprint again; the handlers are idempotent).
            session.page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
            session.wait_drawn()
            pdf = session.page.pdf(
                format=paper.upper() if len(paper) == 2 else paper.capitalize(),
                landscape=landscape,
                print_background=True,
            )
        path.write_bytes(pdf)
        return path

    return outside_event_loop(render)
