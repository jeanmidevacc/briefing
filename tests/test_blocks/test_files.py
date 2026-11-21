"""Image and Attachment take what they embed, and refuse what they can't (#36)."""
from __future__ import annotations

import typing as t
from pathlib import Path

import pandas as pd
import pytest

import briefing as bf
from tests.banner_images import JPEG_MAGIC, PNG_MAGIC, RED_SVG


def test_an_image_from_a_file_or_bytes(tmp_path: Path) -> None:
    path = tmp_path / "red.svg"
    path.write_bytes(RED_SVG)
    assert bf.Image(path).image == bf.Image(RED_SVG).image == RED_SVG
    assert [bf.Image(data).mime for data in (PNG_MAGIC, JPEG_MAGIC, RED_SVG)] == ["image/png", "image/jpeg",
                                                                                 "image/svg+xml"]


@pytest.mark.parametrize(("width", "css"), [(None, None), (300, "300px"), ("60%", "60%"), ("20rem", "20rem")])
def test_an_images_width(width: t.Any, css: str | None) -> None:
    assert bf.Image(RED_SVG, width=width).width == css


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"image": b"not an image"}, "must be a PNG, JPEG, GIF, WebP or SVG"),
        ({"image": "missing.png"}, "file not found"),
        ({"image": RED_SVG, "width": "wide"}, "width must be a CSS width"),
        ({"image": RED_SVG, "width": 0}, "width must be a CSS width"),
        ({"image": RED_SVG, "width": True}, "width must be a CSS width"),
    ],
)
def test_an_image_refuses_what_it_cant_show(kwargs: dict[str, t.Any], message: str) -> None:
    with pytest.raises(bf.BriefingError, match=message):
        bf.Image(**kwargs)


def test_an_attachment_from_a_file_bytes_or_a_dataframe(tmp_path: Path) -> None:
    path = tmp_path / "model_card.pdf"
    path.write_bytes(b"%PDF-1.7 ...")
    from_file = bf.Attachment(path)
    assert (from_file.file, from_file.filename) == (b"%PDF-1.7 ...", "model_card.pdf")
    assert from_file.mime == "application/pdf"
    assert bf.Attachment(path, filename="card.pdf").filename == "card.pdf"
    assert bf.Attachment(b"x", filename="notes.txt").mime == "text/plain"
    frame = bf.Attachment(pd.DataFrame({"n": [1]}))
    assert frame.filename == "data.csv" and frame.mime == "text/csv" and isinstance(frame.file, pd.DataFrame)
    assert bf.Attachment(pd.DataFrame({"n": [1]}), name="orders").filename == "orders.csv"
    assert bf.Attachment(b"x", filename="weird.zzz").mime == "application/octet-stream"


@pytest.mark.parametrize(
    ("file", "kwargs", "message"),
    [
        (b"x", {}, "bytes need a filename"),
        ("missing.pdf", {}, "file not found"),
        (pd.DataFrame({"n": [1]}), {"filename": "orders.xlsx"}, "a dataframe downloads as CSV"),
        (b"x", {"filename": "../up.txt"}, "filename must be a file name"),
        (b"x", {"filename": " "}, "filename must be a file name"),
        (3, {}, "file must be a file path, bytes or a dataframe, not int"),
    ],
)
def test_an_attachment_says_what_to_pass(file: t.Any, kwargs: dict[str, t.Any], message: str) -> None:
    with pytest.raises(bf.BriefingError, match=message):
        bf.Attachment(file, **kwargs)
