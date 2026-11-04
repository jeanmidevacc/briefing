"""Export entry points fail clearly and keep Playwright out of `import briefing` (#49)."""
from __future__ import annotations

import builtins
import subprocess
import sys
from pathlib import Path

import pytest

import briefing as bf
from briefing.export._render import browser_error


def test_import_briefing_does_not_import_playwright() -> None:
    code = "import sys, briefing; print('playwright' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_missing_playwright_names_the_extra(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    real_import = builtins.__import__

    def no_playwright(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("playwright"):
            raise ImportError("No module named 'playwright'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_playwright)
    with pytest.raises(bf.BriefingError, match=r'pip install "briefing\[image\]"'):
        bf.save_image(bf.Text("x"), tmp_path / "x.png")


def test_missing_browser_names_the_install_command() -> None:
    exc = Exception("BrowserType.launch: Executable doesn't exist at /root/.cache/ms-playwright/chromium-1/chrome")
    err = browser_error(exc)
    assert err is not None and "playwright install chromium" in str(err)
    assert browser_error(Exception("something else")) is None


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"size": "banner"}, "size"),
        ({"width": 0}, "width"),
        ({"scale": 0}, "scale"),
    ],
)
def test_bad_arguments_raise_before_launching(tmp_path: Path, kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.save_image(bf.Text("x"), tmp_path / "x.png", **kwargs)  # type: ignore[arg-type]


def test_unsupported_suffix_raises(tmp_path: Path) -> None:
    with pytest.raises(bf.BriefingError, match=r"\.png, \.jpg or \.webp"):
        bf.save_image(bf.Text("x"), tmp_path / "x.gif")


def test_save_pdf_missing_playwright_names_the_extra(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    real_import = builtins.__import__

    def no_playwright(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("playwright"):
            raise ImportError("No module named 'playwright'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_playwright)
    with pytest.raises(bf.BriefingError, match=r'pip install "briefing\[image\]"'):
        bf.save_pdf(bf.Text("x"), tmp_path / "x.pdf")


def test_save_pdf_bad_arguments(tmp_path: Path) -> None:
    with pytest.raises(bf.BriefingError, match="paper"):
        bf.save_pdf(bf.Text("x"), tmp_path / "x.pdf", paper="b7")
    with pytest.raises(bf.BriefingError, match=r"\.pdf"):
        bf.save_pdf(bf.Text("x"), tmp_path / "x.png")
