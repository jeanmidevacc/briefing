"""Publish the reference for agents as ``llms.txt`` and ``llms-full.txt`` beside the built pages (#32).

``llms-full.txt`` is ``briefing/reference.md``, the file ``python -m briefing reference``
prints; ``llms.txt`` is a short index of it and of the pages an agent needs, following
https://llmstxt.org. Links are relative, so each version of the docs points to its own pages.
"""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sphinx.application import Sphinx

INDEX = """\
# briefing

> briefing turns analysis into one self-contained HTML report (text, numbers, charts, tables
> and layout in a single file that works offline), written in Python or as JSON that agents
> write and check.

These pages document briefing {release}. With briefing installed, `python -m briefing reference`
prints the reference of the installed version, and `python -m briefing validate report.json`
checks a report's JSON.

## Docs

- [Reference for agents](llms-full.txt): the JSON format, every block and option, the diagnostic codes, an example
- [Reports as JSON](guides/json.html): write a report's JSON, check it, render it
- [Quickstart](quickstart.html): a first report in Python
- [Blocks](api/blocks.html): every block's parameters, in Python

## Optional

- [Changelog](changelog.html): what changed in each version
"""


def write_llms(outdir: Path, release: str) -> None:
    """Write ``llms.txt`` and ``llms-full.txt`` into *outdir*."""
    reference = (files("briefing") / "reference.md").read_text(encoding="utf-8")
    (outdir / "llms-full.txt").write_text(reference, encoding="utf-8")
    (outdir / "llms.txt").write_text(INDEX.format(release=release), encoding="utf-8")


def _build_finished(app: Sphinx, exception: Exception | None) -> None:
    if exception is None and app.builder.format == "html":
        write_llms(Path(app.outdir), app.config.release)


def setup(app: Sphinx) -> dict[str, Any]:
    app.connect("build-finished", _build_finished)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
