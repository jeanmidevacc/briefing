"""bf.diff (#30): what changed between two runs of a report."""
from __future__ import annotations

import json
import typing as t
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from tests.banner_images import RED_SVG


def _run(leaders: list[str], intro: str = "Line one\nLine two", revenue: float = 1.2,
         status: str = "OK", extra: bool = False) -> bf.Briefing:
    ridings = pd.DataFrame({"riding": ["A", "B", "C"], "leader": leaders, "margin": [10, 20, 30]})
    summary = [bf.BigNumber("Revenue", revenue, name="revenue", format="${:.1f}M"),
               bf.BigNumber("Status", status, name="status"), bf.Text(intro, name="intro"), bf.Text("unnamed")]
    if extra:
        summary.append(bf.Alert("New", name="alert"))
    return bf.Briefing(bf.Page(*summary, title="Summary", name="summary"),
                       bf.Page(bf.DataTable(ridings, name="ridings"), title="Detail", name="detail"))


def _texts(report: bf.Briefing) -> list[str]:
    return [b.content for b in report.blocks if isinstance(b, bf.Text)]


def _table(report: bf.Briefing) -> pd.DataFrame:
    return next(b.df for b in report.blocks if isinstance(b, bf.DataTable))


def test_nothing_changed() -> None:
    result = bf.diff(_run(["L", "C", "N"]), _run(["L", "C", "N"]))
    assert _texts(result)[0].startswith("## What changed\n\nNothing changed")
    assert "1 unnamed block wasn't compared" in _texts(result)[0] and len(result.blocks) == 1


def test_numbers_show_their_change() -> None:
    result = bf.diff(_run(["L", "C", "N"], revenue=1.2, status="OK"), _run(["L", "C", "N"], revenue=1.5,
                                                                          status="late"))
    group = next(b for b in result.blocks if isinstance(b, bf.Group))
    revenue, status = group.blocks
    assert isinstance(revenue, bf.BigNumber) and revenue.prev_value == 1.2 and revenue.value == 1.5
    assert revenue.format == "${:.1f}M"
    assert isinstance(status, bf.BigNumber) and status.change == "was OK"
    assert "▲ +25.0%" in bf.stringify(result)


def test_a_keyed_table_lists_rows_added_removed_and_changed() -> None:
    old = bf.Briefing(bf.DataTable(pd.DataFrame({"id": [1, 2, 3], "v": [10, 20, 30]}), name="t"))
    new = bf.Briefing(bf.DataTable(pd.DataFrame({"id": [1, 2, 4], "v": [10, 25, 40], "w": [0, 0, 0]}), name="t"))
    result = bf.diff(old, new, keys={"t": "id"})
    assert "**`t`**: 1 added, 1 removed, 1 changed; columns added: w." in _texts(result)
    rows = _table(result).to_dict("records")
    assert rows == [{"change": "added", "id": "4", "v": "40"}, {"change": "removed", "id": "3", "v": "30"},
                    {"change": "changed", "id": "2", "v": "20 → 25"}]


def test_an_unkeyed_table_lists_rows_added_and_removed() -> None:
    old = bf.Briefing(bf.Table(pd.DataFrame({"a": [1, 2, 2]}), name="t"))
    new = bf.Briefing(bf.Table(pd.DataFrame({"a": [2, 3]}), name="t"))
    result = bf.diff(old, new)
    assert "**`t`**: 1 rows added, 2 removed." in _texts(result)
    assert _table(result).to_dict("records") == [{"change": "added", "a": "3"}, {"change": "removed", "a": "1"},
                                                 {"change": "removed", "a": "2"}]


def test_text_shows_a_line_diff() -> None:
    result = bf.diff(_run(["L", "C", "N"]), _run(["L", "C", "N"], intro="Line one\nLine 2"))
    code = next(b for b in result.blocks if isinstance(b, bf.Code))
    assert code.language == "diff" and "-Line two\n+Line 2" in code.content


def test_other_blocks_added_and_removed() -> None:
    old = bf.Briefing(bf.Image(RED_SVG, name="logo"), bf.Alert("Gone", name="old-alert"))
    new = bf.Briefing(bf.Image(RED_SVG, caption="Now captioned", name="logo"), bf.Alert("New", name="new-alert"))
    texts = _texts(bf.diff(old, new))
    assert "### Other blocks that changed\n\n- `logo` (Image)" in texts
    assert "### Added\n\n- `new-alert` (Alert)" in texts and "### Removed\n\n- `old-alert` (Alert)" in texts


def test_every_input_form(tmp_path: Path) -> None:
    old, new = _run(["L", "C", "N"]), _run(["L", "L", "N"])
    expected = bf.stringify(bf.diff(old, new))
    spec, data = bf.to_spec(old)
    inline = bf.to_spec(old, inline=True)[0]
    path = tmp_path / "old.json"
    path.write_text(json.dumps(inline), encoding="utf-8")
    for form in ((spec, data), inline, path, str(path)):
        assert bf.stringify(bf.diff(form, new)) == expected
    block = bf.diff(bf.Text("a", name="x"), bf.Text("b", name="x"))
    assert "1 block changed" in _texts(block)[0]


@pytest.mark.parametrize(("args", "kwargs", "match"), [
    ((3, bf.Briefing(bf.Text("x"))), {}, "old is a Briefing, a block"),
    (("/no/such.json", bf.Briefing(bf.Text("x"))), {}, "old file not found"),
    ((bf.Briefing(bf.Text("x")), bf.Briefing(bf.Text("x", name="x"))), {"keys": {"x": "id"}}, "aren't tables"),
])
def test_bad_inputs(args: tuple[t.Any, ...], kwargs: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.diff(*args, **kwargs)


def test_a_key_that_isnt_a_column() -> None:
    old = bf.Briefing(bf.DataTable(pd.DataFrame({"id": [1]}), name="t"))
    new = bf.Briefing(bf.DataTable(pd.DataFrame({"id": [2]}), name="t"))
    with pytest.raises(bf.BriefingError, match="the key \\['code'\\] of 't' isn't a column of both runs"):
        bf.diff(old, new, keys={"t": "code"})


def test_the_diff_is_a_report_that_keeps_the_contract() -> None:
    from tests.contract import RULES, parse_report

    soup = parse_report(bf.stringify(bf.diff(_run(["L", "C", "N"]), _run(["L", "L", "N"], extra=True),
                                             keys={"detail/ridings": "riding"})))
    for rule in RULES.values():
        rule(soup)
