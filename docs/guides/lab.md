# The lab: DataProfile, DataDive, CalendarHeatmap

`briefing.lab` holds richer, more specialised blocks. They plug into the same
report and follow the theme, and their JavaScript is inlined only in reports that
use them. Install with `pip install "briefing[lab]"`.

## `DataProfile`: a card per column

Each column gets its type, row and missing counts, statistics and a small chart:
a histogram for numbers, top values for categories, a range for dates. Missing
shares above `missing_threshold` are highlighted.

```{briefing-example}
:title: A DataProfile
:height: 640

import numpy as np
import pandas as pd
import briefing as bf

rng = np.random.default_rng(1)
n = 400
customers = pd.DataFrame({
    "signup": pd.Timestamp("2023-01-01") + pd.to_timedelta(rng.integers(0, 365, n), unit="D"),
    "plan": rng.choice(["free", "pro", "team"], n, p=[0.6, 0.3, 0.1]),
    "seats": rng.integers(1, 50, n),
    "monthly_spend": np.where(rng.random(n) < 0.25, np.nan, rng.gamma(2, 30, n).round(2)),
})
bf.save(bf.lab.DataProfile(customers, missing_threshold=0.2), "profile.html", name="Customers")
```

## `DataDive`: every row a dot

Each row becomes a dot. The reader picks which columns drive the X axis, the Y axis
and the colour; `layout="tile"` packs the dots into a grid of cells instead of
plotting them on axes, like Facets Dive.

```{briefing-example}
:title: A DataDive
:height: 620

import numpy as np
import pandas as pd
import briefing as bf

rng = np.random.default_rng(2)
n = 300
stores = pd.DataFrame({
    "revenue": rng.gamma(5, 40_000, n).round(),
    "margin_pct": rng.normal(30, 5, n).round(1),
    "region": rng.choice(["North", "South", "East", "West"], n),
    "format": rng.choice(["mall", "street", "outlet"], n),
})
bf.save(bf.lab.DataDive(stores, x="revenue", y="margin_pct", color="region"), "dive.html", name="Stores")
```

## `CalendarHeatmap`: one cell per day

A GitHub-style calendar: weeks as columns, one cell per day, coloured by the rows
counted (or a value aggregated with `agg`) that day. Days without data look
different from days with a zero.

- `expected=` flags days below a target: a number, a Series indexed by date, or a
  DataFrame with `date` and `expected` columns.
- `events=` marks dates, or spans with a `start`, `end` and `label`.
- `views=("days", "hours")` adds a 7 × 24 weekday-by-hour grid, with tabs between
  the two; `tz=` converts timezone-aware timestamps first.
- `on_click="rows"` lists the rows behind a day or an hour when it is clicked, up to
  `CalendarHeatmap.ROWS_PER_CELL` per cell.
- `center=` with three `colors` gives a diverging scale, for values that go negative.

Click a day in the example to see its runs:

```{briefing-example}
:title: A CalendarHeatmap
:height: 520

import numpy as np
import pandas as pd
import briefing as bf

rng = np.random.default_rng(4)
days = pd.date_range("2023-10-01", "2024-03-31", freq="D")
days = days[rng.random(len(days)) > 0.06]           # a few days with no run at all
runs = pd.DataFrame({
    "run_at": days + pd.to_timedelta(rng.integers(0, 24 * 60, len(days)), unit="min"),
    "rows": rng.normal(1_200, 250, len(days)).round().clip(0),
    "status": rng.choice(["ok", "ok", "ok", "slow"], len(days)),
})

report = bf.lab.CalendarHeatmap(
    runs,
    date="run_at",
    value="rows",
    expected=900,
    events=pd.DataFrame({"start": ["2023-12-22"], "end": ["2024-01-02"], "label": ["Freeze"]}),
    views=("days", "hours"),
    on_click="rows",
)
bf.save(report, "calendar.html", name="Pipeline runs")
```

For values that go negative, such as a daily balance, `center=0` switches to a
diverging scale. `colors` then takes three colours: below, at and above the centre.

```{briefing-example}
:title: A diverging CalendarHeatmap

import numpy as np
import pandas as pd
import briefing as bf

rng = np.random.default_rng(9)
ledger = pd.DataFrame({"day": pd.date_range("2024-01-01", "2024-06-30", freq="D")})
ledger["balance"] = rng.normal(0, 400, len(ledger)).cumsum().round()

bf.save(
    bf.lab.CalendarHeatmap(
        ledger, date="day", value="balance", center=0, colors=["#dc2626", "#f3f4f6", "#16a34a"]
    ),
    "balance.html",
    name="Daily balance",
)
```
