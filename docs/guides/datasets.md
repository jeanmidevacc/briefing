# Sample datasets

`bf.datasets` gives you data to try briefing with, shaped for the blocks it shows off.
Nothing is downloaded and there is no data file: each dataset is generated on your
machine with numpy, from a seed. The same name, size and seed give the same rows on
every machine, so an example you share shows the same report to whoever runs it.

```python
import briefing as bf

bf.datasets.names()     # ['collection_log', 'corpus', 'embeddings', 'recsys', 'sales', 'train_test']

sales = bf.datasets.load("sales")                       # a pandas DataFrame, 1,000 rows
sales = bf.datasets.load("sales", n=50_000, seed=1)     # bigger, and other rows of the same shape
sales = bf.datasets.load("sales", engine="polars")      # or engine="pyarrow"
```

- **`n=`** sets the size, counted in what the dataset is made of: order lines, days,
  comments, customers, users or points.
- **`seed=`** gives other rows of the same shape.
- **`engine=`** picks the kind of table: `"pandas"` (the default), `"polars"` or
  `"pyarrow"`, which you install yourself. A missing value is `NaN` in pandas and a
  null in polars and pyarrow.

`"train_test"` and `"recsys"` hold several tables. They come back as a `Tables`, which
you read by name, as an attribute or a key: `rec.history` or `rec["history"]`.

| Name | What it is | `n` counts (default) | Made for |
| --- | --- | --- | --- |
| `sales` | Shop transactions over 2025 | order lines (1,000) | numbers, tables, DataDive |
| `collection_log` | A daily pipeline's runs, with gaps and failures | days (120) | `CalendarHeatmap`, `TimeHeatmap` |
| `corpus` | Short comments in two groups, with their tokens | comments (400) | word clouds |
| `train_test` | Two customer splits with drift | customers (2,000) | comparing datasets |
| `recsys` | Films, watch history, two models' recommendations | users (200) | inspecting recommendations |
| `embeddings` | 2D points in six clusters | points (1,500) | embedding maps in `DataDive` |

## `sales`

Order lines from a shop over 2025, busier in November and December and on weekdays.

| Column | |
| --- | --- |
| `order_id` | a whole number, unique |
| `ordered_at` | a timestamp, in order |
| `region` | North, South, East or West |
| `channel` | Online, Store or Partner |
| `category`, `product` | ten products in Stationery, Office and Electronics |
| `units`, `unit_price`, `discount` | the discount is 0, 0.1 or 0.2 |
| `revenue` | units × unit price × (1 − discount) |
| `customer_id` | such as `C00111`; customers come back |

```{briefing-example}
:title: Sales
:height: 560

import briefing as bf

sales = bf.datasets.load("sales")
by_region = sales.groupby("region", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
report = bf.Briefing(
    bf.Group(
        bf.BigNumber("Revenue", sales["revenue"].sum(), format="${:,.0f}"),
        bf.BigNumber("Orders", len(sales), format="{:,}"),
        bf.BigNumber("Average order", sales["revenue"].mean(), format="${:,.2f}"),
        columns=3,
    ),
    bf.Table(by_region, caption="Revenue by region"),
    bf.DataTable(sales, caption="Every order line"),
)
bf.save(report, "sales.html", name="Sales 2025")
```

## `collection_log`

A data pipeline's runs over the `n` days up to 20 November 2026. Most days run once, some
twice, a few not at all, and some runs fail.

| Column | |
| --- | --- |
| `run_at` | a timestamp, in order |
| `status` | `ok` or `failed` |
| `rows` | rows loaded: 0 when the run failed |
| `duration_s` | seconds |

```{briefing-example}
:title: A pipeline's runs
:height: 420

import briefing as bf

runs = bf.datasets.load("collection_log", n=365)
bf.save(
    bf.Briefing(
        bf.lab.CalendarHeatmap(runs, date="run_at", value="rows"),
        bf.lab.TimeHeatmap(runs, date="run_at", rows="weekday", columns="hour"),
    ),
    "runs.html",
    name="Pipeline runs",
)
```

