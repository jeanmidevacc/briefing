"""Developer tasks: `nox -s tests browser lint typecheck` (or just `nox`)."""
from __future__ import annotations

import nox

nox.options.sessions = ["tests", "browser", "lint", "typecheck"]
nox.options.reuse_existing_virtualenvs = True

PYTHONS = ["3.11", "3.12", "3.13"]


@nox.session(python=PYTHONS)
@nox.parametrize("pandas", ["2", "3"])
def tests(session: nox.Session, pandas: str) -> None:
    """Run the test suite with coverage, against pandas 2 and pandas 3."""
    session.install("-e", ".[dev]", f"pandas=={pandas}.*")
    session.run("pytest", "-m", "not browser", *session.posargs)


@nox.session(python="3.12")
def browser(session: nox.Session) -> None:
    """Browser tests in headless Chromium (pytest -m browser)."""
    session.install("-e", ".[dev]")
    session.run("playwright", "install", "chromium")
    session.run("pytest", "-m", "browser", "--no-cov", *session.posargs)


@nox.session(python="3.11")
def lint(session: nox.Session) -> None:
    """Ruff lint (no autofix)."""
    session.install("ruff>=0.4")
    session.run("ruff", "check", "src", "tests")


@nox.session(python="3.11")
def typecheck(session: nox.Session) -> None:
    """Strict mypy over the package and the tests."""
    session.install("-e", ".[dev]")
    session.run("mypy", "src/briefing", "tests")


@nox.session(python="3.11")
def demo(session: nox.Session) -> None:
    """Regenerate the demo reports in ../demo/."""
    session.install("-e", ".[dev]", "plotly", "matplotlib")
    session.run("python", "../demo/generate.py", external=True)
