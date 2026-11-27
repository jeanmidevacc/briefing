"""RecInspector rendering (#18): a summary per model, then one user's history and lists.

The numbers come from ``lab/_recs.py``. Python draws the summary and the first user, which is
what prints and what a page without scripts shows; ``script.bf-recs__data`` holds every user,
each item's id and title stored once, and ``lab/static/recs.js`` draws the user picked with
the same markup as :func:`user_html` (a browser test compares the two for every user).

Model *k* is drawn in ``var(--bf-recs-k)`` (recs.css): the theme's accent, then hues apart from it.
"""
from __future__ import annotations

import html as _html
import typing as t

from briefing.lab._render_profile import _fmt_num
from briefing.renderers.script_json import script_json

if t.TYPE_CHECKING:
    from briefing.lab._blocks import RecInspector
    from briefing.lab._recs import Inspection, User


def _e(text: object) -> str:
    return _html.escape(str(text))


def _count(n: int, one: str, many: str) -> str:
    return f"{n:,} {one if n == 1 else many}"


def _pct(share: float | None) -> str:
    if share is None:
        return "—"
    if 0 < share < 0.001:
        return "&lt;0.1%"
    return f"{share * 100:.1f}%"


# ── one user ──────────────────────────────────────────────────────────────────


def _name(inspection: Inspection, item: int) -> str:
    """An item's title and id (CSS shows one of them), and a tooltip with both and its popularity."""
    item_id, title = inspection.items[item], inspection.titles[item]
    interactions = _count(inspection.popularity[item], "interaction", "interactions")
    tip = f"{item_id} · {title}" if title else item_id
    tip += f" · {interactions} in the history"
    shown = f'<span class="bf-recs__title">{_e(title)}</span>' if title else ""
    return f'<span class="bf-recs__name" title="{_e(tip)}">{shown}<span class="bf-recs__id">{_e(item_id)}</span></span>'


def _marks(seen: bool, others: list[str], user: str) -> str:
    out = ""
    if seen:
        tip = f"Already in {user}’s history"
        out += f'<span class="bf-recs__mark bf-recs__mark--seen" title="{_e(tip)}">seen</span>'
    if others:
        tip = "Also recommended by " + ", ".join(others)
        out += f'<span class="bf-recs__mark bf-recs__mark--shared" title="{_e(tip)}">shared</span>'
    return out


def user_html(inspection: Inspection, index: int) -> str:
    """The inner HTML of the section that shows user *index*: who, their history, each model's list."""
    user: User = inspection.users[index]
    history = {item for item, _ in user.history}
    count = _count(len(user.history), "interaction", "interactions")
    out = (f'<div class="bf-recs__who"><span class="bf-recs__user-id">{_e(user.id)}</span>'
           f"<small>{count} in the history</small></div>")
    if user.history:
        strip = "".join(
            f'<li class="bf-recs__item" data-item="{_e(inspection.items[item])}">{_name(inspection, item)}'
            f'<span class="bf-recs__when">{_e(stamp)}</span></li>'
            for item, stamp in user.history
        )
        out += ('<div class="bf-recs__history"><div class="bf-recs__heading">History, most recent first</div>'
                f'<ol class="bf-recs__strip">{strip}</ol></div>')
    else:
        out += ('<div class="bf-recs__history"><div class="bf-recs__heading">History</div>'
                '<p class="bf-recs__none">No history.</p></div>')
    lists = [None if rows is None else {item for item, _ in rows} for rows in user.lists]
    columns = ""
    for k, model in enumerate(inspection.models):
        rows = user.lists[k]
        head = f'<div class="bf-recs__heading">{_e(model)}</div>'
        if rows is None:
            columns += f'<div class="bf-recs__model" data-k="{k}">{head}<p class="bf-recs__none">No list.</p></div>'
            continue
        items = ""
        for item, rank in rows:
            seen = item in history
            others = [inspection.models[o] for o, theirs in enumerate(lists)
                      if o != k and theirs is not None and item in theirs]
            cls = ("bf-recs__item" + (" bf-recs__item--seen" if seen else "")
                   + (" bf-recs__item--shared" if others else ""))
            items += (f'<li class="{cls}" data-item="{_e(inspection.items[item])}">'
                      f'<span class="bf-recs__rank">{_e(rank)}</span>{_name(inspection, item)}'
                      f"{_marks(seen, others, user.id)}</li>")
        columns += f'<div class="bf-recs__model" data-k="{k}">{head}<ol class="bf-recs__list">{items}</ol></div>'
    return out + f'<div class="bf-recs__models">{columns}</div>'


