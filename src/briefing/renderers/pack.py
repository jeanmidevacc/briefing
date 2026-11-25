"""Text a report stores compressed, for ``static/unpack.js`` to unpack as the report opens (#38).

Raw DEFLATE at the highest level, then base64: deterministic (no header, no timestamp),
and unpacked synchronously by ``window.briefingUnpack(base64, size)``.
"""
from __future__ import annotations

import base64
import zlib
from importlib.resources import files

#: ``static/unpack.js``: defines ``window.briefingUnpack``, once per page.
UNPACK_JS = (files("briefing") / "static" / "unpack.js").read_text(encoding="utf-8")


def pack(text: str, level: int = 9) -> tuple[str, int]:
    """``(base64 of the raw-deflated UTF-8 of text, its length in bytes)``.

    *level* trades time for size: 9 is the smallest; 6 is about eight times faster on
    megabytes of data for 2 % more (a DataDive's columns, #16).
    """
    data = text.encode()
    compressor = zlib.compressobj(level, zlib.DEFLATED, -15, 9)
    packed = compressor.compress(data) + compressor.flush()
    return base64.b64encode(packed).decode("ascii"), len(data)


def unpack(packed: str, size: int) -> str:
    """The text :func:`pack` packed (what ``briefingUnpack`` does in the page)."""
    data = zlib.decompress(base64.b64decode(packed), -15)
    if len(data) != size:
        raise ValueError(f"unpacked {len(data)} bytes, not {size}")
    return data.decode()
