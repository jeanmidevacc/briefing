"""Sample datasets, generated on your machine from a seed (#46).

Each dataset is drawn with numpy from a seed: no download, no data file, no licence, and the
same name, size and seed give the same rows on every machine. They are shaped for the blocks
they show off, and are what briefing's own lab examples and tests start from::

    import briefing as bf

    bf.datasets.names()                        # ['collection_log', 'corpus', 'embeddings', ...]
    sales = bf.datasets.load("sales")          # a pandas DataFrame
    sales = bf.datasets.load("sales", n=50_000, seed=1, engine="polars")
    rec = bf.datasets.load("recsys")           # several tables: rec.history, rec.recs, rec.catalog
"""
from __future__ import annotations

import base64
import typing as t
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass

from briefing._error import BriefingError

if t.TYPE_CHECKING:
    import numpy as np

#: A table as it is generated: column name -> numpy array or list, before it becomes a frame.
_Columns = dict[str, t.Any]

#: The dataframe libraries ``engine=`` accepts.
ENGINES = ("pandas", "polars", "pyarrow")

_NS = 1_000_000_000  # nanoseconds in a second


class Tables(Mapping[str, t.Any]):
    """The related tables of one dataset, by name: ``rec.history`` or ``rec["history"]``.

    Args:
        tables: Each table's name and frame, in order.
    """

    def __init__(self, tables: Mapping[str, t.Any]) -> None:
        self._tables = dict(tables)

    def __getitem__(self, name: str) -> t.Any:
        return self._tables[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._tables)

    def __len__(self) -> int:
        return len(self._tables)

    def __getattr__(self, name: str) -> t.Any:
        try:
            return self.__dict__["_tables"][name]
        except KeyError:
            raise AttributeError(f"this dataset has no table {name!r}; it has {', '.join(self)}") from None

    def __repr__(self) -> str:
        return "Tables(" + ", ".join(f"{name}: {len(frame):,} rows" for name, frame in self.items()) + ")"


# ── the datasets ──────────────────────────────────────────────────────────────


def _days(start: str, count: int) -> np.ndarray:
    import numpy as np

    return np.datetime64(start, "ns") + np.arange(count) * np.timedelta64(86_400 * _NS, "ns")


