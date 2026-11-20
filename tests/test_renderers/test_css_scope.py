"""scope_css keeps briefing's stylesheet inside a fragment's root (#122)."""
from __future__ import annotations

import pytest

from briefing.renderers.css_scope import rem_to_var, scope_css, split_selectors


def _selectors(css: str) -> list[str]:
    return [line.split(" {")[0] for line in scope_css(css).splitlines() if " {" in line]


@pytest.mark.parametrize(
    ("selector", "scoped"),
    [
        ("body", ".bf-embed"),
        ("html", ".bf-embed"),
        (":root", ".bf-embed"),
        ("html.bf-printing .bf-report", ".bf-embed.bf-printing .bf-report"),
        ("*", ".bf-embed, .bf-embed *"),
        ("*::before", ".bf-embed::before, .bf-embed *::before"),
        (".bf-text p", ".bf-embed .bf-text p"),
        ("a", ".bf-embed a"),
        ("[data-bf-link]", ".bf-embed [data-bf-link]"),
        (".bf-embed .bf-embed__footer", ".bf-embed .bf-embed__footer"),  # already scoped
        ("html, body", ".bf-embed"),  # the same root once
        ("bodyish", ".bf-embed bodyish"),  # only the whole word maps to the root
    ],
)
def test_each_selector_starts_at_the_root(selector: str, scoped: str) -> None:
    assert _selectors(f"{selector} {{ color: red }}") == [scoped]


def test_selector_lists_split_only_at_top_level_commas() -> None:
    assert split_selectors(":is(h1, h2):hover > .x, a[title='a,b']") == [":is(h1, h2):hover > .x", "a[title='a,b']"]
    assert _selectors(":is(h1, h2) .x { color: red }") == [".bf-embed :is(h1, h2) .x"]


def test_media_rules_are_scoped_and_page_rules_dropped() -> None:
    css = "@page { margin: 12mm; } @media print { body { padding: 0; } .bf-x { color: red; } }"
    assert scope_css(css) == "@media print {\n.bf-embed { padding: 0; }\n.bf-embed .bf-x { color: red; }\n}\n"


def test_other_at_rules_stay_as_they_are() -> None:
    css = '@property --bf-rem { syntax: "<length>"; inherits: true; initial-value: 16px; }'
    assert scope_css(css) == css + "\n"


def test_comments_go_and_braces_in_strings_stay() -> None:
    assert scope_css('/* { */ .bf-x::after { content: "}{"; }') == '.bf-embed .bf-x::after { content: "}{"; }\n'


@pytest.mark.parametrize(
    ("css", "rewritten"),
    [
        ("margin: 1rem", "margin: calc(1 * var(--bf-rem))"),
        ("margin: 0 -0.5rem", "margin: 0 calc(-0.5 * var(--bf-rem))"),
        ("width: calc(100% - 2.5rem)", "width: calc(100% - calc(2.5 * var(--bf-rem)))"),
        ("font-size: .875rem", "font-size: calc(.875 * var(--bf-rem))"),
        ("--bf-x2rem: 1em", "--bf-x2rem: 1em"),
        ("width: 2em", "width: 2em"),
    ],
)
def test_rem_follows_the_roots_size(css: str, rewritten: str) -> None:
    assert rem_to_var(css) == rewritten
