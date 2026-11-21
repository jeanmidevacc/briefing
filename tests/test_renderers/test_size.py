"""The size budget (#38): a report over ``max_size`` warns, naming its largest parts and where they are."""
from __future__ import annotations

import json
import typing as t
import warnings
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from briefing.renderers.size import Part, format_size, over_budget, parse_size
from tests.banner_images import PNG_MAGIC
from tests.scenarios import plotly_figure


def _rows(n: int = 2_000) -> pd.DataFrame:
    return pd.DataFrame({"x": [i / 7 for i in range(n)], "word": [f"word {i}" for i in range(n)]})


def _warning(*args: t.Any, **kwargs: t.Any) -> str:
    with pytest.warns(UserWarning, match="over max_size") as caught:
        bf.stringify(*args, **kwargs)
    assert len(caught) == 1
    return str(caught[0].message)


@pytest.mark.parametrize(
    ("value", "size"),
    [(2048, 2048), ("10 MB", 10_000_000), ("500kb", 500_000), ("1.5 GB", 1_500_000_000), ("300", 300),
     ("2 B", 2), (None, None)],
)
def test_sizes_read_as_bytes(value: int | str | None, size: int | None) -> None:
    assert parse_size(value) == size


@pytest.mark.parametrize("value", ["lots", "-1 MB", "0", 0, -5, True, "10 TB", 1.5])
def test_a_size_it_cant_read_says_what_to_pass(value: t.Any) -> None:
    with pytest.raises(bf.BriefingError, match="max_size takes a number of bytes or a size such as '10 MB'"):
        parse_size(value)
    with pytest.raises(bf.BriefingError, match="max_size takes"):
        bf.stringify(bf.Text("x"), max_size=value)


def test_sizes_read_well() -> None:
    assert [format_size(n) for n in (512, 1_500, 850_000, 14_230_000)] == ["512 B", "2 KB", "850 KB", "14.2 MB"]


def test_a_report_over_its_budget_names_its_largest_parts() -> None:
    report = bf.Briefing(
        bf.Text("# Rows"),
        bf.Group(bf.DataTable(_rows(), name="rows"), bf.Text("note"), columns=2),
        bf.Toggle(bf.DataTable(_rows(500)), label="More"),
    )
    message = _warning(report, max_size="100 KB")
    total = len(bf.stringify(report, max_size=None).encode())
    assert message.startswith(f"The report is {format_size(total)}, over max_size (100 KB); its largest parts: ")
    assert 'DataTable "rows" at /blocks/1/blocks/0 (' in message
    assert "DataTable at /blocks/2/blocks/0 (" in message
    assert "Text" not in message  # parts under 1 % of the file aren't worth naming
    assert message.endswith("Pass max_size= to change the limit, or None to turn this warning off.")


def test_the_warning_points_at_the_callers_line(tmp_path: Path) -> None:
    with pytest.warns(UserWarning, match="over max_size") as caught:
        bf.save(bf.DataTable(_rows()), str(tmp_path / "r.html"), max_size=1_000)
    assert caught[0].filename == __file__


def test_paths_inside_pages_are_those_of_to_spec() -> None:
    report = bf.Briefing(bf.Page(bf.Text("a"), title="A"), bf.Page(bf.DataTable(_rows()), title="B"))
    assert "DataTable at /blocks/1/blocks/0 (" in _warning(report, max_size="50 KB")
    spec, _ = bf.to_spec(report)
    assert spec["blocks"][1]["blocks"][0]["type"] == "DataTable"


def test_chart_runtimes_count() -> None:
    message = _warning(bf.Plot(plotly_figure()), max_size="1 MB")
    assert "its largest parts: the Plotly runtime (" in message


def test_copy_embed_data_counts() -> None:
    message = _warning(bf.Briefing(bf.DataTable(_rows()), export="embed"), max_size="50 KB")
    assert "the copy-embed data (" in message


def test_a_fragment_counts_its_assets_only_when_it_carries_them() -> None:
    figure = plotly_figure()
    assert "the Plotly runtime" in _warning(bf.Plot(figure), full_html=False, max_size="1 MB")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bf.stringify(bf.Plot(figure), full_html=False, include_assets=False, max_size="1 MB")


def test_under_budget_or_without_one_is_silent() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bf.stringify(bf.DataTable(_rows()))  # 10 MB by default
        bf.stringify(bf.DataTable(_rows()), max_size=None)


def test_an_image_is_a_part_and_no_longer_warns_on_its_own() -> None:
    big = PNG_MAGIC + b"\x00" * 3_000_000
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        banner = bf.Banner("# Cover", image=big)  # the 2 MB warning of 0.2 is gone: the budget covers it
    assert "Banner at /blocks/0 (4.0 MB)" in _warning(banner, max_size="1 MB")


def test_over_budget_lists_at_most_three_parts() -> None:
    parts = [Part(f"part {i}", 100 * i) for i in range(1, 6)]
    message = over_budget(2_000, parts, 1_000)
    assert message == (
        "The report is 2 KB, over max_size (1 KB); its largest parts: part 5 (500 B), part 4 (400 B), part 3 (300 B)."
    )
    assert over_budget(1_000, parts, 1_000) is None


# ── validate ──────────────────────────────────────────────────────────────────


def test_validate_reports_too_big_with_the_paths_of_the_json() -> None:
    spec = {"briefing": 1, "blocks": [{"type": "Toggle", "label": "More", "blocks": [
        {"type": "Text", "text": "a"},
        {"type": "DataTable", "df": {"ref": "rows"}},
    ]}]}
    found = bf.validate(spec, {"rows": _rows()}, max_size="50 KB")
    assert [(d.severity, d.code, d.path) for d in found] == [("warning", "too-big", "")]
    assert "DataTable at /blocks/0/blocks/1 (" in found[0].message  # the JSON's path, not the Toggle's Group
    assert found[0].hint is not None and "max_rows=" in found[0].hint
    assert bf.validate(spec, {"rows": _rows()}) == []
    assert bf.validate(spec, {"rows": _rows()}, max_size=None) == []


def test_validate_says_when_it_cant_read_max_size() -> None:
    found = bf.validate({"briefing": 1, "blocks": [{"type": "Text", "text": "a"}]}, max_size="lots")
    assert [(d.code, d.path) for d in found] == [("wrong-type", "")]


def test_the_command_line_takes_max_size(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from briefing import _cli

    spec = tmp_path / "r.json"
    spec.write_text(json.dumps({"briefing": 1, "blocks": [{"type": "Text", "text": "# x"}]}), encoding="utf-8")
    assert _cli.main(["validate", str(spec), "--max-size", "1 KB"]) == 0  # a warning, not an error
    assert "warning too-big at the report: The report is" in capsys.readouterr().out
    assert _cli.main(["validate", str(spec), "--max-size", "none"]) == 0
    assert capsys.readouterr().out == "No problems found.\n"
    with pytest.warns(UserWarning, match="over max_size"):
        assert _cli.main(["render", str(spec), "--max-size", "1 KB"]) == 0
    with pytest.raises(SystemExit):
        _cli.main(["validate", str(spec), "--max-size", "lots"])
