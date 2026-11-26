"""The opt-in export menu: bf.Briefing(..., export="png") (#49, #119)."""
from __future__ import annotations

import pandas as pd
import pytest

import briefing as bf
from tests.html_helpers import attr, find_one, parse

EXPORT_JS_MARKER = "briefing export menu"


def test_menu_lists_the_requested_actions_in_the_header() -> None:
    html = bf.stringify(bf.Briefing(bf.Text("x"), export=("png",)), name="Q1")
    menu = find_one(parse(html), ".bf-report__header .bf-export")
    buttons = menu.select("button.bf-export__btn")
    assert [attr(b, "data-export") for b in buttons] == ["png"]
    assert [b.get_text() for b in buttons] == ["Save as PNG"]
    assert EXPORT_JS_MARKER in html


def test_a_single_string_works() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.Text("x"), export="png"), name="Q1"))
    assert [attr(b, "data-export") for b in soup.select(".bf-export button")] == ["png"]


def test_reports_without_export_contain_no_export_code() -> None:
    for report in (bf.Briefing(bf.Text("x")), bf.Briefing(bf.Text("x"), export=())):
        html = bf.stringify(report, name="Q1")
        assert "bf-export" not in html and EXPORT_JS_MARKER not in html


def test_menu_gets_a_header_even_with_the_default_name() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.Text("x"), export=("png",))))
    assert find_one(soup, ".bf-report__header .bf-export")


@pytest.mark.parametrize("bad", [("png", "gif"), ("svg",), "print", 3])
def test_unknown_actions_raise(bad: object) -> None:
    with pytest.raises(bf.BriefingError, match="export accepts 'png'"):
        bf.Briefing(bf.Text("x"), export=bad)  # type: ignore[arg-type]


def test_export_is_kept_when_a_briefing_is_rewrapped() -> None:
    inner = bf.Briefing(bf.Text("x"), export=("png",))
    assert bf.Briefing(inner).export == ("png",)
    assert bf.Briefing.wrap(inner).export == ("png",)


# ── export="pdf": the "Print" button is gone (removed in 0.4.0, tests/test_deprecations.py) ──


def test_there_is_only_a_save_as_png_button() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.Text("x"), export="png"), name="Q1"))
    assert [b.get_text() for b in soup.select(".bf-export button")] == ["Save as PNG"]


# ── export="snapshot": a camera button on each block (#215) ──


def _snapshot_report(*export: str) -> bf.Briefing:
    return bf.Briefing(
        bf.Page(
            bf.Text("# Summary"),
            bf.Group(bf.BigNumber("Revenue", "$4.2M"), label="Numbers"),
            bf.Group(bf.Text("plain")),
            title="Summary",
        ),
        bf.Page(bf.Table(pd.DataFrame({"n": [1]})), title="Detail"),
        export=export,
    )


def test_snapshot_marks_the_blocks_that_copy_embed_would() -> None:
    snap = parse(bf.stringify(_snapshot_report("snapshot"), name="Q1"))
    embed = parse(bf.stringify(_snapshot_report("embed"), name="Q1"))
    assert [str(el) for el in snap.select("[data-bf-snap]")] != []
    assert [el.get("class") for el in snap.select("[data-bf-snap]")] == [
        el.get("class") for el in embed.select("[data-bf-embed]")]
    labels = [attr(el, "data-bf-embed") for el in embed.select("[data-bf-embed]")]
    assert labels == ["the Summary page", "Summary", "Numbers", "Revenue", "this text", "the Detail page",
                      "this table"]
    # The heading's camera takes its section (#226); its copy-embed button, the heading alone.
    assert [attr(el, "data-bf-snap") for el in snap.select("[data-bf-snap]")] == [
        "the Summary page", "the Summary section", "Numbers", "Revenue", "this text", "the Detail page",
        "this table"]


def test_snapshot_alone_ships_the_script_but_no_menu_or_embed_data() -> None:
    html = bf.stringify(_snapshot_report("snapshot"), name="Q1")
    soup = parse(html)
    assert EXPORT_JS_MARKER in html
    assert soup.select(".bf-export, [data-bf-embed], script.bf-copy-data") == []
    assert any(".bf-copy__tools {" in style.get_text() for style in soup.select("style"))


