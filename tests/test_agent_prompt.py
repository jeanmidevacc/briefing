"""The prompt for coding agents (#234) stays true to the code: its report.py runs and builds
every output it offers, and every name and command it mentions exists."""
from __future__ import annotations

import argparse
import re
import runpy
import typing as t
import warnings
from pathlib import Path

import pytest

import briefing as bf
from briefing._cli import _parser

PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "briefing-agent.md"
TEXT = PROMPT.read_text(encoding="utf-8")


def _section(title: str) -> str:
    return TEXT.split(f"## {title}", 1)[1].split("\n## ", 1)[0]


def _ticks(title: str) -> dict[str, bool]:
    return {label: mark == "x" for mark, label in re.findall(r"^- \[( |x)\] ([^:]+):", _section(title), re.M)}


def test_by_default_it_asks_for_a_strict_html_report() -> None:
    assert _ticks("What to produce (tick with [x])") == {
        "HTML report": True, "Slide deck": False, "Email digest": False, "Embed": False,
    }
    assert _ticks("Freedom (tick one)") == {"Strict": True, "Open": False}


def test_each_output_has_its_rules() -> None:
    rules = _section("Rules for each output (follow only the ones ticked)")
    for output in _ticks("What to produce (tick with [x])"):
        assert f"### {output}" in rules


def test_its_report_py_builds_every_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    [code] = re.findall(r"^```python\n(.*?)^```", TEXT, re.M | re.S)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "orders.csv").write_text(
        "region,revenue,target\nNorth,400,450\nSouth,300,290\nEast,350,340\nNorth,20,10\n", encoding="utf-8")
    (tmp_path / "report.py").write_text(code, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # from_report is experimental; the email leaves the Toggle out
        names = runpy.run_path("report.py", run_name="__main__")
    assert sorted(p.name for p in (tmp_path / "reports").iterdir()) == [
        "deck.html", "digest.eml", "embed.html", "index.html"]
    build = t.cast(t.Callable[[t.Any], bf.Briefing], names["build"])
    assert bf.validate(build(names["load"]())) == []


def test_every_name_it_mentions_exists() -> None:
    names = set(re.findall(r"\bbf\.([A-Za-z_][\w.]*[A-Za-z_])", TEXT))
    assert {"save", "deck.from_report", "email.from_report", "HTML"} <= names
    for name in names:
        found: object = bf
        for part in name.split("."):
            assert hasattr(found, part), f"bf.{name}"
            found = getattr(found, part)


def test_every_command_it_mentions_exists() -> None:
    [commands] = [a for a in _parser()._actions if isinstance(a, argparse._SubParsersAction)]
    mentioned = set(re.findall(r"python -m briefing (\w+)", TEXT))
    assert mentioned == {"reference", "image"}
    assert mentioned <= set(commands.choices)
