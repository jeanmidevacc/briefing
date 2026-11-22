"""Slide decks (#197): briefing's blocks on slides, in one self-contained HTML file.

A deck is written like a report: a :class:`Deck` of :class:`Slide` objects, each holding
any of briefing's blocks. It runs in the browser like a report, so every block keeps its
own renderer (charts stay interactive, tables sort) and the report's theme applies.

Example::

    deck = bf.deck.Deck(
        bf.deck.Slide(bf.Banner("Q3 review", subtitle="Sales and operations")),
        bf.deck.Slide(bf.Text("Revenue grew in **every** region."), title="Summary"),
        bf.deck.Slide(bf.Plot(fig), title="Revenue by month"),
        footer="Sales analytics",
    )
    spec, data = bf.to_spec(deck)  # its JSON form: {"briefing": 1, "slides": [...]}
"""
from __future__ import annotations

import typing as t
from collections.abc import Mapping

from briefing.deck import _render  # noqa: F401  (registers the slide renderer)
from briefing.deck._blocks import Deck, Slide


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


__all__ = ["Deck", "Slide", "from_spec"]
