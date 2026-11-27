# The lab: DataProfile, DataCompare, DataDive, RecInspector, CalendarHeatmap, TimeHeatmap

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

## `DataCompare`: datasets column by column

`DataCompare` puts two or more datasets side by side, such as train and test, or this
week's run and last week's. Each column gets a row: a line of statistics per dataset, in
that dataset's colour, and their distributions overlaid on one chart.

- **Numbers and dates** are histograms on bins every dataset shares, so the bars line up.
- **Categories** are bars of their most frequent values. Above 20 distinct values, they're
  cumulative curves instead: how much of the data the top 1, 2, … values cover.
- **Badges** flag a column only some datasets have, one whose type differs, and one that
  has *drifted*: its distance from the first dataset, the reference, is above
  `distance_threshold`.
- **Missing values and zeros** above `missing_threshold` and `zero_threshold` are highlighted.

Pass the datasets as a dict: its keys name them, and the first one is the reference.
`sort=` puts the columns that need a look first: `"distance"`, `"missing"`, `"zeros"` or
`"non_uniformity"` (how far a column is from spreading its values evenly).

Above the rows, the reader can:

- **sort** them again, **search** column names and show only numbers, categories or dates;
- switch the charts between **percentages** of each dataset (the default, so datasets of
  different sizes compare) and **counts**;
- put them on a **log scale**: the bars' heights for numbers, dates and categories; the
  ranks for a cumulative curve, so a long tail spreads out;
- show each dataset's **deciles** as ticks above a number's chart, its median taller.

The controls need the page's script. Printed, the rows keep their order and filters, and
the controls are left out.

```{briefing-example}
:title: Train and test compared
:height: 720

import briefing as bf

split = bf.datasets.load("train_test")
bf.save(
    bf.lab.DataCompare({"train": split.train, "test": split.test}, sort="distance"),
    "compare.html",
    name="Train and test",
)
```

Every statistic is computed in Python. The report carries them, not the rows, so comparing
ten million rows makes as small a file as comparing a thousand.

### The distance

By default, the distance between a dataset and the reference is the **Jensen–Shannon
distance**. It compares the two distributions on the same bins (the shared histogram bins
for numbers and dates, the most frequent values for categories) as proportions, so
datasets of different sizes compare fairly. It's symmetric, it runs from 0 (the same
distribution) to 1 (nothing in common), and it means the same for every type of column,
so one threshold works for all of them.

`distance=` picks another measure:

| `distance=` | Range | Drifted above (default) |
|---|---|---|
| `"jensen_shannon"` (default) | 0 to 1 | 0.10 |
| `"hellinger"` | 0 to 1 | 0.10 |
| `"total_variation"` | 0 to 1 | 0.10 |
| `"psi"`, the population stability index | 0 and up | 0.20 |

Or pass a function of your own. It gets two NumPy arrays of proportions over the same
bins, the reference's first, with missing values left out, and returns a number. Without
`distance_threshold=`, no column is marked as drifted, but the distance is still shown and
sortable.

```python
import numpy as np

def largest_gap(p, q):
    """The largest difference in share in any one bin."""
    return float(np.max(np.abs(p - q)))

bf.lab.DataCompare({"train": train, "test": test}, distance=largest_gap, distance_threshold=0.05)
```

In the JSON form, `distance` is one of the names; a function travels by reference
(`{"ref": "..."}`), like any other Python object.

## `DataDive`: every row a dot

Each row becomes a dot. The reader picks which columns drive the X axis, the Y axis
and the colour; `layout="tile"` packs the dots into a grid of cells instead of
plotting them on axes, like Facets Dive.

- The legend under the controls filters: a click hides or shows a category's dots, and
  Alt+click shows that category alone. A number or a date column colours along a ramp.
- Clicking a dot opens a card with its whole row, under the chart; web addresses in it are
  links. **Pin** keeps a card, so the next click opens another beside it: two pinned rows
  compare side by side. × or Esc closes them. `title=` names the column that heads each
  card and tooltip, such as a product's or an article's name; without it, a card is
  headed by its row number.
- The search box finds rows by any text in them, `title=` included: the first matches are
  listed under it, and Enter or a click opens a match's card. **+ Filter** adds a filter on
  a column: tick a category's values, or give a number or a date a range. **Highlight**
  dims the rows that don't match; **Filter** hides them. All of it happens in the page.
