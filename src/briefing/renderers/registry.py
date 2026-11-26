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

    def __init__(
        self,
        prefix: str | None = None,
        *,
        prefix_links: bool = True,
        embeds: bool = False,
        snaps: bool = False,
        weigh: bool = False,
    ) -> None:
        """Start numbering ids.

        *prefix_links* ``False`` leaves link ids unprefixed: a report with the copy-embed
        button prefixes its made-up ids but keeps its addresses (``#detail/x``). With
        *embeds*, :attr:`embeds` collects the blocks that get that button (#124). With
        *snaps*, the same blocks get a snapshot button (#215). With
        *weigh*, :attr:`weights` records the bytes of each block's own HTML (#38).
        """
        self._counter = itertools.count(1)
        self._prefix = f"{prefix}-" if prefix else ""
        self._link_prefix = self._prefix if prefix_links else ""
        #: What each block with a copy-embed button needs, in the order they render.
        self.embeds: list[dict[str, t.Any]] | None = [] if embeds else None
        #: Whether the blocks with a copy-embed label get a snapshot button too (#215).
        self.snaps = snaps
        #: id(block) -> how many blocks after it its heading section holds, in a one-column flow (#226).
        self.sections: dict[int, int] = {}
        #: id(block) -> the UTF-8 bytes of its rendered HTML, for each block that isn't a container.
        self.weights: dict[int, int] | None = {} if weigh else None
        self._made: list[str] = []
        self._links: dict[int, str] = {}  # id(block) -> its link id
        self._pages: dict[int, str | None] = {}  # id(block) -> the name of its page
        self._page_blocks: set[int] = set()  # id() of the blocks that are pages
        self._owners: dict[str, str] = {}  # link id -> what claimed it, for error messages
        self._named: dict[str, Block] = {}  # link id -> the named block that has it
        self._targets: list[tuple[Block, str, str, type]] = []  # (sender, name, link id, kind) to check (#21)

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

    def mark_page(self, block: Block) -> None:
        """Record that *block* is one of the report's pages."""
        self._page_blocks.add(id(block))

    def is_page(self, block: Block) -> bool:
        return id(block) in self._page_blocks

    def claim(self, block: Block, name: str, what: str) -> str:
        """Reserve the link id of *name* in *block*'s page and return it.

        *what* says what carries the name (``"a Text block"``, ``"a heading"``) for the
        error raised when another block or heading of the same page already has it.
        """
        page = self._pages.get(id(block))
        link = f"{self._link_prefix}{page}/{name}" if page else f"{self._link_prefix}{name}"
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
            self._links[id(block)] = link = self.claim(block, block.name, what)
            self._named[link] = block

    def target(self, sender: Block, name: str, kind: type) -> str:
        """The link id of the block named *name* in *sender*'s page, which must be a *kind* (#21).

        It's checked once every name is claimed, by :meth:`check_links`; until then,
        :meth:`named` may not know it yet (a block drawn alone).
        """
        page = self._pages.get(id(sender))
        link = f"{self._link_prefix}{page}/{name}" if page else f"{self._link_prefix}{name}"
        self._targets.append((sender, name, link, kind))
        return link

    def named(self, link: str) -> Block | None:
        """The named block whose link id is *link*, if one has claimed it."""
        return self._named.get(link)

    @property
    def claimed(self) -> list[str]:
        """Every link id claimed so far, prefix included."""
        return list(self._owners)

    def link(self, block: Block) -> str | None:
        """The link id of *block*, if it is named."""
        return self._links.get(id(block))

    def clashes(self) -> list[tuple[str, str]]:
        """Each claimed link id that matches an id briefing made up, with that id."""
        found = []
        for link in self._owners:
            clash = next((m for m in self._made if link == m or link.startswith(f"{m}-")), None)
            if clash is not None:
                found.append((link, clash))
        return found

    def missing_targets(self) -> list[tuple[Block, str]]:
        """Each block whose target (:meth:`target`) isn't a block of the kind it needs, and why."""
        found = []
        for sender, name, link, kind in self._targets:
            block = self._named.get(link)
            if isinstance(block, kind):
                continue
            page = self._pages.get(id(sender))
            where = f"in page {page!r}" if page else "in this report"
            others = sorted(str(b.name) for b in self._named.values()
                            if isinstance(b, kind) and self._pages.get(id(b)) == page)
            if others:
                there = f"The {kind.__name__} blocks there: {', '.join(map(repr, others))}."
            elif block is None:
                there = f"Give the {kind.__name__} name={name!r}."
            else:
                there = f"There is no named {kind.__name__} there."
            if block is None:
                problem = f"there is no block named {name!r} {where}"
            else:
                problem = f"the block named {name!r} {where} is a {type(block).__name__}, not a {kind.__name__}"
            found.append((sender, f"{type(sender).__name__} selects={name!r}, but {problem}. {there}"))
        return found

    def check_links(self) -> None:
        """Raise if a name matches an id briefing made up, so every id in the page stays unique,
        or if a block selects rows in a block that isn't there (#21)."""
        for link, clash in self.clashes():
            raise BriefingError(clash_message(link, clash))
        for _, message in self.missing_targets():
            raise BriefingError(message)


def clash_message(link: str, made: str) -> str:
    """What :meth:`IdGen.check_links` says when the name *link* matches the made-up id *made*."""
    return (
        f"The name {link!r} matches the id {made!r} that briefing gives another element "
        "of this report. Pick a name that doesn't look like '<word>-<number>'."
    )


_RENDERERS: dict[type, Renderer] = {}
_ASSET_JS: dict[type, str] = {}
_ASSET_CSS: dict[type, str] = {}
#: Scripts and stylesheets a block needs only with some options: (block class, test, js, css).
_OPTIONAL_ASSETS: list[tuple[type, Callable[[Block], bool], str | None, str | None]] = []


def register_assets(
    block_cls: type, when: Callable[[t.Any], bool], *, js: str | None = None, css: str | None = None
) -> None:
    """Inline *js* and *css* once when a *block_cls* block for which ``when(block)`` holds is present."""
    _OPTIONAL_ASSETS.append((block_cls, when, js, css))


def optional_assets_for(block: Block) -> list[tuple[str | None, str | None]]:
    """The ``(js, css)`` of each :func:`register_assets` entry that *block* needs."""
    return [(js, css) for cls, when, js, css in _OPTIONAL_ASSETS if isinstance(block, cls) and when(block)]


def register_renderer(
    block_cls: type, fn: Renderer, *, js_asset: str | None = None, css_asset: str | None = None
) -> None:
    """Register *fn* as the renderer for *block_cls*.

    *js_asset* is JavaScript, and *css_asset* a stylesheet, to inline in the report
    exactly once whenever a block of this type (or a subclass) appears in the tree.
    """
    _RENDERERS[block_cls] = fn
    if js_asset is not None:
        _ASSET_JS[block_cls] = js_asset
    if css_asset is not None:
        _ASSET_CSS[block_cls] = css_asset


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


def asset_css_for(block: Block) -> str | None:
    """Return the stylesheet that must be inlined when *block* is present, if any."""
    for klass in type(block).__mro__:
        css = _ASSET_CSS.get(klass)
        if css is not None:
            return css
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
