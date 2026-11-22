"""``validate``: every problem in a report or its JSON form, without raising (#31).

Three passes, each only when the one before found no error:

1. **Reading** (:class:`~briefing.spec._convert.Reader`): the JSON's shape and options,
   names, references, and each block's own constructor checks and warnings.
2. **Drawing each block alone**, so an error or a warning while rendering points at its block.
3. **Rendering the report's blocks together**, with an :class:`IdGen` that records name
   clashes (two headings named alike, a name that matches an id briefing makes up)
   instead of raising, so each points at the block that has it.

Passes 2 and 3 need every block built, so they are skipped while a reference has no object
(``validate(spec)`` without ``data``).
"""
from __future__ import annotations

import html as _html
import re
import typing as t
import warnings
from collections.abc import Iterator, Mapping

from briefing._error import BriefingError
from briefing.blocks.asset import Plot
from briefing.blocks.base import Block, ContainerBlock
from briefing.blocks.layout import Briefing, Page
from briefing.deck._blocks import Deck
from briefing.renderers.html import render_content, render_report
from briefing.renderers.normalize import normalize
from briefing.renderers.registry import IdGen, clash_message, lookup_renderer
from briefing.renderers.size import DEFAULT_MAX_SIZE, Part, over_budget, parse_size
from briefing.spec._convert import Reader, load, to_spec
from briefing.spec._diagnostic import Diagnostic

_ISSUES = "https://github.com/jeanmidevacc/briefing/issues"


def validate(
    report_or_spec: object, data: Mapping[str, t.Any] | None = None, max_size: int | str | None = DEFAULT_MAX_SIZE
) -> list[Diagnostic]:
    """Every problem :func:`briefing.validate` reports; never raises."""
    try:
        found = _validate(report_or_spec, data, parse_size(max_size))
    except BriefingError as exc:  # a max_size it can't read: the caller's mistake, said the same way
        found = [Diagnostic("error", "wrong-type", "", str(exc))]
    except RecursionError:
        found = [Diagnostic("error", "too-deep", "", "The blocks nest too deeply to check.",
                            "Flatten the report: a few levels of Group, Select and Toggle are plenty.")]
    except Exception as exc:  # noqa: BLE001 — validate never raises; this is briefing's bug, not the input's
        found = [Diagnostic("error", "internal-error", "", f"validate() itself failed: {type(exc).__name__}: {exc}",
                            f"This is a bug in briefing; please report it at {_ISSUES}.")]
    return _unique(found)


def _unique(found: list[Diagnostic]) -> list[Diagnostic]:
    """Each problem once: the same code at the same place is the same problem."""
    seen: set[tuple[str, str, str]] = set()
    kept = []
    for diagnostic in found:
        key = (diagnostic.code, diagnostic.path, diagnostic.message if diagnostic.severity == "warning" else "")
        if key not in seen:
            seen.add(key)
            kept.append(diagnostic)
    return kept


def _validate(report_or_spec: object, data: Mapping[str, t.Any] | None, limit: int | None) -> list[Diagnostic]:
    if isinstance(report_or_spec, Block | list | Deck):
        try:
            spec, data = to_spec(report_or_spec)
        except BriefingError as exc:
            return [Diagnostic("error", "unknown-type", "", str(exc))]
    else:
        spec, problem = load(report_or_spec)
        if problem is not None:
            return [problem]
    if data is not None and not isinstance(data, Mapping):
        return [Diagnostic("error", "wrong-type", "", f"data must be a dict of the objects the JSON names, "
                           f"not {type(data).__name__}.")]
    reader = Reader(data, capture_warnings=True)
    built = reader.root(spec)
    found = reader.diagnostics
    if built is None or reader.has_errors:
        return found
    # A deck's slides are checked as the blocks of one report; they render the same way.
    report = Briefing(*built.slides) if isinstance(built, Deck) else built
    paths = _paths(report, reader.paths)
    found += _draw_each(report, paths)
    if not any(d.severity == "error" for d in found):
        found += _render(report, paths, deck=isinstance(built, Deck))
    if isinstance(built, Deck):
        return found
    if limit is not None and not any(d.severity == "error" for d in found):
        found += _weigh(report, paths, limit)
    return found


def _weigh(report: Briefing, paths: dict[int, str], limit: int) -> list[Diagnostic]:
    """A ``too-big`` warning when the rendered report is over *limit* bytes (#38)."""
    parts: list[Part] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            html = render_report(report, parts=parts, paths=paths)
        except Exception as exc:  # noqa: BLE001 — reported, not raised
            return [Diagnostic("error", "render-error", "", f"{type(exc).__name__}: {exc}")]
    message = over_budget(len(html.encode()), parts, limit)
    if message is None:
        return []
    return [Diagnostic("warning", "too-big", "", message,
                       "Make it lighter (fewer rows with DataTable's max_rows=, smaller images), or pass "
                       "max_size= to change the limit.")]


