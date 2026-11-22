"""How heavy a report is, and what makes it so: the size budget (#38).

:func:`~briefing.renderers.html.render_report` and
:func:`~briefing.renderers.fragment.render_fragment` list the :class:`Part` objects a
report is made of when asked to (each block's own HTML, each chart runtime, the
copy-embed data); :func:`check_size` warns when the whole is over ``max_size``,
naming the largest parts.
"""
from __future__ import annotations

import re
import typing as t
import warnings
from dataclasses import dataclass

from briefing._error import BriefingError
from briefing.blocks.base import Block, ContainerBlock

#: The budget ``save``, ``stringify`` and ``validate`` use unless told otherwise.
DEFAULT_MAX_SIZE = "10 MB"

_UNITS = {"": 1, "b": 1, "kb": 10**3, "mb": 10**6, "gb": 10**9}
_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kmg]?b?)\s*$", re.I)

#: What a chart runtime is called, by the global it defines.
RUNTIME_NAMES = {"Plotly": "the Plotly runtime", "vegaEmbed": "the Vega runtime"}


def parse_size(value: int | str | None) -> int | None:
    """``max_size`` in bytes: a number of bytes, or text such as ``"10 MB"`` (``None``: no budget)."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    match = _SIZE.match(value) if isinstance(value, str) else None
    if match is None or float(match.group(1)) <= 0:
        raise BriefingError(
            f"max_size takes a number of bytes or a size such as '10 MB', '500 KB' or '1.5 GB', "
            f"or None for no limit; not {value!r}."
        )
    return int(float(match.group(1)) * _UNITS[match.group(2).lower()])


def format_size(size: int) -> str:
    """*size* bytes for a person: ``"14.2 MB"``, ``"850 KB"``, ``"512 B"``."""
    if size >= 10**6:
        return f"{size / 10**6:.1f} MB"
    if size >= 10**3:
        return f"{size / 10**3:.0f} KB"
    return f"{size} B"


@dataclass(frozen=True)
class Part:
    """Something a report holds, and how many bytes it takes."""

    what: str  # "DataTable at /blocks/2", "the Plotly runtime"
    size: int


def block_paths(root: Block) -> dict[int, str]:
    """The path of each block under *root* by its place: ``/blocks/1/blocks/0``, as ``bf.to_spec`` writes it."""
    paths: dict[int, str] = {}

    def walk(block: Block, path: str) -> None:
        paths[id(block)] = path
        for i, child in enumerate(block.blocks if isinstance(block, ContainerBlock) else []):
            walk(child, f"{path}/blocks/{i}")

    walk(root, "")
    return paths


def block_parts(root: Block, weights: dict[int, int], paths: dict[int, str] | None = None) -> list[Part]:
    """A part for each block under *root* whose rendered HTML was weighed (``IdGen(weigh=True)``)."""
    from briefing.spec._model import type_name

    blocks: dict[int, Block] = {}

    def walk(block: Block) -> None:
        blocks[id(block)] = block
        for child in block.blocks if isinstance(block, ContainerBlock) else []:
            walk(child)

    walk(root)
    paths = paths if paths is not None else block_paths(root)

    def what(block: Block) -> str:
        kind = type_name(block) or type(block).__name__
        named = f' "{block.name}"' if block.name else ""
        return f"{kind}{named} at {paths.get(id(block)) or '/'}"

    return [Part(what(blocks[i]), size) for i, size in weights.items() if i in blocks]


def over_budget(total: int, parts: t.Sequence[Part], limit: int) -> str | None:
    """What the budget warning says when *total* bytes is over *limit*, else ``None``."""
    if total <= limit:
        return None
    largest = [p for p in sorted(parts, key=lambda p: -p.size)[:3] if p.size * 100 >= total]  # 1 % or more
    listed = ", ".join(f"{p.what} ({format_size(p.size)})" for p in largest)
    hint = ""
    if largest and largest[0].what.startswith(("Image", "Banner")):  # a picture is the heaviest part (#186)
        hint = (' To make it lighter, give it max_width=2400 and format="webp" '
                '(pip install "briefing[pillow]").')
    return (
        f"The report is {format_size(total)}, over max_size ({format_size(limit)})"
        + (f"; its largest parts: {listed}." if listed else ".") + hint
    )


def check_size(html: str, parts: t.Sequence[Part], max_size: int | None, *, stacklevel: int) -> None:
    """Warn when *html* is over *max_size* bytes, naming its largest *parts*."""
    if max_size is None:
        return
    message = over_budget(len(html.encode()), parts, max_size)
    if message is not None:
        warnings.warn(
            f"{message} Pass max_size= to change the limit, or None to turn this warning off.",
            UserWarning,
            stacklevel=stacklevel + 1,
        )
