"""The reference for agents (#32): in sync with the classes, small enough to read whole, and true.

Its examples run here: each JSON example must validate with no problem and render, and
each Python example must run.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import typing as t
from importlib.resources import files
from pathlib import Path

import pytest

import briefing as bf
from briefing.spec._diagnostic import CODES
from briefing.spec._model import block_types
from briefing.spec._reference import SKILL, build_reference, deprecated

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = (files("briefing") / "reference.md").read_text(encoding="utf-8")

#: An agent should read the whole reference in one go: about 6,000 tokens.
BUDGET = 25_000


def _blocks(language: str) -> list[str]:
    return re.findall(rf"^```{language}\n(.*?)^```", REFERENCE, re.M | re.S)


def test_the_checked_in_reference_matches_the_block_classes() -> None:
    assert build_reference() == REFERENCE, (
        "the block classes changed: run `python -m briefing.spec` and commit briefing/reference.md"
    )


def test_it_fits_its_budget() -> None:
    assert len(REFERENCE.encode()) < BUDGET


def test_every_block_and_option_is_in_it() -> None:
    sections = dict(re.findall(r"^### (\S+)\n(.*?)(?=^### |^## |\Z)", REFERENCE, re.M | re.S))
    for name, kind in block_types().items():
        assert name in sections, f"no section for {name}"
        for field in kind.fields:
            if field.name not in ("name", "label") and (field.attr or field.name == "file"):
                if deprecated(field):  # left out on purpose: agents shouldn't use it
                    assert f"- `{field.key}`" not in sections[name], f"{name}.{field.key} is deprecated"
                else:
                    assert f"- `{field.key}`" in sections[name], f"{name}.{field.key} is missing"


def test_every_diagnostic_code_is_in_it_and_in_the_guide() -> None:
    guide = (ROOT / "docs" / "guides" / "json.md").read_text(encoding="utf-8")
    for code in CODES:
        assert f"- `{code}` (" in REFERENCE
        assert f"`{code}`" in guide, f"docs/guides/json.md doesn't list {code}"


def test_every_code_validate_reports_is_listed() -> None:
    source = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "briefing" / "spec").glob("*.py"))
    used = set(re.findall(r'(?:Diagnostic|_add)\(\s*"(?:error|warning)",\s*"([a-z-]+)"', source))
    used |= set(re.findall(r'code = "([a-z-]+)" if .* else "([a-z-]+)"', source)[0])
    assert used and used <= set(CODES), sorted(used - set(CODES))


@pytest.mark.parametrize("example", _blocks("json"), ids=lambda e: e[:30])
def test_its_json_examples_are_valid_reports(example: str) -> None:
    spec = json.loads(example)
    assert bf.validate(spec) == []
    assert "Made with briefing" in bf.stringify(bf.from_spec(spec))


@pytest.mark.parametrize("example", _blocks("python"), ids=lambda e: e[:30])
def test_its_python_examples_run(example: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    exec(compile(example, "reference.md", "exec"), {})  # noqa: S102 — our own documentation
    assert list(tmp_path.glob("*.html"))


def test_it_ships_in_the_package_and_the_command_prints_it(capsys: pytest.CaptureFixture[str]) -> None:
    from briefing import _cli

    assert _cli.main(["reference"]) == 0
    assert capsys.readouterr().out == REFERENCE


def test_the_skill_points_to_the_reference() -> None:
    front = re.match(r"^---\nname: briefing\ndescription: (.+)\n---\n", SKILL)
    assert front and len(front.group(1)) < 1024
    assert "python -m briefing reference" in SKILL


# ── the docs publish it as llms.txt (docs/_ext/llms.py) ───────────────────────


def _llms() -> t.Any:
    spec = importlib.util.spec_from_file_location("docs_llms", ROOT / "docs" / "_ext" / "llms.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_docs_publish_it_as_llms_full_txt_with_an_index(tmp_path: Path) -> None:
    _llms().write_llms(tmp_path, "9.9.9")
    assert (tmp_path / "llms-full.txt").read_text(encoding="utf-8") == REFERENCE
    index = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    assert index.startswith("# briefing\n\n> ") and "briefing 9.9.9" in index
    for link in re.findall(r"\]\(([^)]+)\)", index):
        source = ROOT / "docs" / link.replace(".html", "")
        found = link == "llms-full.txt" or source.with_suffix(".md").exists() or source.with_suffix(".rst").exists()
        assert found, link