def _paths(report: Briefing, built: dict[int, str]) -> dict[int, str]:
    """The JSON Pointer of every block in *report*; a block briefing added (a Toggle's Group) takes its parent's."""
    paths: dict[int, str] = {}

    def walk(block: Block, inherited: str) -> None:
        path = built.get(id(block), inherited)
        paths[id(block)] = path
        for child in block.blocks if isinstance(block, ContainerBlock) else []:
            walk(child, path)

    walk(report, "")
    return paths


def _walk(root: Block) -> Iterator[Block]:
    yield root
    for child in root.blocks if isinstance(root, ContainerBlock) else []:
        yield from _walk(child)


#: The "⚠" box a block renders as when it has nothing to draw, or can't draw what it was given.
_PLACEHOLDER = re.compile(r'<div class="[^"]*\bbf-placeholder\b[^"]*">(.*?)</div>', re.S)


def _draw_each(report: Briefing, paths: dict[int, str]) -> list[Diagnostic]:
    found = []
    for block in _walk(report):
        renderer = lookup_renderer(block)
        if isinstance(block, ContainerBlock) or renderer is None:
            continue
        path = paths[id(block)]
        tracer = _Tracer(paths)
        html = ""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                html = renderer(block, tracer)
            except Exception as exc:  # noqa: BLE001 — whatever stops a block from rendering is reported, not raised
                found.append(Diagnostic("error", "render-error", path,
                                        f"{type(block).__name__} can't be rendered: {type(exc).__name__}: {exc}"
                                        if not isinstance(exc, BriefingError) else str(exc)))
        found += tracer.found
        for warning in caught:
            code = "deprecated" if issubclass(warning.category, DeprecationWarning) else "block-warning"
            found.append(Diagnostic("warning", code, path, str(warning.message)))
        if box := _PLACEHOLDER.search(html):
            text = _html.unescape(re.sub(r"<[^>]+>", "", box[1])).strip().lstrip("⚠").strip()
            if isinstance(block, Plot):  # a figure it can't draw: the chart is missing
                found.append(Diagnostic("error", "render-error", path, f"This Plot shows a warning box instead of "
                                        f"a chart: {text}", "Pass a Plotly, Altair, Matplotlib or Bokeh figure."))
            else:
                found.append(Diagnostic("warning", "placeholder", path,
                                        f"This {type(block).__name__} shows a warning box: {text}"))
    return found


class _Tracer(IdGen):
    """An :class:`IdGen` that records name clashes, with the path of their block, instead of raising."""

    def __init__(self, paths: dict[int, str]) -> None:
        super().__init__()
        self.paths = paths
        self.found: list[Diagnostic] = []
        self._owners_of: dict[str, Block] = {}

    def claim(self, block: Block, name: str, what: str) -> str:
        try:
            link = super().claim(block, name, what)
        except BriefingError as exc:
            self.found.append(Diagnostic("error", "duplicate-name", self.paths.get(id(block), ""), str(exc)))
            return name  # carry on, to find the others
        self._owners_of[link] = block
        return link

    def check_links(self) -> None:
        for link, made in self.clashes():
            block = self._owners_of.get(link)
            path = self.paths.get(id(block), "") if block is not None else ""
            self.found.append(Diagnostic("error", "name-clash", path, clash_message(link, made)))


def _render(report: Briefing, paths: dict[int, str], deck: bool = False) -> list[Diagnostic]:
    try:
        normalised = report if deck else normalize(report)  # a deck's slides need no normalising
    except BriefingError as exc:
        return [Diagnostic("error", "render-error", "", str(exc))]
    paths = dict(paths)
    if all(isinstance(b, Page) for b in report.blocks):  # the pages became one Select of Groups
        for group, page in zip(normalised.blocks[0].blocks, report.blocks, strict=True):  # type: ignore[attr-defined]
            paths[id(group)] = paths[id(page)]
    paths = _paths(normalised, paths)
    tracer = _Tracer(paths)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # each block's warnings were reported when it was drawn alone
        try:
            render_content(normalised, tracer)
        except Exception as exc:  # noqa: BLE001 — reported, not raised
            return [*tracer.found, Diagnostic("error", "render-error", "", f"{type(exc).__name__}: {exc}")]
    return tracer.found
