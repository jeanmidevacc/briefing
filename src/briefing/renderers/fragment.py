"""Fragments: blocks as one ``<div>`` to put into another page, like Plotly's ``full_html=False`` (#122).

A fragment is a ``<div class="bf-embed">`` that carries its own theme, ids that all
start with its *embed id*, and (unless ``include_assets=False``) briefing's CSS scoped
to ``.bf-embed`` and the scripts its blocks need. Its last script runs
``briefing.init(root)`` on that ``<div>`` only. Full reports don't go through here.
"""
from __future__ import annotations

import base64
import functools
import gzip
import hashlib
import html as _html
import json
import re
import typing as t
from collections.abc import Iterable
from datetime import datetime

from briefing._error import BriefingError
from briefing._version import __version__
from briefing.blocks.base import _NAME_RE, Block
from briefing.blocks.layout import Briefing
from briefing.renderers.css_scope import rem_to_var, scope_css
from briefing.renderers.formatting import Formatting
from briefing.renderers.html import (
    _CSS,
    _JS,
    _jinja_env,
    _load_static,
    _resolve_now,
    block_scripts,
    footer_text,
    render_content,
)
from briefing.renderers.normalize import normalize
from briefing.renderers.plot import runtime_sources, scan_for_plots
from briefing.renderers.registry import IdGen
from briefing.renderers.size import RUNTIME_NAMES, Part, block_parts

#: Stands for the embed id while the fragment is rendered, until a hash of it names it.
_TOKEN = "bfembedidtoken"


@functools.cache
def embed_css() -> str:
    """briefing's stylesheet, scoped to ``.bf-embed``, between the two embed files."""
    return scope_css(_load_static("embed-reset.css") + _CSS + _load_static("embed.css"))


def _runtime(defined: str, source: str) -> str:
    """A chart runtime that defines itself once per page, also where RequireJS is loaded."""
    return (
        f"<script>if (!window.{defined}) (function (define, module, exports) {{\n{source}\n}}).call(window);"
        "</script>\n"
    )


def asset_tags(roots: Iterable[Block]) -> str:
    """The ``<style>`` and ``<script>`` tags the fragments of *roots* need, each once."""
    roots = list(roots)
    libraries = set().union(*(scan_for_plots(root) for root in roots))
    scripts = list(dict.fromkeys(js for root in roots for js in block_scripts(root)))
    runtimes = "".join(_runtime(defined, source) for defined, source in runtime_sources(libraries))
    return f"<style>\n{embed_css()}</style>\n{runtimes}<script>{chr(10).join([_JS, *scripts])}</script>\n"


def check_embed_id(embed_id: str) -> str:
    if not _NAME_RE.match(embed_id):
        raise BriefingError(
            f"Invalid embed_id {embed_id!r}: like a block name, it must start with a letter and "
            "contain only letters, digits, '_' and '-'."
        )
    return embed_id


_HREF = re.compile(r'href="#([^"]*)"')


def _prefix_links(html: str, idgen: IdGen) -> str:
    """Point ``#detail/x`` links written with the report's names at this fragment's prefixed ids."""
    names = {link.removeprefix(idgen.prefix) for link in idgen.claimed}
    return _HREF.sub(lambda m: f'href="#{idgen.prefix}{m[1]}"' if m[1] in names else m[0], html)


def _named(root: Briefing) -> str | None:
    """The name a fragment takes by default: the report's, or that of its only block."""
    if root.name:
        return root.name
    return root.blocks[0].name if len(root.blocks) == 1 else None


def render_fragment(
    blocks: Briefing,
    name: str = "Report",
    formatting: Formatting | None = None,
    now: datetime | None = None,
    *,
    include_assets: bool = True,
    embed_id: str | None = None,
    header: bool = False,
    parts: list[Part] | None = None,
) -> str:
    """Render *blocks* as an HTML fragment: one ``<div class="bf-embed">``, see the module docstring.

    *embed_id* defaults to the report's name, else the name of its only block, else
    ``bf-e`` and 8 hex digits of a hash of the fragment. *name* shows only with *header*.
    *parts*, when given, is filled as by :func:`~briefing.renderers.html.render_report`.
    """
    fmt = formatting or Formatting()
    normalised = normalize(blocks)
    known = check_embed_id(embed_id) if embed_id else _named(normalised)

    idgen = IdGen(prefix=known or _TOKEN, weigh=parts is not None)
    content_html = _prefix_links(render_content(normalised, idgen), idgen)
    if parts is not None:
        parts += block_parts(blocks, idgen.weights or {})
        if include_assets:
            parts += [Part(RUNTIME_NAMES.get(defined, defined), len(source.encode()))
                      for defined, source in runtime_sources(scan_for_plots(normalised))]
    header_html = ""
    if header:
        when = _resolve_now(now)
        header_html = (
            f'<header class="bf-report__header"><span class="bf-report__title">{_html.escape(name)}</span>'
            f'<time class="bf-report__date" datetime="{when.isoformat()}">{when.strftime("%Y-%m-%d %H:%M UTC")}'
            "</time></header>"
        )
    theme_css = rem_to_var(fmt.to_css_vars(f"#{known or _TOKEN}"))
    if known is None:
        digest = hashlib.sha256(f"{theme_css}{header_html}{content_html}".encode()).hexdigest()[:8]
        known = f"bf-e{digest}"
        content_html, theme_css = content_html.replace(_TOKEN, known), theme_css.replace(_TOKEN, known)

    return _jinja_env.get_template("fragment.html.j2").render(
        embed_id=known,
        version=__version__,
        assets=asset_tags([normalised]) if include_assets else "",
        theme_css=theme_css,
        header_html=header_html,
        content_html=content_html,
        footer_text=footer_text(normalised.footer),
    )


def copy_data(
    root: Briefing, fmt: Formatting, body: str, prefix: str, embeds: list[dict[str, t.Any]], scripts: list[str]
) -> str:
    """The untouched copy that a report with copy-embed buttons carries (#124), as a ``<script>``.

    ``copy-embed.js`` cuts a block out of *body* (the report's blocks as rendered, before
    any script ran), renames the *prefix* its made-up ids start with to the block's embed
    id, and wraps it like :func:`render_fragment`: the scoped CSS, the scripts it needs
    (by their index in *scripts*, the report's own ``<script data-bf-script>`` tags), the
    theme on its id, the footer. Gzip with a fixed time keeps the bytes reproducible.
    """
    payload = {
        "version": __version__,
        "prefix": prefix,
        "token": _TOKEN,
        "css": embed_css(),
        "theme": rem_to_var(fmt.to_css_vars(f"#{_TOKEN}")),
        "footer": footer_text(root.footer),
        "blocks": [
            {"runtimes": embed["runtimes"], "scripts": [0, *(scripts.index(js) for js in embed["scripts"])]}
            for embed in embeds
        ],
        "body": body,
    }
    packed = gzip.compress(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(), compresslevel=9, mtime=0
    )
    return f'<script type="application/json" class="bf-copy-data">"{base64.b64encode(packed).decode("ascii")}"</script>'


def render_embed_assets(roots: Iterable[Block]) -> str:
    """The assets of :func:`render_fragment`, once for a page that holds several fragments."""
    return f"<!-- briefing {__version__} embed assets -->\n{asset_tags(roots)}"


__all__ = ["embed_css", "render_embed_assets", "render_fragment"]
