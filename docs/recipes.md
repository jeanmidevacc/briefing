# Recipes

## A KPI dashboard with tabbed detail

```{briefing-example}
:title: A KPI dashboard
:height: 720

import numpy as np
import pandas as pd
import briefing as bf

rng = np.random.default_rng(8)
n = 240
sales = pd.DataFrame({
    "month": pd.date_range("2023-01-01", periods=12, freq="MS").repeat(n // 12),
    "region": rng.choice(["North", "South", "East", "West"], n),
    "revenue": rng.gamma(4, 1_300, n).round(2),
    "margin_pct": rng.normal(31, 4, n).round(1),
})
by_region = sales.groupby("region", as_index=False).agg(revenue=("revenue", "sum"), margin_pct=("margin_pct", "mean"))
monthly = sales.groupby("month", as_index=False)["revenue"].sum()
monthly["revenue"] = monthly["revenue"].round()

report = bf.Briefing(
    bf.Text("# Sales, 2023"),
    bf.Group(
        bf.BigNumber("Revenue", f"€ {sales.revenue.sum():,.0f}", change="+12.4%", is_upward_change=True),
        bf.BigNumber("Avg margin", f"{sales.margin_pct.mean():.1f} %", change="-0.8 pt", is_upward_change=False),
        bf.BigNumber("Return rate", "8.0 %", change="+0.2 pt", is_upward_change=True, is_positive_intent=False),
        columns=3,
    ),
    bf.Alert("South region margin dropped below 25 % in December.", level="warning", title="Action needed"),
    bf.Select(
        bf.DataTable(by_region.round(1), caption="Region summary", label="By region"),
        bf.DataTable(monthly, caption="Monthly revenue", label="Monthly"),
        bf.DataTable(sales, caption="All transactions", label="Raw data"),
    ),
    bf.Toggle(
        bf.Text("**Refresh**: nightly at 02:00 UTC. **Source**: the sales warehouse."),
        bf.Code("SELECT * FROM sales WHERE month >= '2023-01-01'", language="sql"),
        label="Methodology and sources",
    ),
)
bf.save(report, "dashboard.html", name="Sales, 2023", formatting=bf.Formatting(accent_color="#0f766e"))
```

## A pipeline health report

```{briefing-example}
:title: A pipeline health report
:height: 640

import numpy as np
import pandas as pd
import briefing as bf

rng = np.random.default_rng(12)
days = pd.date_range("2024-01-01", "2024-03-31", freq="D")
runs = pd.DataFrame({
    "day": days,
    "rows": rng.normal(10_000, 1_500, len(days)).round().clip(0),
    "minutes": rng.gamma(6, 2, len(days)).round(1),
})
failed = runs.rows < 7_000

report = bf.Briefing(
    bf.Text("# Ingestion, Q1 2024"),
    bf.Group(
        bf.BigNumber("Runs", len(runs)),
        bf.BigNumber("Days below target", int(failed.sum())),
        bf.BigNumber("Median duration", f"{runs.minutes.median():.0f} min"),
        columns=3,
    ),
    bf.lab.CalendarHeatmap(runs, date="day", value="rows", expected=7_000),
    bf.Toggle(bf.DataTable(runs[failed], caption="Days below target"), label="Days below target"),
)
bf.save(report, "pipeline.html", name="Ingestion health")
```

## Building a report in steps

A report is a list, so it can grow as an analysis runs, one block per finding:

```python
blocks = [bf.Text("# Data quality checks")]
for check in checks:
    level = "success" if check.passed else "error"
    blocks.append(bf.Alert(check.message, level=level, title=check.name))
bf.save(blocks, "checks.html", name="Data quality")
```
