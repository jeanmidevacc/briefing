"""Banner: markdown text over a background image, with a fade or a uniform veil (#50)."""
from __future__ import annotations

import re
import typing as t
import warnings
from pathlib import Path

from briefing._error import BriefingError
from briefing.blocks.base import Block, BlockId

_LENGTH = re.compile(r"^\d+(?:\.\d+)?(?:px|rem|em|vh|%)$")


def _image_type(data: bytes) -> str | None:
    """The MIME type of an image from its first bytes (no imaging library)."""
    head = data[:512].lstrip()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:2048]):
        return "image/svg+xml"
    return None


def _percent(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 100:
        raise BriefingError(f"Banner: {name} must be a number from 0 to 100, not {value!r}.")
    return float(value)


class Banner(Block):
    """Markdown text over a background image: a report cover, a section opener or a social card.

    The image fills the banner; the text sits on a veil of the theme's background
    colour that fades in from the image side (``fade=True``) or covers the whole
    image evenly (``fade=False``). The image is embedded in the report once, as a
    data URI.

    Args:
        text: Markdown, rendered exactly like :class:`Text`.
        image: A file path, or the image bytes (PNG, JPEG, GIF, WebP or SVG).
        text_position: 0–100: where the text column begins (``side="right"``) or
            ends (``side="left"``), in percent of the banner's width.
        opacity: 0–100: how much the veil covers the image under the text: 100 is
            a plain text panel, around 80 leaves the image faintly visible. No
            readability warning is given at any value; that is your call.
        side: ``"right"`` (text on the right, image clear on the left) or ``"left"``.
            Ignored when ``fade=False``.
        fade: ``True`` fades the veil in over 20 % of the width before the text;
            ``False`` covers the whole image with one veil at ``opacity``.
        height: CSS height such as ``"16rem"`` (default) or a number of pixels.
        focus: ``(x, y)`` in percent: the point of the image kept in view when it is cropped.
        alt: A description of the image; by default it is decorative.
        name: Stable block id.
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.Banner("# Q1 2026\\n\\n**Sales briefing**", image="cover.jpg", text_position=55, opacity=80)
    """

    #: Images above this size warn: the report embeds them (until #38 adds a size budget).
    MAX_IMAGE_BYTES: t.ClassVar[int] = 2 * 1024 * 1024

    def __init__(
        self,
        text: str,
        image: str | Path | bytes,
        text_position: float = 50,
        opacity: float = 80,
        side: str = "right",
        fade: bool = True,
        height: str | int = "16rem",
        focus: tuple[float, float] = (50, 50),
        alt: str | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        if isinstance(image, bytes):
            data = image
        else:
            path = Path(image).expanduser()
            if not path.is_file():
                raise BriefingError(f"Banner: image file not found: {path}")
            data = path.read_bytes()
        mime = _image_type(data)
        if mime is None:
            raise BriefingError("Banner: the image must be a PNG, JPEG, GIF, WebP or SVG file (or its bytes).")
        if len(data) > self.MAX_IMAGE_BYTES:
            warnings.warn(
                f"Banner: the image is {len(data) / 1024 / 1024:.1f} MB and is embedded in the report; "
                "consider a smaller or more compressed image.",
                UserWarning,
                stacklevel=2,
            )
        if side not in ("left", "right"):
            raise BriefingError(f"Banner: side must be 'left' or 'right', not {side!r}.")
        css_height = f"{height}px" if isinstance(height, int) and not isinstance(height, bool) else height
        if not isinstance(css_height, str) or not _LENGTH.match(css_height):
            raise BriefingError(
                f"Banner: height must be a CSS length such as '16rem' or a number of pixels, not {height!r}."
            )
        if not isinstance(focus, tuple | list) or len(focus) != 2:
            raise BriefingError(f"Banner: focus must be an (x, y) pair of percentages, not {focus!r}.")
        self.text = text
        self.image, self.mime = data, mime
        self.text_position = _percent("text_position", text_position)
        self.opacity = _percent("opacity", opacity)
        self.side, self.fade, self.height = side, fade, css_height
        self.focus = (_percent("focus", focus[0]), _percent("focus", focus[1]))
        self.alt = alt


__all__: list[str] = ["Banner"]