- Changing an axis or a facet moves the dots to their new places (up to 30,000 dots, and
  not when the reader's system asks for less motion). Ctrl or ⌘ + scroll (a trackpad's
  pinch) zooms in around the pointer, dragging pans, and a double-click or **Reset** shows
  everything again; a plain scroll still scrolls the page. Zoom is shared by every panel,
  and close up the dots carry their `title=`.
- `thumbnails=` names a column of pictures (data URIs, file paths or bytes): in the
  `"tile"` layout, dots become their pictures when the cells have room, framed in their
  colour, and the tooltip and the card show them too. Each distinct picture is embedded once.
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

With pictures, tiles show what each row is:

```{briefing-example}
:title: Films as thumbnails
:height: 720

import briefing as bf

films = bf.datasets.load("recsys").catalog
bf.save(
    bf.lab.DataDive(films, x="genre", y="year", color="genre", layout="tile", title="title",
                    thumbnails="thumbnail", buckets={"genre": 6, "year": 3}),
    "films.html",
    name="Films",
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
bf.save(bf.lab.DataDive(points, x="x", y="y", color="cluster", colors=topics, title="title"), "map.html",
        name="Articles")
```

## Linked selection: a bar selects rows in a `DataDive`

`selects=` on a `DataProfile` or a `DataCompare` names a `DataDive` in the same page. A
click on a bar then highlights that bar's rows there:

- a number's or a date's bar selects the rows that fall in it, exactly as the chart counted
  them;
- a category's bar selects its value;
- **Shift**+click adds another bar of the same column;
- click the bar again, click × on the chip that names the selection in the DataDive, or
  press **Esc** to clear it.

The DataDive matches the bar on the column of the same name. A column it doesn't have
(or holds as another type) isn't clickable, and the chart's tooltip says why. Its
Highlight and Filter buttons apply to the selection as to its own filters, and two
senders add two chips. Bars and chips also work from the keyboard (Tab, then Enter).

```{briefing-example}
:title: A profile that selects rows in a DataDive
:height: 900

import briefing as bf

sales = bf.datasets.load("sales")
bf.save(
    bf.Briefing(
        "Click a bar in the profile: its orders light up in the DataDive below.",
        bf.lab.DataProfile(sales[["region", "channel", "units", "revenue"]], selects="orders"),
        bf.lab.DataDive(sales, x="units", y="revenue", color="region", name="orders"),
    ),
    "linked.html",
    name="Sales",
)
```

The target must be a `DataDive` named in the sender's page: rendering raises an error that
lists the DataDives there otherwise, and `bf.validate` reports it as `unknown-target`. A
selection stays in its report: two embeds on one page don't select rows in each other.

## `RecInspector`: recommendations next to each user's history

`RecInspector` shows what recommender models suggest to each user, next to what that user
did, one column per model. A summary comes first, one line per model over every user:

| Column | What it says |
| --- | --- |
| already seen | The share of recommendations already in the user's history. |
| items | The distinct items the model recommends, and their share of every item the inspector knows (its coverage). |
| median popularity | How many interactions the items recommended have in the history, next to the items users interacted with. A model far above it recommends what everyone already gets. |
| overlap | The mean share of a user's list that each other model recommends too. |

Then one user at a time, picked from a list you can search: their history, most recent
first, and each model's list by rank. An item is marked **seen** when it is already in the
user's history, and **shared** when another model recommends it to them too. With `items`,
items show their title, and a switch shows their ids instead.

The frames have **fixed column names**, so the code that feeds the inspector can't drift
from it. Other columns are ignored, and a missing one raises an error that names it:

| Frame | Columns |
| --- | --- |
| `history` | `user`, `item`, `timestamp`: one row per interaction |
| `recs` | `user`, `item`, `rank` (1 first), `model`: one row per recommendation |
| `items` (optional) | `item`, `title` |

The models (up to 4) and the users (up to 100) are the ones `recs` holds, in order. Choose
them where you extract the data: sample the users, cut each list to its top *k*.

```{briefing-example}
:title: Two models' recommendations, user by user
:height: 900

import briefing as bf

rec = bf.datasets.load("recsys", n=50)
bf.save(
    bf.lab.RecInspector(
        history=rec.history.rename(columns={"user_id": "user", "item_id": "item", "watched_at": "timestamp"}),
        recs=rec.recs.rename(columns={"user_id": "user", "item_id": "item"}),
        items=rec.catalog.rename(columns={"item_id": "item"}),
    ),
    "recs.html",
    name="Recommendations",
)
```

In this dataset neither model recommends what a user already watched, so nothing is marked
**seen**; the popularity model's median popularity shows how much more it leans on the
films everyone watches.

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
