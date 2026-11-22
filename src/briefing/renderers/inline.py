"""Inline Markdown for short fields: captions, alert titles and messages, BigNumber headings (#26).

Only bold, italics, code, links, autolinks and backslash escapes render; block syntax
(headings, lists, tables) and images stay literal text, and raw HTML stays escaped,
unlike in ``Text``: these fields often hold values from data. Where text must be plain
(an ``alt`` attribute, a button's label, a file name), :func:`inline_plain` keeps the
words and drops the markup.
"""
from __future__ import annotations

import functools
import typing as t

if t.TYPE_CHECKING:
    from markdown_it import MarkdownIt

_RULES = ["emphasis", "backticks", "link", "image", "autolink", "escape", "entity", "newline"]


def _image_as_text(self: t.Any, tokens: t.Any, idx: int, options: t.Any, env: t.Any) -> str:
    """An image stays the text it was written as: no image is fetched or embedded from a caption."""
    import html

    token = tokens[idx]
    return html.escape(f"![{token.content}]({token.attrGet('src') or ''})")


def _space(self: t.Any, tokens: t.Any, idx: int, options: t.Any, env: t.Any) -> str:
    return " "


@functools.cache
def _parser() -> MarkdownIt:
    from markdown_it import MarkdownIt

    # "zero" turns everything off (html too); enable only the inline rules above.
    md = MarkdownIt("zero").enable(_RULES)
    md.add_render_rule("image", _image_as_text)
    for kind in ("softbreak", "hardbreak"):  # one line: a newline is a space
        md.add_render_rule(kind, _space)
    return md


def inline_markdown(text: str) -> str:
    """*text* as inline HTML: ``**bold**``, ``*italic*``, ```code```, ``[links](url)``; the rest escaped.

    Args:
        text: One short line of user text, such as a caption.

    Example::

        inline_markdown("Revenue, **in $k**")  # 'Revenue, <strong>in $k</strong>'
    """
    return str(_parser().renderInline(text)).strip()


def inline_plain(text: str) -> str:
    """*text* without its inline Markdown: the words a reader sees, as plain text (not escaped).

    Args:
        text: One short line of user text, such as a caption.

    Example::

        inline_plain("Revenue, **in $k**")  # 'Revenue, in $k'
    """
    parts: list[str] = []
    for token in _parser().parseInline(text):
        for child in token.children or []:
            if child.type in ("text", "code_inline"):
                parts.append(child.content)
            elif child.type == "image":
                parts.append(f"![{child.content}]({child.attrGet('src') or ''})")
            elif child.type in ("softbreak", "hardbreak"):
                parts.append(" ")
    return "".join(parts).strip()


__all__ = ["inline_markdown", "inline_plain"]