# ── the summary ───────────────────────────────────────────────────────────────


def _summary(inspection: Inspection) -> str:
    others = len(inspection.models) > 1
    heads = ["model", "users", "recommendations", "already seen", "items", "median popularity"]
    if others:
        heads.append("overlap")
    head = "".join(f'<th scope="col">{h}</th>' for h in heads)
    body = ""
    for k, row in enumerate(inspection.summary):
        swatch = f'<span class="bf-recs__swatch" data-k="{k}"></span>'
        cells = [
            f"{row.users:,}",
            f"{row.recs:,}",
            _pct(row.seen),
            f"{row.items:,} <small>({_pct(row.coverage)})</small>",
            _e(_fmt_num(row.popularity)) if row.popularity is not None else "—",
        ]
        if others:
            cells.append(" · ".join(
                f"{_e(model)} {_pct(share)}" for model, share in row.overlap.items()
            ))
        body += f'<tr><th scope="row">{swatch}{_e(row.model)}</th>' + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    baseline = (_e(_fmt_num(inspection.history_popularity))
                if inspection.history_popularity is not None else "—")
    notes = [
        "<b>already seen</b>: the share of recommendations already in the user’s history",
        f"<b>items</b>: the distinct items recommended, and their share of the {inspection.known:,} known",
        f"<b>median popularity</b>: interactions in the history with the items recommended; "
        f"the items users interacted with: {baseline}",
    ]
    if others:
        notes.append("<b>overlap</b>: the mean share of a user’s list that the other model recommends too")
    return (
        f'<div class="bf-recs__summary"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
        f'<p class="bf-recs__notes">{" · ".join(notes)}</p></div>'
    )


# ── the controls and the data ─────────────────────────────────────────────────


def _controls(inspection: Inspection) -> str:
    """The user picker and the ids/titles switch, which recs.js runs; hidden until it does."""
    options = "".join(
        f'<option value="{i}">{_e(user.id)} · {_count(len(user.history), "interaction", "interactions")}</option>'
        for i, user in enumerate(inspection.users)
    )
    switch = (
        '<span class="bf-recs__switch" role="group" aria-label="Show items as">'
        '<button type="button" class="bf-recs__show" data-show="titles" aria-pressed="true">titles</button>'
        '<button type="button" class="bf-recs__show" data-show="ids" aria-pressed="false">ids</button></span>'
        if inspection.has_titles else ""
    )
    return (
        '<div class="bf-recs__controls" hidden>'
        '<input type="search" class="bf-recs__search" placeholder="Search users" aria-label="Search users">'
        f'<select class="bf-recs__pick" aria-label="User">{options}</select>'
        '<span class="bf-recs__shown" aria-live="polite"></span>'
        f"{switch}</div>"
    )


def _legend() -> str:
    return (
        '<p class="bf-recs__legend"><span class="bf-recs__mark bf-recs__mark--seen">seen</span> already in the '
        'user’s history · <span class="bf-recs__mark bf-recs__mark--shared">shared</span> another model '
        "recommends it to them too</p>"
    )


def _payload(inspection: Inspection) -> dict[str, t.Any]:
    """What recs.js needs to draw any user: the items once, then each user's indexes into them."""
    return {
        "models": inspection.models,
        "items": [[item, title, n] for item, title, n in
                  zip(inspection.items, inspection.titles, inspection.popularity, strict=True)],
        "users": [{"id": user.id, "history": [[item, stamp] for item, stamp in user.history],
                   "lists": [None if rows is None else [[item, rank] for item, rank in rows] for rows in user.lists]}
                  for user in inspection.users],
    }


# ── public entry ──────────────────────────────────────────────────────────────


def render_recs(block: RecInspector) -> str:
    """Render a :class:`~briefing.lab.RecInspector`: the summary, the controls, then the first user."""
    inspection = block.inspection
    show = ' data-show="titles"' if inspection.has_titles else ""
    return (
        f'<div class="bf-block bf-recs" style="--bf-recs-models:{len(inspection.models)}"{show}>'
        f"{_summary(inspection)}{_controls(inspection)}{_legend()}"
        f'<section class="bf-recs__user" data-user="0" aria-live="polite">{user_html(inspection, 0)}</section>'
        f'<script type="application/json" class="bf-recs__data">{script_json(_payload(inspection))}</script>'
        "</div>"
    )


__all__ = ["render_recs", "user_html"]
