"""Notebook previews — a block as a complete report, isolated in its own iframe.

Jupyter and VS Code display an object's ``_repr_html_()``. A report's CSS and
script are global, so pasting two reports into one notebook page makes them
fight (shared ids, page-wide styles). Each preview is therefore a full report
in an ``<iframe srcdoc>``: it looks exactly like the saved file, and nothing
leaks in or out. A small script inside the iframe grows it to fit its content,
also after a toggle opens; the saved report itself doesn't contain it.
"""
from __future__ import annotations

import html as _html
import typing as t

if t.TYPE_CHECKING:
    from briefing.renderers.formatting import Formatting

# Runs inside the preview's own document: size the iframe holding it to the page.
_FIT_SCRIPT = (
    '<script id="bf-preview-fit">(function () {'
    "var frame; try { frame = window.frameElement; } catch (e) { return; }"
    "if (!frame) return;"
    "function fit() { frame.style.height = Math.ceil(document.documentElement.getBoundingClientRect().height) + 'px'; }"
    "fit(); window.addEventListener('load', fit);"
    "if (window.ResizeObserver) new ResizeObserver(fit).observe(document.documentElement);"
    "})();</script>"
)


def preview_html(blocks: t.Any, *, name: str = "Report", formatting: Formatting | None = None) -> str:
    """Return *blocks* rendered as a complete report inside a self-sizing ``<iframe srcdoc>``."""
    from briefing.blocks.layout import Briefing
    from briefing.renderers.html import render_report

    page = render_report(Briefing.wrap(blocks), name=name, formatting=formatting)
    end = page.rfind("</body>")
    page = page[:end] + _FIT_SCRIPT + page[end:]
    # The height is a fallback for notebooks that don't run the fit script. The text
    # inside <iframe> only shows where the iframe is stripped (an untrusted notebook).
    return (
        f'<iframe class="bf-preview" srcdoc="{_attribute(page)}" '
        f'title="{_html.escape(name, quote=True)} preview" '
        'style="width: 100%; height: 360px; border: 0; display: block;">'
        f"{_FALLBACK}</iframe>"
    )


_FALLBACK = "briefing preview: run this cell, or trust the notebook, to display it."


def _attribute(text: str) -> str:
    """*text* escaped for an HTML attribute, in pure ASCII (``&#9650;`` for ▲).

    The preview then survives a host page that doesn't declare UTF-8.
    """
    return _html.escape(text, quote=True).encode("ascii", "xmlcharrefreplace").decode("ascii")


class Preview:
    """A notebook preview of *blocks* with a report name and theme; see :func:`preview`."""

    def __init__(self, blocks: t.Any, *, name: str = "Report", formatting: Formatting | None = None) -> None:
        self.blocks = blocks
        self.name = name
        self.formatting = formatting

    def _repr_html_(self) -> str:
        return preview_html(self.blocks, name=self.name, formatting=self.formatting)


def preview(blocks: t.Any, *, name: str = "Report", formatting: Formatting | None = None) -> Preview:
    """Preview *blocks* in a notebook with a report name or a theme.

    Any block already previews itself when it is the last expression of a cell;
    use this to see it with the ``name`` and ``formatting`` you will save with.

    Args:
        blocks: A block, a list of blocks, or a :class:`~briefing.Briefing`.
        name: Report title, shown in the header as in :func:`~briefing.save`.
        formatting: The theme, as in :func:`~briefing.save`.

    Example::

        bf.preview(report, name="Q1 Analysis", formatting=bf.Formatting.dark())
    """
    return Preview(blocks, name=name, formatting=formatting)


__all__ = ["Preview", "preview", "preview_html"]
