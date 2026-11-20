"""close_open_markup keeps one block's raw markup from running into the rest of the report (#45)."""
from __future__ import annotations

import pytest
from hypothesis import given

from briefing.renderers.markup import close_open_markup
from tests.strategies import markup

CLOSED = [
    pytest.param("<p>plain <b>bold</b></p>", id="closed-elements"),
    pytest.param("a < b and c > d", id="bare-angle-brackets"),
    pytest.param("ends with <", id="trailing-lt"),
    pytest.param("ends with </", id="trailing-end-tag-open"),
    pytest.param("<!-- note --> after", id="comment"),
    pytest.param("<!-->", id="abruptly-closed-comment"),
    pytest.param("<!--->", id="abruptly-closed-comment-dash"),
    pytest.param("<!---->", id="empty-comment"),
    pytest.param("<!-- a --!> b", id="comment-closed-with-bang"),
    pytest.param("<SCRIPT>x</script >", id="script-any-case"),
    pytest.param("<script><!-- x</script>", id="comment-text-inside-script"),
    pytest.param('<div title="<!--">text</div>', id="comment-opener-in-attribute"),
    pytest.param("<p title='>'>a</p>", id="gt-in-quoted-attribute"),
    pytest.param('<p a"b=c>x</p>', id="quote-inside-attribute-name"),
    pytest.param("<br/>", id="self-closing"),
    pytest.param("</>", id="empty-end-tag"),
    pytest.param("<!DOCTYPE html>", id="doctype"),
]

OPEN = [
    pytest.param("<!-- draft note", "-->", id="comment"),
    pytest.param("<p>Intro</p>\n<!-- draft\n", "-->", id="comment-after-markdown"),
    pytest.param("<!-- a -", "-->", id="comment-ending-in-dash"),
    pytest.param("<!-- a --!", "-->", id="comment-ending-in-bang"),
    pytest.param("<script>var a = 1", "</script>", id="script"),
    pytest.param("<script>a = '</scripts>'", "</script>", id="script-with-longer-end-tag"),
    pytest.param("<style>", "</style>", id="style"),
    pytest.param("<STYLE>p { }", "</style>", id="style-upper-case"),
    pytest.param("<textarea>", "</textarea>", id="textarea"),
    pytest.param("<iframe>", "</iframe>", id="iframe"),
    pytest.param("<xmp>", "</xmp>", id="xmp"),
    pytest.param("<script", "></script>", id="script-tag-cut-off"),
    pytest.param("<script src='a", "'></script>", id="script-attribute-cut-off"),
    pytest.param('<a title="x', '">', id="double-quoted-attribute"),
    pytest.param("<a title='x", "'>", id="single-quoted-attribute"),
    pytest.param("<a href=x", ">", id="unquoted-attribute"),
    pytest.param("<a href=", ">", id="missing-attribute-value"),
    pytest.param("</div", ">", id="end-tag"),
    pytest.param("<!x", ">", id="bogus-comment"),
    pytest.param("<?php", ">", id="processing-instruction"),
    pytest.param("<!DOCTYPE html", ">", id="doctype"),
    pytest.param("<script>x</script><style>", "</style>", id="second-element"),
]


@pytest.mark.parametrize("html", CLOSED)
def test_markup_that_closes_everything_is_unchanged(html: str) -> None:
    assert close_open_markup(html) == html


@pytest.mark.parametrize(("html", "suffix"), OPEN)
def test_what_is_left_open_is_closed_at_the_end(html: str, suffix: str) -> None:
    assert close_open_markup(html) == html + suffix


@given(markup)
def test_it_only_appends_and_is_stable(html: str) -> None:
    closed = close_open_markup(html)
    assert closed.startswith(html)
    assert close_open_markup(closed) == closed
