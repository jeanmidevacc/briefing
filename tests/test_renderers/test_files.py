"""How Image and Attachment render (#36); downloading is in tests/test_browser/test_files.py."""
from __future__ import annotations

import base64
import json

import pandas as pd

import briefing as bf
from briefing.renderers.pack import unpack
from briefing.renderers.table import csv_text
from tests.banner_images import PNG_MAGIC, RED_SVG
from tests.golden import static_files
from tests.html_helpers import attr, find_one, parse


def _stored(html: str) -> bytes:
    data = find_one(parse(html), "script.bf-attachment__data")
    encoded = json.loads(data.get_text())
    if data.has_attr("data-packed"):
        return unpack(encoded, int(attr(data, "data-size"))).encode()
    return base64.b64decode(encoded)


def test_an_image_is_a_data_uri_with_its_description_and_width() -> None:
    soup = parse(bf.stringify(bf.Image(RED_SVG, caption="A red field", width=300)))
    img = find_one(soup, "figure.bf-image img")
    assert attr(img, "src") == "data:image/svg+xml;base64," + base64.b64encode(RED_SVG).decode()
    assert attr(img, "alt") == "A red field" and attr(img, "style") == "width: 300px"  # alt from the caption
    assert find_one(soup, "figcaption").get_text() == "A red field"
    assert attr(find_one(parse(bf.stringify(bf.Image(RED_SVG, alt="Red"))), "img"), "alt") == "Red"
    assert attr(find_one(parse(bf.stringify(bf.Image(RED_SVG))), "img"), "alt") == ""  # decorative


def test_an_attachment_shows_its_label_type_and_size() -> None:
    soup = parse(bf.stringify(bf.Attachment(PNG_MAGIC, filename="logo.png", label="Logo")))
    button = find_one(soup, "button.bf-attachment__button")
    assert attr(button, "data-bf-filename") == "logo.png" and attr(button, "data-bf-type") == "image/png"
    assert find_one(button, ".bf-attachment__label").get_text() == "Logo"
    assert find_one(button, ".bf-attachment__meta").get_text() == f"PNG, {len(PNG_MAGIC)} B"
    named = parse(bf.stringify(bf.Attachment(b"x", filename="notes.txt")))
    assert find_one(named, ".bf-attachment__label").get_text() == "notes.txt"


def test_binary_files_are_stored_as_they_are_and_text_packed() -> None:
    binary = bf.stringify(bf.Attachment(bytes(range(256)), filename="blob.bin"))
    assert _stored(binary) == bytes(range(256))
    assert not find_one(parse(binary), "script.bf-attachment__data").has_attr("data-packed")
    assert static_files()["static/unpack.js"] not in binary
    text = bf.stringify(bf.Attachment(b'{"a": 1}' * 1000, filename="data.json"))
    assert _stored(text) == b'{"a": 1}' * 1000
    assert find_one(parse(text), "script.bf-attachment__data").has_attr("data-packed")
    assert static_files()["static/unpack.js"] in text
    stored = find_one(parse(text), "script.bf-attachment__data").get_text()
    assert len(stored) < 300  # 8 KB of repetitive JSON packs into a few hundred bytes


def test_a_dataframe_downloads_as_the_csv_of_datatables_button() -> None:
    frame = pd.DataFrame({"name": ["Zoë", "=SUM(A1)", "a,b"], "n": [3, -5, None],
                          "day": pd.to_datetime(pd.Series(["2024-01-05", None, "2024-02-01"]))})
    stored = _stored(bf.stringify(bf.Attachment(frame, filename="orders.csv")))
    assert stored.decode() == csv_text(frame) == (
        "﻿name,n,day\r\nZoë,3,2024-01-05T00:00:00\r\n'=SUM(A1),-5,\r\n\"a,b\",,2024-02-01T00:00:00\r\n"
    )


def test_the_size_budget_names_a_heavy_image_or_attachment() -> None:
    import pytest

    with pytest.warns(UserWarning, match=r"Attachment at /blocks/1 \(.*\), Image at /blocks/0"):
        bf.stringify(bf.Briefing(bf.Image(PNG_MAGIC + b"\x00" * 600_000), bf.Attachment(bytes(900_000),
                                 filename="big.bin")), max_size="1 MB")
