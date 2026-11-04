# Tables

Both table blocks take a pandas dataframe, or a polars or pyarrow table, or
anything with the dataframe interchange protocol, or a dict of columns. They
convert it for you. For PySpark, call `.toPandas()` first.

## Interactive tables with `DataTable`

A `DataTable` sorts when you click a column header, searches as you type, and
pages long data. Dates and formatted numbers sort by their real value. Rows beyond
`max_rows` (10,000 by default) are dropped with a warning, because every row is
embedded in the file.

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
