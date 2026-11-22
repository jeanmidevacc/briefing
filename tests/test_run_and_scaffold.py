"""bf.run and python -m briefing new (#193)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from briefing._cli import main
from tests.contract import RULES, parse_report


def _report(value: int = 1) -> bf.Briefing:
    return bf.Briefing(bf.BigNumber("N", value, name="n"), bf.Text("Hello"))


def test_run_writes_the_report_and_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "reports" / "index.html"
    path = bf.run(_report, out=out, name="Daily", argv=[])
    assert path == out and out.is_file() and "<title>Daily</title>" in out.read_text(encoding="utf-8")
    assert capsys.readouterr().out.startswith(f"{out}: ")


def test_run_options(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    first = tmp_path / "a.html"
    bf.run(lambda: _report(1), argv=["--out", str(first), "--spec", "--max-size", "none"])
    spec = json.loads(first.with_suffix(".json").read_text(encoding="utf-8"))
    assert spec["blocks"][0]["value"] == 1
    second = tmp_path / "b.html"
    bf.run(lambda: [bf.BigNumber("N", 2, name="n"), bf.Text("Hello")],
           argv=["--out", str(second), "--diff", str(first.with_suffix(".json")), "--open"])
    changes = (tmp_path / "b-changes.html").read_text(encoding="utf-8")
    assert "1 block changed" in changes and opened == [second.resolve().as_uri()]
    printed = capsys.readouterr().out
    assert "a.json" in printed and "b-changes.html" in printed


def test_spec_warns_when_json_cant_hold_the_report(tmp_path: Path) -> None:
    frame = pd.DataFrame({"a": [2, 1]}).sort_values("a")  # an index of its own: not inline
    with pytest.warns(UserWarning, match=r"--spec: datatable-1 can't be written into JSON"):
        bf.run(lambda: bf.Briefing(bf.DataTable(frame)), argv=["--out", str(tmp_path / "r.html"), "--spec"])


def test_run_rejects_a_bad_size(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        bf.run(_report, argv=["--out", str(tmp_path / "r.html"), "--max-size", "huge"])


# ── python -m briefing new ────────────────────────────────────────────────────


def test_new_writes_a_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    folder = tmp_path / "pipeline-health"
    assert main(["new", str(folder)]) == 0
    assert sorted(p.name for p in folder.iterdir()) == ["README.md", "build_report.py", "report.md", "theme.py"]
    assert "TITLE = 'Pipeline health'" in (folder / "build_report.py").read_text(encoding="utf-8")
    assert "python build_report.py --open" in capsys.readouterr().out


def test_new_wont_overwrite_without_force(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["new", str(tmp_path), "--title", "One"])
    assert main(["new", str(tmp_path), "--title", "Two"]) == 1
    assert "already holds build_report.py" in capsys.readouterr().err
    assert main(["new", str(tmp_path), "--title", 'Two "quoted"', "--force"]) == 0
    assert "TITLE = 'Two \"quoted\"'" in (tmp_path / "build_report.py").read_text(encoding="utf-8")


def test_the_new_project_runs_and_its_report_keeps_the_contract(tmp_path: Path) -> None:
    main(["new", str(tmp_path / "demo"), "--title", "Demo"])
    project = tmp_path / "demo"
    done = subprocess.run([sys.executable, "build_report.py", "--spec"], cwd=project, capture_output=True,
                          text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr
    assert not done.stderr.strip(), done.stderr  # no warning either
    html = (project / "reports" / "index.html").read_text(encoding="utf-8")
    soup = parse_report(html)
    for rule in RULES.values():
        rule(soup)
    assert "Data through November 20, 2026:" in soup.get_text()
    again = subprocess.run([sys.executable, "build_report.py", "--diff", "reports/index.json"], cwd=project,
                           capture_output=True, text=True, timeout=300, check=False)
    assert again.returncode == 0, again.stderr
    assert "Nothing changed" in (project / "reports" / "index-changes.html").read_text(encoding="utf-8")


