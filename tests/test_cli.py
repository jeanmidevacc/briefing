"""`python -m briefing image|pdf` maps its options onto save_image / save_pdf (#49)."""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from briefing import _cli

Calls = list[tuple[str, tuple[object, ...], dict[str, object]]]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "briefing", *args], capture_output=True, text=True)


def test_help_lists_the_commands() -> None:
    out = _run("--help")
    assert out.returncode == 0
    for command in ("reference", "validate", "render", "skill", "image", "pdf"):
        assert command in out.stdout


@pytest.mark.parametrize("command", ["image", "pdf"])
def test_each_command_has_help(command: str) -> None:
    out = _run(command, "--help")
    assert out.returncode == 0 and "--page" in out.stdout and "--output" in out.stdout


def test_version() -> None:
    import briefing

    assert _run("--version").stdout.strip() == f"briefing {briefing.__version__}"


@pytest.fixture
def report(tmp_path: Path) -> Path:
    path = tmp_path / "q1.html"
    path.write_text("<html><body>saved report</body></html>")
    return path


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    seen: Calls = []

    def fake(kind: str, result: object) -> object:
        def record(*args: object, **kwargs: object) -> object:
            seen.append((kind, args, kwargs))
            return result
        return record

    monkeypatch.setattr(_cli, "save_image", fake("image", [Path("out.png")]))
    monkeypatch.setattr(_cli, "save_pdf", fake("pdf", Path("out.pdf")))
    return seen


def test_image_defaults_to_the_input_name(report: Path, calls: Calls) -> None:
    assert _cli.main(["image", str(report)]) == 0
    kind, args, kwargs = calls[0]
    assert kind == "image" and args == (report, report.with_suffix(".png"))
    assert kwargs == {"page": "all", "width": 1200, "scale": 2.0, "size": None, "expand": True}


def test_image_options(report: Path, tmp_path: Path, calls: Calls) -> None:
    out = tmp_path / "cards"
    out.mkdir()
    _cli.main(["image", str(report), "--page", "1", "-o", str(out), "--size", "og", "--width", "800",
               "--scale", "1", "--format", "webp", "--no-expand"])
    _, args, kwargs = calls[0]
    assert args == (report, out / "q1.webp")  # a directory output keeps the input's name
    assert kwargs == {"page": 1, "width": 800, "scale": 1.0, "size": "og", "expand": False}


def test_page_by_title(report: Path, calls: Calls) -> None:
    _cli.main(["image", str(report), "--page", "Detail view", "-o", "x.png"])
    assert calls[0][2]["page"] == "Detail view" and calls[0][1][1] == Path("x.png")


def test_pdf(report: Path, calls: Calls) -> None:
    assert _cli.main(["pdf", str(report)]) == 0
    _cli.main(["pdf", str(report), "-o", "r.pdf", "--paper", "letter", "--landscape", "--page", "Summary"])
    assert calls[0][1] == (report, report.with_suffix(".pdf"))
    assert calls[0][2] == {"page": "all", "paper": "a4", "landscape": False}
    assert calls[1][2] == {"page": "Summary", "paper": "letter", "landscape": True}


