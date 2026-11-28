"""``nox -s prepare -- X.Y.Z`` (#198): a release touches _version.py and CHANGELOG.md only."""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import typing as t
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("prepare_release", ROOT / "tools" / "prepare_release.py")
assert _spec is not None and _spec.loader is not None
release: t.Any = importlib.util.module_from_spec(_spec)
sys.modules["prepare_release"] = release
_spec.loader.exec_module(release)

_REPO = "https://github.com/jeanmidevacc/briefing"
_CHANGELOG = f"""# Changelog

## [Unreleased]

### Added

- Something new.

## [0.10.0] - 2026-11-26

### Added

- Older.

[Unreleased]: {_REPO}/compare/v0.10.0...HEAD
[0.10.0]: {_REPO}/compare/v0.9.0...v0.10.0
"""


def _project(tmp_path: Path, changelog: str = _CHANGELOG) -> Path:
    (tmp_path / "src" / "briefing").mkdir(parents=True)
    (tmp_path / "src" / "briefing" / "_version.py").write_text('"""v."""\n__version__ = "0.10.0"\n')
    (tmp_path / "CHANGELOG.md").write_text(changelog)
    return tmp_path


def test_it_dates_the_changes_and_moves_the_links(tmp_path: Path) -> None:
    root = _project(tmp_path)
    release.prepare("0.11.0", root, dt.date(2026, 11, 28))
    assert (root / "src/briefing/_version.py").read_text() == '"""v."""\n__version__ = "0.11.0"\n'
    changelog = (root / "CHANGELOG.md").read_text()
    assert "## [Unreleased]\n\n## [0.11.0] - 2026-11-28\n\n### Added\n\n- Something new." in changelog
    assert changelog.endswith(
        f"[Unreleased]: {_REPO}/compare/v0.11.0...HEAD\n[0.11.0]: {_REPO}/compare/v0.10.0...v0.11.0\n"
        f"[0.10.0]: {_REPO}/compare/v0.9.0...v0.10.0\n")


@pytest.mark.parametrize(("version", "message"), [
    ("0.11", "A version is X.Y.Z"),
    ("0.10.0", "doesn't come after the current version, 0.10.0"),
    ("0.9.9", "doesn't come after"),
])
def test_a_version_must_be_newer(tmp_path: Path, version: str, message: str) -> None:
    with pytest.raises(release.ReleaseError, match=message):
        release.prepare(version, _project(tmp_path))


def test_nothing_to_release_writes_nothing(tmp_path: Path) -> None:
    empty = _CHANGELOG.replace("### Added\n\n- Something new.\n\n", "", 1)
    root = _project(tmp_path, empty)
    with pytest.raises(release.ReleaseError, match="Unreleased\\] is empty"):
        release.prepare("0.11.0", root)
    assert '"0.10.0"' in (root / "src/briefing/_version.py").read_text()  # neither file changed
    assert (root / "CHANGELOG.md").read_text() == empty


def test_the_repositorys_own_files_can_be_prepared() -> None:
    version = (ROOT / "src/briefing/_version.py").read_text()
    current = release._VERSION.search(version).group(1)
    major, minor, _ = release._parse(current)
    release.bump_version(version, f"{major}.{minor + 1}.0")
    changelog = (ROOT / "CHANGELOG.md").read_text()
    if "## [Unreleased]\n\n## [" not in changelog:  # something to release
        release.date_changelog(changelog, f"{major}.{minor + 1}.0", dt.date(2026, 1, 1))


def test_main_reports_errors_without_a_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    assert release.main([]) == 2
    assert release.main(["nope"]) == 1
    assert "A version is X.Y.Z" in capsys.readouterr().err
