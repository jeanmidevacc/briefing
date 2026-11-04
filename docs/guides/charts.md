# Charts with `Plot`

`bf.Plot` takes a figure from Plotly, Altair, Matplotlib (so Seaborn and Plotnine
too) or Bokeh. briefing finds the library from the figure, and imports only that
one. Size the figure in its own library; with `responsive=True` (the default) it
fills the width of its column.

| Library | In the report | Extra |
| --- | --- | --- |
| Plotly | interactive; the Plotly runtime is embedded once per report | `[plotly]` |
| Altair / Vega-Lite | interactive; the Vega runtime is embedded once per report | `[altair]` |
| Matplotlib, Seaborn, Plotnine | inline SVG | `[matplotlib]` |
| Bokeh | interactive, in a frame with Bokeh's resources inlined | `[bokeh]` |

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
4.6 MB to the report, once, however many Plotly charts it holds.

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
bf.Plot(p)                              # needs briefing[bokeh]
```

Printing, `save_pdf` and the in-report "Save as PNG" button handle each library
differently; see {doc}`export`.
