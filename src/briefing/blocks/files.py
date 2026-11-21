"""Image and Attachment: a picture in the report, a file to download from it (#36).

Both embed what they hold in the report itself, so it stays one offline file; the
report's size budget (#38) names them when they make it heavy.
"""
from __future__ import annotations

import mimetypes
import re
import typing as t
from pathlib import Path

from briefing._error import BriefingError
from briefing._frames import looks_like_dataframe, to_pandas
from briefing.blocks.banner import _image_type
from briefing.blocks.base import _MAX_CAPTION_LEN, Block, BlockId, _truncate

if t.TYPE_CHECKING:
    import pandas as pd

_WIDTH = re.compile(r"^\d+(?:\.\d+)?(?:px|rem|em|vw|%)$")
_FORMATS = "PNG, JPEG, GIF, WebP or SVG"


def _read(source: str | Path, what: str) -> bytes:
    path = Path(source).expanduser()
    if not path.is_file():
        raise BriefingError(f"{what}: file not found: {path}")
    return path.read_bytes()


class Image(Block):
    """A picture: a PNG, JPEG, GIF, WebP or SVG file, embedded in the report.

    The image goes into the report once, as a data URI, so the report stays one
    offline file. It shows at its natural size, shrunk to fit its column, unless
    ``width`` says otherwise. An SVG is shown as an image, so any script in it never runs.

    Args:
        image: A file path, or the image's bytes (PNG, JPEG, GIF, WebP or SVG).
        caption: Optional caption below the image.
        alt: What the image shows, for readers who can't see it; by default the
            caption. With neither, the image is decorative.
        width: A CSS width such as ``"60%"`` or ``"20rem"``, or a number of pixels.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.Image("pipeline.png", caption="How the data flows", width="60%")
    """

    embed_noun: t.ClassVar[str | None] = "image"

    def __init__(
        self,
        image: str | Path | bytes,
        caption: str | None = None,
        alt: str | None = None,
        width: str | int | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        data = image if isinstance(image, bytes) else _read(image, "Image")
        mime = _image_type(data)
        if mime is None:
            raise BriefingError(f"Image: the image must be a {_FORMATS} file (or its bytes).")
        css = f"{width}px" if isinstance(width, int) and not isinstance(width, bool) and width > 0 else width
        if css is not None and (not isinstance(css, str) or not _WIDTH.match(css)):
            raise BriefingError(
                f"Image: width must be a CSS width such as '60%' or '20rem', or a number of pixels, not {width!r}."
            )
        self.image, self.mime = data, mime
        self.caption = _truncate(caption, _MAX_CAPTION_LEN) if caption else caption
        self.alt = alt
        self.width = css


class Attachment(Block):
    """A file readers download from the report: any file, some bytes, or a dataframe as CSV.

    The file is embedded in the report (text files compressed) and downloaded from
    the page, with no server. It shows as a link with its label and size, such as
    "Model card · PDF, 1.2 MB"; in print and exports, as one line naming the file.

    Args:
        file: A file path (any type), bytes (then ``filename`` is needed), or a
            dataframe, which downloads as CSV in the format of ``DataTable``'s
            CSV button: raw values, UTF-8 with a byte-order mark.
        filename: The name the file downloads as; by default the file's own name,
            or for a dataframe the block's ``name`` (else ``data``) with ``.csv``.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: The link's text (by default the file name), and its tab title inside a ``Select``.

    Example::

        bf.Attachment("model_card.pdf", label="Model card")
        bf.Attachment(orders, filename="orders.csv")
    """

    embed_noun: t.ClassVar[str | None] = "file"

    def __init__(
        self,
        file: str | Path | bytes | pd.DataFrame | t.Any,
        filename: str | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        if filename is not None and (not isinstance(filename, str) or not filename.strip() or "/" in filename
                                     or "\\" in filename):
            raise BriefingError(f"Attachment: filename must be a file name such as 'orders.csv', not {filename!r}.")
        self.file: bytes | pd.DataFrame
        if isinstance(file, bytes):
            if filename is None:
                raise BriefingError("Attachment: bytes need a filename, such as filename='notes.txt'.")
            self.file = file
        elif isinstance(file, str | Path):
            self.file = _read(file, "Attachment")
            filename = filename or Path(file).name
        elif looks_like_dataframe(file):
            self.file = to_pandas(file, block="Attachment")
            filename = filename or f"{name or 'data'}.csv"
            if not filename.lower().endswith(".csv"):
                raise BriefingError(f"Attachment: a dataframe downloads as CSV; name it '….csv', not {filename!r}.")
        else:
            raise BriefingError(
                f"Attachment: file must be a file path, bytes or a dataframe, not {type(file).__name__}."
            )
        self.filename: str = filename
        self.mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"


__all__: list[str] = ["Attachment", "Image"]
