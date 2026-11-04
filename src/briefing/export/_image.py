"""``bf.save_image``: report pages as PNG, JPEG or WebP images."""
from __future__ import annotations

import base64
import typing as t
import warnings
from pathlib import Path

from briefing._error import BriefingError
from briefing.export._render import ReportPage, ReportSource, Session, open_report, outside_event_loop, slug

if t.TYPE_CHECKING:
    from briefing.renderers.formatting import Formatting

#: Social-card sizes in CSS pixels; the page is shrunk to fit, never cropped.
PRESETS: dict[str, tuple[int, int]] = {"og": (1200, 630), "square": (1080, 1080), "portrait": (1080, 1350)}
_FORMATS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def save_image(
    report: ReportSource,
    path: str | Path,
    *,
    page: str | int = "all",
    width: int = 1200,
    scale: float = 2,
    size: str | None = None,
    expand: bool = True,
    name: str = "Report",
    formatting: Formatting | None = None,
) -> list[Path]:
    """Save report pages as images, rendered in headless Chromium.

    Needs ``pip install "briefing[image]"`` and, once, ``playwright install chromium``.
    Rendering is offline: every network request is blocked.

    Args:
        report: A :class:`~briefing.Briefing`, a block or a list of blocks, or the
            path to a saved report ``.html``.
        path: Destination file. Its suffix picks the format: ``.png``, ``.jpg`` or ``.webp``.
        page: ``"all"`` writes one image per top-level ``Page``, named after it
            (``q1.png`` → ``q1_summary.png``, ``q1_detail.png``). A page title,
            a page's ``name`` or a 0-based index writes just that page to ``path``.
            A report without pages is one image either way.
        width: Layout width in CSS pixels.
        scale: Device pixels per CSS pixel; ``width=1200, scale=2`` gives 2400-pixel-wide images.
        size: ``None`` for the full page height, or a preset: ``"og"`` (1200×630),
            ``"square"`` (1080×1080), ``"portrait"`` (1080×1350). The page is laid
            out at ``width``, then shrunk to fit and centred on the theme
            background, never cropped; below half size a warning suggests ``size=None``.
        expand: Open every toggle before capturing, so hidden content is included.
        name: Report title, when ``report`` is a block (as in :func:`~briefing.save`).
        formatting: Theme, when ``report`` is a block (as in :func:`~briefing.save`).

    Returns:
        The paths written, in page order.

    Raises:
        BriefingError: For an unknown size, page or suffix, or when Playwright or
            its Chromium isn't installed (the message says how to install it).

    Example::

        bf.save_image(report, "q1.png", page="all")              # one PNG per page
        bf.save_image(report, "card.png", page=0, size="og")     # a 1200×630 social card
    """
    path = Path(path)
    mime = _FORMATS.get(path.suffix.lower())
    if mime is None:
        raise BriefingError(f"save_image writes .png, .jpg or .webp files, not {path.suffix or 'no suffix'!r}.")
    if size is not None and size not in PRESETS:
        raise BriefingError(f"Unknown size {size!r}: use None (full height) or one of {', '.join(PRESETS)}.")
    if width <= 0:
        raise BriefingError(f"width must be a positive number of CSS pixels, not {width!r}.")
    if scale <= 0:
        raise BriefingError(f"scale must be positive, not {scale!r}.")

    def render() -> list[Path]:
        written: list[Path] = []
        with open_report(report, width=width, scale=scale, name=name, formatting=formatting) as session:
            targets = session.resolve(page)
            for target in targets:
                session.show(target)
                if expand:
                    session.expand()
                png = session.page.screenshot(full_page=True, type="png")
                if size is not None:
                    png = _fit(session, png, size, scale)
                dest = _destination(path, target, per_page=page == "all" and len(session.pages) > 0)
                dest.write_bytes(png if mime == "image/png" else _encode(session, png, mime))
                written.append(dest)
        return written

    return outside_event_loop(render)


def _destination(path: Path, target: ReportPage | None, *, per_page: bool) -> Path:
    if not per_page or target is None:
        return path
    return path.with_name(f"{path.stem}_{slug(target.title, target.index)}{path.suffix}")


def _fit(session: Session, png: bytes, size: str, scale: float) -> bytes:
    """Shrink a full-page capture into the preset, centred on the report background."""
    box_w, box_h = PRESETS[size]
    page_w, page_h = session.page.evaluate(
        "() => [document.documentElement.scrollWidth, document.documentElement.scrollHeight]"
    )
    # Keep a margin inside the card, so content never touches its edges.
    margin = round(0.04 * min(box_w, box_h))
    factor = min(1.0, (box_w - 2 * margin) / page_w, (box_h - 2 * margin) / page_h)
    if factor < 0.5:
        warnings.warn(
            f"save_image: the page was shrunk to {factor:.0%} to fit {size!r} ({box_w}×{box_h}); "
            "text may be hard to read. Consider size=None for a full-height image.",
            UserWarning,
            stacklevel=3,
        )
    src = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    card = session.page.context.new_page()
    try:
        card.set_viewport_size({"width": box_w, "height": box_h})
        card.set_content(
            f'<html><body style="margin:0;width:{box_w}px;height:{box_h}px;display:flex;'
            f'align-items:center;justify-content:center;background:{session.background()}">'
            f'<img src="{src}" style="width:{page_w * factor}px;height:{page_h * factor}px"></body></html>'
        )
        card.wait_for_function("() => document.images[0].complete")
        return card.screenshot(type="png")
    finally:
        card.close()


def _encode(session: Session, png: bytes, mime: str) -> bytes:
    """Re-encode a PNG as JPEG or WebP with the browser's canvas (no imaging library)."""
    src = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    data_url: str = session.page.evaluate(
        """async ([src, mime]) => {
          const img = new Image(); img.src = src; await img.decode();
          const canvas = document.createElement('canvas');
          canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = getComputedStyle(document.body).backgroundColor;  // JPEG has no alpha
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0);
          return canvas.toDataURL(mime, 0.92);
        }""",
        [src, mime],
    )
    return base64.b64decode(data_url.split(",", 1)[1])
