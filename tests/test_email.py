"""Email digests (#42): blocks built for mail apps, charts as attached PNGs, a plain-text part."""
from __future__ import annotations

import email
import email.policy
import typing as t
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from tests.contract import PAYLOAD
from tests.html_helpers import parse

LINK = "https://example.com/report.html"


def _figure() -> t.Any:
    plt = pytest.importorskip("matplotlib.pyplot")
    fig, ax = plt.subplots(figsize=(4, 2))
    ax.plot([1, 3, 2])
    return fig


def _digest(**kwargs: t.Any) -> bf.email.Digest:
    return bf.email.Digest(
        bf.Text("## Daily\n\n**2 sources** below target. See [the detail](#detail/sources)."),
        bf.Group(bf.BigNumber("Calls", 1284, prev_value=1247), bf.BigNumber("Failed", "2.1%"), columns=2),
        bf.Alert("News missed 3 runs.", level="warning", title="Watch"),
        bf.Plot(_figure(), caption="Calls per day"),
        bf.Table(pd.DataFrame({"source": ["News", "Social"], "runs": [21, 24]}), caption="Runs"),
        link=LINK, footer="Data team", **kwargs)


def test_the_message_has_text_html_and_its_charts() -> None:
    message = bf.email.to_message(_digest(), subject="Daily digest", sender="bot@example.com",
                                  to=["a@example.com", "b@example.com"])
    assert message["Subject"] == "Daily digest" and message["To"] == "a@example.com, b@example.com"
    assert [p.get_content_type() for p in message.walk()] == [
        "multipart/alternative", "text/plain", "multipart/related", "text/html", "image/png"]
    html = message.get_body(("html",)).get_content()  # type: ignore[union-attr]
    image = next(p for p in message.walk() if p.get_content_type() == "image/png")
    assert f'src="cid:{image["Content-ID"].strip("<>")}"' in html
    assert image.get_content().startswith(b"\x89PNG")


def test_nothing_a_mail_app_would_drop_or_run() -> None:
    body, _ = bf.email.to_html(_digest())
    soup = parse(body)
    assert not soup.find("script") and not soup.find("svg") and not soup.find("style") and "data:" not in body
    assert all(tag.get("style") or tag.name in ("html", "head", "meta", "tr", "strong", "em")
               for tag in soup.find_all(True) if tag.name not in ("table", "td", "a", "img", "div", "body"))


def test_links_lead_into_the_full_report() -> None:
    body, _ = bf.email.to_html(_digest())
    hrefs = [a["href"] for a in parse(body).find_all("a")]
    assert f"{LINK}#detail/sources" in hrefs and LINK in hrefs  # the anchor, and the button
    assert f"[the detail]({LINK}#detail/sources)" in bf.email.to_text(_digest())


def test_an_anchor_needs_the_report_link() -> None:
    digest = bf.email.Digest(bf.Text("See [the detail](#detail)."))
    with pytest.raises(bf.BriefingError, match="leads into the full report: give the digest link="):
        bf.email.to_html(digest)


def test_raw_html_in_text_is_escaped() -> None:
    body, _ = bf.email.to_html(bf.email.Digest(bf.Text(f"Hello {PAYLOAD}")))
    assert parse(body).find("img") is None and "&lt;img" in body


def test_the_plain_text_part() -> None:
    text = bf.email.to_text(_digest())
    assert "Calls: 1284 (+3.0%)" in text and "Failed: 2.1%" in text
    assert "[Warning] Watch: News missed 3 runs." in text and "[Chart: Calls per day]" in text
    assert f"Full report: {LINK}" in text and text.rstrip().endswith("Data team · Made with briefing "
                                                                     + bf.__version__)


@pytest.mark.parametrize("block", [
    lambda: bf.DataTable(pd.DataFrame({"a": [1]})),
    lambda: bf.Select(bf.Text("a", label="A"), bf.Text("b", label="B")),
    lambda: bf.Toggle(bf.Text("a"), label="More"),
    lambda: bf.lab.DataProfile(pd.DataFrame({"a": [1]})),
    lambda: bf.Group(bf.DataTable(pd.DataFrame({"a": [1]}))),
])
def test_interactive_blocks_are_refused(block: t.Callable[[], bf.Block]) -> None:
    with pytest.raises(bf.BriefingError, match="mail apps run no script. A digest takes Text, BigNumber, Alert"):
        bf.email.Digest(block())


def test_a_long_table_is_refused() -> None:
    with pytest.raises(bf.BriefingError, match="at most 30 rows; this one has 31"):
        bf.email.Digest(bf.Table(pd.DataFrame({"a": range(31)})))


@pytest.mark.parametrize(("kwargs", "match"), [({"link": "report.html"}, "link is the full report's address")])
def test_bad_options(kwargs: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.email.Digest("x", **kwargs)


def test_output_is_deterministic() -> None:
    fig = _figure()
    first = bf.email.to_html(bf.email.Digest(bf.Plot(fig)))
    second = bf.email.to_html(bf.email.Digest(bf.Plot(fig)))
    assert first == second


def test_plotly_needs_kaleido_and_bokeh_a_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Bar(x=[1, 2], y=[3, 4]))

    def no_kaleido(*args: t.Any, **kwargs: t.Any) -> bytes:
        raise ValueError("Image export using the 'kaleido' engine requires the kaleido package")

    monkeypatch.setattr(type(fig), "to_image", no_kaleido)
    with pytest.raises(bf.BriefingError, match="pip install kaleido"):
        bf.email.to_html(bf.email.Digest(bf.Plot(fig)))


def test_an_altair_chart_is_drawn_with_vl_convert() -> None:
    alt = pytest.importorskip("altair")
    pytest.importorskip("vl_convert")
    chart = alt.Chart(pd.DataFrame({"x": [1, 2], "y": [3, 4]})).mark_bar().encode(x="x:O", y="y:Q")
    _, pictures = bf.email.to_html(bf.email.Digest(bf.Plot(chart)))
    assert pictures[0].png.startswith(b"\x89PNG")


def test_to_eml_writes_a_message_a_mail_app_opens(tmp_path: Path) -> None:
    path = bf.email.to_eml(_digest(), tmp_path / "digest.eml", subject="Daily digest")
    message = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    assert message["Subject"] == "Daily digest" and message.is_multipart()


def test_a_dark_theme() -> None:
    body, _ = bf.email.to_html(_digest(), formatting=bf.Formatting.dark())
    assert "background: #0f172a" in body
