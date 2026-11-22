"""Formatting.to_css_vars sets the theme on a selector of the caller's choice (#123); preset fonts (#28)."""
from __future__ import annotations

import re

import pytest

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


# ── fonts every system has (#28) ──────────────────────────────────────────────

#: Fonts that ship with each system (macOS, Windows, common Linux distributions), plus
#: the CSS generic and system keywords. A preset may name only these.
_MACOS = {"-apple-system", "Helvetica Neue", "Helvetica", "Avenir", "Avenir Next", "Seravek", "Charter", "Georgia"}
_WINDOWS = {"Segoe UI", "Arial", "Corbel", "Calibri", "Gill Sans Nova", "Sitka Text", "Cambria", "Georgia"}
_LINUX = {"Roboto", "Noto Sans", "Liberation Sans", "Nimbus Sans", "URW Gothic", "URW Gothic L", "Ubuntu",
          "DejaVu Sans", "Bitstream Charter", "DejaVu Serif"}
_GENERIC = {"system-ui", "sans-serif", "serif"}

_PRESETS = {"default": bf.Formatting(), "dark": bf.Formatting.dark(), "corporate": bf.Formatting.corporate(),
            "minimal": bf.Formatting.minimal(), "ocean": bf.Formatting.ocean(), "warm": bf.Formatting.warm()}


def _families(stack: str) -> list[str]:
    return [f.strip().strip("'\"") for f in stack.split(",")]


@pytest.mark.parametrize("preset", list(_PRESETS))
def test_presets_name_only_fonts_every_system_has(preset: str) -> None:
    families = _families(_PRESETS[preset].font)
    assert set(families) <= _MACOS | _WINDOWS | _LINUX | _GENERIC
    for system in (_MACOS, _WINDOWS, _LINUX):
        assert set(families) & (system | {"system-ui"})  # a font of its own on every system
    assert families[-1] in ("sans-serif", "serif")


def test_each_preset_has_a_look_of_its_own() -> None:
    stacks = {name: f.font for name, f in _PRESETS.items() if name != "dark"}  # dark is the default in the dark
    assert len(set(stacks.values())) == len(stacks)
    assert _PRESETS["warm"].font.endswith(", serif")


def test_the_stylesheet_default_matches_formatting() -> None:
    from importlib.resources import files

    css = (files("briefing") / "static" / "report.css").read_text(encoding="utf-8")
    match = re.search(r"--bf-font:\s*([^;]+);", css)
    assert match and match.group(1).strip() == bf.Formatting().font
