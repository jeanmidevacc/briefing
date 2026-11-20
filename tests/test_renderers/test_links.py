"""Named blocks and headings get link ids: ``page/name``, or ``name`` outside a named page (#24)."""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

import briefing as bf
from tests.banner_images import RED_SVG
from tests.html_helpers import attr, find_one, parse


def _render(*blocks: bf.Block) -> BeautifulSoup:
    return parse(bf.stringify(bf.Briefing(*blocks)))


def _links(soup: BeautifulSoup) -> list[str]:
    return [attr(el, "id") for el in soup.select("[data-bf-link]")]


def test_pages_and_the_blocks_in_them_link_by_their_names() -> None:
    soup = _render(
        bf.Page(bf.Text("a", name="intro"), title="Summary", name="summary"),
        bf.Page(bf.Select(bf.Text("n", label="N", name="north"), bf.Text("s", label="S"), name="by-region"),
                title="Detail", name="detail"),
    )
    assert _links(soup) == ["summary", "summary/intro", "detail", "detail/by-region", "detail/north"]
    assert "bf-group" in find_one(soup, '[id="detail"]')["class"]


def test_outside_a_named_page_a_name_links_as_itself() -> None:
    assert _links(_render(bf.Text("a", name="intro"), bf.Group(bf.Text("b", name="more")))) == ["intro", "more"]
    pages = _render(bf.Page(bf.Text("a", name="intro"), title="One"), bf.Page(bf.Text("b"), title="Two"))
    assert _links(pages) == ["intro"]


def test_unnamed_blocks_get_no_link() -> None:
    assert _links(_render(bf.Text("a"), bf.Toggle(bf.Text("b"), label="More"))) == []


def test_a_named_block_keeps_the_ids_its_parts_point_to() -> None:
    soup = _render(bf.Toggle(bf.Text("b"), label="More", name="more"))
    toggle = find_one(soup, ".bf-toggle")
    assert attr(toggle, "id") == "more"  # the made-up outer id gives way to the link
    body = attr(find_one(toggle, ".bf-toggle__body"), "id")
    assert attr(find_one(toggle, ".bf-toggle__header"), "aria-controls") == body


# ── headings ──────────────────────────────────────────────────────────────────


def test_a_named_heading_links_within_its_page() -> None:
    soup = _render(bf.Page(bf.Text("a"), title="One"),
                   bf.Page(bf.Text("## Methodology {#methodology}\n\nHow."), title="Detail", name="detail"))
    heading = find_one(soup, "h2")
    assert attr(heading, "id") == "detail/methodology"
    assert heading.get_text() == "Methodology"
    assert attr(find_one(heading, "a.bf-heading-link"), "href") == "#detail/methodology"


def test_a_heading_without_a_valid_name_stays_as_written() -> None:
    soup = _render(bf.Text("## Plain\n\n## Odd {#9lives}\n\n## Spaced {#a b}"))
    assert [h.get_text() for h in soup.select("h2")] == ["Plain", "Odd {#9lives}", "Spaced {#a b}"]
    assert soup.select("h2[id], .bf-heading-actions") == []


def test_a_banner_heading_can_be_named_too() -> None:
    soup = _render(bf.Banner("# Cover {#cover}", image=RED_SVG))
    assert attr(find_one(soup, ".bf-banner h1"), "id") == "cover"


# ── names are unique within a page ────────────────────────────────────────────


@pytest.mark.parametrize(
    "blocks",
    [
        [bf.Text("a", name="x"), bf.Text("b", name="x")],
        [bf.Text("a", name="x"), bf.Text("## X {#x}")],
        [bf.Text("## X {#x}\n\n## Again {#x}")],
        [bf.Page(bf.Text("a"), title="One", name="p"), bf.Page(bf.Text("b"), title="Two", name="p")],
        [bf.Page(bf.Group(bf.Text("## X {#x}")), bf.Toggle(bf.Text("a", name="x")), title="One", name="p"),
         bf.Page(bf.Text("b"), title="Two")],
    ],
    ids=["two-blocks", "block-and-heading", "two-headings", "two-pages", "nested-in-one-page"],
)
def test_a_name_used_twice_in_a_page_is_an_error(blocks: list[bf.Block]) -> None:
    with pytest.raises(bf.BriefingError, match="unique within its page"):
        bf.stringify(bf.Briefing(*blocks))


def test_the_same_name_in_two_pages_is_fine() -> None:
    soup = _render(
        bf.Page(bf.Text("## Notes {#notes}"), title="One", name="one"),
        bf.Page(bf.Text("## Notes {#notes}"), title="Two", name="two"),
    )
    assert _links(soup) == ["one", "one/notes", "two", "two/notes"]


def test_a_name_that_matches_a_made_up_id_is_an_error() -> None:
    with pytest.raises(bf.BriefingError, match="'sel-1-panel-0' matches the id 'sel-1'"):
        bf.stringify(bf.Briefing(bf.Select(bf.Text("a", label="A", name="sel-1-panel-0"), bf.Text("b", label="B"))))
