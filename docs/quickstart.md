# Quick start

## Install

```bash
pip install briefing            # every block, HTML reports and fragments, tables
pip install "briefing[altair]"  # for Altair charts: the Vega runtime they embed
pip install "briefing[image]"   # save_image and save_pdf (then, once: playwright install chromium)
```

briefing installs pandas, for tables, but no chart library: `Plot` renders the figure
you pass, from the library you already have (Plotly 5+, Altair 5+, Matplotlib 3.7+,
Bokeh 3+), and says so when that library is too old. Polars and pyarrow tables are
converted for you.

| Extra | Adds |
| --- | --- |
| `briefing[altair]` | vl-convert-python, which embeds the Vega runtime so Altair charts work offline |
| `briefing[image]` | Playwright, for {doc}`save_image and save_pdf <guides/export>` |
| `briefing[lab]` | nothing today: the {doc}`briefing.lab <guides/lab>` blocks come with briefing |

## A first report

A report is a list of blocks. `bf.save` writes it as one HTML file with every
script, style and image inside it, so it opens offline, forever, on any machine.

```{briefing-example}
:title: A first report

import pandas as pd
import briefing as bf

sales = pd.DataFrame({
    "region": ["North", "South", "East", "West"],
    "revenue": [412_000, 287_500, 351_200, 198_300],
    "margin_pct": [31.2, 24.8, 29.5, 33.1],
})

report = bf.Briefing(
    bf.Text("# Sales, Q1 2024\n\nRevenue by region, before returns."),
    bf.Group(
        bf.BigNumber("Revenue", "$1.25M", change="+8%", is_upward_change=True),
        bf.BigNumber("Regions", 4),
        columns=2,
    ),
    bf.DataTable(sales, caption="By region"),
)
bf.save(report, "first.html", name="Sales, Q1 2024")
```

The rest of the guides show each family of blocks:

- {doc}`guides/text`: Markdown, code, formulas, KPIs and callouts
- {doc}`guides/tables`: static and interactive tables
- {doc}`guides/charts`: Plotly, Altair, Matplotlib and Bokeh figures
- {doc}`guides/layout`: columns, tabs, toggles and pages
- {doc}`guides/banner`: a text-over-image cover
- {doc}`guides/assets`: images, raw HTML and report size

## Getting the HTML as a string

`bf.stringify(report)` returns the same page as a string, for an email body, a
web response or a test. With the same input and `SOURCE_DATE_EPOCH` set (or
`now=` passed), the output is byte-identical from one run to the next.
