"""Every ```python example in the README runs as written, offline (#13).

Examples assume what the README says they assume: ``import briefing as bf``, a
DataFrame ``df`` and a chart ``fig``, plus the few other names a snippet uses
(``report``, ``plot_a``, …). Each example runs in a fresh temporary directory
with every network connection refused, and every HTML file it writes must pass
the contract's offline rule.
"""
from __future__ import annotations

import re
import socket
import typing as t
import warnings
from pathlib import Path

import pytest

from tests.contract import check_json_scripts_parse, check_no_external_urls, parse_report

ROOT = Path(__file__).resolve().parents[1]
_BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)


def _examples() -> list[t.Any]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    cases = []
    for match in _BLOCK.finditer(readme):
        line = readme.count("\n", 0, match.start()) + 2
        first = match.group(1).strip().splitlines()[0][:40]
        cases.append(pytest.param(match.group(1), id=f"line{line}: {first}"))
    return cases


def _prelude() -> dict[str, t.Any]:
    """The names README examples assume."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import plotly.express as px

    import briefing as bf

    rng = np.random.default_rng(0)
    n = 120
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=n, freq="3D"),
        "region": rng.choice(["North", "South", "East", "West"], n),
        "channel": rng.choice(["Online", "Retail"], n),
        "product": rng.choice(["A", "B", "C"], n),
        "revenue": rng.normal(12_000, 3_000, n).round(2),
        "margin_pct": rng.normal(0.31, 0.05, n).round(3),
    })
    fig = px.line(df.sort_values("date"), x="date", y="revenue")
    mpl_fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(df["revenue"].to_numpy()[:20])
    names: dict[str, t.Any] = {
        "bf": bf, "pd": pd, "df": df, "fig": fig, "plotly_fig": fig, "mpl_fig": mpl_fig,
        "plot_a": bf.Plot(fig), "plot_b": bf.Plot(mpl_fig),
        "a": bf.Text("a"), "b": bf.Text("b"), "c": bf.Text("c"),
        "summary_group": bf.Group(bf.Text("summary")), "detail_group": bf.Group(bf.Text("detail")),
        "by_region": df.groupby("region", as_index=False)["revenue"].sum(),
        "monthly": df.groupby(df["date"].dt.to_period("M").astype(str))["revenue"].sum().reset_index(),
    }
    try:
        import altair as alt

        names["altair_chart"] = alt.Chart(df).mark_point().encode(x="revenue", y="margin_pct")
    except ImportError:
        pass
    names["report"] = names["blocks"] = bf.Briefing(bf.Text("# Report"), bf.DataTable(df.head(5)))
    return names


@pytest.fixture
def offline_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    def refuse(*args: object, **kwargs: object) -> t.NoReturn:
        raise AssertionError(f"README example opened a network connection: {args}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr("webbrowser.open", lambda *a, **k: True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("code", _examples())
def test_readme_example_runs_offline(code: str, offline_tmp: Path) -> None:
    if "IPython" in code:
        pytest.importorskip("IPython")
    if "altair_chart" in code:
        pytest.importorskip("altair")
    names = _prelude()
    names["df"].to_csv(offline_tmp / "sales.csv", index=False)  # Quick start reads it
    (offline_tmp / "notes.md").write_text("# Notes\n\nFrom a file.\n")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # e.g. a one-child Select in a snippet
        exec(compile(code, "<README>", "exec"), names)  # noqa: S102
    for page in offline_tmp.glob("*.html"):
        soup = parse_report(page.read_text(encoding="utf-8"))
        check_no_external_urls(soup)
        check_json_scripts_parse(soup)


def test_readme_has_examples() -> None:
    # The README is a pitch and a quick start; the long-form examples live in docs/ and
    # run in tests/test_docs_gallery.py.
    assert len(_examples()) >= 1


def test_no_fl_prefix_left_in_docs() -> None:
    old = re.compile(r"(?:\\n|\b)fl\.")  # also inside strings: "…\nfl.save(…"
    hits = [
        f"{path.relative_to(ROOT)}:{n}"
        for path in [ROOT / "README.md", *sorted((ROOT / "src").rglob("*.py"))]
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if old.search(line)
    ]
    assert hits == []
