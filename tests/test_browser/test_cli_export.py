"""The command line exports a saved report end to end (#49)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import briefing as bf
from tests.image_helpers import png_size
from tests.pdf_reader import read_pdf


def _saved(tmp_path: Path) -> Path:
    path = tmp_path / "q1.html"
    bf.save(bf.Briefing(bf.Page(bf.Text("# One"), title="One"), bf.Page(bf.Text("# Two"), title="Two")), str(path))
    return path


def test_image_page_all_into_a_directory(tmp_path: Path) -> None:
    saved, out = _saved(tmp_path), tmp_path / "out"
    out.mkdir()
    run = subprocess.run([sys.executable, "-m", "briefing", "image", str(saved), "--page", "all", "-o", str(out),
                          "--scale", "1", "--width", "640"], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert sorted(p.name for p in out.iterdir()) == ["q1_one.png", "q1_two.png"]
    assert png_size(out / "q1_one.png")[0] == 640
    assert str(out / "q1_one.png") in run.stdout


def test_pdf(tmp_path: Path) -> None:
    saved = _saved(tmp_path)
    run = subprocess.run([sys.executable, "-m", "briefing", "pdf", str(saved), "-o", str(tmp_path / "r.pdf")],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert len(read_pdf((tmp_path / "r.pdf").read_bytes()).pages) == 2
