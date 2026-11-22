"""Turning the suite's report scenarios into decks, so every block is checked on a slide too (#197)."""
from __future__ import annotations

import briefing as bf


def as_deck(report: bf.Briefing) -> bf.deck.Deck:
    """*report* as a deck: a slide per page, or one slide holding every block."""
    if all(isinstance(b, bf.Page) for b in report.blocks):
        slides = [bf.deck.Slide(*page.blocks, title=page.title, name=page.name)
                  for page in report.blocks if isinstance(page, bf.Page)]
    else:
        slides = [bf.deck.Slide(*report.blocks)]
    return bf.deck.Deck(*slides, footer=report.footer)
