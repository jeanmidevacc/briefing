"""Image and Banner: max_width, format and quality make pictures lighter (#186)."""
from __future__ import annotations

import builtins
import io
import typing as t

import pytest

import briefing as bf
from briefing.renderers.size import Part, over_budget
from tests.banner_images import RED_SVG

PIL = pytest.importorskip("PIL.Image")


def _png(width: int, height: int, mode: str = "RGB", color: t.Any = (200, 30, 60)) -> bytes:
    out = io.BytesIO()
    PIL.new(mode, (width, height), color).save(out, "PNG")
    return out.getvalue()


def _size(data: bytes) -> tuple[int, int]:
    return t.cast("tuple[int, int]", PIL.open(io.BytesIO(data)).size)


def test_a_wide_image_is_scaled_down_and_keeps_its_format() -> None:
    image = bf.Image(_png(3000, 1500), max_width=1200)
    assert image.mime == "image/png" and _size(image.image) == (1200, 600)


def test_a_narrow_image_is_left_as_it_is() -> None:
    data = _png(800, 400)
    assert bf.Image(data, max_width=1200).image == data


@pytest.mark.parametrize(("fmt", "mime"), [("webp", "image/webp"), ("jpeg", "image/jpeg"), ("png", "image/png")])
def test_re_encoding(fmt: str, mime: str) -> None:
    data = _png(400, 200)
    image = bf.Image(data, format=fmt)
    assert image.mime == mime and PIL.open(io.BytesIO(image.image)).format == fmt.upper()


def test_jpeg_puts_transparency_on_white() -> None:
    image = bf.Image(_png(10, 10, "RGBA", (0, 0, 0, 0)), format="jpeg")
    assert PIL.open(io.BytesIO(image.image)).convert("RGB").getpixel((5, 5)) == (255, 255, 255)


def test_quality_shapes_the_size_and_output_is_byte_stable() -> None:
    noisy = PIL.effect_noise((600, 400), 80).convert("RGB")
    out = io.BytesIO()
    noisy.save(out, "PNG")
    low, high = (bf.Image(out.getvalue(), format="webp", quality=q).image for q in (20, 95))
    assert len(low) < len(high)
    assert bf.Image(out.getvalue(), format="webp", quality=20).image == low


def test_a_banner_takes_the_same_options() -> None:
    banner = bf.Banner("# Cover", image=_png(4000, 1000), max_width=2400, format="webp")
    assert banner.mime == "image/webp" and _size(banner.image) == (2400, 600)


def test_svg_is_vector() -> None:
    assert bf.Image(RED_SVG, max_width=10).image == RED_SVG
    with pytest.raises(bf.BriefingError, match="an SVG is vector"):
        bf.Image(RED_SVG, format="webp")


def test_an_animated_gif_isnt_silently_flattened() -> None:
    frames = [PIL.new("RGB", (20, 20), c) for c in ("red", "blue")]
    out = io.BytesIO()
    frames[0].save(out, "GIF", save_all=True, append_images=frames[1:])
    assert bf.Image(out.getvalue()).mime == "image/gif"  # nothing asked: kept, frames and all
    with pytest.raises(bf.BriefingError, match="would lose its frames"):
        bf.Image(out.getvalue(), max_width=10)


@pytest.mark.parametrize(("kwargs", "match"), [
    ({"max_width": 0}, "max_width is a number of pixels"),
    ({"max_width": "2400px"}, "max_width is a number of pixels"),
    ({"format": "avif"}, "format is 'webp', 'jpeg' or 'png'"),
    ({"format": "webp", "quality": 0}, "quality is a whole number from 1 to 100"),
    ({"quality": 50}, "quality is for a re-encoded image"),
])
def test_bad_options(kwargs: dict[str, t.Any], match: str) -> None:
    with pytest.raises(bf.BriefingError, match=match):
        bf.Image(_png(10, 10), **kwargs)


def test_without_pillow_the_error_says_what_to_install(monkeypatch: pytest.MonkeyPatch) -> None:
    real = builtins.__import__

    def no_pil(name: str, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError(name)
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_pil)
    with pytest.raises(bf.BriefingError, match=r'pip install "briefing\[pillow\]"'):
        bf.Image(_png(10, 10), format="webp")
    bf.Image(_png(10, 10))  # without the options, Pillow is never needed


def test_the_json_form_holds_the_lighter_image_and_may_ask_for_one() -> None:
    report = bf.Briefing(bf.Image(_png(3000, 1500), max_width=1200, format="webp"))
    spec, data = bf.to_spec(report, inline=True)
    assert "max_width" not in spec["blocks"][0] and spec["blocks"][0]["image"].startswith("data:image/webp")
    assert bf.stringify(bf.from_spec(spec, data)) == bf.stringify(report)
    asked = {"briefing": 1, "blocks": [{"type": "Image", "image": {"ref": "pic"}, "max_width": 600}]}
    built = bf.from_spec(asked, {"pic": _png(3000, 1500)})
    assert _size(t.cast(bf.Image, built.blocks[0]).image) == (600, 300)


def test_the_size_warning_suggests_it_when_a_picture_is_heaviest() -> None:
    message = over_budget(12_000_000, [Part('Image at /blocks/0', 11_000_000), Part("Text at /blocks/1", 900)],
                          10_000_000)
    assert message is not None and 'max_width=2400 and format="webp"' in message
    other = over_budget(12_000_000, [Part("DataTable at /blocks/0", 11_000_000)], 10_000_000)
    assert other is not None and "max_width" not in other
