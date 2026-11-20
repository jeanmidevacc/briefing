"""Property tests for the JSON form (#31): any JSON gets diagnostics, never an exception.

Hypothesis writes report JSON the way an agent might, right or wrong: real block types
with good and bad options, misspelt keys, names that clash, empty containers, tables
with missing cells. For each:

- ``validate`` never raises;
- it reports an error exactly when building or rendering the report fails;
- a report that builds survives ``to_spec`` and ``from_spec`` again, byte for byte.
"""
from __future__ import annotations

import json
import typing as t
import warnings

from hypothesis import event, given
from hypothesis import strategies as st

import briefing as bf
from tests.contract import RULES, parse_report
from tests.golden import NOW

Strategy = st.SearchStrategy[t.Any]

#: Any JSON value at all, for the places an agent might put the wrong thing.
JSON: Strategy = st.recursive(
    st.none() | st.booleans() | st.integers(-3, 3) | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=6),
    lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=6), inner, max_size=3),
    max_leaves=8,
)

TEXT = st.text(max_size=12)
WORD = st.text("abcxyz -#*{}", max_size=10)
LABEL = st.none() | st.sampled_from(["A", "B", ""])


def _block(type_: str, required: dict[str, Strategy], optional: dict[str, Strategy], broken: bool) -> Strategy:
    """A block of *type_*; when *broken*, any option may be any JSON and it may have an unknown one."""
    if broken:
        required = {k: st.one_of(v, v, v, JSON) for k, v in required.items()}
        optional = {**{k: st.one_of(v, v, v, JSON) for k, v in optional.items()}, "colour": JSON}
    names = st.sampled_from(["a", "b", "x", "sel-1-panel-0", "1st", ""] if broken else ["a", "b", "x"])
    return st.fixed_dictionaries({"type": st.just(type_), **required}, optional={**optional, "name": names})


def _tables(broken: bool) -> Strategy:
    columns = st.lists(st.sampled_from(["n", "w", "x"]), min_size=1, max_size=3, unique=True)
    cell = st.none() | st.integers(-5, 5) | st.sampled_from(["a", "b"])
    return columns.flatmap(lambda cs: st.fixed_dictionaries({
        "columns": st.just(cs),
        "rows": st.lists(st.lists(cell, min_size=len(cs) - broken, max_size=len(cs)), max_size=4),
    }))


def _leaves(broken: bool) -> Strategy:
    leaves = [
        _block("Text", {"text": WORD.filter(str.strip)}, {"label": LABEL}, broken),
        _block("BigNumber", {"heading": WORD, "value": WORD | st.integers()},
               {"change": WORD, "is_upward_change": st.none() | st.booleans()}, broken),
        _block("Alert", {"message": WORD},
               {"level": st.sampled_from(["info", "warning", "warn"] if broken else ["info", "warning"]),
                "title": WORD}, broken),
        _block("Code", {"code": TEXT}, {"language": st.sampled_from(["python", "sql", "nope"]), "caption": WORD},
               broken),
        _block("HTML", {"html": st.text("abc <b>", max_size=10)}, {}, broken),
        _block("DataTable", {"df": _tables(broken)}, {"max_rows": st.integers(0, 3), "caption": WORD}, broken),
    ]
    if broken:
        leaves.append(st.fixed_dictionaries({"type": st.sampled_from(["Txt", "Page", "Briefing"]), "text": WORD}))
    return st.one_of(leaves)


def _containers(broken: bool) -> t.Callable[[Strategy], Strategy]:
    def make(children: Strategy) -> Strategy:
        blocks = st.lists(children, max_size=3)
        group = {"columns": st.integers(0, 3), "widths": st.lists(st.integers(-1, 2)),
                 "valign": st.sampled_from(["top", "middle"])} if broken else {"columns": st.integers(1, 3)}
        return st.one_of(
            _block("Group", {"blocks": blocks}, {**group, "label": LABEL}, broken),
            _block("Select", {"blocks": blocks},
                   {"select_type": st.sampled_from(["tabs", "dropdown", "x"] if broken else ["tabs", "dropdown"]),
                    "label": LABEL}, broken),
            _block("Toggle", {"blocks": st.lists(children, min_size=0 if broken else 1, max_size=2)},
                   {"label": LABEL}, broken),
        )

    return make


def _specs(broken: bool) -> Strategy:
    blocks = st.recursive(_leaves(broken), _containers(broken), max_leaves=6)
    pages = st.lists(_block("Page", {"blocks": st.lists(blocks, min_size=1, max_size=3)}, {"title": LABEL}, broken),
                     min_size=1, max_size=3)
    return st.fixed_dictionaries(
        {"briefing": st.sampled_from([1, 1, 1, 2] if broken else [1]),
         "blocks": st.one_of(st.lists(blocks, min_size=1, max_size=3), pages)},
        optional={"footer": WORD, "export": st.sampled_from(
            [[], ["png"], ["embed"], ["pdf"], "png"] if broken else [[], ["png"], ["embed"], ["png", "embed"]])},
    )


#: Report JSON as an agent might write it: half of it right, half of it with mistakes.
SPECS: Strategy = st.one_of(_specs(broken=False), _specs(broken=True))


def _build_and_render(spec: t.Any) -> str | None:
    """The report's HTML, or ``None`` when it can't be built or rendered."""
    try:
        return bf.stringify(bf.from_spec(spec), now=NOW)
    except bf.BriefingError:
        return None


@given(SPECS)
def test_validate_reports_an_error_exactly_when_the_report_fails(spec: dict[str, t.Any]) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        found = bf.validate(spec)
        html = _build_and_render(spec)
    assert all(isinstance(d, bf.Diagnostic) and d.severity in ("error", "warning") for d in found)
    errors = [d for d in found if d.severity == "error"]
    event("renders" if html is not None else "fails")
    assert (html is None) == bool(errors), errors
    if html is not None:
        soup = parse_report(html)
        for rule in RULES.values():
            rule(soup)


@given(SPECS)
def test_a_report_that_builds_survives_another_round_trip(spec: dict[str, t.Any]) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        html = _build_and_render(spec)
        if html is None:
            return
        again, data = bf.to_spec(bf.from_spec(spec), inline=True)
        assert data == {}
        assert bf.stringify(bf.from_spec(json.loads(json.dumps(again))), now=NOW) == html


@given(JSON, st.text(max_size=30))
def test_any_json_gets_diagnostics_never_an_exception(junk: t.Any, text: str) -> None:
    # As JSON text (a Python list would be a list of blocks, a Python report), and as broken JSON text.
    for found in (bf.validate(json.dumps(junk)), bf.validate("{" + text)):
        assert found and all(isinstance(d, bf.Diagnostic) for d in found)
    if isinstance(junk, dict):
        assert any(d.severity == "error" for d in bf.validate(junk))
