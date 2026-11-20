"""Renderer registry — maps block classes to their HTML render functions.

Core blocks register here at import time (``renderer_for`` decorators in
``renderers/html.py``). Optional subpackages such as ``briefing.lab`` register
their own blocks when they are imported, and may attach a JS asset that the
renderer inlines only when a block of that type is present.

Lookup walks the block's MRO, so a subclass of a registered block inherits its
renderer instead of falling through to the placeholder.
"""
from __future__ import annotations

import itertools
import typing as t
from collections.abc import Callable, Iterator

from briefing._error import BriefingError

if t.TYPE_CHECKING:
    from briefing.blocks.base import Block

#: A renderer takes a block and the per-render ID generator, returns an HTML
#: fragment. The block parameter is typed ``Any`` so concrete renderers may
#: annotate their own block type (``_render_text(block: Text, ...)``) without
#: tripping function-argument contravariance.
Renderer = Callable[[t.Any, "IdGen"], str]


class IdGen:
    """Sequential DOM-ID generator, unique within one render pass.

    With a *prefix*, every id starts with ``<prefix>-``, so the ids of two outputs
    on one page can't collide.

    It also holds the link ids of named blocks and headings (#24): a block named
    ``methodology`` in the page named ``detail`` gets ``detail/methodology``, which
    is what ``#detail/methodology`` opens. ``renderers/links.py`` claims them before
    rendering; a name used twice within a page is an error.
    """

    def __init__(self, prefix: str | None = None) -> None:
        self._counter = itertools.count(1)
        self._prefix = f"{prefix}-" if prefix else ""
        self._made: list[str] = []
        self._links: dict[int, str] = {}  # id(block) -> its link id
        self._pages: dict[int, str | None] = {}  # id(block) -> the name of its page
        self._owners: dict[str, str] = {}  # link id -> what claimed it, for error messages

    @property
    def prefix(self) -> str:
        """The prefix every id starts with (``"revenue-"``), or ``""``."""
        return self._prefix

    def next(self, prefix: str = "bf") -> str:
        made = f"{self._prefix}{prefix}-{next(self._counter)}"
        self._made.append(made)
        return made

    def place(self, block: Block, page: str | None) -> None:
        """Record that *block* sits in the page named *page* (``None``: no named page)."""
        self._pages[id(block)] = page

    def claim(self, block: Block, name: str, what: str) -> str:
        """Reserve the link id of *name* in *block*'s page and return it.

        *what* says what carries the name (``"a Text block"``, ``"a heading"``) for the
        error raised when another block or heading of the same page already has it.
        """
        page = self._pages.get(id(block))
        link = f"{self._prefix}{page}/{name}" if page else f"{self._prefix}{name}"
        if link in self._owners:
            where = f" in page {page!r}" if page else ""
            raise BriefingError(
                f"Two blocks{where} are named {name!r}: {self._owners[link]} and {what}. A name must be "
                f"unique within its page, so that the link #{link} leads to one place; rename one of them."
            )
        self._owners[link] = what
        return link

    def name(self, block: Block, what: str) -> None:
        """Claim the link id of a named *block* (see :meth:`claim`)."""
        if block.name:
            self._links[id(block)] = self.claim(block, block.name, what)

    @property
    def claimed(self) -> list[str]:
        """Every link id claimed so far, prefix included."""
        return list(self._owners)

    def link(self, block: Block) -> str | None:
        """The link id of *block*, if it is named."""
        return self._links.get(id(block))

    def check_links(self) -> None:
        """Raise if a name matches an id briefing made up, so every id in the page stays unique."""
        for link in self._owners:
            clash = next((m for m in self._made if link == m or link.startswith(f"{m}-")), None)
            if clash is not None:
                raise BriefingError(
                    f"The name {link!r} matches the id {clash!r} that briefing gives another element "
                    "of this report. Pick a name that doesn't look like '<word>-<number>'."
                )


_RENDERERS: dict[type, Renderer] = {}
_ASSET_JS: dict[type, str] = {}


def register_renderer(block_cls: type, fn: Renderer, *, js_asset: str | None = None) -> None:
    """Register *fn* as the renderer for *block_cls*.

    *js_asset* is JavaScript to inline in the report exactly once whenever a
    block of this type (or a subclass) appears in the tree.
    """
    _RENDERERS[block_cls] = fn
    if js_asset is not None:
        _ASSET_JS[block_cls] = js_asset


def renderer_for(
    block_cls: type, *, js_asset: str | None = None
) -> Callable[[Renderer], Renderer]:
    """Decorator form of :func:`register_renderer`."""

    def _decorate(fn: Renderer) -> Renderer:
        register_renderer(block_cls, fn, js_asset=js_asset)
        return fn

    return _decorate


def lookup_renderer(block: Block) -> Renderer | None:
    """Return the renderer registered for *block*'s type or nearest base; else ``None``."""
    for klass in type(block).__mro__:
        fn = _RENDERERS.get(klass)
        if fn is not None:
            return fn
    return None


def asset_js_for(block: Block) -> str | None:
    """Return the JS asset that must be inlined when *block* is present, if any."""
    for klass in type(block).__mro__:
        js = _ASSET_JS.get(klass)
        if js is not None:
            return js
    return None


def iter_blocks(root: Block) -> Iterator[Block]:
    """Yield *root* and every descendant block, depth-first."""
    from briefing.blocks.base import ContainerBlock

    stack: list[Block] = [root]
    while stack:
        block = stack.pop()
        yield block
        if isinstance(block, ContainerBlock):
            stack.extend(block.blocks)


__all__ = [
    "IdGen",
    "Renderer",
    "asset_js_for",
    "iter_blocks",
    "lookup_renderer",
    "register_renderer",
    "renderer_for",
]
