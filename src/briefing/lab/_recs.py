"""RecInspector's statistics (#18): each user's history and lists, and a summary per model.

Everything is computed here, in Python; ``_render_recs.py`` only writes it out, and
``static/recs.js`` draws another user from the same numbers. The frames have fixed column
names, which :func:`check_columns` enforces:

- ``history``: ``user``, ``item``, ``timestamp``; one row per interaction;
- ``recs``: ``user``, ``item``, ``rank``, ``model``; one row per recommendation;
- ``items`` (optional): ``item``, ``title``.

Users and items are matched as text, so ``7``, ``7.0`` and ``"7"`` are the same id across
frames. The models and the users are the ones ``recs`` holds, in order of first appearance.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics
import typing as t
import warnings
from dataclasses import dataclass, field

from briefing._error import BriefingError

if t.TYPE_CHECKING:
    import pandas as pd

HISTORY = ("user", "item", "timestamp")
RECS = ("user", "item", "rank", "model")
ITEMS = ("item", "title")

#: Users and models one inspector holds; more raise an error that says to sample them first.
MAX_USERS = 100
MAX_MODELS = 4


def check_columns(frame: pd.DataFrame, argument: str, needed: tuple[str, ...]) -> None:
    """Raise when *frame* lacks one of the *needed* columns, naming them and the ones it has."""
    have = [str(c) for c in frame.columns]
    missing = [c for c in needed if c not in have]
    if not missing:
        return
    has = ", ".join(have) if have else "no columns"
    raise BriefingError(
        f"RecInspector '{argument}' needs the columns {', '.join(needed)}; it has {has}. "
        f"Rename yours first, such as {argument}.rename(columns={{'{_guess(have, missing[0])}': '{missing[0]}'}})."
    )


def _guess(have: list[str], wanted: str) -> str:
    """A column of *have* that likely stands for *wanted* (``user_id`` for ``user``), for the message."""
    for name in have:
        if name.lower().startswith(wanted) and name != wanted:
            return name
    return f"your_{wanted}_column"


def key(value: object) -> str | None:
    """An id as text, the same for ``7``, ``7.0`` and ``"7"``; None for a missing value."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return str(int(value))
    try:
        import pandas as pd

        if value is pd.NaT or value is pd.NA:
            return None
    except ImportError:  # pragma: no cover - pandas comes with every frame
        pass
    if hasattr(value, "item") and not isinstance(value, str | bytes):  # a NumPy scalar
        return key(value.item())
    return str(value)


def _ids(frame: pd.DataFrame, column: str, argument: str) -> list[str]:
    out = [key(v) for v in frame[column].tolist()]
    missing = sum(v is None for v in out)
    if missing:
        rows = "row" if missing == 1 else "rows"
        raise BriefingError(
            f"RecInspector '{argument}' has {missing:,} {rows} without a {column}; drop them first, "
            f"such as {argument}.dropna(subset=['{column}'])."
        )
    return t.cast(list[str], out)


def when(value: object) -> str:
    """A timestamp as the history strip shows it: a date, with the time when it isn't midnight."""
    if key(value) is None:  # None, NaN, NaT
        return ""
    if hasattr(value, "to_pydatetime"):  # a pandas Timestamp
        value = value.to_pydatetime()
    if isinstance(value, dt.datetime):
        if value.hour or value.minute or value.second:
            return value.strftime("%Y-%m-%d %H:%M")
        return value.strftime("%Y-%m-%d")
    if isinstance(value, dt.date):
        return value.isoformat()
    text = key(value)
    return "" if text is None else text


def rank_text(value: object) -> str:
    """A rank as the lists show it: ``3``, or ``2.5`` when ranks aren't whole numbers."""
    number = float(t.cast(float, value))
    return str(int(number)) if number.is_integer() else f"{number:g}"


