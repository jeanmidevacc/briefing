"""A Banner as a reader sees it: text position and veil opacity (#50)."""
from __future__ import annotations

import io
import re

import pytest
from playwright.sync_api import Page

import briefing as bf
from tests.banner_images import RED_SVG
from tests.pdf_reader import read_pdf
from tests.test_browser.conftest import Viewer

PIL = pytest.importorskip("PIL.Image")

_THEMES = {"default": (bf.Formatting(), (255, 255, 255)), "dark": (bf.Formatting.dark(), (15, 23, 42))}


def _open(viewer: Viewer, theme: str = "default", **kwargs: object) -> Page:
    args: dict[str, object] = {"image": RED_SVG, **kwargs}
    banner = bf.Banner("## Q1 cover\n\nA line of text.", **args)  # type: ignore[arg-type]
    return viewer.open(bf.Briefing(banner), formatting=_THEMES[theme][0])


def _alpha_along(page: Page, fractions: list[float]) -> list[float]:
    """Veil opacity at points across the banner's bottom edge, from the pixel colour over pure red."""
    box = page.locator(".bf-banner").bounding_box()
    assert box is not None
    image = PIL.open(io.BytesIO(page.locator(".bf-banner").screenshot())).convert("RGB")
    y = image.height - 4  # below the text
    alphas = []
    for f in fractions:
        g = image.getpixel((min(image.width - 1, round(f * image.width)), y))[1]
        bg_g = page.evaluate("() => getComputedStyle(document.body).backgroundColor.match(/\\d+/g).map(Number)[1]")
        alphas.append(round(g / bg_g, 2) if bg_g else 0.0)  # red has g = 0, so g scales with the veil
    return alphas


def _text_edges(page: Page) -> tuple[float, float]:
    banner, text = page.locator(".bf-banner").bounding_box(), page.locator(".bf-banner__text").bounding_box()
    assert banner is not None and text is not None
    return (text["x"] - banner["x"]) / banner["width"], (text["x"] + text["width"] - banner["x"]) / banner["width"]


@pytest.mark.parametrize("theme", ["default", "dark"])
def test_fade_right(viewer: Viewer, theme: str) -> None:
    page = _open(viewer, theme, text_position=60, opacity=80, side="right")
    start, end = _text_edges(page)
    assert start == pytest.approx(0.60, abs=0.01) and end == pytest.approx(1.0, abs=0.01)
    if theme == "default":
        clear, mid, under = _alpha_along(page, [0.2, 0.5, 0.8])
        assert clear == pytest.approx(0, abs=0.03) and under == pytest.approx(0.8, abs=0.03) and 0.05 < mid < 0.75


@pytest.mark.parametrize("theme", ["default", "dark"])
def test_fade_left(viewer: Viewer, theme: str) -> None:
    page = _open(viewer, theme, text_position=40, opacity=100, side="left")
    start, end = _text_edges(page)
    assert start == pytest.approx(0.0, abs=0.01) and end == pytest.approx(0.40, abs=0.01)
    if theme == "default":
        under, clear = _alpha_along(page, [0.2, 0.8])
        assert under == pytest.approx(1.0, abs=0.03) and clear == pytest.approx(0, abs=0.03)


def test_the_fade_eases_in_with_no_visible_edge(viewer: Viewer) -> None:
    page = _open(viewer, text_position=60, opacity=100, side="right")
    alphas = _alpha_along(page, [0.40 + i * 0.01 for i in range(21)])  # the 20 % fade before the text
    assert alphas == sorted(alphas)  # monotonic
    steps = [b - a for a, b in zip(alphas, alphas[1:], strict=False)]
    assert max(steps) < 0.12 and steps[0] < 0.03 and steps[-1] < 0.03  # eases in and out


def test_dark_theme_fades_into_its_own_background(viewer: Viewer) -> None:
    page = _open(viewer, "dark", text_position=50, opacity=100, side="right")
    image = PIL.open(io.BytesIO(page.locator(".bf-banner").screenshot())).convert("RGB")
    # inside the text column, clear of the rounded corner
    assert image.getpixel((image.width - 24, image.height - 6)) == pytest.approx((15, 23, 42), abs=2)


def test_phone_width_stacks_the_image_above_the_text(viewer: Viewer) -> None:
    page = _open(viewer, text_position=60)
    page.set_viewport_size({"width": 390, "height": 800})
    image, text = page.locator(".bf-banner__image").bounding_box(), page.locator(".bf-banner__text").bounding_box()
    assert image is not None and text is not None
    assert text["y"] >= image["y"] + image["height"] - 40 and text["width"] > 300


def test_printed_banner_keeps_its_image_and_colours(viewer: Viewer) -> None:
    page = _open(viewer)
    raw = page.pdf(format="A4", print_background=True)
    assert "Q1 cover" in read_pdf(raw).pages[0]
    # The SVG image prints as vector shapes in the banner's red, so look for the fill colour.
    assert re.search(rb"1 0 0 (?:rg|sc)", b"".join(_streams(raw)))


def _streams(raw: bytes) -> list[bytes]:
    import zlib

    out = []
    for m in re.finditer(rb"/Length (\d+)[^>]*>>\s*stream\r?\n", raw):
        data = raw[m.end():m.end() + int(m.group(1))]
        try:
            out.append(zlib.decompress(data))
        except zlib.error:
            out.append(data)
    return out



def test_a_page_that_starts_with_a_banner_is_a_social_card(tmp_path: object) -> None:
    from pathlib import Path

    from tests.image_helpers import png_size

    report = bf.Briefing(bf.Page(bf.Banner("# Q1 2026\n\n**Sales briefing**", image=RED_SVG, text_position=50),
                                 bf.Text("Details follow."), title="Cover"))
    (card,) = bf.save_image(report, Path(str(tmp_path)) / "card.png", page="Cover", size="og", scale=1)
    assert png_size(card) == (1200, 630)


@pytest.mark.parametrize("theme", ["default", "dark"])
@pytest.mark.parametrize("side", ["right", "left"])
def test_uniform_veil_has_one_opacity_everywhere(viewer: Viewer, theme: str, side: str) -> None:
    page = _open(viewer, theme, text_position=35, opacity=60, side=side, fade=False)
    start, end = _text_edges(page)
    assert start == pytest.approx(0.35, abs=0.01) and end == pytest.approx(1.0, abs=0.01)  # side is ignored
    image = PIL.open(io.BytesIO(page.locator(".bf-banner").screenshot())).convert("RGB")
    bg = _THEMES[theme][1]
    y = image.height - 4
    samples = [image.getpixel((round(f * image.width), y)) for f in (0.05, 0.25, 0.5, 0.75, 0.95)]
    expected = tuple(round(255 * 0.4 + c * 0.6) if i == 0 else round(c * 0.6) for i, c in enumerate(bg))
    for pixel in samples:  # red under a 60 % veil of the theme background, the same at every x
        assert pixel == pytest.approx(expected, abs=3)
