"""Typed BeautifulSoup helpers shared by the HTML tests.

beautifulsoup4 4.13+ types ``find()`` as ``Tag | None`` and attribute values as
``str | AttributeValueList``. These helpers assert what a test expects and hand
back plain types, so tests stay short and mypy stays strict.
"""
from __future__ import annotations

from bs4 import BeautifulSoup, Tag


def parse(html: str) -> BeautifulSoup:
    """Parse an HTML fragment or document with the stdlib parser."""
    return BeautifulSoup(html, "html.parser")


def find_one(root: Tag, selector: str) -> Tag:
    """Return the first element matching the CSS ``selector``; fail if there is none."""
    found = root.select_one(selector)
    assert found is not None, f"no element matches {selector!r}"
    return found


def attr(tag: Tag, name: str) -> str:
    """Return attribute ``name`` as a string; fail if it is missing.

    Multi-valued attributes such as ``class`` come back space-separated, as in the source.
    """
    value = tag.get(name)
    assert value is not None, f"<{tag.name}> has no {name!r} attribute"
    return value if isinstance(value, str) else " ".join(value)


def classes(tag: Tag) -> list[str]:
    """Return the element's classes (empty if it has no ``class`` attribute)."""
    return tag.get_attribute_list("class")
