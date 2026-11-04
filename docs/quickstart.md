# Quick start

## Install

```bash
pip install briefing            # the block grammar and the HTML renderer
pip install "briefing[pandas]"  # tables from dataframes
```

The core has no plotting or dataframe dependency. Install the extra for what you
use: `[pandas]`, `[lab]`, `[plotly]`, `[altair]`, `[bokeh]`, `[matplotlib]`, `[charts]`
(every chart library) or `[image]` (image and PDF export).

| Extra | Adds |
| --- | --- |
| `briefing[pandas]` | pandas, for `Table` and `DataTable` |
| `briefing[lab]` | the {doc}`briefing.lab <guides/lab>` blocks |
| `briefing[plotly]`, `[altair]`, `[bokeh]`, `[matplotlib]` | the matching backend for `Plot` |
| `briefing[charts]` | all four `Plot` backends at once |
| `briefing[image]` | Playwright, for {doc}`save_image and save_pdf <guides/export>` |

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
