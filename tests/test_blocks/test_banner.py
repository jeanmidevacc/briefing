"""bf.Banner: markdown text over a background image (#50)."""
from __future__ import annotations

from pathlib import Path

import pytest

import briefing as bf
from tests.banner_images import JPEG_MAGIC, PNG_MAGIC, RED_SVG, WEBP_MAGIC
from tests.html_helpers import attr, find_one, parse


def _html(**kwargs: object) -> str:
    args: dict[str, object] = {"image": RED_SVG, **kwargs}
    return bf.stringify(bf.Briefing(bf.Banner("# Title\n\nSome **bold** text.", **args)))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"text_position": 101}, "text_position"),
        ({"text_position": -1}, "text_position"),
        ({"opacity": 120}, "opacity"),
        ({"side": "top"}, "side"),
        ({"focus": (50, 150)}, "focus"),
        ({"height": "tall"}, "height"),
        ({"image": b"not an image"}, "image"),
    ],
)
def test_bad_arguments(kwargs: dict[str, object], match: str) -> None:
    args: dict[str, object] = {"image": RED_SVG, **kwargs}
    with pytest.raises(bf.BriefingError, match=match):
        bf.Banner("x", **args)  # type: ignore[arg-type]


@pytest.mark.parametrize(("data", "mime"), [(RED_SVG, "image/svg+xml"), (PNG_MAGIC, "image/png"),
                                            (JPEG_MAGIC, "image/jpeg"), (WEBP_MAGIC, "image/webp")])
def test_image_is_embedded_once_as_a_data_uri(data: bytes, mime: str) -> None:
    import base64

    html = _html(image=data)
    assert html.count(base64.b64encode(data).decode()) == 1  # the image is embedded exactly once
    assert attr(find_one(parse(html), ".bf-banner img.bf-banner__image"), "src").startswith(f"data:{mime};base64,")


def test_image_from_a_file(tmp_path: Path) -> None:
    path = tmp_path / "cover.svg"
    path.write_bytes(RED_SVG)
    assert "data:image/svg+xml;base64," in _html(image=path) and "data:image/svg+xml;base64," in _html(image=str(path))
    with pytest.raises(bf.BriefingError, match="not found"):
        bf.Banner("x", image=tmp_path / "missing.png")


def test_large_images_warn() -> None:
    big = PNG_MAGIC + b"\x00" * (2 * 1024 * 1024)
    with pytest.warns(UserWarning, match=r"2\.0 MB"):
        bf.Banner("x", image=big)


@pytest.mark.parametrize("opacity", [0, 37, 100])
def test_any_opacity_renders_without_a_warning(opacity: int) -> None:
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _html(opacity=opacity)


def test_text_renders_like_a_text_block() -> None:
    soup = parse(_html())
    text = find_one(soup, ".bf-banner .bf-banner__text")
    assert "bf-text" in (text.get("class") or [])
    assert find_one(text, "h1").get_text() == "Title" and find_one(text, "strong").get_text() == "bold"


def test_decorative_by_default_and_alt_when_given() -> None:
    img = find_one(parse(_html()), "img.bf-banner__image")
    assert attr(img, "alt") == "" and attr(img, "aria-hidden") == "true"
    img = find_one(parse(_html(alt='Lake <at> "dawn"')), "img.bf-banner__image")
    assert attr(img, "alt") == 'Lake <at> "dawn"' and img.get("aria-hidden") is None


def test_layout_variables() -> None:
    banner = find_one(parse(_html(text_position=30, opacity=60, focus=(20, 80), height="20rem")), ".bf-banner")
    style = attr(banner, "style")
    assert "--bf-banner-pos: 30%" in style and "--bf-banner-h: 20rem" in style and "--bf-banner-focus: 20% 80%" in style
    assert "rgba(var(--bf-bg-rgb), 0.6)" in attr(find_one(banner, ".bf-banner__veil"), "style")


def test_height_in_pixels() -> None:
    assert "--bf-banner-h: 300px" in attr(find_one(parse(_html(height=300)), ".bf-banner"), "style")


@pytest.mark.parametrize(("preset", "rgb"), [(bf.Formatting(), "255, 255, 255"), (bf.Formatting.dark(), "15, 23, 42"),
                                             (bf.Formatting(bg_color="#abc"), "170, 187, 204")])
def test_theme_background_as_rgb(preset: bf.Formatting, rgb: str) -> None:
    assert f"--bf-bg-rgb:     {rgb};" in preset.to_css_vars()


def test_deterministic() -> None:
    assert _html() == _html()
