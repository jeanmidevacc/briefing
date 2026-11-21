# Tables

Both table blocks take a pandas dataframe, or a polars or pyarrow table, or
anything with the dataframe interchange protocol, or a dict of columns. They
convert it for you. For PySpark, call `.toPandas()` first.

## Interactive tables with `DataTable`

A `DataTable` sorts when you click a column header, searches as you type, and
pages long data. Dates and formatted numbers sort by their real value. Rows beyond
`max_rows` (10,000 by default) are dropped with a warning, because every row is
embedded in the file.

A table of up to 1,000 rows keeps every row in the HTML. A bigger one keeps its first
page there and its rows compressed, which the page's script unpacks as the report
opens: 10,000 rows of numbers weigh a few hundred kilobytes instead of megabytes. It
sorts, searches, pages and prints (up to 1,000 rows) like a small one; a reader without
JavaScript sees its first 25 rows and a line saying how many more there are.

```{briefing-example}
:title: A DataTable
:height: 520

import numpy as np
import pandas as pd
import briefing as bf

rng = np.random.default_rng(7)
orders = pd.DataFrame({
    "order_date": pd.date_range("2024-01-01", periods=60, freq="D"),
    "region": rng.choice(["North", "South", "East", "West"], 60),
    "units": rng.integers(1, 40, 60),
    "revenue": rng.gamma(4, 250, 60).round(2),
})
bf.save(bf.DataTable(orders, caption="Orders, January–February"), "datatable.html", name="Orders")
```

### Number formats and links

`formats=` shows a column's values with a Python format string (the kind pandas'
`Styler.format` takes) or a function; the cell still sorts by its value, so `12.3%`
sorts before `50.0%` and `30 Nov 2023` before `05 Jan 2024`. `links=` turns a column's
cells into links: `{}` in the URL is the cell's value, `{url}` the value of the column
`url` in the same row. Only `http(s)://` and `mailto:` URLs become links, which open in
a new tab; anything else stays text, with a warning.

```{briefing-example}
:title: Formatted and linked cells
:height: 280

import pandas as pd
import briefing as bf

papers = pd.DataFrame({
    "title": ["Graph recommenders", "Learning to rank", "Contextual bandits"],
    "doi": ["10.1000/182", "10.1000/183", None],
    "citations": [12_345, 678, 9],
    "share": [0.1234, 0.5, None],
    "published": pd.to_datetime(["2024-01-05", "2023-11-30", "2024-02-01"]),
})
table = bf.DataTable(
    papers,
    formats={"citations": "{:,}", "share": "{:.1%}", "published": "{:%d %b %Y}"},
    links={"doi": "https://doi.org/{}"},
)
bf.save(table, "datatable-formats.html", name="Papers")
```

## Static tables with `Table`

`Table` renders a dataframe as plain HTML, and keeps a pandas `Styler`'s formats,
colours and bars. Use it for small, formatted summaries.

```{briefing-example}
:title: A styled Table

import pandas as pd
import briefing as bf

summary = pd.DataFrame({
    "region": ["North", "South", "East", "West"],
    "revenue": [412_000, 287_500, 351_200, 198_300],
    "margin_pct": [0.312, 0.248, 0.295, 0.331],
}).set_index("region")

styled = (
    summary.style
    .format({"revenue": "$ {:,.0f}", "margin_pct": "{:.1%}"})
    .bar(subset=["revenue"], color="#c7d2fe")
)
bf.save(bf.Table(styled, caption="Revenue and margin by region"), "table.html", name="Summary")
```

A dataframe passed where a block is expected, for example inside a `Group`,
becomes a `DataTable`.
