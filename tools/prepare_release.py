"""Prepare a release (#198): ``nox -s prepare -- 0.11.0``, or ``python tools/prepare_release.py 0.11.0``.

Sets ``__version__`` in ``src/briefing/_version.py``, turns the CHANGELOG's ``## [Unreleased]``
into ``## [X.Y.Z] - <today>`` under a fresh, empty ``[Unreleased]``, and updates the compare
links at the bottom. Nothing else holds the version, so a release touches these two files only.
Then open a "Prepare X.Y.Z" pull request; once it is merged, a GitHub Release publishes.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/jeanmidevacc/briefing"

_VERSION = re.compile(r'^__version__ = "(\d+\.\d+\.\d+)"$', re.MULTILINE)
_UNRELEASED_LINK = re.compile(rf"^\[Unreleased\]: {re.escape(REPO)}/compare/v(\d+\.\d+\.\d+)\.\.\.HEAD$", re.MULTILINE)


class ReleaseError(Exception):
    """A release that can't be prepared, with what to do instead."""


def _parse(version: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ReleaseError(f"A version is X.Y.Z, such as 0.11.0; not {version!r}.")
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def bump_version(text: str, version: str) -> str:
    """``_version.py`` with *version*; it must come after the current one."""
    found = _VERSION.search(text)
    if not found:
        raise ReleaseError("_version.py has no line __version__ = \"X.Y.Z\".")
    if _parse(version) <= _parse(found.group(1)):
        raise ReleaseError(f"{version} doesn't come after the current version, {found.group(1)}.")
    return _VERSION.sub(f'__version__ = "{version}"', text, count=1)


def date_changelog(text: str, version: str, today: dt.date) -> str:
    """The CHANGELOG with its unreleased changes dated as *version*, and the compare links updated."""
    head = "## [Unreleased]\n"
    if text.count(head) != 1:
        raise ReleaseError("CHANGELOG.md needs exactly one '## [Unreleased]' heading.")
    start = text.index(head) + len(head)
    following = text.find("\n## [", start)
    if not text[start:following if following != -1 else len(text)].strip():
        raise ReleaseError("## [Unreleased] is empty: there is nothing to release.")
    if f"## [{version}]" in text:
        raise ReleaseError(f"CHANGELOG.md already has a section for {version}.")
    link = _UNRELEASED_LINK.search(text)
    if not link:
        raise ReleaseError(f"CHANGELOG.md has no line '[Unreleased]: {REPO}/compare/vX.Y.Z...HEAD'.")
    previous = link.group(1)
    text = text.replace(head, f"{head}\n## [{version}] - {today.isoformat()}\n", 1)
    return _UNRELEASED_LINK.sub(
        f"[Unreleased]: {REPO}/compare/v{version}...HEAD\n[{version}]: {REPO}/compare/v{previous}...v{version}",
        text, count=1,
    )


def prepare(version: str, root: Path = ROOT, today: dt.date | None = None) -> None:
    """Write both files, or neither when one can't be prepared."""
    version_file, changelog = root / "src" / "briefing" / "_version.py", root / "CHANGELOG.md"
    new_version = bump_version(version_file.read_text(encoding="utf-8"), version)
    new_changelog = date_changelog(changelog.read_text(encoding="utf-8"), version, today or dt.date.today())
    version_file.write_text(new_version, encoding="utf-8")
    changelog.write_text(new_changelog, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: nox -s prepare -- X.Y.Z", file=sys.stderr)
        return 2
    try:
        prepare(argv[0])
    except ReleaseError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Prepared {argv[0]}: src/briefing/_version.py and CHANGELOG.md. Open a 'Prepare {argv[0]}' pull request.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
