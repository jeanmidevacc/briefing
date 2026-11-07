"""The documentation's live examples run offline and follow the report contract (#41).

``docs/_ext/gallery.py`` is what the ``briefing-example`` directive runs at build
time; running it here too keeps the gallery honest without building the site.
"""
from __future__ import annotations

import importlib.util
import inspect
import re
import sys
import typing as t
from pathlib import Path

import pytest

import briefing as bf
from briefing.blocks.base import Block
from tests.contract import RULES, parse_report

DOCS = Path(__file__).resolve().parents[1] / "docs"


def _load_gallery() -> t.Any:
    spec = importlib.util.spec_from_file_location("docs_gallery", DOCS / "_ext" / "gallery.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up while being created
    spec.loader.exec_module(module)
    return module


gallery = _load_gallery()
EXAMPLES = list(gallery.find_examples(DOCS))
BY_ID = {example.id: example for example in EXAMPLES}

#: Rules every report fails today, as in tests/test_contract.py.
KNOWN_FAILURES: dict[str, str] = {}

_reports: dict[str, str] = {}


def _report(example_id: str, tmp_path_factory: pytest.TempPathFactory) -> str:
    if example_id not in _reports:
        workdir = tmp_path_factory.mktemp("example")
        path = gallery.run_example(BY_ID[example_id].code, workdir, where=example_id)
        _reports[example_id] = path.read_text(encoding="utf-8")
    return _reports[example_id]


def _cases() -> list[t.Any]:
    cases = []
    for rule in RULES:
        marks = [pytest.mark.xfail(reason=KNOWN_FAILURES[rule], strict=True)] if rule in KNOWN_FAILURES else []
        cases += [pytest.param(rule, ex.id, marks=marks, id=f"{rule}:{ex.id}") for ex in EXAMPLES]
    return cases


def test_the_docs_have_live_examples() -> None:
    assert len(EXAMPLES) >= 10, [e.id for e in EXAMPLES]


@pytest.mark.parametrize(("rule", "example_id"), _cases())
def test_example_follows_rule(rule: str, example_id: str, tmp_path_factory: pytest.TempPathFactory) -> None:
    RULES[rule](parse_report(_report(example_id, tmp_path_factory)))


@pytest.mark.parametrize("example_id", [ex.id for ex in EXAMPLES])
def test_example_is_deterministic(example_id: str, tmp_path_factory: pytest.TempPathFactory) -> None:
    again = gallery.run_example(BY_ID[example_id].code, tmp_path_factory.mktemp("again"), where=example_id)
    assert again.read_text(encoding="utf-8") == _report(example_id, tmp_path_factory)


def _public_blocks() -> list[str]:
    names = [f"bf.{n}" for n in bf.__all__ if inspect.isclass(getattr(bf, n)) and issubclass(getattr(bf, n), Block)]
    names += [f"lab.{n}" for n in bf.lab.__all__ if issubclass(getattr(bf.lab, n), Block)]
    return [n for n in names if n != "bf.Block"]


@pytest.mark.parametrize("name", _public_blocks())
def test_every_block_has_a_live_example(name: str) -> None:
    call = name.split(".", 1)[1] + "("
    assert any(f".{call}" in ex.code for ex in EXAMPLES), f"no briefing-example in docs/ uses {name}"


# ── the runner itself ─────────────────────────────────────────────────────────


def test_find_examples_reads_options_and_code(tmp_path: Path) -> None:
    (tmp_path / "page.md").write_text(
        "# Page\n\n```{briefing-example}\n:height: 300\n\nx = 1\n```\n\n````{briefing-example}\ny = 2\n````\n"
    )
    found = list(gallery.find_examples(tmp_path))
    assert [(e.id, e.options, e.code) for e in found] == [
        ("page.md:3", {"height": "300"}, "x = 1\n"),
        ("page.md:9", {}, "y = 2\n"),
    ]


def test_run_example_returns_the_saved_report(tmp_path: Path) -> None:
    code = 'import briefing as bf\nbf.save(bf.Text("hi"), "hi.html", name="Hi")\n'
    path = gallery.run_example(code, tmp_path)
    assert path.name == "hi.html"
    assert "2024-01-01" in path.read_text()  # SOURCE_DATE_EPOCH is pinned


@pytest.mark.parametrize(
    ("code", "message"),
    [
        pytest.param("raise ValueError('boom')", "raised ValueError: boom", id="raises"),
        pytest.param("import warnings\nwarnings.warn('careful')", "warned (UserWarning): careful", id="warns"),
        pytest.param("x = 1", "saved none", id="no-report"),
        pytest.param(
            'import briefing as bf\nbf.save(bf.Text("a"), "a.html")\nbf.save(bf.Text("b"), "b.html")',
            "saved a.html, b.html",
            id="two-reports",
        ),
    ],
)
def test_run_example_rejects(code: str, message: str, tmp_path: Path) -> None:
    with pytest.raises(gallery.ExampleError, match=re.escape(message)):
        gallery.run_example(code, tmp_path)
