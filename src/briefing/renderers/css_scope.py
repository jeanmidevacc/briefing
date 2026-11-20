"""Scope briefing's own CSS to an embedded fragment's root (#122).

A full report owns its page: its stylesheet styles ``html``, ``body`` and ``*``. A
fragment shares the page with its host, so every rule must stay inside the fragment:

- ``html``, ``body`` and ``:root`` become the root (``.bf-embed``), and so does
  ``html.bf-printing`` (``.bf-embed.bf-printing``: report.js puts the class on an
  element root while printing);
- ``*`` becomes the root and everything in it;
- every other selector gains the ``.bf-embed`` prefix, inside ``@media`` too;
- ``@page`` is dropped: it would set the host's print margins;
- a length in ``rem`` becomes ``calc(N * var(--bf-rem))``, so it follows the size the
  root sets instead of the host page's root font size.

This is for briefing's stylesheet only, not arbitrary CSS: no new dependency, and
it understands what report.css uses (rules, ``@media``, quoted strings, comments).
"""
from __future__ import annotations

import re
from collections.abc import Iterator

ROOT = ".bf-embed"

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_PAGE_ROOT = re.compile(r"^(?:html|body|:root)(?![\w-])")
_REM = re.compile(r"(?<![\w.-])(-?(?:\d+\.\d*|\.\d+|\d+))rem\b")
_NESTED_AT_RULES = ("@media", "@supports", "@container")


def scope_css(css: str, root: str = ROOT) -> str:
    """Return *css* with every rule scoped to the element matching *root*.

    Args:
        css: A stylesheet of briefing's own (report.css and the embed files).
        root: The selector of the fragment's root element.

    Example::

        scope_css("body { color: red } .bf-text p { margin: 1rem }")
        # '.bf-embed { color: red }\\n.bf-embed .bf-text p { margin: calc(1 * var(--bf-rem)) }\\n'
    """
    return "".join(_scope_rules(_COMMENT.sub("", css), root))


def rem_to_var(css: str) -> str:
    """Rewrite every ``rem`` length in *css* as a multiple of ``var(--bf-rem)``."""
    return _REM.sub(r"calc(\1 * var(--bf-rem))", css)


def _scope_rules(css: str, root: str) -> Iterator[str]:
    for prelude, body in _rules(css):
        if prelude.startswith("@page"):
            continue
        if prelude.startswith(_NESTED_AT_RULES):
            yield f"{prelude} {{\n{''.join(_scope_rules(body, root))}}}\n"
        elif prelude.startswith("@"):  # @property, @keyframes, @font-face: as they are
            yield f"{prelude} {{{body}}}\n"
        else:
            selectors = list(dict.fromkeys(s for part in split_selectors(prelude) for s in _scope_selector(part, root)))
            yield f"{', '.join(selectors)} {{ {rem_to_var(' '.join(body.split()))} }}\n"


def _scope_selector(selector: str, root: str) -> list[str]:
    selector = " ".join(selector.split())
    if re.match(rf"{re.escape(root)}(?![\w-])", selector):
        return [selector]  # already scoped (the embed files)
    page = _PAGE_ROOT.match(selector)
    if page:
        return [root + selector[page.end():]]
    if selector.startswith("*"):
        return [root + selector[1:], f"{root} {selector}"]
    return [f"{root} {selector}"]


def split_selectors(prelude: str) -> list[str]:
    """Split a selector list at its top-level commas (not those inside ``:is(…)`` or ``[…]``)."""
    parts, depth, start, quote = [], 0, 0, ""
    for i, char in enumerate(prelude):
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(prelude[start:i])
            start = i + 1
    parts.append(prelude[start:])
    return [p.strip() for p in parts if p.strip()]


def _rules(css: str) -> Iterator[tuple[str, str]]:
    """Each top-level rule of *css* as (prelude, text between its braces)."""
    i = 0
    while (open_ := _find_brace(css, i)) >= 0:
        close = _matching_brace(css, open_)
        yield " ".join(css[i:open_].split()), css[open_ + 1:close]
        i = close + 1


def _find_brace(css: str, start: int) -> int:
    quote = ""
    for i in range(start, len(css)):
        char = css[i]
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char == "{":
            return i
    return -1


def _matching_brace(css: str, open_: int) -> int:
    depth, quote = 0, ""
    for i in range(open_, len(css)):
        char = css[i]
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced braces in CSS")
