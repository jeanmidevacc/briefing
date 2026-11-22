"""The report header's extras (#25): a subtitle, an author, a logo, a "data as of" date and a time zone."""
from __future__ import annotations

import dataclasses
import datetime as dt
import typing as t
from collections.abc import Mapping
from pathlib import Path

from briefing._error import BriefingError
from briefing.blocks.banner import _image_type
from briefing.blocks.base import _MAX_CAPTION_LEN, _truncate

_FORMATS = "PNG, JPEG, GIF, WebP or SVG"


@dataclasses.dataclass(frozen=True)
class Header:
    """What the report header shows besides the report's name and the time it was rendered.

    Pass it as ``Briefing(header=...)``; every field is optional.

    Args:
        subtitle: A line under the title, with inline Markdown as in captions.
        author: Who made the report, shown as "By <author>".
        logo: A PNG, JPEG, GIF, WebP or SVG image (a path, its bytes or a ``data:``
            URI), embedded in the report and drawn beside the title.
        as_of: The date (or date and time) the data runs to, shown as "Data as of …"
            beside the render time: a ``date``, a ``datetime`` or an ISO string.
        tz: An IANA time zone such as ``"America/Montreal"`` for the times shown
            (the render time, and an ``as_of`` with a time); UTC without it.

    Example::

        report = bf.Briefing(
            bf.Text("..."),
            header=bf.Header(subtitle="Weekly search interest", author="Analytics team",
                             logo="logo.svg", as_of="2026-11-20", tz="America/Montreal"),
        )
        bf.save(report, "report.html", name="Search report")
    """

    subtitle: str | None = None
    author: str | None = None
    logo: bytes | str | Path | None = None
    as_of: dt.date | dt.datetime | str | None = None
    tz: str | None = None

    def __post_init__(self) -> None:
        for option in ("subtitle", "author"):
            value = getattr(self, option)
            if value is not None and not isinstance(value, str):
                raise BriefingError(f"Header: {option} is text, not {value!r}.")
            object.__setattr__(self, option, _truncate(value.strip(), _MAX_CAPTION_LEN) if value else None)
        object.__setattr__(self, "logo", _logo(self.logo))
        object.__setattr__(self, "as_of", _as_of(self.as_of))
        if self.tz is not None:
            _zone(self.tz)

    @property
    def logo_bytes(self) -> bytes | None:
        """The logo's bytes (``logo`` is read and checked when the Header is made)."""
        return self.logo if isinstance(self.logo, bytes) else None

    @property
    def logo_mime(self) -> str | None:
        """The logo's MIME type, from its bytes."""
        return _image_type(self.logo) if isinstance(self.logo, bytes) else None

    @classmethod
    def of(cls, value: Header | Mapping[str, t.Any] | None) -> Header | None:
        """*value* as a Header: a Header, a dict of its fields (the JSON form) or ``None``."""
        if value is None or isinstance(value, Header):
            return value
        if isinstance(value, Mapping):
            fields = [f.name for f in dataclasses.fields(cls)]
            unknown = [k for k in value if k not in fields]
            if unknown:
                raise BriefingError(f"Briefing header=: Header has no field {unknown[0]!r}; "
                                    f"it takes {', '.join(fields)}.")
            return cls(**value)
        raise BriefingError(f"Briefing header= takes a bf.Header(...) or a dict of its fields, not {value!r}.")

    def to_dict(self) -> dict[str, t.Any]:
        """The fields that are set, as JSON: the logo as a ``data:`` URI, ``as_of`` in ISO form."""
        from briefing.spec._data import encode_image

        out: dict[str, t.Any] = {}
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if value is None:
                continue
            if field.name == "logo":
                value = encode_image(value)
            elif field.name == "as_of":
                value = value.isoformat()
            out[field.name] = value
        return out


def _logo(logo: object) -> bytes | None:
    if logo is None:
        return None
    if isinstance(logo, bytes):
        data = logo
    elif isinstance(logo, str) and logo.startswith("data:"):
        from briefing.spec._data import decode_image

        data = decode_image(logo)
    elif isinstance(logo, str | Path):
        path = Path(logo).expanduser()
        if not path.is_file():
            raise BriefingError(f"Header: logo file not found: {path}")
        data = path.read_bytes()
    else:
        raise BriefingError(f"Header: logo is a {_FORMATS} file's path, its bytes or a data: URI, not {logo!r}.")
    if _image_type(data) is None:
        raise BriefingError(f"Header: the logo must be a {_FORMATS} image.")
    return data


def _as_of(value: object) -> dt.date | None:
    if isinstance(value, dt.datetime) and type(value) is not dt.datetime:  # pd.Timestamp and the like
        return dt.datetime.fromisoformat(value.isoformat())
    if value is None or isinstance(value, dt.date):  # a datetime is a date too
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value) if len(value.strip()) == 10 else dt.datetime.fromisoformat(value)
        except ValueError:
            pass
    raise BriefingError(f"Header: as_of is a date, a datetime or an ISO string such as '2026-11-20', not {value!r}.")


def _zone(tz: str) -> dt.tzinfo:
    import zoneinfo

    try:
        return zoneinfo.ZoneInfo(tz)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise BriefingError(f"Header: unknown time zone {tz!r}; use an IANA name such as 'Europe/Paris'.") from exc


def local_time(when: dt.datetime, tz: str | None) -> dt.datetime:
    """*when* in *tz* (UTC without it); a naive *when* is taken as already in that zone."""
    zone = _zone(tz) if tz else dt.UTC
    return when.replace(tzinfo=zone) if when.tzinfo is None else when.astimezone(zone)


__all__ = ["Header", "local_time"]
