"""``bf.deck.save_pdf`` and ``bf.deck.save_image`` (#197): a deck's slides as a PDF or images.

Both open the deck in headless Chromium, offline, through the same session as the report
exports (``briefing.export``): ``pip install "briefing[image]"``, then once
``playwright install chromium``.
"""
from __future__ import annotations

import typing as t
from pathlib import Path

from briefing._error import BriefingError
from briefing.deck._render import HEIGHT, WIDTH

if t.TYPE_CHECKING:
    from briefing.deck._blocks import Deck
    from briefing.export._render import Session
    from briefing.renderers.formatting import Formatting

#: Which slides an export takes: ``"all"``, a slide's number (1 for the first) or its name.
SlideChoice: t.TypeAlias = "str | int"

_FORMATS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
_SLIDES_JS = """() => [...document.querySelectorAll('.bf-deck__stage > .bf-slide')].map(s => [
  Number(s.dataset.bfSlide), s.hasAttribute('data-bf-link') ? s.id : null])"""
_HIDE_CONTROLS = ".bf-deck__controls { display: none !important; }"


def _numbers(session: Session, slide: SlideChoice) -> list[int]:
    """The numbers of the slides *slide* picks."""
    found: list[tuple[int, str | None]] = [(int(n), name) for n, name in session.page.evaluate(_SLIDES_JS)]
    if slide == "all":
        return [n for n, _ in found]
    if isinstance(slide, int) and not isinstance(slide, bool):
        if 1 <= slide <= len(found):
            return [slide]
        raise BriefingError(f"slide={slide} is out of range: the deck has {len(found)} slides, numbered from 1.")
    named = [n for n, name in found if name == slide]
    if named:
        return named
    names = ", ".join(repr(name) for _, name in found if name) or "none"
    raise BriefingError(f"No slide named {slide!r}. Named slides: {names}. Pass a slide's number (1 for the "
                        "first), its name, or \"all\".")


def _deck_session(deck: Deck | str | Path, scale: float, name: str, formatting: Formatting | None) -> t.Any:
    from briefing.export._render import open_report

    return open_report(deck, width=WIDTH, height=HEIGHT, scale=scale, name=name, formatting=formatting, deck=True)


def _show(session: Session, number: int) -> None:
    """Show slide *number* through its address, as a reader's link would."""
    session.page.evaluate("n => { location.hash = '#' + n; }", number)
    session.page.wait_for_function(
        "n => document.querySelector('.bf-slide--current')?.dataset.bfSlide === String(n)", arg=number
    )
    session.wait_drawn()


def save_pdf(
    deck: Deck | str | Path,
    path: str | Path,
    *,
    slide: SlideChoice = "all",
    name: str = "Deck",
    formatting: Formatting | None = None,
) -> Path:
    """Save a deck as a PDF, one slide per page, each page the size of a 16:9 slide.

    The pages are what printing the deck from the browser gives: 1280 × 720 CSS pixels
    (13.33 × 7.5 inches), every slide as it shows, text selectable and charts vector.
    Needs ``pip install "briefing[image]"`` and, once, ``playwright install chromium``.

    Args:
        deck: A :class:`Deck`, or the path of a deck saved with :func:`save`.
        path: Destination ``.pdf`` file.
        slide: ``"all"``, or one slide by its number (1 for the first) or its ``name``.
        name: The deck's title, when ``deck`` is a :class:`Deck`.
        formatting: The theme, when ``deck`` is a :class:`Deck`.

    Returns:
        The path written.

    Raises:
        BriefingError: For an unknown slide or suffix, a report in place of a deck, or
            when Playwright or its Chromium isn't installed (the message says how).

    Example::

        bf.deck.save_pdf(deck, "q3-review.pdf")
        bf.deck.save_pdf("q3-review.html", "summary.pdf", slide="summary")
    """
    from briefing.export._render import outside_event_loop

    path = Path(path)
    if path.suffix.lower() != ".pdf":
        raise BriefingError(f"save_pdf writes .pdf files, not {path.suffix or 'no suffix'!r}.")

    def render() -> Path:
        with _deck_session(deck, 1, name, formatting) as session:
            numbers = _numbers(session, slide)
            if slide != "all":
                session.page.add_style_tag(content="@media print { .bf-deck__stage > .bf-slide"
                                           f':not([data-bf-slide="{numbers[0]}"]) {{ display: none !important; }} }}')
            session.page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
            session.wait_drawn()
            pdf = session.page.pdf(prefer_css_page_size=True, print_background=True)
        path.write_bytes(pdf)
        return path

    return outside_event_loop(render)


def save_image(
    deck: Deck | str | Path,
    path: str | Path,
    *,
    slide: SlideChoice = "all",
    scale: float = 2,
    name: str = "Deck",
    formatting: Formatting | None = None,
) -> list[Path]:
    """Save a deck's slides as images, each one slide at 1280 × 720 CSS pixels.

    Needs ``pip install "briefing[image]"`` and, once, ``playwright install chromium``.

    Args:
        deck: A :class:`Deck`, or the path of a deck saved with :func:`save`.
        path: Destination file; its suffix picks the format: ``.png``, ``.jpg`` or ``.webp``.
            With ``slide="all"`` each slide gets its number: ``q3.png`` → ``q3_01.png``,
            ``q3_02.png``, ….
        slide: ``"all"``, or one slide by its number (1 for the first) or its ``name``,
            written to ``path`` itself.
        scale: Device pixels per CSS pixel: 2 gives 2560 × 1440 images.
        name: The deck's title, when ``deck`` is a :class:`Deck`.
        formatting: The theme, when ``deck`` is a :class:`Deck`.

    Returns:
        The paths written, in slide order.

    Raises:
        BriefingError: For an unknown slide, size or suffix, a report in place of a deck,
            or when Playwright or its Chromium isn't installed (the message says how).

    Example::

        bf.deck.save_image(deck, "q3.png")                    # q3_01.png, q3_02.png, ...
        bf.deck.save_image(deck, "cover.webp", slide=1, scale=1)
    """
    from briefing.export._image import _encode
    from briefing.export._render import outside_event_loop

    path = Path(path)
    mime = _FORMATS.get(path.suffix.lower())
    if mime is None:
        raise BriefingError(f"save_image writes .png, .jpg or .webp files, not {path.suffix or 'no suffix'!r}.")
    if scale <= 0:
        raise BriefingError(f"scale must be positive, not {scale!r}.")

    def render() -> list[Path]:
        written: list[Path] = []
        with _deck_session(deck, scale, name, formatting) as session:
            session.page.add_style_tag(content=_HIDE_CONTROLS)
            numbers = _numbers(session, slide)
            total = session.page.locator(".bf-deck__stage > .bf-slide").count()
            for number in numbers:
                _show(session, number)
                png = session.page.screenshot(type="png")
                dest = path if slide != "all" else path.with_name(
                    f"{path.stem}_{number:0{max(2, len(str(total)))}d}{path.suffix}")
                dest.write_bytes(png if mime == "image/png" else _encode(session, png, mime))
                written.append(dest)
        return written

    return outside_event_loop(render)


__all__ = ["SlideChoice", "save_image", "save_pdf"]
