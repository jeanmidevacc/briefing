"""``validate``: each problem it reports, with its code and place; it never raises (#31)."""
from __future__ import annotations

import json
import typing as t
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf


def _spec(*blocks: t.Any, **options: t.Any) -> dict[str, t.Any]:
    return {"briefing": 1, **options, "blocks": list(blocks)}


def _text(text: str = "a", **options: t.Any) -> dict[str, t.Any]:
    return {"type": "Text", "text": text, **options}


def _found(report_or_spec: t.Any, data: t.Any = None) -> list[tuple[str, str, str]]:
    return [(d.severity, d.code, d.path) for d in bf.validate(report_or_spec, data)]


def _one(report_or_spec: t.Any, data: t.Any = None) -> bf.Diagnostic:
    found = bf.validate(report_or_spec, data)
    assert len(found) == 1, found
    return found[0]


def test_a_good_report_has_no_problem() -> None:
    assert bf.validate(_spec(_text("# Hi"), {"type": "Group", "columns": 2, "blocks": [_text("a"), _text("b")]})) == []
    assert bf.validate(bf.Briefing(bf.Text("# Hi"))) == []


# ── reading the JSON ──────────────────────────────────────────────────────────


def test_text_that_isnt_json() -> None:
    problem = _one('{"briefing": 1, "blocks": [}')
    assert (problem.code, problem.path) == ("invalid-json", "")
    assert "line 1, column 28" in problem.message


def test_a_file_that_cant_be_read(tmp_path: Path) -> None:
    assert _one(tmp_path / "missing.json").code == "unreadable-file"


def test_json_that_isnt_a_report_object() -> None:
    assert _one("[1, 2]").code == "not-a-spec"
    assert _one(object()).code == "not-a-spec"


def test_the_format_version() -> None:
    assert _found({"blocks": [_text()]}) == [("error", "missing-version", "")]
    assert _found(_spec(_text()) | {"briefing": "1"}) == [("error", "wrong-type", "/briefing")]
    assert _found(_spec(_text()) | {"briefing": 0}) == [("error", "unsupported-version", "/briefing")]
    newer = _one({"briefing": 2, "blocks": [{"type": "Hologram"}], "theme": "dark"})  # nothing else is read
    assert newer.code == "unsupported-version" and newer.hint == "Upgrade briefing: pip install -U briefing."


def test_unknown_options_suggest_the_closest_one() -> None:
    root = _one(_spec(_text(), fotter="Team"))
    assert (root.code, root.path, root.hint) == ("unknown-option", "/fotter", 'Did you mean "footer"?')
    group = _one(_spec({"type": "Group", "colums": 2, "blocks": [_text()]}))
    assert (group.path, group.hint) == ("/blocks/0/colums", 'Did you mean "columns"?')
    blocks = _one(_spec({"type": "Text", "text": "a", "blocks": []}))
    assert blocks.code == "unknown-option" and blocks.hint == "Its options are: text, file, values, name, label."


def test_unknown_block_types() -> None:
    assert _one(_spec({"type": "Txt", "text": "a"})).hint == 'Did you mean "Text"?'
    assert _one(_spec({"type": "DataProfile", "df": {"ref": "x"}})).hint == 'Did you mean "lab.DataProfile"?'
    assert "go at the top of the JSON" in str(_one(_spec({"type": "Briefing", "blocks": []})).hint)
    assert _found(_spec({"text": "a"})) == [("error", "missing-type", "/blocks/0")]
    assert _found(_spec("just text")) == [("error", "not-a-block", "/blocks/0")]


def test_wrong_types_say_what_is_expected() -> None:
    problem = _one(_spec({"type": "Group", "columns": "2", "blocks": [_text()]}))
    assert (problem.code, problem.path) == ("wrong-type", "/blocks/0/columns")
    assert problem.message == 'Group "columns" must be a whole number, not "2".'
    assert _one(_spec({"type": "Group", "columns": 2.0, "blocks": [_text()]})).code == "wrong-type"
    level = _one(_spec({"type": "Alert", "message": "m", "level": "warn"}))
    assert level.message.startswith('Alert "level" must be one of "info", "success", "warning", "error"')
    name = _one(_spec(_text(name="1st")))
    assert name.message == 'Text "name" must be a name (a letter, then letters, digits, _ or -) or null, not "1st".'


def test_missing_options() -> None:
    assert _found(_spec({"type": "BigNumber", "heading": "Users"})) == [("error", "missing-option", "/blocks/0")]
    assert _one(_spec({"type": "Text"})).message == 'Text needs "text" (or "file", the path of a .md file).'
    assert _found({"briefing": 1}) == [("error", "missing-option", "")]


# ── the report's structure ────────────────────────────────────────────────────


def test_pages_go_at_the_top_and_only_with_other_pages() -> None:
    page = {"type": "Page", "title": "One", "blocks": [_text()]}
    assert _found(_spec(page, _text())) == [("error", "mixed-pages", "/blocks")]
    assert _found(_spec({"type": "Group", "blocks": [page]})) == [("error", "misplaced-page", "/blocks/0/blocks/0")]