@dataclass
class Summary:
    """One model over every user: how many lists, how much of them users had seen, and so on."""

    model: str
    users: int = 0
    recs: int = 0
    seen: float | None = None  # share of the recommendations already in the user's history
    items: int = 0  # distinct items recommended
    coverage: float | None = None  # items / every item the inspector knows
    popularity: float | None = None  # median interactions of the items recommended
    overlap: dict[str, float | None] = field(default_factory=dict)  # mean share of a list another model has too


@dataclass
class User:
    """One user: their history, most recent first, and each model's list (None: no list)."""

    id: str
    history: list[tuple[int, str]]  # (item index, timestamp text)
    lists: list[list[tuple[int, str]] | None]  # per model: (item index, rank text), by rank


@dataclass
class Inspection:
    """What RecInspector shows, computed once from its three frames."""

    models: list[str]
    users: list[User]
    items: list[str]  # item ids, by index
    titles: list[str | None]  # their titles, when ``items`` gives one
    popularity: list[int]  # interactions with each item in the whole history
    has_titles: bool
    known: int  # every item in the history, the recommendations and the catalogue
    history_popularity: float | None  # median popularity of what users interacted with
    summary: list[Summary]


def inspect(history: pd.DataFrame, recs: pd.DataFrame, items: pd.DataFrame | None) -> Inspection:
    """Check the three frames and compute everything RecInspector shows."""
    check_columns(history, "history", HISTORY)
    check_columns(recs, "recs", RECS)
    if items is not None:
        check_columns(items, "items", ITEMS)
    history = history.rename(columns=str)
    recs = recs.rename(columns=str)

    rec_users = _ids(recs, "user", "recs")
    rec_items = _ids(recs, "item", "recs")
    rec_models = _ids(recs, "model", "recs")
    ranks = _ranks(recs)
    models = list(dict.fromkeys(rec_models))
    users = list(dict.fromkeys(rec_users))
    if not users:
        raise BriefingError("RecInspector 'recs' is empty: it needs one row per recommendation.")
    if len(models) > MAX_MODELS:
        raise BriefingError(
            f"RecInspector shows up to {MAX_MODELS} models side by side; 'recs' has {len(models)}: "
            f"{', '.join(map(repr, models))}. Keep the ones to compare, such as recs[recs.model.isin([...])]."
        )
    if len(users) > MAX_USERS:
        raise BriefingError(
            f"RecInspector shows up to {MAX_USERS} users; 'recs' has {len(users):,}. Sample them where you "
            f"extract the data, such as recs[recs.user.isin(recs.user.drop_duplicates().sample({MAX_USERS}))]."
        )

    hist_users = _ids(history, "user", "history")
    hist_items = _ids(history, "item", "history")
    times = history["timestamp"].tolist()

    titles_by_item: dict[str, str | None] = {}
    if items is not None:
        items = items.rename(columns=str)
        twice: list[str] = []
        for item, title in zip(_ids(items, "item", "items"), items["title"].tolist(), strict=True):
            if item in titles_by_item:
                twice.append(item)
                continue
            text = key(title) if not isinstance(title, str) else title
            titles_by_item[item] = text if text else None
        if twice:
            shown = ", ".join(map(repr, twice[:3])) + (" …" if len(twice) > 3 else "")
            warnings.warn(f"RecInspector 'items' has some items more than once ({shown}); "
                          "each keeps its first title.", stacklevel=3)

    popularity_by_item: dict[str, int] = {}
    for item in hist_items:
        popularity_by_item[item] = popularity_by_item.get(item, 0) + 1

    # The items the users shown need, in order of first use: their history, then their lists.
    index: dict[str, int] = {}

    def at(item: str) -> int:
        if item not in index:
            index[item] = len(index)
        return index[item]

    wanted = set(users)
    rows_by_user: dict[str, list[tuple[object, int]]] = {u: [] for u in users}
    for position, user in enumerate(hist_users):
        if user in wanted:
            rows_by_user[user].append((times[position], position))
    user_rows: list[User] = []
    for user in users:
        ordered = _recent_first(rows_by_user[user])
        user_rows.append(User(user, [(at(hist_items[p]), when(times[p])) for p in ordered], [None] * len(models)))
    by_id = {u.id: u for u in user_rows}

    lists: dict[tuple[str, int], list[tuple[float, int, str]]] = {}
    model_at = {m: k for k, m in enumerate(models)}
    for position, (user, item, model) in enumerate(zip(rec_users, rec_items, rec_models, strict=True)):
        lists.setdefault((user, model_at[model]), []).append((ranks[position], position, item))
    for (user, k), rows in lists.items():
        rows.sort()
        by_id[user].lists[k] = [(at(item), rank_text(rank)) for rank, _, item in rows]

    item_ids = list(index)
    known = set(hist_items) | set(rec_items) | set(titles_by_item)
    history_popularity = _median([popularity_by_item[i] for i in hist_items])
    inspection = Inspection(
        models=models,
        users=user_rows,
        items=item_ids,
        titles=[titles_by_item.get(i) for i in item_ids],
        popularity=[popularity_by_item.get(i, 0) for i in item_ids],
        has_titles=items is not None,
        known=len(known),
        history_popularity=history_popularity,
        summary=[],
    )
    inspection.summary = [_summary(inspection, k) for k in range(len(models))]
    return inspection