def test_missing_input_is_a_clean_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli.main(["pdf", str(tmp_path / "nope.html")]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ") and "nope.html" in err and "Traceback" not in err


def test_bad_size_is_rejected_by_argparse(report: Path) -> None:
    out = _run("image", str(report), "--size", "banner")
    assert out.returncode == 2 and "invalid choice" in out.stderr


# ── report JSON, for agents (#32) ─────────────────────────────────────────────

_SPEC = {"briefing": 1, "blocks": [
    {"type": "Text", "text": "# Q1"},
    {"type": "Group", "columns": 2, "blocks": [{"type": "DataTable", "df": {"ref": "sales"}}]},
]}


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    path = tmp_path / "q1.json"
    path.write_text(json.dumps(_SPEC), encoding="utf-8")
    (tmp_path / "sales.csv").write_text("region,revenue\nNorth,412000\nSouth,287500\n", encoding="utf-8")
    return path


def test_validate_lists_the_problems_and_fails(spec: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec.write_text(json.dumps(_SPEC).replace('"columns"', '"colums"'), encoding="utf-8")
    assert _cli.main(["validate", str(spec)]) == 1
    out = capsys.readouterr()
    assert out.out == (
        'error unknown-option at /blocks/1/colums: Group has no option "colums". Did you mean "columns"?\n'
    )
    assert "the reference sales and the rendering weren't checked" in out.err


def test_validate_checks_references_given_as_files(spec: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli.main(["validate", str(spec), "--data", f"sales={spec.parent / 'sales.csv'}"]) == 0
    out = capsys.readouterr()
    assert out.out == "No problems found.\n" and out.err == ""


def test_validate_prints_json(spec: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec.write_text(json.dumps({"briefing": 1, "blocks": [{"type": "Select", "blocks": []}]}), encoding="utf-8")
    assert _cli.main(["validate", str(spec), "--json"]) == 0  # a warning isn't an error
    assert json.loads(capsys.readouterr().out) == [{
        "severity": "warning", "code": "too-few-panels", "path": "/blocks/0",
        "message": "This Select has 0 panels; it shows one at a time, so it needs at least 2.",
        "hint": "Add panels, or use a Group.",
    }]


def test_validate_reads_standard_input(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"briefing": 1, "blocks": [{"type": "Txt"}]}'))
    assert _cli.main(["validate", "-"]) == 1
    assert 'There is no block type "Txt". Did you mean "Text"?' in capsys.readouterr().out


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ("sales", "--data takes name=file.csv"),
        ("sales=missing.csv", "there is no file 'missing.csv'"),
        ("sales=q1.json", "read .csv and .parquet files, not 'q1.json'"),
    ],
)
def test_bad_data_says_what_to_pass(
    spec: Path, data: str, message: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(spec.parent)
    assert _cli.main(["validate", str(spec), "--data", data]) == 1
    assert message in capsys.readouterr().err


def test_render_writes_the_report_next_to_its_json(spec: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli.main(["render", str(spec), "--data", f"sales={spec.parent / 'sales.csv'}", "--name", "Q1 sales"]) == 0
    written = spec.with_suffix(".html")
    assert capsys.readouterr().out == f"{written}\n"
    html = written.read_text(encoding="utf-8")
    assert "<title>Q1 sales</title>" in html and "South" in html


def test_render_reads_parquet(spec: Path, tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    import pandas as pd

    pd.DataFrame({"region": ["East"], "revenue": [351200]}).to_parquet(tmp_path / "sales.parquet")
    out = tmp_path / "out.html"
    assert _cli.main(["render", str(spec), "-o", str(out), "--data", f"sales={tmp_path / 'sales.parquet'}"]) == 0
    assert "East" in out.read_text(encoding="utf-8")


def test_render_says_how_to_pass_a_missing_reference(spec: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli.main(["render", str(spec)]) == 1
    err = capsys.readouterr().err
    assert "No object named 'sales' was passed in data." in err and "--data name=file.csv" in err
    assert not spec.with_suffix(".html").exists()


def test_render_builds_a_deck_from_its_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec = tmp_path / "q3.json"
    spec.write_text(json.dumps({"briefing": 1, "slides": [
        {"title": "Q3"}, {"title": "Regions", "blocks": [{"type": "DataTable", "df": {"ref": "sales"}}]}]}))
    (tmp_path / "sales.csv").write_text("region,revenue\nSouth,287500\n")
    assert _cli.main(["render", str(spec), "--data", f"sales={tmp_path / 'sales.csv'}"]) == 0
    html = spec.with_suffix(".html").read_text(encoding="utf-8")
    assert "<title>Deck</title>" in html and "data-bf-deck" in html and "South" in html
    assert capsys.readouterr().out == f"{spec.with_suffix('.html')}\n"


@pytest.mark.filterwarnings("ignore::briefing.ExperimentalWarning")
def test_render_deck_also_drafts_a_deck_from_a_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec = tmp_path / "q3.json"
    spec.write_text(json.dumps({"briefing": 1, "blocks": [{"type": "Text", "text": "## One\n\na\n\n## Two\n\nb"}]}))
    deck = tmp_path / "q3-deck.html"
    assert _cli.main(["render", str(spec), "--deck", str(deck)]) == 0
    assert capsys.readouterr().out == f"{spec.with_suffix('.html')}\n{deck}\n"
    assert deck.read_text(encoding="utf-8").count('data-bf-slide=') == 2


def test_render_deck_on_a_decks_json_says_it_is_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec = tmp_path / "d.json"
    spec.write_text(json.dumps({"briefing": 1, "slides": [{"title": "a"}]}))
    assert _cli.main(["render", str(spec), "--deck", str(tmp_path / "x.html")]) == 1
    assert "this JSON is already a deck" in capsys.readouterr().err


def test_render_from_standard_input_needs_an_output(capsys: pytest.CaptureFixture[str]) -> None:
    assert _cli.main(["render", "-"]) == 1
    assert "pass --output report.html" in capsys.readouterr().err


def test_skill_prints_or_installs_itself(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from briefing.spec._reference import SKILL

    assert _cli.main(["skill"]) == 0
    assert capsys.readouterr().out == SKILL
    target = tmp_path / ".claude" / "skills" / "briefing" / "SKILL.md"
    assert _cli.main(["skill", "--install", "--dir", str(tmp_path)]) == 0
    assert target.read_text(encoding="utf-8") == SKILL
    assert _cli.main(["skill", "--install", "--dir", str(tmp_path)]) == 0  # the same again: fine
    target.write_text("my own notes", encoding="utf-8")
    assert _cli.main(["skill", "--install", "--dir", str(tmp_path)]) == 1
    assert "pass --force" in capsys.readouterr().err
    assert target.read_text(encoding="utf-8") == "my own notes"
    assert _cli.main(["skill", "--install", "--dir", str(tmp_path), "--force"]) == 0
    assert target.read_text(encoding="utf-8") == SKILL