def test_containers_that_need_blocks() -> None:
    assert _found(_spec()) == [("error", "empty-container", "/blocks")]
    assert _found(_spec({"type": "Toggle", "label": "More"})) == [("error", "empty-container", "/blocks/0")]
    assert _found(_spec({"type": "Page", "title": "One", "blocks": []})) == [("error", "empty-container", "/blocks/0")]
    assert _found(_spec({"type": "Group", "blocks": []})) == []  # a Group may be empty


def test_selects_need_two_labelled_panels() -> None:
    select = {"type": "Select", "blocks": [_text("a", label="A"), _text("b")]}
    problem = _one(_spec(select))
    assert (problem.severity, problem.code, problem.path) == ("warning", "missing-label", "/blocks/0/blocks/1")
    assert problem.message == 'This panel has no label, so its tab shows "Tab 2".'
    dropdown = _one(_spec(select | {"select_type": "dropdown"}))
    assert dropdown.message == 'This panel has no label, so its option shows "Option 2".'
    lonely = _spec({"type": "Select", "blocks": [_text(label="A")]})
    assert _found(lonely) == [("warning", "too-few-panels", "/blocks/0")]


def test_pages_without_a_title() -> None:
    pages = _spec({"type": "Page", "title": "One", "blocks": [_text()]}, {"type": "Page", "blocks": [_text()]})
    problem = _one(pages)
    assert (problem.code, problem.path, problem.message) == (
        "missing-label", "/blocks/1", 'This page has no title, so its tab shows "Tab 2".')


def test_names_are_unique_within_their_page() -> None:
    problem = _one(_spec(_text("a", name="x"), {"type": "Group", "blocks": [_text("b", name="x")]}))
    assert (problem.code, problem.path) == ("duplicate-name", "/blocks/1/blocks/0")
    assert problem.message == "Two blocks are named 'x': the one at /blocks/0 and this Text."
    two_pages = _spec({"type": "Page", "title": "A", "name": "a", "blocks": [_text(name="x")]},
                      {"type": "Page", "title": "B", "name": "b", "blocks": [_text(name="x")]})
    assert bf.validate(two_pages) == []
    in_tabs = _spec({"type": "Select", "blocks": [
        {"type": "Group", "label": "A", "name": "a", "blocks": [_text(name="x"), _text(name="x")]},
        {"type": "Group", "label": "B", "name": "b", "blocks": [_text(name="x")]},
    ]})
    assert _found(in_tabs) == [("error", "duplicate-name", "/blocks/0/blocks/0/blocks/1")]


def test_heading_names_are_checked_when_rendering() -> None:
    problem = _one(_spec(_text("## One {#part}\n\n## Two {#part}")))
    assert (problem.code, problem.path) == ("duplicate-name", "/blocks/0")
    assert "named 'part': the heading {#part} and the heading {#part}" in problem.message


def test_a_name_that_matches_an_id_briefing_makes_up() -> None:
    spec = _spec({"type": "Select", "blocks": [_text("a", label="A", name="sel-1-panel-0"), _text("b", label="B")]})
    problem = _one(spec)
    assert (problem.code, problem.path) == ("name-clash", "/blocks/0/blocks/0")
    assert "'sel-1-panel-0' matches the id 'sel-1'" in problem.message


# ── references ────────────────────────────────────────────────────────────────


def test_references_are_checked_against_data() -> None:
    spec = _spec({"type": "DataTable", "df": {"ref": "sales"}})
    assert bf.validate(spec) == []  # no data: not checked, and nothing rendered
    problem = _one(spec, {"sale": pd.DataFrame({"n": [1]})})
    assert (problem.code, problem.path, problem.hint) == ("unknown-ref", "/blocks/0/df", 'Did you mean "sale"?')
    assert bf.validate(spec, {"sales": pd.DataFrame({"n": [1]})}) == []
    assert _found(spec, [1]) == [("error", "wrong-type", "")]
    assert _found(_spec({"type": "DataTable", "df": {"ref": 3}}), {}) == [("error", "wrong-type", "/blocks/0/df")]


def test_any_option_can_be_a_reference() -> None:
    spec = _spec({"type": "BigNumber", "heading": "Ratio", "value": {"ref": "ratio"}})
    assert bf.validate(spec, {"ratio": float("nan")}) == []


# ── what blocks themselves check ──────────────────────────────────────────────


def test_bad_inline_data() -> None:
    rows = _one(_spec({"type": "DataTable", "df": {"columns": ["a", "b"], "rows": [[1]]}}))
    assert (rows.code, rows.path) == ("invalid-data", "/blocks/0/df")
    assert rows.message == 'DataTable "df": row 0 of the table has 1 values for 2 columns.'
    dtype = _one(_spec({"type": "DataTable", "df": {"columns": ["a"], "dtypes": ["nope"], "rows": [[1]]}}))
    assert dtype.code == "invalid-data" and "column 'a' doesn't hold nope values" in dtype.message
    image = _one(_spec({"type": "Banner", "text": "x", "image": "data:image/png;base64,***"}))
    assert image.code == "invalid-data"


