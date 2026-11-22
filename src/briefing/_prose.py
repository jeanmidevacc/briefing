"""Prose with values (#184): ``Text(values=)`` fills ``{name}`` fields, and headings get slugs."""
from __future__ import annotations

import re
import string
import typing as t
import unicodedata
from collections.abc import Mapping

from briefing._error import BriefingError

#: ``{{``, ``}}``, or a field named by an identifier with an optional format spec.
_FIELD = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)(?::([^{}]*))?\}")
#: Fenced code blocks (``` or ~~~) and inline code spans, kept as one captured group for re.split.
_CODE = re.compile(
    r"(?:^|(?<=\n))[ ]{0,3}(?P<fence>`{3,}|~{3,})[^\n]*\n.*?(?:\n[ ]{0,3}(?P=fence)[`~]*[ \t]*(?=\n|$)|$)"  # fenced
    r"|(?<!`)(?P<ticks>`+)(?!`).+?(?<!`)(?P=ticks)(?!`)",  # inline: closed by a run of the same length
    re.S,
)
#: ASCII punctuation: a backslash before any of them shows it as written in CommonMark.
_PUNCTUATION = re.compile("([" + re.escape(string.punctuation) + "])")


def escape_markdown(text: str) -> str:
    """*text* with every ASCII punctuation mark backslash-escaped: Markdown shows it as written."""
    return _PUNCTUATION.sub(r"\\\1", text)


def fill(template: str, values: Mapping[str, t.Any]) -> str:
    """*template* with ``{name}`` and ``{name:spec}`` filled from *values*, each value escaped.

    Only fields named by an identifier are filled; other braces stay. ``{{`` and ``}}`` are
    literal braces.
    """
    if not isinstance(values, Mapping) or not all(isinstance(k, str) for k in values):
        raise BriefingError(f"Text: values is a dict of names and values, not {type(values).__name__}.")

    def one(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in ("{{", "}}"):
            return token[0]
        name, spec = match.group(1), match.group(2) or ""
        if name not in values:
            raise BriefingError(f"Text: no value for {{{name}}}; values has {sorted(values)!r}.")
        try:
            shown = format(values[name], spec)
        except (ValueError, TypeError) as exc:
            raise BriefingError(f"Text: {{{name}:{spec}}} can't show {values[name]!r}: {exc}.") from exc
        return escape_markdown(shown)

    # Code is shown as written: fields inside fenced blocks and inline code spans stay.
    out, end = [], 0
    for code in _CODE.finditer(template):
        out += [_FIELD.sub(one, template[end:code.start()]), code.group(0)]
        end = code.end()
    out.append(_FIELD.sub(one, template[end:]))
    return "".join(out)


def slug(text: str) -> str:
    """A link name for *text*: lower case, accents folded, anything else a ``-``.

    Names start with a letter, so a slug that would start with a digit gets ``h-`` in front.

    Args:
        text: A heading or any title.

    Example::

        bf.slug("🍕 Food and delivery")  # 'food-and-delivery'
        bf.slug("2026 results")          # 'h-2026-results'
    """
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    name = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    if not name:
        raise BriefingError(f"bf.slug: {text!r} has no letters or digits to make a name from.")
    return name if name[0].isalpha() else f"h-{name}"


__all__ = ["escape_markdown", "fill", "slug"]
