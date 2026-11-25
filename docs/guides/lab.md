# The lab: DataProfile, DataDive, CalendarHeatmap, TimeHeatmap

`briefing.lab` holds richer, more specialised blocks. They plug into the same
report and follow the theme, and their JavaScript is inlined only in reports that
use them. They come with briefing (`pip install "briefing[lab]"` still works, and adds nothing today).

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

- The legend under the controls filters: a click hides or shows a category's dots, and
  Alt+click shows that category alone. A number or a date column colours along a ramp.
- `facet_row=` and `facet_col=` split the dots into small multiples, one panel per value,
  on scales shared by every panel; the reader can change or remove them in the controls.
  A number splits into `buckets=` bins with round edges (5 by default), and a category
  keeps its most frequent values plus an "other". `buckets={"age": 4}` sets it per
  column; it also sets the cells of a `"tile"` layout.
- `colors=` takes a `bf.Scale`, so the dots match the report's other charts. A categorical
  scale colours the categories it names; a numeric one colours numbers and dates. Without
  it, categories take the theme's palette and numbers a ramp to its accent.
- The dots are drawn on a canvas, so a DataDive stays quick up to `DataDive.MAX_ROWS`
  (100,000) rows; a larger frame is sampled down to `max_rows=`, with a warning. Printed
  or saved with `save_pdf`, up to 5,000 dots stay vector; more print as a picture, with
  their axes and labels still text.

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

Facets compare groups side by side, here customers by plan and region:

```{briefing-example}
:title: A DataDive in facets
:height: 760

import briefing as bf

customers = bf.datasets.load("train_test").train
bf.save(
    bf.lab.DataDive(customers, x="age", y="income_k", color="churned", facet_row="plan", facet_col="region"),
    "facets.html",
    name="Customers",
)
```

An embedding map is a DataDive of precomputed coordinates, coloured by cluster:

```{briefing-example}
:title: An embedding map, coloured with a bf.Scale
:height: 620

import briefing as bf

points = bf.datasets.load("embeddings")
topics = bf.Scale(["#2563eb", "#16a34a", "#9333ea", "#ea580c", "#dc2626", "#0891b2"],
                  domain=["sports", "finance", "science", "travel", "food", "music"])
bf.save(bf.lab.DataDive(points, x="x", y="y", color="cluster", colors=topics), "map.html", name="Articles")
```

## `CalendarHeatmap`: one cell per day

A GitHub-style calendar: weeks as columns, one cell per day, coloured by the rows
counted (or a value aggregated with `agg`) that day. Days without data look
different from days with a zero.

- `expected=` flags days below a target: a number, a Series indexed by date, or a
  DataFrame with `date` and `expected` columns.
- `events=` marks dates, or spans with a `start`, `end` and `label`. A single day is
  outlined and dotted; a span draws as a band and leaves its days' colours in view.
  An optional `color` column (any CSS colour) colours an event's marks and legend entry;
  without it they take the theme's accent.
- `tz=` converts timezone-aware timestamps before they are placed on a day.
- `start=` and `end=` fix the first and last day shown, whatever the data covers, so
  calendars side by side line up week for week. Rows outside the span are left out, with
  a warning.
- `group=` draws one calendar per group, stacked on one colour scale, sorted by name;
  `group_order=["Worldwide", "United States"]` puts those first, in that order.
- `on_click="rows"` lists the rows behind a day when it is clicked, up to
  `CalendarHeatmap.ROWS_PER_CELL` per cell.
