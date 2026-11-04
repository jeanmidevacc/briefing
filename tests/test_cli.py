"""`python -m briefing image|pdf` maps its options onto save_image / save_pdf (#49)."""
from __future__ import annotations

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
    assert "image" in out.stdout and "pdf" in out.stdout


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
