"""Lighter pictures (#186): scale an image down and re-encode it on the way in, with Pillow."""
from __future__ import annotations

import typing as t

from briefing._error import BriefingError

#: What ``format=`` re-encodes to, and the MIME type it gives (#186).
_ENCODINGS = {"webp": ("WEBP", "image/webp"), "jpeg": ("JPEG", "image/jpeg"), "png": ("PNG", "image/png")}


def lighten(data: bytes, mime: str, max_width: object, fmt: object, quality: object,
            where: str) -> tuple[bytes, str]:
    """*data* scaled down to *max_width* and/or re-encoded as *fmt* (#186); untouched when nothing is asked.

    Pillow is imported only here. Output carries no metadata, so the same input gives the same bytes.
    """
    if max_width is None and fmt is None:
        if quality != 80:
            raise BriefingError(f"{where}: quality is for a re-encoded image: pass format='webp' or 'jpeg'.")
        return data, mime
    if max_width is not None and (not isinstance(max_width, int) or isinstance(max_width, bool) or max_width < 1):
        raise BriefingError(f"{where}: max_width is a number of pixels such as 2400, not {max_width!r}.")
    if fmt is not None and fmt not in _ENCODINGS:
        raise BriefingError(f"{where}: format is 'webp', 'jpeg' or 'png', not {fmt!r}.")
    if not isinstance(quality, int) or isinstance(quality, bool) or not 1 <= quality <= 100:
        raise BriefingError(f"{where}: quality is a whole number from 1 to 100, not {quality!r}.")
    if mime == "image/svg+xml":
        if fmt is not None:
            raise BriefingError(f"{where}: an SVG is vector: it can't be re-encoded as {fmt}, and needs no max_width.")
        return data, mime  # max_width: a vector image is already as light at any size
    try:
        from PIL import Image as PILImage
    except ImportError as exc:
        raise BriefingError(f'{where}: max_width and format need Pillow: pip install "briefing[pillow]".') from exc
    import io

    opened = PILImage.open(io.BytesIO(data))
    if getattr(opened, "n_frames", 1) > 1:
        raise BriefingError(f"{where}: an animated image would lose its frames: drop max_width and format.")
    picture: PILImage.Image = opened
    resize = isinstance(max_width, int) and picture.width > max_width
    if not resize and fmt is None:
        return data, mime  # narrow enough, and no new format asked for
    if resize and isinstance(max_width, int):
        height = max(1, round(picture.height * max_width / picture.width))
        picture = picture.resize((max_width, height), PILImage.Resampling.LANCZOS)
    target = str(fmt) if fmt is not None else {"image/jpeg": "jpeg", "image/webp": "webp"}.get(mime, "png")
    encoder, out_mime = _ENCODINGS[target]
    if target == "jpeg" and picture.mode not in ("RGB", "L"):
        rgba = picture.convert("RGBA")
        flat = PILImage.new("RGB", rgba.size, "white")  # JPEG has no transparency
        flat.paste(rgba, mask=rgba.getchannel("A"))
        picture = flat
    elif picture.mode == "P":
        picture = picture.convert("RGBA")
    out = io.BytesIO()
    options: dict[str, t.Any] = {"quality": quality} if target in ("webp", "jpeg") else {"optimize": True}
    if target == "webp":
        options["method"] = 6
    picture.save(out, encoder, **options)
    return out.getvalue(), out_mime


__all__ = ["lighten"]