- `colors=` takes `"github"`, a list of colours, or a `bf.Scale` (below).

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
    events=pd.DataFrame({
        "start": ["2023-12-22", "2024-02-14"],
        "end": ["2024-01-02", None],
        "label": ["Freeze", "Schema change"],
        "color": ["#0891b2", "#9333ea"],
    }),
    on_click="rows",
)
bf.save(report, "calendar.html", name="Pipeline runs")
```

:::{note}
The weekday-by-hour grid, `views=("days", "hours")`, was **removed in 0.5.0** (deprecated
since 0.2.2). Use [`TimeHeatmap`](#timeheatmap-when-does-it-usually-happen) with
`rows="weekday"` and `columns="hour"`, which draws other time patterns too; put it next
to the calendar in a `Select` or `Group` to show both.
:::

### Colour scales

A list of colours is spread over each block's own data, so the same colour can mean
different values in two calendars side by side. A {class}`~briefing.Scale` fixes that:
its `domain` says which values its colours stand for, in every block that uses it, and
its colours are mixed in OKLab, so equal steps in value look like equal steps in colour.
`steps=5` turns it into five classes, and calling a scale with a value gives its colour,
for chips or anything else. {mod}`briefing.color` has the OKLab helpers (`ramp`, `mix`).

When several calendars share a scale, show its legend once with {class}`~briefing.Legend`
and give the calendars `legend=False`:

```{briefing-example}
:title: Calendars on one scale, with one legend
:height: 480

import numpy as np
import pandas as pd
import briefing as bf

rng = np.random.default_rng(2)
days = pd.date_range("2026-05-19", "2026-08-31", freq="D")
interest = bf.Scale(["#1b2c80", "#9a3fc4", "#f5479a", "#ffc46b"], domain=(0, 100))
events = pd.DataFrame({"start": ["2026-06-05"], "label": ["Trailer"], "color": ["#2dd4bf"]})

report = [bf.Legend(interest, title="Search interest, 0 to 100", events=events)]
for place, level in [("Worldwide", 55), ("United States", 35)]:
    df = pd.DataFrame({"day": days, "interest": rng.normal(level, 15, len(days)).clip(0, 100).round()})
    report.append(bf.Text(f"#### {place}"))
    report.append(bf.lab.CalendarHeatmap(df, date="day", value="interest", colors=interest,
                                         events=events, legend=False))
bf.save(report, "one-legend.html", name="One legend")
```

For values that go negative, such as a daily balance, `bf.Scale(..., center=0)` makes the scale
diverging, with an odd number of colours: the middle one sits at the centre.

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
        ledger, date="day", value="balance",
        colors=bf.Scale(["#dc2626", "#f3f4f6", "#16a34a"], center=0),
    ),
    "balance.html",
    name="Daily balance",
)
```

## `TimeHeatmap`: when does it usually happen?

Where the calendar shows what happened on which date, `TimeHeatmap` shows a time
pattern: it crosses two units of one date column, `rows` down the side and `columns`
across. Weekday by hour shows when runs happen; weekday by month, seasonality; day of the
month by month, month-end effects; month by year, year over year. The units are `hour`,
`weekday`, `day` (of the month), `week` (ISO), `month`, `quarter` and `year`.

```{briefing-example}
:title: A TimeHeatmap
:height: 300

import numpy as np
import pandas as pd
import briefing as bf

rng = np.random.default_rng(111)
# Four weeks of pipeline runs, busier on weekday mornings.
starts = pd.date_range("2026-01-05", periods=28 * 24, freq="h")
weight = np.where((starts.day_of_week < 5) & (starts.hour >= 7) & (starts.hour < 12), 6, 1)
runs = pd.DataFrame({"run_at": starts.repeat(rng.poisson(weight))})

bf.save(bf.lab.TimeHeatmap(runs, date="run_at", rows="weekday", columns="hour"), "time-heatmap.html",
        name="When do runs happen?")
```

Counts and sums are **averaged per occurrence** of their cell in the data's date range:
"Monday 09:00" occurs once per Monday, so a weekday that appears five times in a month
doesn't outweigh one that appears four times. Hovering a cell shows its average, its
total and how many times it occurs. Means, medians, minimums and maximums (`agg=`)
aggregate the cell's rows directly. Cells that can't exist, such as 31 February, are left
blank; cells with no data have a dashed outline; zeros are grey.

It takes the calendar's other options too: `value` and `agg`, `colors` (a `bf.Scale` too),
`tz=`, `week_start=` (the first weekday of a `weekday` axis), `group=` (one grid per
group, on one colour scale) with `group_order=`, and `on_click="rows"`.
