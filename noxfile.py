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
def docs(session: nox.Session) -> None:
    """Build the Sphinx site into docs/_build/html; any warning fails the build."""
    session.install("-e", ".[docs]")
    session.run("sphinx-build", "-W", "--keep-going", "-b", "html", "docs", "docs/_build/html")


# Re-executes the walkthrough in place. SOURCE_DATE_EPOCH pins every timestamp, so
# re-running it without code changes leaves the notebook and its saved report as they are.
_RUN_WALKTHROUGH = """
import nbformat
from nbclient import NotebookClient
path = "notebook_walkthrough.ipynb"
nb = nbformat.read(path, as_version=4)
NotebookClient(
    nb, timeout=300, kernel_name="python3", record_timing=False, resources={"metadata": {"path": "."}}
).execute()
for cell in nb.cells:
    cell.metadata.pop("execution", None)  # wall-clock timings would change on every run
nbformat.write(nb, path)
print("re-executed", path)
"""


@nox.session(python="3.11")
def examples(session: nox.Session) -> None:
    """Re-execute examples/notebook_walkthrough.ipynb (which also rewrites examples/sales_report.html)."""
    session.install("-e", ".[dev]", "nbclient", "nbformat", "ipykernel")
    session.chdir("examples")
    session.run("python", "-c", _RUN_WALKTHROUGH, env={"SOURCE_DATE_EPOCH": "1704067200"})