def _ranks(recs: pd.DataFrame) -> list[float]:
    import pandas as pd

    column = recs["rank"]
    if not pd.api.types.is_numeric_dtype(column) or pd.api.types.is_bool_dtype(column):
        raise BriefingError(
            f"RecInspector 'recs' column 'rank' holds numbers, 1 first; it holds {column.dtype}. "
            "Convert it first, such as recs['rank'].astype(int)."
        )
    values = [float(v) for v in column.tolist()]
    missing = sum(not math.isfinite(v) for v in values)
    if missing:
        raise BriefingError(
            f"RecInspector 'recs' has {missing:,} rank{'s' if missing > 1 else ''} missing or infinite; "
            "every recommendation needs its place in the list."
        )
    return values


def _recent_first(rows: list[tuple[object, int]]) -> list[int]:
    """Positions of a user's interactions, the most recent first; those without a time last, in order."""
    dated = [(stamp, p) for stamp, p in rows if when(stamp)]
    undated = [p for stamp, p in rows if not when(stamp)]
    try:
        # Stable, reverse=True included: interactions at the same time keep the frame's order.
        dated.sort(key=lambda row: t.cast(t.Any, row[0]), reverse=True)
    except TypeError as exc:
        raise BriefingError(
            "RecInspector 'history' column 'timestamp' must hold values that sort together "
            "(dates, times or numbers), not a mix."
        ) from exc
    return [p for _, p in dated] + undated


def _median(values: list[int]) -> float | None:
    return float(statistics.median(values)) if values else None


def _summary(inspection: Inspection, k: int) -> Summary:
    summary = Summary(inspection.models[k])
    seen = 0
    recommended: set[int] = set()
    popular: list[int] = []
    overlaps: dict[int, list[float]] = {o: [] for o in range(len(inspection.models)) if o != k}
    for user in inspection.users:
        mine = user.lists[k]
        if mine is None:
            continue
        summary.users += 1
        summary.recs += len(mine)
        history = {item for item, _ in user.history}
        mine_items = [item for item, _ in mine]
        seen += sum(item in history for item in mine_items)
        recommended.update(mine_items)
        popular += [inspection.popularity[item] for item in mine_items]
        own = set(mine_items)
        for other, shares in overlaps.items():
            theirs = user.lists[other]
            if theirs is not None and own:
                shares.append(len(own & {item for item, _ in theirs}) / len(own))
    summary.seen = seen / summary.recs if summary.recs else None
    summary.items = len(recommended)
    summary.coverage = len(recommended) / inspection.known if inspection.known else None
    summary.popularity = _median(popular)
    summary.overlap = {
        inspection.models[o]: (sum(shares) / len(shares) if shares else None) for o, shares in overlaps.items()
    }
    return summary


__all__ = ["HISTORY", "ITEMS", "MAX_MODELS", "MAX_USERS", "RECS", "Inspection", "check_columns", "inspect"]
