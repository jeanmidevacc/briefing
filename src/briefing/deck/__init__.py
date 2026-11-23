"""Slide decks (#197): briefing's blocks on slides, in one self-contained HTML file.

A deck is written like a report: a :class:`Deck` of :class:`Slide` objects, each holding
any of briefing's blocks. It runs in the browser like a report, so every block keeps its
own renderer (charts stay interactive, tables sort) and the report's theme applies.

Example::

    deck = bf.deck.Deck(
        bf.deck.Slide(bf.Banner("# Q3 review", image="cover.jpg")),
        bf.deck.Slide(bf.Text("Revenue grew in **every** region."), title="Summary"),
        bf.deck.Slide(bf.Plot(fig), title="Revenue by month"),
        footer="Sales analytics",
    )
    bf.deck.save(deck, "q3-review.html", name="Q3 review")
    spec, data = bf.to_spec(deck)  # its JSON form: {"briefing": 1, "slides": [...]}
"""
from __future__ import annotations

import typing as t
import webbrowser
from collections.abc import Mapping
from pathlib import Path

from briefing.deck._blocks import Deck, Slide
from briefing.deck._convert import from_report
from briefing.deck._export import save_image, save_pdf
from briefing.deck._render import render_deck
from briefing.renderers.formatting import Formatting
from briefing.renderers.size import DEFAULT_MAX_SIZE, Part, check_size, parse_size


def _render(deck: Deck, name: str, formatting: Formatting | None, max_size: int | str | None) -> str:
    limit = parse_size(max_size)
    parts: list[Part] | None = [] if limit is not None else None
    html = render_deck(deck, name=name, formatting=formatting, parts=parts, stacklevel=4)  # the caller's line
    check_size(html, parts or [], limit, stacklevel=3)  # 3: _render <- to_html/save <- the caller
    return html


def to_html(
    deck: Deck,
    *,
    name: str = "Deck",
    formatting: Formatting | None = None,
    max_size: int | str | None = DEFAULT_MAX_SIZE,
) -> str:
    """The deck as one self-contained HTML page: its slides, in the report's theme.

    Slides are drawn at 1280 × 720 and scaled to the window. The arrow keys, space and Page
    Up/Down move between them, ``O`` shows every slide, ``F`` goes full screen, and the
    address bar holds the slide's number (``#3``) or its name.

    Args:
        deck: The :class:`Deck`.
        name: The deck's title, shown in the browser tab.
        formatting: A :class:`~briefing.Formatting`: the same theme as a report's.
        max_size: Warn when the page is bigger than this, as :func:`briefing.save` does:
            a number of bytes or a size such as ``"25 MB"``; ``None`` never warns.

    Returns:
        The HTML page.

    Example::

        html = bf.deck.to_html(deck, name="Q3 review", formatting=bf.Formatting.from_accent("#0f766e"))
    """
    return _render(deck, name, formatting, max_size)


def save(
    deck: Deck,
    path: str | Path,
    *,
    open: bool = False,  # noqa: A002
    name: str = "Deck",
    formatting: Formatting | None = None,
    max_size: int | str | None = DEFAULT_MAX_SIZE,
) -> None:
    """Save the deck as one self-contained HTML file, to share as it is or print to PDF.

    Args:
        deck: The :class:`Deck`.
        path: Where to write it, such as ``"q3-review.html"``.
        open: Open it in the default browser afterwards.
        name: The deck's title, shown in the browser tab.
        formatting: A :class:`~briefing.Formatting`: the same theme as a report's.
        max_size: Warn when the file is bigger than this, as :func:`briefing.save` does.

    Example::

        bf.deck.save(deck, "q3-review.html", name="Q3 review", open=True)
    """
    html = _render(deck, name, formatting, max_size)
    dest = Path(path)
    dest.write_text(html, encoding="utf-8")
    if open:
        webbrowser.open(dest.resolve().as_uri())


def from_spec(spec: object, data: Mapping[str, t.Any] | None = None) -> Deck:
    """Build the deck a JSON form describes: ``{"briefing": 1, "slides": [...]}``.

    Each slide is an object with its ``"title"``, its ``"name"`` and its ``"blocks"``,
    written as in a report's JSON. :func:`briefing.to_spec` writes a deck's JSON, and
    :func:`briefing.validate` checks it.

    Args:
        spec: The JSON form: a dict, JSON text, or the path of a ``.json`` file.
        data: The objects its references name: ``{"sales": df, "trend": fig}``.

    Returns:
        The deck, as if written in Python.

    Raises:
        BriefingError: When the JSON can't be built into a deck; the message lists each
            problem with its place in the JSON.

    Example::

        deck = bf.deck.from_spec({
            "briefing": 1,
            "slides": [
                {"title": "Q1 sales", "blocks": [{"type": "Text", "text": "Up **8%**."}]},
                {"title": "By region", "blocks": [{"type": "DataTable", "df": {"ref": "sales"}}]},
            ],
        }, data={"sales": df})
    """
    from briefing.spec._convert import deck_from_spec

    return deck_from_spec(spec, data)


__all__ = ["Deck", "Slide", "from_report", "from_spec", "save", "save_image", "save_pdf", "to_html"]
