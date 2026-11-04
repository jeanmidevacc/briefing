"""Find and run the live examples of the documentation, without Sphinx.

The ``briefing-example`` directive (``briefing_example.py``) runs each example
at build time through :func:`run_example`; ``tests/test_docs_gallery.py`` runs
the same examples through the same function and checks the reports against the
contract rules, so a gallery example can never need the network.

An example is Python code that saves exactly one report with ``bf.save``, to a
file name of its choice, in the current directory.
"""
from __future__ import annotations

import contextlib
import os
import re
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

#: Pinned timestamp for every example: 2024-01-01 00:00 UTC.
SOURCE_DATE_EPOCH = "1704067200"

# A MyST directive fence: ```{briefing-example}, its :options:, the code, ```.
_FENCE = re.compile(r"^(`{3,})\{briefing-example\}[^\n]*\n(.*?)^\1[ \t]*$", re.M | re.S)
_OPTION = re.compile(r"^:([\w-]+):[ \t]*(.*)$")


class ExampleError(Exception):
    """An example raised, warned, or didn't save exactly one report."""


@dataclass(frozen=True)
class Example:
    source: str  # file it was found in, relative to docs/
    line: int  # 1-based line of the opening fence
    code: str
    options: dict[str, str]

    @property
    def id(self) -> str:
        return f"{self.source}:{self.line}"


def split_options(lines: list[str]) -> tuple[dict[str, str], str]:
    """Separate a directive body's leading ``:key: value`` lines from its code."""
    options: dict[str, str] = {}
    rest = list(lines)
    while rest and (match := _OPTION.match(rest[0])):
        options[match.group(1)] = match.group(2).strip()
        rest.pop(0)
    while rest and not rest[0].strip():
        rest.pop(0)
    return options, "\n".join(rest).rstrip() + "\n"


def find_examples(docs: Path) -> Iterator[Example]:
    """Every ``briefing-example`` in the Markdown pages under *docs*."""
    for page in sorted(docs.rglob("*.md")):
        if "_build" in page.parts:
            continue
        text = page.read_text(encoding="utf-8")
        for match in _FENCE.finditer(text):
            options, code = split_options(match.group(2).splitlines())
            line = text.count("\n", 0, match.start()) + 1
            yield Example(page.relative_to(docs).as_posix(), line, code, options)


@contextlib.contextmanager
def _environment(workdir: Path) -> Iterator[None]:
    saved = {key: os.environ.get(key) for key in ("SOURCE_DATE_EPOCH", "MPLBACKEND")}
    os.environ["SOURCE_DATE_EPOCH"] = SOURCE_DATE_EPOCH
    os.environ["MPLBACKEND"] = "Agg"  # no display at build time
    try:
        with contextlib.chdir(workdir):
            yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_example(code: str, workdir: Path, *, where: str = "<example>") -> Path:
    """Run *code* in *workdir* and return the one report it saved.

    Raises:
        ExampleError: When the code raises or warns, or saves no report or several.
    """
    namespace: dict[str, object] = {"__name__": "__example__"}
    with _environment(workdir), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            exec(compile(code, where, "exec"), namespace)  # noqa: S102 - the docs' own examples
        except Exception as exc:
            raise ExampleError(f"{where} raised {type(exc).__name__}: {exc}") from exc
        finally:
            _close_figures()
    if caught:
        first = caught[0]
        raise ExampleError(f"{where} warned ({first.category.__name__}): {first.message}")
    reports = sorted(workdir.glob("*.html"))
    if len(reports) != 1:
        names = ", ".join(p.name for p in reports) or "none"
        raise ExampleError(f"{where} must save exactly one report with bf.save(); it saved {names}.")
    return reports[0]


def _close_figures() -> None:
    """Free Matplotlib figures between examples, if Matplotlib was used."""
    import sys

    pyplot = sys.modules.get("matplotlib.pyplot")
    if pyplot is not None:
        pyplot.close("all")
