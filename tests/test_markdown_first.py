"""bf.from_markdown (#191): the prose in Markdown, Python supplying values and blocks."""
from __future__ import annotations

import typing as t
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from tests.contract import PAYLOAD, RULES, check_user_text_escaped, parse_report

OUTLINE = """## Topics and queries {#auto}

The {searches:,} searches are grouped into {groups} families.

::: block families
[Add the panel view with the families]
:::

```python
print(f"{not_a_field}")
```

That's all.
"""


def _kinds(report: bf.Briefing) -> list[str]:
    return [type(b).__name__ for b in report.blocks]


def test_prose_values_and_a_slot() -> None:
    report = bf.from_markdown(OUTLINE, values={"searches": 2410, "groups": 7},
                              blocks={"families": [bf.BigNumber("Families", 7), "A note"]})
    assert _kinds(report) == ["Text", "BigNumber", "Text", "Text"]
    first = t.cast(bf.Text, report.blocks[0])
    assert "The 2\\,410 searches are grouped into 7 families." in first.content
    html = bf.stringify(report)
    assert "Add the panel view" not in html  # the fence holds a note for the author
    assert 'id="topics-and-queries"' in html and "{not_a_field}" in html


def test_a_file(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text(OUTLINE, encoding="utf-8")
    for source in (path, str(path)):
        report = bf.from_markdown(source, values={"searches": 1, "groups": 2}, blocks={"families": "x"})
        assert _kinds(report) == ["Text", "Text", "Text"]


def test_slots_take_frames_strings_and_lists() -> None:
    report = bf.from_markdown("::: block t\n:::\n\n::: block many\n:::",
                              blocks={"t": pd.DataFrame({"a": [1]}), "many": ["one", bf.Alert("two")]})
    assert _kinds(report) == ["DataTable", "Text", "Alert"]


def test_pages() -> None:
    md = "# Overview {#overview}\n\nHello {x}.\n\n::: block t\n:::\n\n# The detail {#auto}\n\nMore.\n\n# Plain\n\nEnd."
    report = bf.from_markdown(md, values={"x": 1}, blocks={"t": "T"}, pages=True, footer="Team")
    pages = [(p.title, p.name, [type(b).__name__ for b in p.blocks]) for p in t.cast(list[bf.Page], report.blocks)]
    assert pages == [("Overview", "overview", ["Text", "Text"]), ("The detail", "the-detail", ["Text"]),
                     ("Plain", None, ["Text"])]
    assert report.footer == "Team"


@pytest.mark.parametrize(("md", "kwargs", "match"), [
    (OUTLINE, {"blocks": {"families": "x"}}, r"<markdown>:3: no value for \{searches\}"),
    (OUTLINE, {"values": {"searches": 1, "groups": 2}}, r"<markdown>:5: no block for the slot 'families'"),
    (OUTLINE, {"values": {"searches": 1, "groups": 2}, "blocks": {"families": "x", "extra": "y"}},
     r"blocks \['extra'\] have no slot"),
    ("Intro\n\n::: block a\nnote", {"blocks": {"a": "x"}}, r"<markdown>:3: the slot 'a' isn't closed"),
    ("::: note\nhi\n:::", {}, r"<markdown>:1: the only fence here is a slot"),
    ("Before\n\n# Page", {"pages": True}, r"<markdown>:1: with pages=True, the report starts with"),
    ("No heading", {"pages": True}, r"starts with a '# Page title' heading"),
    ("", {}, r"the report is empty"),
    ("::: block a\n:::", {"blocks": {"a": 3}}, r"the block for the slot 'a'"),
])
def test_errors_say_where(md: str, kwargs: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.from_markdown(md, **kwargs)


def test_a_missing_file() -> None:
    with pytest.raises(bf.BriefingError, match="file not found"):
        bf.from_markdown("no-such-report.md")


def test_values_stay_text_and_the_report_keeps_the_contract() -> None:
    report = bf.from_markdown("# Hi {who}\n\n{who} wrote this.\n\n# Two\n\nMore.", values={"who": PAYLOAD},
                              pages=True)
    soup = parse_report(bf.stringify(report))
    for rule in RULES.values():
        rule(soup)
    check_user_text_escaped(soup)
