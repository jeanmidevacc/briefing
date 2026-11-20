"""Formatting.to_css_vars sets the theme on a selector of the caller's choice (#123)."""
from __future__ import annotations

import briefing as bf


def test_the_theme_sits_on_root_by_default() -> None:
    css = bf.Formatting().to_css_vars()
    assert css.startswith(":root {\n  --bf-bg:")
    assert css == bf.Formatting().to_css_vars(":root")


def test_a_selector_scopes_the_same_variables_to_one_element() -> None:
    theme = bf.Formatting.dark()
    scoped = theme.to_css_vars("#revenue")
    assert scoped.startswith("#revenue {\n")
    assert scoped.removeprefix("#revenue") == theme.to_css_vars().removeprefix(":root")