def test_a_blocks_own_checks() -> None:
    widths = _one(_spec({"type": "Group", "columns": 2, "widths": [1], "blocks": [_text()]}))
    assert (widths.code, widths.path) == ("invalid-value", "/blocks/0")
    assert widths.message == "Group 'widths' length (1) must match 'columns' (2)."
    column = _one(_spec({"type": "lab.DataDive", "df": {"columns": ["a"], "rows": [[1]]}, "x": "b"}))
    assert column.code == "invalid-value" and "column 'b' (passed as 'x') not found" in column.message


def test_a_blocks_warnings() -> None:
    dropped = _one(_spec({"type": "DataTable", "df": {"columns": ["n"], "rows": [[1], [2]]}, "max_rows": 1}))
    assert (dropped.severity, dropped.code, dropped.path) == ("warning", "block-warning", "/blocks/0")
    assert "truncating to 1" in dropped.message


def test_deprecated_options(monkeypatch: pytest.MonkeyPatch) -> None:
    # Nothing is deprecated right now (the calendar's hour view was removed in 0.5.0, #111), so
    # a stand-in deprecation checks that one is reported as a "deprecated" warning.
    import functools
    import warnings

    original = bf.Alert.__init__

    @functools.wraps(original)
    def deprecated(self: bf.Alert, *args: t.Any, **kwargs: t.Any) -> None:
        warnings.warn("Alert: this option is deprecated since 0.5.0.", DeprecationWarning, stacklevel=2)
        original(self, *args, **kwargs)

    monkeypatch.setattr(bf.Alert, "__init__", deprecated)
    problem = _one(_spec({"type": "Alert", "message": "m"}))
    assert (problem.severity, problem.code, problem.path) == ("warning", "deprecated", "/blocks/0")
    assert "deprecated since 0.5.0" in problem.message


def test_a_figure_that_cant_be_drawn_is_an_error() -> None:
    problem = _one(_spec({"type": "Plot", "figure": {"ref": "figure"}}), {"figure": object()})
    assert (problem.severity, problem.code, problem.path) == ("error", "render-error", "/blocks/0")
    assert problem.message.startswith("This Plot shows a warning box instead of a chart: Unsupported figure type")


def test_a_block_with_nothing_to_draw_is_a_warning() -> None:
    problem = _one(_spec({"type": "lab.DataDive", "df": {"columns": [], "rows": []}}))
    assert (problem.severity, problem.code, problem.path) == ("warning", "placeholder", "/blocks/0")
    assert problem.message == "This DataDive shows a warning box: DataDive: no columns to display."


def test_a_warning_while_rendering_points_at_its_block() -> None:
    pytest.importorskip("latex2mathml")
    problem = _one(_spec(_text(), {"type": "Formula", "formula": r"\frac{a}{"}))
    assert (problem.severity, problem.code, problem.path) == ("warning", "block-warning", "/blocks/1")
    assert problem.message.startswith("Formula: couldn't convert")


# ── Python reports ────────────────────────────────────────────────────────────


def test_a_python_report_is_checked_through_its_json_form() -> None:
    report = bf.Briefing(bf.Text("a", name="x"), bf.Group(bf.Text("b", name="x")))
    assert _found(report) == [("error", "duplicate-name", "/blocks/1/blocks/0")]
    assert _found([bf.Select(bf.Text("a", label="A"))]) == [("warning", "too-few-panels", "/blocks/0")]


def test_a_block_class_briefing_doesnt_define() -> None:
    class Note(bf.Text):
        pass

    assert _found(bf.Briefing(Note("a"))) == [("error", "unknown-type", "")]


# ── it never raises ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("junk", [None, 3, "", "{", [], {}, {"briefing": 1, "blocks": [{}]}, b"{}", {"blocks": None}])
def test_junk_gets_diagnostics_not_exceptions(junk: t.Any) -> None:
    found = bf.validate(junk)
    assert found and all(isinstance(d, bf.Diagnostic) for d in found)


def test_blocks_nested_too_deeply() -> None:
    depth = 3000
    text = '{"briefing": 1, "blocks": [' + '{"type": "Group", "blocks": [' * depth + '{"type": "Text", "text": "a"}'
    text += "]}" * depth + "]}"
    assert _found(text) == [("error", "too-deep", "")]  # as JSON text
    spec: dict[str, t.Any] = _text()
    for _ in range(depth):
        spec = {"type": "Group", "blocks": [spec]}
    assert _found(_spec(spec)) == [("error", "too-deep", "")]  # as a dict


def test_a_diagnostic_reads_as_one_line_and_as_json() -> None:
    problem = _one(_spec({"type": "Group", "colums": 2, "blocks": [_text()]}))
    assert str(problem) == (
        'error unknown-option at /blocks/0/colums: Group has no option "colums". Did you mean "columns"?'
    )
    assert json.loads(json.dumps(problem.to_dict())) == {
        "severity": "error", "code": "unknown-option", "path": "/blocks/0/colums",
        "message": 'Group has no option "colums".', "hint": 'Did you mean "columns"?',
    }
