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
    bf.Text("# Sales, Q1 2026\n\nRevenue by region, before returns."),
    bf.Group(
        bf.BigNumber("Revenue", sales["revenue"].sum(), prev_value=1_156_500, format="${:,.0f}"),
        bf.BigNumber("Regions", len(sales)),
        columns=2,
    ),
    bf.DataTable(sales, caption="By region", formats={"revenue": "${:,.0f}", "margin_pct": "{:.1f}%"}),
)
bf.save(report, "first.html", name="Sales, Q1 2026")
```

`BigNumber` computes the change from `prev_value` and colours it: up is good, unless
`higher_is_better=False`. Next:

- {doc}`concepts`: how blocks, names, the theme and the three outputs fit together
- {doc}`guides/text`, {doc}`guides/tables`, {doc}`guides/charts` and {doc}`guides/layout`:
  the blocks
- {doc}`guides/decks` and {doc}`guides/email`: the same blocks as a slide deck or an email
- {doc}`guides/project`: a report project in one command

## Getting the HTML as a string

`bf.stringify(report)` returns the same page as a string, for an email body, a
web response or a test. With the same input and `SOURCE_DATE_EPOCH` set (or
`now=` passed), the output is byte-identical from one run to the next.
