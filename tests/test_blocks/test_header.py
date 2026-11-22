"""bf.Header: subtitle, author, logo, "data as of" date and time zone in the report header (#25)."""
from __future__ import annotations

import datetime as dt
import typing as t
from pathlib import Path

import pytest

import briefing as bf
from tests.banner_images import PNG_MAGIC, RED_SVG
from tests.html_helpers import attr, find_one, parse

NOW = dt.datetime(2026, 11, 22, 14, 0, tzinfo=dt.UTC)


def _header(report: bf.Briefing, name: str = "Search report", **kwargs: t.Any) -> t.Any:
    return parse(bf.stringify(report, name=name, now=NOW, **kwargs)).find("header")


def test_every_field() -> None:
    header = _header(bf.Briefing(bf.Text("x"), header=bf.Header(
        subtitle="Weekly **search** interest", author="Analytics <team>", logo=RED_SVG,
        as_of="2026-11-20", tz="America/Montreal")))
    logo = find_one(header, "img.bf-report__logo")
    assert attr(logo, "src").startswith("data:image/svg+xml;base64,") and attr(logo, "alt") == ""
    heading = find_one(header, ".bf-report__heading")
    assert find_one(heading, ".bf-report__title").get_text() == "Search report"
    assert find_one(heading, ".bf-report__subtitle strong").get_text() == "search"
    assert find_one(heading, ".bf-report__author").get_text() == "By Analytics <team>"  # escaped
    assert find_one(header, ".bf-report__asof").get_text() == "Data as of 2026-11-20"
    date = find_one(header, "time.bf-report__date")
    assert date.get_text() == "2026-11-22 09:00 EST" and attr(date, "datetime") == "2026-11-22T09:00:00-05:00"


@pytest.mark.parametrize(("as_of", "tz", "shown"), [
    (dt.date(2026, 11, 20), None, "2026-11-20"),
    (dt.datetime(2026, 11, 20, 23, 30, tzinfo=dt.UTC), "America/Montreal", "2026-11-20 18:30 EST"),
    (dt.datetime(2026, 11, 20, 23, 30), "America/Montreal", "2026-11-20 23:30 EST"),  # naive: already local
    ("2026-07-01T12:00:00+00:00", "Europe/Paris", "2026-07-01 14:00 CEST"),
    ("2026-07-01T12:00", None, "2026-07-01 12:00 UTC"),
])
def test_as_of(as_of: t.Any, tz: str | None, shown: str) -> None:
    header = _header(bf.Briefing(bf.Text("x"), header=bf.Header(as_of=as_of, tz=tz)))
    assert find_one(header, ".bf-report__asof").get_text() == f"Data as of {shown}"


def test_a_pandas_timestamp_is_a_datetime() -> None:
    pd = pytest.importorskip("pandas")
    assert bf.Header(as_of=pd.Timestamp("2026-11-20 08:00")).as_of == dt.datetime(2026, 11, 20, 8, 0)


def test_the_render_time_without_tz_is_unchanged() -> None:
    plain = _header(bf.Briefing(bf.Text("x")))
    with_header = _header(bf.Briefing(bf.Text("x"), header=bf.Header(author="A")))
    assert find_one(with_header, "time.bf-report__date") == find_one(plain, "time.bf-report__date")


def test_the_default_name_is_never_a_title() -> None:
    assert _header(bf.Briefing(bf.Text("x")), name="Report") is None
    menu_only = _header(bf.Briefing(bf.Text("x"), export="png"), name="Report")
    assert menu_only.select(".bf-report__title") == [] and menu_only.select("time.bf-report__date")
    header_only = _header(bf.Briefing(bf.Text("x"), header=bf.Header(subtitle="Sub")), name="Report")
    assert header_only.select(".bf-report__title") == []
    assert find_one(header_only, ".bf-report__subtitle").get_text() == "Sub"


def test_a_logo_from_a_file_bytes_or_data_uri(tmp_path: Path) -> None:
    path = tmp_path / "logo.png"
    path.write_bytes(PNG_MAGIC)
    from_file, from_bytes = bf.Header(logo=path), bf.Header(logo=PNG_MAGIC)
    assert from_file == from_bytes and from_file.logo_mime == "image/png"
    assert bf.Header(logo=from_bytes.to_dict()["logo"]) == from_bytes


@pytest.mark.parametrize(("kwargs", "match"), [
    ({"tz": "Mars/Base"}, "unknown time zone 'Mars/Base'"),
    ({"logo": b"not an image"}, "logo must be a PNG, JPEG, GIF, WebP or SVG image"),
    ({"logo": "/no/such/logo.png"}, "logo file not found"),
    ({"logo": 12}, "logo is a PNG"),
    ({"as_of": "last week"}, "as_of is a date, a datetime or an ISO string"),
    ({"as_of": 2026}, "as_of is a date"),
    ({"subtitle": 3}, "subtitle is text"),
])
def test_bad_fields_say_what_to_pass(kwargs: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.Header(**kwargs)


def test_a_dict_is_a_header() -> None:
    assert bf.Briefing(bf.Text("x"), header={"author": "A"}).header == bf.Header(author="A")
    with pytest.raises(bf.BriefingError, match="Header has no field 'title'"):
        bf.Briefing(bf.Text("x"), header={"title": "T"})
    with pytest.raises(bf.BriefingError, match=r"takes a bf.Header\(...\) or a dict"):
        bf.Briefing(bf.Text("x"), header="My header")  # type: ignore[arg-type]


def test_rewrapping_keeps_the_header() -> None:
    assert bf.Briefing(bf.Briefing(bf.Text("x"), header=bf.Header(author="A"))).header == bf.Header(author="A")


def test_fragments_draw_the_same_header() -> None:
    report = bf.Briefing(bf.Text("x"), header=bf.Header(subtitle="Sub", as_of="2026-11-20"))
    header = _header(report, full_html=False, header=True)
    assert find_one(header, ".bf-report__subtitle").get_text() == "Sub"
    assert find_one(header, ".bf-report__asof").get_text() == "Data as of 2026-11-20"


def test_the_json_form() -> None:
    report = bf.Briefing(bf.Text("x"), header=bf.Header(subtitle="Sub", logo=RED_SVG, as_of=dt.date(2026, 11, 20)))
    spec, data = bf.to_spec(report)
    assert spec["header"]["as_of"] == "2026-11-20" and spec["header"]["logo"].startswith("data:image/svg+xml")
    assert set(spec["header"]) == {"subtitle", "logo", "as_of"}
    assert bf.stringify(bf.from_spec(spec, data), now=NOW) == bf.stringify(report, now=NOW)
    blocks = [{"type": "Text", "text": "x"}]
    assert not bf.validate({"briefing": 1, "header": {"as_of": "2026-11-20"}, "blocks": blocks})
    (error,) = bf.validate({"briefing": 1, "header": {"logo": 3}, "blocks": blocks})
    assert error.code == "wrong-type" and error.path == "/header"