def _sales(rng: np.random.Generator, n: int) -> _Columns:
    """Shop transactions over 2025, one row per order line.

    ``order_id`` (int), ``ordered_at`` (timestamp, busier in November and December and on
    weekdays), ``region`` (North, South, East, West), ``channel`` (Online, Store, Partner),
    ``category`` and ``product`` (ten products in three categories), ``units`` (int),
    ``unit_price``, ``discount`` (0, 0.1 or 0.2), ``revenue`` (units × price × (1 − discount))
    and ``customer_id``. For KPIs, tables, calendars and DataDive tiles.
    """
    import numpy as np

    products = [
        ("Notebook", "Stationery", 4.5, 9), ("Pen set", "Stationery", 8.0, 7), ("Planner", "Stationery", 14.0, 4),
        ("Desk lamp", "Office", 32.0, 4), ("Office chair", "Office", 149.0, 2), ("Monitor stand", "Office", 39.0, 3),
        ("Headphones", "Electronics", 79.0, 4), ("Keyboard", "Electronics", 49.0, 5),
        ("Webcam", "Electronics", 59.0, 3), ("USB hub", "Electronics", 24.0, 5),
    ]
    days = _days("2025-01-01", 365)
    month = days.astype("datetime64[M]").astype(int) % 12
    weekday = (days.astype("datetime64[D]").astype(int) + 3) % 7  # 1970-01-01 was a Thursday: 0 = Monday
    weight = (1 + 0.6 * (month >= 10) + 0.15 * np.cos(month / 12 * 2 * np.pi)) * np.where(weekday >= 5, 0.6, 1.0)
    day = rng.choice(len(days), n, p=weight / weight.sum())
    seconds = rng.integers(8 * 3600, 22 * 3600, n)
    ordered_at = np.sort(days[day] + seconds * np.timedelta64(_NS, "ns"))
    popularity = np.array([p[3] for p in products], dtype=float)
    pick = rng.choice(len(products), n, p=popularity / popularity.sum())
    units = np.minimum(1 + rng.poisson(0.6, n), 9)
    price = np.array([products[i][2] for i in pick])
    discount = rng.choice([0.0, 0.1, 0.2], n, p=[0.75, 0.18, 0.07])
    customers = rng.integers(1, max(50, n // 4) + 1, n)
    return {
        "order_id": 100_001 + np.arange(n),
        "ordered_at": ordered_at,
        "region": rng.choice(["North", "South", "East", "West"], n, p=[0.35, 0.25, 0.22, 0.18]).tolist(),
        "channel": rng.choice(["Online", "Store", "Partner"], n, p=[0.5, 0.35, 0.15]).tolist(),
        "category": [products[i][1] for i in pick],
        "product": [products[i][0] for i in pick],
        "units": units,
        "unit_price": price,
        "discount": discount,
        "revenue": np.round(units * price * (1 - discount), 2),
        "customer_id": [f"C{c:05d}" for c in customers],
    }


def _collection_log(rng: np.random.Generator, n: int) -> _Columns:
    """A daily data pipeline over the *n* days up to 2026-11-20, one row per run.

    ``run_at`` (timestamp), ``status`` (``ok`` or ``failed``), ``rows`` (int, 0 when the run
    failed) and ``duration_s``. Most days run once, some twice, and a few have no run at
    all, so a calendar shows gaps and failures. For CalendarHeatmap and TimeHeatmap.
    """
    import numpy as np

    days = _days("2026-11-20", 1) - np.arange(n)[::-1] * np.timedelta64(86_400 * _NS, "ns")
    ran = rng.random(n) >= 0.04
    runs = np.where(ran, np.where(rng.random(n) < 0.1, 2, 1), 0)
    day = np.repeat(days, runs)
    second = np.arange(len(day)) - np.repeat(np.cumsum(runs) - runs, runs) == 1  # a day's second run
    hour = np.where(second, rng.integers(13, 18, len(day)), rng.integers(1, 4, len(day)))
    run_at = day + (hour * 3600 + rng.integers(0, 3600, len(day))) * np.timedelta64(_NS, "ns")
    failed = rng.random(len(day)) < 0.06
    rows = np.where(failed, 0, rng.normal(1200, 300, len(day)).clip(0).round()).astype(np.int64)
    return {
        "run_at": run_at,
        "status": np.where(failed, "failed", "ok").tolist(),
        "rows": rows,
        "duration_s": np.round(
            np.where(failed, rng.uniform(2, 20, len(day)), rows / 40 + rng.normal(30, 5, len(day))), 1
        ),
    }


_STOP = {"a", "and", "another", "but", "finally", "got", "i", "is", "it", "my", "needs", "new", "now", "on", "since",
         "so", "the", "to", "too", "when", "with", "work", "works", "opened", "feels", "makes", "love", "keeps",
         "giving", "me", "in"}
_THINGS = ["app", "page", "account", "order", "checkout", "screen", "support", "price", "settings", "profile"]
#: Each group's words and sentences: what its comments share with the other group is _THINGS.
_GROUPS = {
    "before": (
        ["slow", "confusing", "cluttered", "broken", "frustrating", "clunky"],
        ["crash", "error", "freeze", "login problem", "long wait", "lost order"],
        ["The {t} is {a}.", "Another {n} in the {t}.", "The {t} feels {a} and {b}.",
         "Got a {n} when I opened my {t}.", "Too {a}: the {t} needs work.", "The {t} keeps giving me a {n}."],
    ),
    "after": (
        ["fast", "simple", "clean", "easy", "smooth", "clear"],
        ["search", "dark mode", "quick checkout", "new layout", "helpful tips", "faster login"],
        ["The {t} is {a} now.", "Love the {n} in the {t}.", "The {t} feels {a} and {b}.",
         "The {n} makes my {t} {a}.", "So {a}: the {t} finally works.", "The {t} is {a} with the {n}."],
    ),
}


def _corpus(rng: np.random.Generator, n: int) -> _Columns:
    """Short customer comments in two groups, before and after a redesign.

    ``id`` (int), ``group`` (``before`` or ``after``), ``rating`` (1 to 5, higher after),
    ``text`` (one or two sentences) and ``tokens`` (its lower-case words without stop
    words, a list). The groups share the things they talk about (the app, the checkout…)
    and differ in how they describe them. For WordCloud (#15).
    """
    import numpy as np

    group = np.where(np.arange(n) < n // 2, "before", "after")
    rng.shuffle(group)
    texts, tokens, ratings = [], [], []
    for g in group:
        adjectives, nouns, templates = _GROUPS[str(g)]
        sentences = []
        for _ in range(1 + int(rng.random() < 0.4)):
            a, b = rng.choice(len(adjectives), 2, replace=False)
            sentence = templates[int(rng.integers(len(templates)))].format(
                t=_THINGS[int(rng.integers(len(_THINGS)))], a=adjectives[a], b=adjectives[b],
                n=nouns[int(rng.integers(len(nouns)))])
            sentences.append(sentence)
        text = " ".join(sentences)
        texts.append(text)
        words = "".join(ch if ch.isalpha() or ch == " " else " " for ch in text.lower()).split()
        tokens.append([w for w in words if w not in _STOP])
        ratings.append(int(np.clip(round(rng.normal(2.2 if g == "before" else 3.9, 0.9)), 1, 5)))
    return {"id": np.arange(1, n + 1), "group": group.tolist(), "rating": np.array(ratings), "text": texts,
            "tokens": tokens}


def _customers(rng: np.random.Generator, n: int, first: int, drift: bool) -> _Columns:
    import numpy as np

    plans = ["basic", "pro", "enterprise", "trial"]
    plan_p = [0.40, 0.42, 0.13, 0.05] if drift else [0.55, 0.32, 0.13, 0.0]
    plan = rng.choice(plans, n, p=plan_p)
    age = np.clip(rng.normal(41 if drift else 38, 11, n).round(), 18, 85).astype(np.int64)
    income = np.round(rng.lognormal(np.log(58 * (1.08 if drift else 1.0)), 0.4, n), 1)
    income[rng.random(n) < (0.08 if drift else 0.02)] = np.nan
    tenure = rng.integers(0, 61, n)
    spend = np.round(np.select([plan == "basic", plan == "pro", plan == "enterprise"], [19, 49, 199], 0)
                     * rng.uniform(0.8, 1.2, n), 2)
    odds = -1.2 - 0.04 * tenure + np.select([plan == "trial", plan == "basic"], [1.5, 0.4], 0.0)
    churned = rng.random(n) < 1 / (1 + np.exp(-odds))
    regions = rng.choice(["North", "South", "East", "West"], n, p=[0.3, 0.25, 0.25, 0.2]).tolist()
    return {
        "customer_id": first + np.arange(n),
        "age": age,
        "income_k": income,
        "tenure_months": tenure,
        "plan": plan.tolist(),
        "region": regions,
        "monthly_spend": spend,
        "churned": churned,
    }


def _train_test(rng: np.random.Generator, n: int) -> dict[str, _Columns]:
    """Customers split into ``train`` (80 % of *n*) and ``test``, with drift between them.

    Both have ``customer_id``, ``age``, ``income_k`` (with missing values), ``tenure_months``,
    ``plan`` (basic, pro, enterprise), ``region``, ``monthly_spend`` and ``churned`` (bool).
    In ``test``, customers are older and richer, more income is missing, the plan mix
    leans to ``pro``, and a ``trial`` plan appears that ``train`` never saw. For DataCompare (#17).
    """
    train = round(n * 0.8)
    return {"train": _customers(rng, train, 1, False), "test": _customers(rng, n - train, train + 1, True)}


_GENRES = {"Drama": "#6366f1", "Comedy": "#f59e0b", "Thriller": "#ef4444", "Documentary": "#10b981",
           "Animation": "#ec4899", "Sci-fi": "#0ea5e9"}
_ADJECTIVES = ["Quiet", "Red", "Last", "Silver", "Hidden", "Long", "Bright", "Cold", "Little", "Wild", "Golden",
               "Broken"]
_NOUNS = ["Harbor", "Summer", "Signal", "Garden", "River", "Orbit", "Kingdom", "Letter", "Island", "Machine",
          "Frontier", "Echo"]


def _thumbnail(title: str, colour: str) -> str:
    """A small SVG cover: the title's initials on the genre's colour, as a data URI."""
    initials = "".join(word[0] for word in title.split()[:2])
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="60" height="90" viewBox="0 0 60 90">'
           f'<rect width="60" height="90" rx="6" fill="{colour}"/>'
           f'<text x="30" y="54" font-family="sans-serif" font-size="22" font-weight="700" fill="#ffffff" '
           f'text-anchor="middle">{initials}</text></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode("ascii")


def _recsys(rng: np.random.Generator, n: int) -> dict[str, _Columns]:
    """A film catalogue, what *n* users watched, and what two models recommend them.

    ``catalog``: ``item_id``, ``title``, ``genre``, ``year`` and ``thumbnail`` (an SVG cover as
    a data URI). ``history``: ``user_id``, ``item_id``, ``watched_at`` and ``rating`` (1 to 5).
    ``recs``: ``user_id``, ``model`` (``popularity`` or ``personal``), ``rank`` (1 to 10),
    ``item_id`` and ``score``; neither model recommends what the user already watched.
    For RecInspector (#18).
    """
    import numpy as np

    genres = list(_GENRES)
    count = 96
    titles = [f"{_ADJECTIVES[i % 12]} {_NOUNS[(i * 5 + i // 12) % 12]}" for i in range(count)]
    genre = rng.choice(len(genres), count)
    popularity = 1 / (1 + np.arange(count)) ** 0.8
    popularity = popularity[rng.permutation(count)]
    item_ids = [f"i{i + 1:03d}" for i in range(count)]
    catalog = {
        "item_id": item_ids,
        "title": titles,
        "genre": [genres[g] for g in genre],
        "year": rng.integers(1990, 2026, count),
        "thumbnail": [_thumbnail(titles[i], _GENRES[genres[genre[i]]]) for i in range(count)],
    }
    history: dict[str, list[t.Any]] = {"user_id": [], "item_id": [], "watched_at": [], "rating": []}
    recs: dict[str, list[t.Any]] = {"user_id": [], "model": [], "rank": [], "item_id": [], "score": []}
    start = np.datetime64("2025-01-01", "ns")
    ranked_by_popularity = np.argsort(-popularity, kind="stable")
    for u in range(n):
        user = f"u{u + 1:04d}"
        taste = rng.dirichlet(np.full(len(genres), 0.6))
        affinity = popularity * taste[genre] * len(genres)
        seen = rng.choice(count, int(rng.integers(5, 31)), replace=False, p=affinity / affinity.sum())
        times = np.sort(start + rng.integers(0, 365 * 86_400, len(seen)) * np.timedelta64(_NS, "ns"))
        for item, when in zip(seen, times, strict=True):
            history["user_id"].append(user)
            history["item_id"].append(item_ids[item])
            history["watched_at"].append(when)
            history["rating"].append(int(np.clip(round(rng.normal(2.5 + 2.5 * taste[genre[item]] ** 0.5, 0.8)), 1, 5)))
        unseen = np.ones(count, dtype=bool)
        unseen[seen] = False
        personal = affinity * rng.uniform(0.8, 1.2, count)
        for model, order, score in (
            ("popularity", ranked_by_popularity, popularity / popularity.max()),
            ("personal", np.argsort(-personal, kind="stable"), personal / personal.max()),
        ):
            top = [i for i in order if unseen[i]][:10]
            for rank, item in enumerate(top, start=1):
                recs["user_id"].append(user)
                recs["model"].append(model)
                recs["rank"].append(rank)
                recs["item_id"].append(item_ids[item])
                recs["score"].append(round(float(score[item]), 4))
    history_columns: _Columns = {**history, "watched_at": np.array(history["watched_at"], dtype="datetime64[ns]"),
                                 "rating": np.array(history["rating"], dtype=np.int64)}
    recs_columns: _Columns = {**recs, "rank": np.array(recs["rank"], dtype=np.int64),
                              "score": np.array(recs["score"])}
    return {"history": history_columns, "recs": recs_columns, "catalog": catalog}


_TOPICS = ["sports", "finance", "science", "travel", "food", "music"]


def _embeddings(rng: np.random.Generator, n: int) -> _Columns:
    """2D points in six clusters of unequal size and spread, like a UMAP of article embeddings.

    ``id`` (int), ``x`` and ``y`` (the coordinates), ``cluster`` (the topic: sports, finance,
    science, travel, food, music) and ``title`` (a short label). For DataDive's embedding
    maps (#16).
    """
    import numpy as np

    sizes = np.array([0.28, 0.22, 0.17, 0.14, 0.11, 0.08])
    cluster = rng.choice(len(_TOPICS), n, p=sizes)
    angle = np.arange(len(_TOPICS)) / len(_TOPICS) * 2 * np.pi + rng.uniform(-0.3, 0.3, len(_TOPICS))
    radius = rng.uniform(4.5, 7.5, len(_TOPICS))
    spread = rng.uniform(0.6, 1.4, len(_TOPICS))
    x = np.cos(angle)[cluster] * radius[cluster] + rng.normal(0, 1, n) * spread[cluster]
    y = np.sin(angle)[cluster] * radius[cluster] + rng.normal(0, 1, n) * spread[cluster] * 0.8
    counters = dict.fromkeys(range(len(_TOPICS)), 0)
    titles = []
    for c in cluster:
        counters[int(c)] += 1
        titles.append(f"{_TOPICS[int(c)].capitalize()} article {counters[int(c)]}")
    return {
        "id": np.arange(1, n + 1),
        "x": np.round(x, 4),
        "y": np.round(y, 4),
        "cluster": [_TOPICS[int(c)] for c in cluster],
        "title": titles,
    }


@dataclass(frozen=True)
class _Dataset:
    make: Callable[[np.random.Generator, int], _Columns | dict[str, _Columns]]
    n: int  # the default size
    least: int  # the smallest size that still has every feature the dataset is for
    what: str  # what n counts


_DATASETS: dict[str, _Dataset] = {
    "collection_log": _Dataset(_collection_log, 120, 7, "days"),
    "corpus": _Dataset(_corpus, 400, 2, "comments"),
    "embeddings": _Dataset(_embeddings, 1500, 6, "points"),
    "recsys": _Dataset(_recsys, 200, 1, "users"),
    "sales": _Dataset(_sales, 1000, 1, "order lines"),
    "train_test": _Dataset(_train_test, 2000, 10, "customers, train and test together"),
}


# ── loading ───────────────────────────────────────────────────────────────────


def names() -> list[str]:
    """The names :func:`load` accepts, sorted.

    Example::

        bf.datasets.names()   # ['collection_log', 'corpus', 'embeddings', 'recsys', 'sales', 'train_test']
    """
    return sorted(_DATASETS)


def load(name: str, *, n: int | None = None, seed: int = 0, engine: str = "pandas") -> t.Any:
    """A sample dataset, generated from a seed: the same rows for the same name, size and seed.

    - ``"sales"``: shop transactions over 2025 (``n``: order lines, 1,000).
    - ``"collection_log"``: a daily pipeline's runs, with gaps and failures (days, 120).
    - ``"corpus"``: short comments in two groups, with their tokens (comments, 400).
    - ``"train_test"``: two customer splits with drift, as :class:`Tables` (customers, 2,000).
    - ``"recsys"``: films, watch history and two models' recommendations, as :class:`Tables`
      (users, 200).
    - ``"embeddings"``: 2D points in six clusters (points, 1,500).

    The datasets guide lists every column.

    Args:
        name: One of :func:`names`.
        n: How big: lines, days, comments, customers, users or points, as above.
        seed: Another seed gives other rows of the same shape.
        engine: ``"pandas"``, ``"polars"`` or ``"pyarrow"``: the kind of table returned.
            Polars and pyarrow are not installed with briefing.

    Returns:
        A table of that engine; for ``"train_test"`` and ``"recsys"``, a :class:`Tables` of
        several (``data.train``, ``data.test``; ``rec.history``, ``rec.recs``, ``rec.catalog``).

    Example::

        sales = bf.datasets.load("sales")
        report = bf.Briefing(
            bf.BigNumber("Revenue", sales["revenue"].sum(), format="${:,.0f}"),
            bf.DataTable(sales),
        )
    """
    dataset = _DATASETS.get(name) if isinstance(name, str) else None
    if dataset is None:
        raise BriefingError(f"bf.datasets.load: no dataset {name!r}. Pass one of {', '.join(names())}.")
    size = dataset.n if n is None else n
    if isinstance(size, bool) or not isinstance(size, int) or size < dataset.least:
        raise BriefingError(
            f"bf.datasets.load: {name!r} needs n= as a whole number of {dataset.what}, at least "
            f"{dataset.least:,}; got {n!r}."
        )
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise BriefingError(f"bf.datasets.load: seed must be a whole number, 0 or more; got {seed!r}.")
    if engine not in ENGINES:
        raise BriefingError(f"bf.datasets.load: engine must be one of {', '.join(ENGINES)}; got {engine!r}.")
    build = _builder(engine)

    import numpy as np

    made = dataset.make(np.random.default_rng(seed), size)
    if name in _SEVERAL:
        return Tables({table: build(columns) for table, columns in t.cast("dict[str, _Columns]", made).items()})
    return build(t.cast("_Columns", made))


#: The datasets made of several tables, returned as :class:`Tables`.
_SEVERAL = frozenset({"recsys", "train_test"})


def _builder(engine: str) -> Callable[[_Columns], t.Any]:
    """What turns generated columns into a table of *engine*: each library reads them directly.

    A missing number is NaN in the generated columns, as in pandas; polars and pyarrow get a
    null instead, their own missing value.
    """
    try:
        if engine == "polars":
            import polars as pl

            return lambda columns: pl.DataFrame(columns, nan_to_null=True)
        if engine == "pyarrow":
            import pyarrow as pa

            return lambda columns: pa.table({k: pa.array(v, from_pandas=True) for k, v in columns.items()})
    except ImportError:
        raise BriefingError(
            f"bf.datasets.load(engine={engine!r}) needs {engine}, which briefing doesn't install: "
            f"pip install {engine}, or leave engine= out for pandas."
        ) from None
    import pandas as pd

    return pd.DataFrame


__all__ = ["ENGINES", "Tables", "load", "names"]
