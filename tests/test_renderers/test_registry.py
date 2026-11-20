"""IdGen numbers ids within one render, optionally under a prefix (#123)."""
from __future__ import annotations

from briefing.renderers.registry import IdGen


def test_ids_count_up_across_kinds() -> None:
    ids = IdGen()
    assert [ids.next("sel"), ids.next("tog"), ids.next()] == ["sel-1", "tog-2", "bf-3"]


def test_a_prefix_starts_every_id() -> None:
    ids = IdGen(prefix="revenue")
    assert [ids.next("sel"), ids.next("mpl")] == ["revenue-sel-1", "revenue-mpl-2"]


def test_an_empty_prefix_is_no_prefix() -> None:
    assert IdGen(prefix="").next("sel") == "sel-1"
