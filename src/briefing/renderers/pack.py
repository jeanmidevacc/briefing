"""Text a report stores compressed, for ``static/unpack.js`` to unpack as the report opens (#38).

Raw DEFLATE at the highest level, then base64: deterministic (no header, no timestamp),
and unpacked synchronously by ``window.briefingUnpack(base64, size)``.
"""
from __future__ import annotations

import base64
import zlib


def pack(text: str) -> tuple[str, int]:
    """``(base64 of the raw-deflated UTF-8 of text, its length in bytes)``."""
    data = text.encode()
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15, 9)
    packed = compressor.compress(data) + compressor.flush()
    return base64.b64encode(packed).decode("ascii"), len(data)


def unpack(packed: str, size: int) -> str:
    """The text :func:`pack` packed (what ``briefingUnpack`` does in the page)."""
    data = zlib.decompress(base64.b64decode(packed), -15)
    if len(data) != size:
        raise ValueError(f"unpacked {len(data)} bytes, not {size}")
    return data.decode()
