"""What ``pip install briefing`` brings, and its extras (#40)."""
from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))


def test_pandas_is_a_core_dependency() -> None:
    assert any(dep.startswith("pandas") for dep in PYPROJECT["project"]["dependencies"])


def test_only_the_extras_that_add_something_remain() -> None:
    extras = PYPROJECT["project"]["optional-dependencies"]
    assert sorted(extras) == ["altair", "dev", "docs", "image", "lab", "pillow"]
    assert extras["lab"] == []  # kept so `pip install "briefing[lab]"` keeps working
    assert any(dep.startswith("vl-convert-python") for dep in extras["altair"])
    assert extras["pillow"] == ["pillow>=10.0"]  # Image/Banner(max_width=, format=) (#186)
