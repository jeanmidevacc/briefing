"""Tests for text and KPI blocks: Text, HTML, Code, Formula, BigNumber, Alert."""
from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from briefing._error import BriefingError
from briefing.blocks.text import HTML, Alert, AlertLevel, BigNumber, Code, Formula, Text

# ── Text ──────────────────────────────────────────────────────────────────────


class TestText:
    def test_basic_string(self):
        b = Text("# Hello")
        assert b.content == "# Hello"

    def test_leading_trailing_whitespace_stripped(self):
        b = Text("  hello world  ")
        assert b.content == "hello world"

    def test_multiline_dedented(self):
        b = Text("""
            # Title
            Some text here.
        """)
        assert b.content == "# Title\nSome text here."

    def test_from_file(self, tmp_path: Path):
        md = tmp_path / "notes.md"
        md.write_text("# From file\nContent here.", encoding="utf-8")
        b = Text(file=md)
        assert "# From file" in b.content

    def test_from_file_string_path(self, tmp_path: Path):
        md = tmp_path / "notes.md"
        md.write_text("file content", encoding="utf-8")
        b = Text(file=str(md))
        assert b.content == "file content"

    def test_file_not_found_raises(self, tmp_path: Path):
        with pytest.raises(BriefingError, match="File not found"):
            Text(file=tmp_path / "nonexistent.md")

    def test_requires_text_or_file(self):
        with pytest.raises(BriefingError):
            Text()

    def test_text_and_file_together_raises(self, tmp_path: Path):
        md = tmp_path / "f.md"
        md.write_text("x")
        with pytest.raises(BriefingError):
            Text(text="hello", file=md)

    def test_name_and_label_stored(self):
        b = Text("hi", name="intro", label="Introduction")
        assert b.name == "intro"
        assert b.label == "Introduction"


# ── HTML ──────────────────────────────────────────────────────────────────────


class TestHTML:
    def test_basic(self):
        b = HTML("<b>Bold</b>")
        assert b.content == "<b>Bold</b>"

    def test_non_string_coerced(self):
        # Should not raise — coerces to str.
        b = HTML(42)  # type: ignore[arg-type]
        assert b.content == "42"

    def test_whitespace_stripped(self):
        b = HTML("  <p>hi</p>  ")
        assert b.content == "<p>hi</p>"

    def test_label_and_name(self):
        b = HTML("<hr>", name="divider", label="Divider")
        assert b.name == "divider"
        assert b.label == "Divider"


# ── Code ──────────────────────────────────────────────────────────────────────


class TestCode:
    def test_defaults_to_python(self):
        b = Code("print('hi')")
        assert b.language == "python"

    def test_custom_language(self):
        b = Code("SELECT 1", language="sql")
        assert b.language == "sql"
        assert b.content == "SELECT 1"

    def test_caption_stored(self):
        b = Code("x = 1", caption="Variable assignment")
        assert b.caption == "Variable assignment"

    def test_caption_truncated_at_512(self):
        long = "c" * 600
        b = Code("x", caption=long)
        assert b.caption is not None
        assert len(b.caption) <= 512
        assert b.caption.endswith("...")

    def test_no_caption_is_none(self):
        b = Code("x = 1")
        assert b.caption is None


# ── Formula ───────────────────────────────────────────────────────────────────


class TestFormula:
    def test_basic(self):
        b = Formula(r"\frac{1}{\sqrt{x^2 + 1}}")
        assert "frac" in b.content

    def test_caption(self):
        b = Formula(r"E = mc^2", caption="Einstein's relation")
        assert b.caption == "Einstein's relation"

    def test_no_caption_is_none(self):
        b = Formula(r"x^2")
        assert b.caption is None


# ── BigNumber ─────────────────────────────────────────────────────────────────


class TestBigNumber:
    def test_string_value(self):
        b = BigNumber("Revenue", "$4.2M")
        assert b.heading == "Revenue"
        assert b.value == "$4.2M"

    def test_int_value(self):
        b = BigNumber("Count", 1_000)
        assert b.value == 1_000

    def test_float_value(self):
        b = BigNumber("Score", 0.924)
        assert b.value == 0.924

    def test_with_change_and_direction(self):
        b = BigNumber("Users", "142K", change="+3%", is_upward_change=True)
        assert b.change == "+3%"
        assert b.is_upward_change is True

    def test_downward_change(self):
        b = BigNumber("Churn", "12%", change="+0.5pp", is_upward_change=False)
        assert b.is_upward_change is False

    def test_change_without_direction_does_not_warn(self):
        # A change without a verdict is normal use: it renders neutral (#71).
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            BigNumber("x", 1, change="+5%")

    def test_no_change_no_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            BigNumber("x", 1)
        assert not any("is_upward_change" in str(w.message) for w in caught)

    def test_name_and_label(self):
        b = BigNumber("x", 1, name="kpi-1", label="KPI One")
        assert b.name == "kpi-1"
        assert b.label == "KPI One"


# ── Alert ─────────────────────────────────────────────────────────────────────


class TestAlert:
    def test_default_level_is_info(self):
        b = Alert("All good.")
        assert b.level == AlertLevel.INFO

    @pytest.mark.parametrize("level", list(AlertLevel))
    def test_all_levels_accepted(self, level: AlertLevel):
        b = Alert("msg", level=level)
        assert b.level == level

    def test_string_level_coerced(self):
        b = Alert("msg", level="warning")
        assert b.level == AlertLevel.WARNING

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError):
            Alert("msg", level="critical")

    def test_title_stored(self):
        b = Alert("msg", title="Heads up")
        assert b.title == "Heads up"

    def test_no_title_is_none(self):
        b = Alert("msg")
        assert b.title is None

    def test_message_stored(self):
        b = Alert("Data drift detected.")
        assert b.message == "Data drift detected."


def test_bignumber_positive_intent_defaults_to_none() -> None:
    assert BigNumber("A", 1).is_positive_intent is None
    assert BigNumber("A", 1, change="+1%", is_upward_change=True, is_positive_intent=False).is_positive_intent is False
