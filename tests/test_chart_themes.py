"""Charts that follow the report theme, and named palettes (#39)."""
from __future__ import annotations

import pandas as pd
import pytest

import briefing as bf
from tests.html_helpers import find_one, parse

PARTIES = bf.Scale(["#d71920", "#1a4782", "#f37021"], domain=["Liberal", "Conservative", "NDP"])
PRESETS = [bf.Formatting(), bf.Formatting.dark(), bf.Formatting.corporate(), bf.Formatting.minimal(),
           bf.Formatting.ocean(), bf.Formatting.warm(), bf.Formatting.from_accent("#f5479a", dark=True)]


# ── named palettes: a categorical Scale ───────────────────────────────────────


def test_a_named_palette() -> None:
    assert PARTIES.categorical and PARTIES("NDP") == "#f37021"
    assert PARTIES.mapping == {"Liberal": "#d71920", "Conservative": "#1a4782", "NDP": "#f37021"}
    with pytest.raises(bf.BriefingError, match="'Green' isn't one of its categories"):
        PARTIES("Green")
    with pytest.raises(bf.BriefingError, match="mapping is for a categorical scale"):
        _ = bf.Scale(["#000", "#fff"], domain=(0, 1)).mapping


@pytest.mark.parametrize(("kwargs", "match"), [
    ({"colors": ["#000", "#fff"], "domain": ["A"]}, "one colour per category"),
    ({"colors": ["#000", "#fff"], "domain": ["A", "A"]}, "named twice"),
    ({"colors": ["#000", "#fff"], "domain": ["A", "B"], "steps": 2}, "center and steps are for numbers"),
])
def test_bad_named_palettes(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.Scale(**kwargs)  # type: ignore[arg-type]


def test_heatmaps_need_a_numeric_scale() -> None:
    with pytest.raises(bf.BriefingError, match="a categorical Scale colours categories"):
        bf.lab.CalendarHeatmap(pd.DataFrame({"d": ["2026-01-01"]}), date="d", colors=PARTIES)


def test_a_legend_lists_the_categories() -> None:
    report = bf.Briefing(bf.Legend(PARTIES, title="Parties"))
    legend = find_one(parse(bf.stringify(report)), ".bf-legend .bf-cal__legend")
    assert legend.get_text(" ").split() == ["Liberal", "Conservative", "NDP"]
    spec, data = bf.to_spec(report)
    assert spec["blocks"][0]["scale"]["domain"] == ["Liberal", "Conservative", "NDP"]
    assert bf.stringify(bf.from_spec(spec, data)) == bf.stringify(report)


# ── the theme's categorical palette ───────────────────────────────────────────


@pytest.mark.parametrize("theme", PRESETS)
def test_every_preset_palette_passes_its_own_check(theme: bf.Formatting) -> None:
    palette = theme.categorical()
    assert palette[0] == theme.accent_color.lower() and len(palette) >= 5
    assert [f for f in bf.color.check(palette, background=theme.bg_color) if f.level == "warning"] == []


def test_the_base_palettes_pass_on_white_and_slate() -> None:
    for palette, bg in ((bf.Formatting.CATEGORICAL_LIGHT, "#ffffff"), (bf.Formatting.CATEGORICAL_DARK, "#0f172a")):
        assert [f for f in bf.color.check(palette, background=bg) if f.level == "warning"] == []


# ── Plotly and Matplotlib ─────────────────────────────────────────────────────


def test_a_plotly_template_in_the_theme() -> None:
    pytest.importorskip("plotly")
    theme = bf.Formatting.dark()
    layout = theme.plotly_template().layout
    assert layout.font.family == theme.font and layout.font.color == theme.text_color
    assert layout.paper_bgcolor == layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert layout.xaxis.gridcolor == theme.border_color and list(layout.colorway) == theme.categorical()
    assert list(theme.plotly_template(PARTIES).layout.colorway) == list(PARTIES.colors)
    assert list(theme.plotly_template(["#111", "#222"]).layout.colorway) == ["#111111", "#222222"]


def test_a_plotly_chart_in_the_theme_renders() -> None:
    px = pytest.importorskip("plotly.express")
    df = pd.DataFrame({"party": ["Liberal", "Conservative", "NDP"], "seats": [160, 119, 25]})
    fig = px.bar(df, x="party", y="seats", color="party", template=bf.Formatting.dark().plotly_template(PARTIES),
                 color_discrete_map=PARTIES.mapping)
    assert [t.marker.color for t in fig.data] == ["#d71920", "#1a4782", "#f37021"]
    assert "bf-plot" in bf.stringify(bf.Briefing(bf.Plot(fig)))


def test_a_matplotlib_style_in_the_theme() -> None:
    plt = pytest.importorskip("matplotlib.pyplot")
    theme = bf.Formatting.warm()
    style = theme.mpl_style(PARTIES)
    assert style["font.family"] == "serif" and style["font.serif"][0] == "Charter"
    with plt.rc_context(style):
        fig, ax = plt.subplots()
        lines = [ax.plot([0, 1], [i, i + 1])[0] for i in range(3)]
        assert [line.get_color() for line in lines] == list(PARTIES.colors)
        assert ax.xaxis.label.get_color() == theme.text_color
        assert "bf-plot" in bf.stringify(bf.Briefing(bf.Plot(fig)))
    plt.close(fig)


def test_a_bad_palette() -> None:
    with pytest.raises(bf.BriefingError, match="palette is a bf.Scale or a list of hex colours"):
        bf.Formatting().mpl_style("#000000")
