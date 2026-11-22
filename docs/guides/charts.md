# Charts with `Plot`

`bf.Plot` takes a figure from Plotly, Altair, Matplotlib (so Seaborn and Plotnine
too) or Bokeh. briefing finds the library from the figure, and imports only that
one. Size the figure in its own library; with `responsive=True` (the default) it
fills the width of its column.

| Library | In the report | Needs |
| --- | --- | --- |
| Plotly | interactive; the Plotly runtime is embedded once per report | plotly 5.0+ |
| Altair / Vega-Lite | interactive; the Vega runtime is embedded once per report | altair 5.0+ and `briefing[altair]` |
| Matplotlib, Seaborn, Plotnine | inline SVG | matplotlib 3.7+ |
| Bokeh | interactive, in a frame with Bokeh's resources inlined | bokeh 3.0+ |

An older version shows, in place of the chart, which version briefing needs.

## Matplotlib

Matplotlib figures become inline SVG: sharp at any zoom, and searchable text.

```{briefing-example}
:title: A Matplotlib chart

import matplotlib.pyplot as plt
import numpy as np
import briefing as bf

rng = np.random.default_rng(3)
days = np.arange(90)
fig, ax = plt.subplots(figsize=(8, 3))
ax.plot(days, 200 + days * 1.5 + rng.normal(0, 12, 90).cumsum(), color="#4F46E5")
ax.set(xlabel="Day", ylabel="Orders")
ax.spines[["top", "right"]].set_visible(False)

bf.save(bf.Plot(fig, caption="Daily orders, last 90 days"), "matplotlib.html", name="Matplotlib")
```

## Plotly

Plotly charts keep their hover, zoom and legend. The Plotly runtime adds about
2 MB to the report (compressed; the report unpacks it as it opens), once, however many
Plotly charts it holds.

```{briefing-example}
:title: A Plotly chart
:height: 520

import numpy as np
import pandas as pd
import plotly.express as px
import briefing as bf

rng = np.random.default_rng(11)
stores = pd.DataFrame({
    "revenue": rng.gamma(5, 40_000, 120),
    "margin_pct": rng.normal(30, 5, 120),
    "region": rng.choice(["North", "South", "East", "West"], 120),
})
fig = px.scatter(stores, x="revenue", y="margin_pct", color="region", height=420)
bf.save(bf.Plot(fig, caption="Stores by revenue and margin"), "plotly.html", name="Plotly")
```

## Altair and Bokeh

They work the same way. These examples aren't run when the documentation is
built, because the docs don't install Altair or Bokeh.

```python
import altair as alt

chart = alt.Chart(stores).mark_point().encode(x="revenue", y="margin_pct", color="region")
bf.Plot(chart, caption="Stores")        # needs briefing[altair]

from bokeh.plotting import figure

p = figure(height=300)
p.line([1, 2, 3], [4, 6, 5])
bf.Plot(p)                              # needs bokeh 3.0+
```

Printing, `save_pdf` and the in-report "Save as PNG" button handle each library
differently; see {doc}`export`.

## Charts in the report's theme

A figure is drawn before briefing sees it, so give the theme to the chart library first.
`Formatting.plotly_template()` is a Plotly template, and `Formatting.mpl_style()` is a dict
of Matplotlib settings for `plt.rc_context`. Both use the theme's font, text and border
colours and see-through backgrounds, so the chart sits on the page. Their trace colours
are the theme's categorical palette (`Formatting.categorical()`: the accent, then hues that
stay apart for colour-blind readers), or the palette you pass.

A named palette, such as party colours, is a {class}`~briefing.Scale` whose domain names
the categories. `scale.mapping` is a dict for Plotly's `color_discrete_map`, `scale("NDP")`
gives one colour, and a {class}`~briefing.Legend` lists them.

```{briefing-example}
:title: A Plotly chart in the dark theme, with party colours
:height: 520

import pandas as pd
import plotly.express as px
import briefing as bf

theme = bf.Formatting.dark()
parties = bf.Scale(["#d71920", "#1a4782", "#f37021", "#33a6b2"],
                   domain=["Liberal", "Conservative", "NDP", "Bloc"])
seats = pd.DataFrame({"party": parties.domain, "seats": [160, 119, 25, 33]})

fig = px.bar(seats, x="party", y="seats", color="party", template=theme.plotly_template(parties),
             color_discrete_map=parties.mapping)
report = [bf.Legend(parties, title="Parties"), bf.Plot(fig, caption="Seats won")]
bf.save(report, "themed-chart.html", name="Seats", formatting=theme)
```

With Matplotlib:

```python
import matplotlib.pyplot as plt

with plt.rc_context(theme.mpl_style(parties)):
    fig, ax = plt.subplots()
    ax.bar(seats["party"], seats["seats"], color=[parties(p) for p in seats["party"]])
```
