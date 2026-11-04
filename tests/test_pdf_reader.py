"""The test-only PDF reader reads streams by their /Length, even when data ends in a newline."""
from __future__ import annotations

import zlib

from tests.pdf_reader import _stream


def test_raw_stream_ending_in_a_newline_is_kept_whole() -> None:
    data = b"ab\nc\n"
    body = b"<< /Length 5 >>\nstream\n" + data + b"\nendstream"
    assert _stream(body) == data


def test_compressed_stream_is_read_by_length() -> None:
    payload = b"BT /F1 12 Tf <0041> Tj ET\n" * 50
    data = zlib.compress(payload) + b""
    body = b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream"
    assert _stream(body) == payload


def test_indirect_length() -> None:
    body = b"<< /Length 7 0 R >>\nstream\nhello\n\nendstream"
    assert _stream(body, {7: b" 6 "}) == b"hello\n"
