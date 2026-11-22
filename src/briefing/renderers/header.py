"""The report header (#25): the name, the render time, the export menu and a Header's extras.

A report without ``header=`` keeps the markup it always had; the default name "Report"
is never shown as a title.
"""
from __future__ import annotations

import base64
import datetime as dt
import html as _html

from briefing.blocks.header import Header, local_time
from briefing.renderers.inline import inline_markdown

#: The name a report gets when none is given: not shown as a title.
DEFAULT_NAME = "Report"


def _time(when: dt.datetime, tz: str | None, cls: str = "") -> str:
    if tz is None:  # as before #25: the time as given, labelled UTC
        shown, iso = when.strftime("%Y-%m-%d %H:%M UTC"), when.isoformat()
    else:
        local = local_time(when, tz)
        shown, iso = f"{local:%Y-%m-%d %H:%M} {local.tzname()}", local.isoformat()
    attr = f' class="{cls}"' if cls else ""
    return f'<time{attr} datetime="{iso}">{shown}</time>'


def _as_of(header: Header) -> str:
    value = header.as_of
    if value is None:
        return ""
    if isinstance(value, dt.datetime):
        when = _time(value, header.tz or "UTC")
    else:
        assert isinstance(value, dt.date)
        when = f'<time datetime="{value.isoformat()}">{value.isoformat()}</time>'
    return f'<span class="bf-report__asof">Data as of {when}</span>'


def render_header(name: str, header: Header | None, now: dt.datetime, export_html: str = "",
                  *, compact: bool = False) -> str:
    """The ``<header>`` of a report, or ``""`` when it has nothing to show.

    *compact* writes it on one line (fragments); a full report indents it as its template does.
    """
    title = f'<span class="bf-report__title">{_html.escape(name)}</span>' if name != DEFAULT_NAME else ""
    if header is None and not title and not export_html:
        return ""
    parts: list[str] = []
    if header is not None and (logo := header.logo_bytes) is not None:
        data = base64.b64encode(logo).decode("ascii")
        parts.append(f'<img class="bf-report__logo" src="data:{header.logo_mime};base64,{data}" alt="">')
    if header is not None and (title or header.subtitle or header.author):
        heading = title
        if header.subtitle:
            heading += f'<span class="bf-report__subtitle">{inline_markdown(header.subtitle)}</span>'
        if header.author:
            heading += f'<span class="bf-report__author">By {_html.escape(header.author)}</span>'
        parts.append(f'<div class="bf-report__heading">{heading}</div>')
    elif title:
        parts.append(title)
    if header is not None and header.as_of is not None:
        parts.append(_as_of(header))
    parts.append(_time(now, header.tz if header else None, "bf-report__date") + export_html)
    if compact:
        return f'<header class="bf-report__header">{"".join(parts)}</header>'
    return '<header class="bf-report__header">\n      ' + "\n      ".join(parts) + "\n    </header>"


__all__ = ["DEFAULT_NAME", "render_header"]
