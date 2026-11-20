"""Keep the raw markup of one block inside that block.

``Text`` (markdown with raw HTML) and ``HTML`` pass the author's markup through
as it is. Left open at the end of the block, ``<!--`` would turn the rest of the
report into a comment and ``<script>`` would turn it into script, so every later
block, the footer and ``report.js`` would vanish. :func:`close_open_markup`
appends what closes it, following the HTML tokenizer's rules.
"""
from __future__ import annotations

import re

#: Elements whose content runs unparsed until their own end tag (raw text and RCDATA).
_RAW_TEXT = frozenset({"script", "style", "textarea", "title", "xmp", "iframe", "noembed", "noframes", "noscript"})
_SPACE = "\t\n\f\r "
_TAG_NAME = re.compile(r"[^\t\n\f\r />]*")


def close_open_markup(html: str) -> str:
    """Return *html* with whatever it leaves open at its end closed.

    That is an unclosed comment (``-->``), a tag cut off inside its attributes
    (``">``) or a raw-text element such as ``<script>`` or ``<style>`` (its end
    tag). Text is only ever appended, so markup that closes everything it opens
    comes back unchanged. ``<plaintext>`` and CDATA inside SVG are left as they are.

    Args:
        html: The markup of one block.

    Example::

        close_open_markup("<p>Intro</p>\\n<!-- draft")  # '<p>Intro</p>\\n<!-- draft-->'
    """
    i, n = 0, len(html)
    while (i := html.find("<", i)) >= 0 and i + 1 < n:
        after = html[i + 1]
        if html.startswith("<!--", i):
            end = _comment_end(html, i + 4)
            if end < 0:
                return html + "-->"
        elif after == "/" and i + 2 < n and _is_letter(html[i + 2]):  # an end tag
            end, suffix = _tag_end(html, _name_end(html, i + 2))
            if suffix:
                return html + suffix
        elif after in "!?" or (after == "/" and i + 2 < n and html[i + 2] != ">"):
            end = html.find(">", i + 2)  # a doctype, "<?…" or "</ …" ends at the next ">"
            if end < 0:
                return html + ">"
            end += 1
        elif _is_letter(after):  # a start tag
            name_end = _name_end(html, i + 1)
            name = html[i + 1:name_end].lower()
            end, suffix = _tag_end(html, name_end)
            if name in _RAW_TEXT:
                closing = re.compile(rf"</{re.escape(name)}(?=[{_SPACE}/>])", re.IGNORECASE).search(html, end)
                if closing is None:
                    return f"{html}{suffix}</{name}>"
                end = closing.start()
            elif suffix:
                return html + suffix
        else:
            end = i + 1  # "<" followed by anything else is text
        i = end
    return html


def _is_letter(char: str) -> bool:
    return char.isascii() and char.isalpha()


def _name_end(html: str, start: int) -> int:
    match = _TAG_NAME.match(html, start)
    return match.end() if match else start


def _comment_end(html: str, start: int) -> int:
    """The index just past the comment whose text starts at *start*, or -1 if it never ends."""
    if html.startswith(">", start):
        return start + 1  # <!-->
    if html.startswith("->", start):
        return start + 2  # <!--->
    ends = [found + len(mark) for mark in ("-->", "--!>") if (found := html.find(mark, start)) >= 0]
    return min(ends, default=-1)


def _tag_end(html: str, start: int) -> tuple[int, str]:
    """Where a tag whose attributes start at *start* ends, as (index past ``>``, "").

    If *html* ends inside the tag, returns (its length, the text that closes it).
    A quote only opens an attribute value right after ``=``, as in the tokenizer.
    """
    state, quote = "before", ""
    for k in range(start, len(html)):
        char = html[k]
        if state == "quoted":
            if char == quote:
                state = "before"
        elif char == ">":
            return k + 1, ""
        elif state == "value":
            if char in "\"'":
                state, quote = "quoted", char
            elif char not in _SPACE:
                state = "unquoted"
        elif state == "unquoted":
            if char in _SPACE:
                state = "before"
        elif char == "=" and state in ("name", "after_name"):
            state = "value"
        elif char in _SPACE:
            state = "after_name" if state == "name" else state
        elif char == "/":
            state = "before"
        else:
            state = "name"
    return len(html), (quote if state == "quoted" else "") + ">"
