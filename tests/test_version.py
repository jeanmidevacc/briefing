"""The version has one home, ``_version.py``, and everything that needs it reads it from there (#23)."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import briefing
from briefing import _version

ROOT = Path(__file__).parent.parent
VERSION_FILE = "src/briefing/_version.py"


def test_the_package_exposes_the_version_module() -> None:
    assert briefing.__version__ == _version.__version__


def test_package_metadata_reads_the_version_module() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["hatch"]["version"]["path"] == VERSION_FILE


def test_the_release_check_reads_the_version_module() -> None:
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    command = re.search(r"grep -Po '\^__version__ = \"\\K\[\^\"\]\+' (\S+?)\)", workflow)
    assert command is not None, "publish.yml no longer greps __version__"
    assert command.group(1) == VERSION_FILE