## `corpus`

Short customer comments, half from before a redesign and half from after. The groups talk
about the same things (the app, the checkout, the account) in different words, and the
ratings rise after.

| Column | |
| --- | --- |
| `id` | a whole number |
| `group` | `before` or `after` |
| `rating` | 1 to 5 |
| `text` | one or two sentences |
| `tokens` | the text's lower-case words without stop words, as a list |

```{briefing-example}
:title: Comments before and after
:height: 480

import briefing as bf

corpus = bf.datasets.load("corpus")
means = corpus.groupby("group")["rating"].mean()
bf.save(
    bf.Briefing(
        bf.Group(
            bf.BigNumber("Rating before", means["before"], format="{:.1f}"),
            bf.BigNumber("Rating after", means["after"], format="{:.1f}"),
            columns=2,
        ),
        bf.DataTable(corpus[["group", "rating", "text"]]),
    ),
    "comments.html",
    name="Comments",
)
```

## `train_test`

Customers split into `train` (80 % of `n`) and `test`. The test customers have drifted:
they are older and richer, more of their incomes are missing, more of them are on the
`pro` plan, and a `trial` plan appears that `train` never saw.

| Column | |
| --- | --- |
| `customer_id` | a whole number, unique across both |
| `age`, `tenure_months` | whole numbers |
| `income_k` | thousands, with missing values |
| `plan` | basic, pro, enterprise, and trial in `test` only |
| `region` | North, South, East or West |
| `monthly_spend` | follows the plan |
| `churned` | true or false |

```{briefing-example}
:title: Train and test
:height: 640

import briefing as bf

split = bf.datasets.load("train_test")
bf.save(
    bf.Briefing(
        bf.Select(
            bf.lab.DataCompare({"train": split.train, "test": split.test}, label="Compared"),
            bf.lab.DataProfile(split.train, label="Train"),
            bf.lab.DataProfile(split.test, label="Test"),
        ),
    ),
    "split.html",
    name="Train and test",
)
```

## `recsys`

A catalogue of 96 films, what `n` users watched, and what two models recommend them: a
popularity model and a personal one that follows each user's taste in genres. Neither
recommends what the user has already watched.

| Table | Columns |
| --- | --- |
| `catalog` | `item_id`, `title`, `genre`, `year`, `thumbnail` (an SVG cover, as a data URI) |
| `history` | `user_id`, `item_id`, `watched_at`, `rating` (1 to 5) |
| `recs` | `user_id`, `model` (`popularity` or `personal`), `rank` (1 to 10), `item_id`, `score` |

```{briefing-example}
:title: One user's recommendations
:height: 520

import briefing as bf

rec = bf.datasets.load("recsys")
user = "u0001"
picks = rec.recs[rec.recs["user_id"] == user].merge(rec.catalog, on="item_id")
bf.save(
    bf.Briefing(
        bf.Select(
            bf.Table(picks[picks["model"] == "personal"][["rank", "title", "genre", "score"]], label="Personal"),
            bf.Table(picks[picks["model"] == "popularity"][["rank", "title", "genre", "score"]], label="Popularity"),
        ),
        bf.DataTable(rec.history[rec.history["user_id"] == user], caption=f"What {user} watched"),
    ),
    "recs.html",
    name="Recommendations",
)
```

## `embeddings`

Points in two dimensions, in six clusters of unequal size and spread, like a UMAP of
article embeddings.

| Column | |
| --- | --- |
| `id` | a whole number |
| `x`, `y` | the coordinates |
| `cluster` | the topic: sports, finance, science, travel, food or music |
| `title` | a short label, such as `Sports article 12` |

```{briefing-example}
:title: An embedding map
:height: 600

import briefing as bf

points = bf.datasets.load("embeddings")
bf.save(bf.lab.DataDive(points, x="x", y="y", color="cluster"), "map.html", name="Articles")
```
