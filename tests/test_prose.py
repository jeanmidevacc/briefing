"""Text(values=), bf.fmt and heading slugs (#184)."""
from __future__ import annotations

import datetime as dt
import typing as t

import pytest

import briefing as bf
from tests.contract import PAYLOAD
from tests.html_helpers import attr, find_one, parse


def _paragraph(text: bf.Text) -> t.Any:
    return find_one(parse(bf.stringify(bf.Briefing(text))), ".bf-text p")


# ── Text(values=) ─────────────────────────────────────────────────────────────


def test_fields_are_filled_and_formatted() -> None:
    p = _paragraph(bf.Text("{n:,} searches, {share:.1%} of them, on {day}.",
                           values={"n": 12345, "share": 0.253, "day": "May 19"}))
    assert p.get_text() == "12,345 searches, 25.3% of them, on May 19."


def test_values_show_exactly_as_written() -> None:
    p = _paragraph(bf.Text("Term: {term}", values={"term": "*not bold* [link](x) `code` \\ # 50%"}))
    assert p.get_text() == "Term: *not bold* [link](x) `code` \\ # 50%" and p.find(True) is None


def test_html_in_values_stays_text() -> None:
    p = _paragraph(bf.Text("Name: {name}", values={"name": PAYLOAD}))
    assert PAYLOAD in p.get_text() and p.find("img") is None


def test_other_braces_stay_as_they_are() -> None:
    text = bf.Text('## Food {#food}\n\nJSON {"a": 1}, set {1, 2}, CSS a { color: red }, {{name}}.\n\n```\n{x}\n```',
                   values={})
    assert text.content.startswith("## Food {#food}") and '{"a": 1}, set {1, 2}, CSS a { color: red }' in text.content
    assert "{name}." in text.content and "```\n{x}\n```" in text.content  # code is shown as written


def test_a_missing_value_names_the_ones_given() -> None:
    with pytest.raises(bf.BriefingError, match=r"no value for \{x\}; values has \['a', 'b'\]"):
        bf.Text("{x}", values={"a": 1, "b": 2})


def test_a_spec_that_doesnt_fit() -> None:
    with pytest.raises(bf.BriefingError, match=r"\{n:\.1%\} can't show 'many'"):
        bf.Text("{n:.1%}", values={"n": "many"})


def test_values_work_with_a_file(tmp_path: t.Any) -> None:
    path = tmp_path / "notes.md"
    path.write_text("Rose {change}.", encoding="utf-8")
    assert _paragraph(bf.Text(file=path, values={"change": "+25%"})).get_text() == "Rose +25%."


def test_the_json_form_keeps_the_filled_text() -> None:
    report = bf.Briefing(bf.Text("Rose {x}.", values={"x": "25%"}))
    spec, data = bf.to_spec(report)
    assert spec["blocks"] == [{"type": "Text", "text": "Rose 25\\%."}]
    assert bf.stringify(bf.from_spec(spec, data)) == bf.stringify(report)
    built = bf.from_spec({"briefing": 1, "blocks": [{"type": "Text", "text": "Rose {x}.", "values": {"x": "25%"}}]})
    assert bf.stringify(built) == bf.stringify(report)
    (problem,) = bf.validate({"briefing": 1, "blocks": [{"type": "Text", "text": "{y}", "values": {"x": 1}}]})
    assert problem.code == "invalid-value" and "no value for {y}" in problem.message


# ── bf.fmt ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("value", "long", "short"), [
    ("2026-11-19", "November 19, 2026", "Nov 19"),
    (dt.date(2026, 5, 1), "May 1, 2026", "May 1"),
    (dt.datetime(2026, 9, 3, 23, 59), "September 3, 2026", "Sep 3"),
])
def test_dates(value: object, long: str, short: str) -> None:
    assert bf.fmt.date(value) == long and bf.fmt.date(value, style="short") == short


def test_a_pandas_timestamp_is_a_date() -> None:
    pd = pytest.importorskip("pandas")
    assert bf.fmt.date(pd.Timestamp("2026-11-19 08:00")) == "November 19, 2026"


@pytest.mark.parametrize(("start", "end", "shown"), [
    ("2026-11-19", "2026-11-20", "November 19 to 20"),
    ("2026-11-30", "2026-12-02", "November 30 to December 2"),
    ("2026-12-30", "2027-01-02", "December 30, 2026 to January 2, 2027"),
    ("2026-11-19", "2026-11-19", "November 19"),
])
def test_spans(start: str, end: str, shown: str) -> None:
    assert bf.fmt.span(start, end) == shown


@pytest.mark.parametrize(("call", "shown"), [
    (lambda: bf.fmt.percent(0.253), "25%"),
    (lambda: bf.fmt.percent(0.253, sign=True), "+25%"),
    (lambda: bf.fmt.percent(-0.04, sign=True), "-4%"),
    (lambda: bf.fmt.percent(0.253, digits=1), "25.3%"),
    (lambda: bf.fmt.number(12345), "12,345"),
    (lambda: bf.fmt.number(1234.56, digits=1), "1,234.6"),
    (lambda: bf.fmt.number(41, sign=True), "+41"),
])
def test_numbers(call: t.Callable[[], str], shown: str) -> None:
    assert call() == shown


@pytest.mark.parametrize(("call", "match"), [
    (lambda: bf.fmt.date("soon"), "an ISO string"),
    (lambda: bf.fmt.date("2026-11-19", style="iso"), "style is 'long' or 'short'"),
    (lambda: bf.fmt.span("2026-11-20", "2026-11-19"), "end .* is before start"),
    (lambda: bf.fmt.percent(float("nan")), "a finite number"),
    (lambda: bf.fmt.number("12"), "a finite number"),
])
def test_bad_values(call: t.Callable[[], str], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        call()


# ── heading slugs ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("text", "name"), [
    ("🍕 Food and delivery", "food-and-delivery"),
    ("Québec élection, 2026!", "quebec-election-2026"),
    ("2026 results", "h-2026-results"),
    ("  Already-a-slug  ", "already-a-slug"),
])
def test_slug(text: str, name: str) -> None:
    assert bf.slug(text) == name


def test_a_slug_needs_letters_or_digits() -> None:
    with pytest.raises(bf.BriefingError, match="no letters or digits"):
        bf.slug("🍕 !")


def test_auto_headings_link_by_their_slug() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.Text("## 🍕 Food and `delivery` {#auto}\n\n## Named {#mine}"))))
    first, second = soup.select(".bf-text h2")
    assert attr(first, "id") == "food-and-delivery" and first.get_text().startswith("🍕 Food and delivery")
    assert attr(second, "id") == "mine"


def test_two_headings_with_one_slug_clash() -> None:
    problems = bf.validate(*bf.to_spec(bf.Briefing(bf.Text("## Food {#auto}\n\n## Food! {#auto}"))))
    assert [p.code for p in problems] == ["duplicate-name"]


def test_code_is_shown_as_written() -> None:
    text = bf.Text("Use `{name}` or ``a `{b}` c``:\n\n```python\nf'{total}'\n```\n\n~~~\n{q}\n~~~\n\nNow {x}.",
                   values={"x": "1"})
    assert "`{name}`" in text.content and "``a `{b}` c``" in text.content
    assert "f'{total}'" in text.content and "~~~\n{q}\n~~~" in text.content and text.content.endswith("Now 1.")