def test_snapshot_and_embed_mark_the_same_blocks() -> None:
    soup = parse(bf.stringify(_snapshot_report("embed", "snapshot"), name="Q1"))
    snapped = soup.select("[data-bf-snap]")
    assert snapped and snapped == soup.select("[data-bf-embed]")


def test_reports_without_snapshot_have_no_snapshot_marks() -> None:
    for export in ((), ("png",), ("embed",)):
        html = bf.stringify(_snapshot_report(*export), name="Q1")
        assert parse(html).select("[data-bf-snap]") == []
        assert (EXPORT_JS_MARKER in html) == ("png" in export)


# ── rows and heading sections (#226) ──


def _labels(report: bf.Briefing, mark: str = "data-bf-snap") -> list[str]:
    return [attr(el, mark) for el in parse(bf.stringify(report, name="Q1")).select(f"[{mark}]")]


def _sections(report: bf.Briefing) -> dict[str, str]:
    soup = parse(bf.stringify(report, name="Q1"))
    return {attr(el, "data-bf-snap"): attr(el, "data-bf-section") for el in soup.select("[data-bf-section]")}


def test_a_row_of_blocks_gets_a_button_without_a_label() -> None:
    one, two = bf.BigNumber("One", 1), bf.BigNumber("Two", 2)
    for export, mark in (("snapshot", "data-bf-snap"), ("embed", "data-bf-embed")):
        report = bf.Briefing(
            bf.Group(one, two, columns=2),
            bf.Group(one, two, min_width="10rem"),
            bf.Group(one, two),  # a stack: no button
            bf.Group(one, columns=2),  # one block: no row
            export=(export,),
        )
        assert _labels(report, mark) == ["this row", "One", "Two", "this row", "One", "Two", "One", "Two", "One"]


def test_a_heading_takes_the_blocks_up_to_the_next_heading_of_its_level() -> None:
    report = bf.Briefing(
        bf.Text("## Activity"),
        bf.Group(bf.BigNumber("Runs", 3), bf.BigNumber("Rows", 9), columns=2),
        bf.Text("### Detail {#detail}\n\nRuns per day."),
        bf.Text("Last year."),
        bf.Text("## Next"),
        bf.Text("More."),
        bf.Text("# Last"),  # nothing after it: no section
        export=("snapshot",),
    )
    assert _sections(report) == {"the Activity section": "3", "the Detail section": "1", "the Next section": "1"}
    assert "Last" in _labels(report)


def test_only_a_heading_at_the_start_of_a_text_counts() -> None:
    report = bf.Briefing(
        bf.Text("Intro\n\n## Not a section"),
        bf.Text("#hashtag is not a heading"),
        bf.Text("## Real"),
        bf.Text("Body\n\n# A heading inside a text doesn't end the section"),
        bf.Text("tail"),
        export=("snapshot",),
    )
    assert _sections(report) == {"the Real section": "2"}


def test_sections_are_found_in_every_one_column_flow_but_not_across_columns() -> None:
    def flow() -> list[bf.Block]:
        return [bf.Text("## Head"), bf.Text("body")]

    report = bf.Briefing(
        bf.Page(bf.Group(*flow()), bf.Card(*flow(), title="Card"), bf.Toggle(*flow(), label="More"), title="A"),
        bf.Page(bf.Group(*flow(), columns=2), title="B"),  # side by side: no section
        export=("snapshot",),
    )
    soup = parse(bf.stringify(report, name="Q1"))
    flows = [el.parent.get("class") for el in soup.select("[data-bf-section]")]  # type: ignore[union-attr]
    assert len(flows) == 3
    assert {"bf-card__body"} <= {c for classes in flows for c in (classes or [])}
    assert all(attr(el, "data-bf-section") == "1" for el in soup.select("[data-bf-section]"))


def test_sections_are_only_marked_for_snapshots() -> None:
    report = bf.Briefing(bf.Text("## Head"), bf.Text("body"), export=("embed",))
    assert parse(bf.stringify(report, name="Q1")).select("[data-bf-section]") == []
    assert _labels(report, "data-bf-embed") == ["Head", "this text"]
