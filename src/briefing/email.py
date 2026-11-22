"""Email digests (#42): a short summary built for mail apps, linking to the full report.

Mail apps run no script, many drop SVG and data-URI images, and Outlook on Windows lays
HTML out with Word. So a digest is not the report: it takes a few blocks (``Text``,
``BigNumber``, ``Alert``, ``Group``, ``Plot`` and a short ``Table``) and writes them as
table-based HTML with every style inline, charts as attached PNG images, and a plain-text
alternative. Sending stays yours: :func:`to_message` returns a standard
``email.message.EmailMessage``.

Example::

    digest = bf.email.Digest(
        bf.Text("**Daily collection, Oct 24**: 2 sources below target."),
        bf.Group(bf.BigNumber("Calls", 1284, prev_value=1247), bf.BigNumber("Failed", "2.1%"), columns=2),
        bf.Plot(fig, caption="Calls per day"),
        link="https://example.com/report.html",
    )
    message = bf.email.to_message(digest, subject="Daily collection digest")
"""
from __future__ import annotations

import dataclasses
import hashlib
import html as _html
import io
import re
import typing as t
from collections.abc import Sequence
from email.message import EmailMessage
from pathlib import Path

from briefing._error import BriefingError
from briefing._version import __version__
from briefing.blocks.asset import Plot, Table
from briefing.blocks.base import Block, wrap_block
from briefing.blocks.layout import Group
from briefing.blocks.text import Alert, BigNumber, Text
from briefing.renderers.formatting import Formatting

#: The blocks a digest takes.
ALLOWED = (Text, BigNumber, Alert, Group, Plot, Table)
#: The most rows a Table shows in an email.
MAX_TABLE_ROWS = 30
#: The width of the digest, in pixels: what mail apps show without scrolling.
WIDTH = 640

_ALERT_HUES = {"info": "#3b82f6", "success": "#22c55e", "warning": "#f59e0b", "error": "#ef4444"}


class Digest:
    """A short email made of a few blocks, that links to the full report.

    Args:
        *blocks: ``Text``, ``BigNumber``, ``Alert``, ``Group``, ``Plot`` or ``Table`` (up
            to 30 rows); strings become ``Text``. Anything interactive belongs in the
            full report.
        link: The full report's address. Adds an "Open the full report" button, and
            ``#anchor`` links in Text lead into that report.
        footer: A line before "Made with briefing", such as a team name.

    Example::

        bf.email.Digest(bf.Text("**2 sources** below target."), link="https://example.com/report.html")
    """

    def __init__(self, *blocks: t.Any, link: str | None = None, footer: str | None = None) -> None:
        if not blocks:
            raise BriefingError("Digest: give it at least one block.")
        self.blocks = [wrap_block(b) for b in blocks]
        for block in self.blocks:
            _check(block)
        if link is not None and (not isinstance(link, str) or not re.match(r"^https?://\S+$", link)):
            raise BriefingError(f"Digest: link is the full report's address, such as 'https://…/report.html', "
                                f"not {link!r}.")
        self.link = link
        self.footer = footer


def _check(block: Block) -> None:
    if not isinstance(block, ALLOWED):
        names = ", ".join(cls.__name__ for cls in ALLOWED)
        raise BriefingError(f"Digest: an email can't show a {type(block).__name__}: mail apps run no script. "
                            f"A digest takes {names}; link to the full report for the rest.")
    if isinstance(block, Group):
        for child in block.blocks:
            _check(child)
    if isinstance(block, Table):
        frame = _frame(block)
        if len(frame) > MAX_TABLE_ROWS:
            raise BriefingError(f"Digest: a Table in an email shows at most {MAX_TABLE_ROWS} rows; this one has "
                                f"{len(frame)}. Pass the top rows, and link to the full report for the rest.")


def _frame(block: Table) -> t.Any:
    data = block.data
    return getattr(data, "data", data)  # a Styler keeps its frame in .data


# ── images ────────────────────────────────────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class Picture:
    """A PNG the HTML shows with ``cid:``: attach it with this Content-ID."""

    cid: str
    png: bytes


def _png(figure: t.Any) -> bytes:
    """A chart as a PNG, drawn by its own library."""
    from briefing.renderers.plot import detect_library

    library = detect_library(figure)
    if library == "matplotlib":
        actual = figure.get_figure() if hasattr(figure, "get_figure") and not hasattr(figure, "savefig") else figure
        out = io.BytesIO()
        actual.savefig(out, format="png", dpi=200, bbox_inches="tight", metadata={"Software": None})
        return out.getvalue()
    if library == "plotly":
        try:
            return t.cast(bytes, figure.to_image(format="png", width=1200, height=700, scale=1))
        except (ValueError, ImportError) as exc:
            raise BriefingError("Digest: a Plotly chart in an email is drawn as a PNG by kaleido: "
                                "pip install kaleido.") from exc
    if library == "altair":
        import vl_convert as vlc

        png: bytes = vlc.vegalite_to_png(figure.to_dict(), scale=2)
        return png
    raise BriefingError(f"Digest: a {library} chart needs a browser to draw: use Matplotlib, Plotly or Altair "
                        "in an email.")


# ── the HTML ──────────────────────────────────────────────────────────────────


class _Writer:
    def __init__(self, digest: Digest, fmt: Formatting) -> None:
        from briefing import color

        self.digest, self.fmt = digest, fmt
        self.pictures: list[Picture] = []
        self.mix = color.mix
        bg = color.check_hex(fmt.bg_color, "bg_color") if fmt.bg_color.startswith("#") else "#ffffff"
        self.bg = bg
        self.font = fmt.font.replace('"', "'")

    def style(self, **rules: str) -> str:
        return "; ".join(f"{k.replace('_', '-')}: {v}" for k, v in rules.items())

    # one function per block

    def block(self, block: Block, width: int) -> str:
        if isinstance(block, Text):
            return self.text(block)
        if isinstance(block, BigNumber):
            return self.bignumber(block)
        if isinstance(block, Alert):
            return self.alert(block)
        if isinstance(block, Group):
            return self.group(block, width)
        if isinstance(block, Plot):
            return self.plot(block, width)
        return self.table(t.cast(Table, block))

    def text(self, block: Text) -> str:
        from markdown_it import MarkdownIt

        source = re.sub(r"\s*\{#[a-zA-Z][\w-]*\}[ \t]*$", "", block.content, flags=re.M)  # heading names
        html = MarkdownIt("commonmark", {"html": False}).enable("table").render(source)
        html = re.sub(r'href="#([^"]*)"', self._anchor, html)
        text, muted, border, accent = self.fmt.text_color, self.fmt.muted_color, self.fmt.border_color, \
            self.fmt.accent_color
        styles = {
            "p": f"margin: 0 0 12px; color: {text}; font-size: 15px; line-height: 1.5",
            "h1": f"margin: 0 0 12px; color: {text}; font-size: 24px; line-height: 1.25",
            "h2": f"margin: 0 0 10px; color: {text}; font-size: 20px; line-height: 1.3",
            "h3": f"margin: 0 0 8px; color: {text}; font-size: 17px",
            "h4": f"margin: 0 0 8px; color: {text}; font-size: 15px",
            "ul": "margin: 0 0 12px; padding-left: 22px", "ol": "margin: 0 0 12px; padding-left: 22px",
            "li": f"color: {text}; font-size: 15px; line-height: 1.5",
            "a": f"color: {accent}", "code": f"font-family: Consolas, monospace; font-size: 13px; color: {text}",
            "pre": f"margin: 0 0 12px; padding: 10px; background: {self.fmt.surface_color}; white-space: pre-wrap",
            "blockquote": f"margin: 0 0 12px; padding-left: 12px; border-left: 3px solid {border}; color: {muted}",
            "table": "border-collapse: collapse; margin: 0 0 12px",
            "th": f"padding: 4px 8px; border-bottom: 1px solid {border}; text-align: left; color: {text}",
            "td": f"padding: 4px 8px; border-bottom: 1px solid {border}; color: {text}",
            "hr": f"border: none; border-top: 1px solid {border}; margin: 16px 0",
        }
        for tag, css in styles.items():
            html = re.sub(rf"<{tag}(?=[\s>])", f'<{tag} style="{css}"', html)
        return f"<tr><td style=\"padding: 0 0 8px\">{html}</td></tr>"

    def _anchor(self, match: re.Match[str]) -> str:
        if self.digest.link is None:
            raise BriefingError(f"Digest: the link #{match.group(1)} leads into the full report: give the digest "
                                "link='https://…/report.html'.")
        return f'href="{_html.escape(self.digest.link.split("#")[0])}#{match.group(1)}"'

    def bignumber(self, block: BigNumber) -> str:
        from briefing.renderers.html import _computed_change, _shown
        from briefing.renderers.inline import inline_markdown

        change, up, good = block.change, block.is_upward_change, block.is_positive_intent
        if block.prev_value is not None:
            change, up, good = _computed_change(block)
        heading = inline_markdown(str(block.heading))
        value = _html.escape(_shown(block, block.value))
        change_html = ""
        if change is not None:
            arrow = "" if up is None else ("▲ " if up else "▼ ")
            if good is not None:
                colour = "#16a34a" if good else "#dc2626"
            elif up is not None:
                colour = self.fmt.up_color if up else self.fmt.down_color
            else:
                colour = self.fmt.muted_color
            change_html = (f'<div style="margin-top: 4px; font-size: 14px; color: {colour}">'
                           f"{arrow}{_html.escape(change)}</div>")
        return (f'<tr><td style="padding: 14px 16px; background: {self.fmt.surface_color}; '
                f'border: 1px solid {self.fmt.border_color}">'
                f'<div style="font-size: 12px; letter-spacing: 0.04em; text-transform: uppercase; '
                f'color: {self.fmt.muted_color}">{heading}</div>'
                f'<div style="margin-top: 4px; font-size: 26px; font-weight: bold; color: {self.fmt.text_color}">'
                f"{value}</div>{change_html}</td></tr>")

    def alert(self, block: Alert) -> str:
        from briefing.renderers.inline import inline_markdown

        hue = _ALERT_HUES[str(block.level)]
        background = self.mix(hue, self.bg, 0.88)
        colour = self.mix(hue, self.fmt.text_color, 0.45) if self.fmt.text_color.startswith("#") else hue
        title = (f'<div style="font-weight: bold; margin-bottom: 4px">{inline_markdown(block.title)}</div>'
                 if block.title else "")
        return (f'<tr><td style="padding: 12px 14px; background: {background}; border-left: 4px solid {hue}; '
                f'color: {colour}; font-size: 14px">{title}{inline_markdown(block.message)}</td></tr>')

    def group(self, block: Group, width: int) -> str:
        columns = max(1, min(block.columns, len(block.blocks) or 1))
        gap = 12
        cell = (width - gap * (columns - 1)) // columns
        rows = []
        children = list(block.blocks)
        for start in range(0, len(children), columns):
            cells = []
            for i, child in enumerate(children[start:start + columns]):
                pad = f"padding-left: {gap}px" if i else ""
                cells.append(f'<td valign="top" width="{cell}" style="width: {cell}px; {pad}">'
                             f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
                             f"{self.block(child, cell)}</table></td>")
            rows.append(f'<tr>{"".join(cells)}</tr>')
        inner = f'<tr><td style="height: {gap}px"></td></tr>'.join(rows)
        return (f'<tr><td style="padding: 0 0 12px"><table role="presentation" width="100%" cellpadding="0" '
                f'cellspacing="0">{inner}</table></td></tr>')

    def plot(self, block: Plot, width: int) -> str:
        from briefing.renderers.inline import inline_markdown, inline_plain

        png = _png(block.figure)
        cid = f"chart-{len(self.pictures) + 1}.{hashlib.sha256(png).hexdigest()[:12]}@briefing"
        self.pictures.append(Picture(cid, png))
        alt = _html.escape(inline_plain(block.caption or "") or "A chart")
        caption = (f'<div style="margin-top: 6px; font-size: 13px; color: {self.fmt.muted_color}">'
                   f"{inline_markdown(block.caption)}</div>" if block.caption else "")
        return (f'<tr><td style="padding: 0 0 12px"><img src="cid:{cid}" width="{width}" alt="{alt}" '
                f'style="display: block; width: 100%; max-width: {width}px; height: auto; border: 0">'
                f"{caption}</td></tr>")

    def table(self, block: Table) -> str:
        from briefing.renderers.inline import inline_markdown
        from briefing.renderers.table import _fmt

        frame = _frame(block)
        border, text = self.fmt.border_color, self.fmt.text_color
        head = "".join(f'<th style="padding: 6px 8px; border-bottom: 2px solid {border}; text-align: left; '
                       f'font-size: 13px; color: {text}">{_html.escape(str(c))}</th>' for c in frame.columns)
        body = "".join(
            "<tr>" + "".join(f'<td style="padding: 6px 8px; border-bottom: 1px solid {border}; font-size: 13px; '
                             f'color: {text}">{_html.escape(str(_fmt(v)))}</td>' for v in row) + "</tr>"
            for row in frame.itertuples(index=False, name=None))
        caption = (f'<div style="margin-bottom: 6px; font-size: 13px; color: {self.fmt.muted_color}">'
                   f"{inline_markdown(block.caption)}</div>" if block.caption else "")
        return (f'<tr><td style="padding: 0 0 12px">{caption}<table role="presentation" cellpadding="0" '
                f'cellspacing="0" style="border-collapse: collapse; width: 100%">'
                f"<tr>{head}</tr>{body}</table></td></tr>")

    def _spaced(self, block: Block) -> str:
        """A top-level block; a framed one (a number, an alert) gets the gap the others have below them."""
        html = self.block(block, WIDTH - 48)
        if isinstance(block, BigNumber | Alert):
            return (f'<tr><td style="padding: 0 0 12px"><table role="presentation" width="100%" cellpadding="0" '
                    f'cellspacing="0">{html}</table></td></tr>')
        return html

    def document(self) -> str:
        rows = "".join(self._spaced(b) for b in self.digest.blocks)
        fmt = self.fmt
        button = ""
        if self.digest.link:
            button = (f'<tr><td style="padding: 8px 0 16px"><a href="{_html.escape(self.digest.link)}" '
                      f'style="display: inline-block; padding: 10px 18px; background: {fmt.accent_color}; '
                      f'color: #ffffff; text-decoration: none; font-weight: bold; font-size: 14px">'
                      f"Open the full report</a></td></tr>")
        footer = f"{_html.escape(self.digest.footer)} · " if self.digest.footer else ""
        return (
            "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<meta name=\"generator\" content=\"briefing {__version__}\"></head>"
            f'<body style="margin: 0; padding: 0; background: {self.bg}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background: {self.bg}">'
            f'<tr><td align="center" style="padding: 24px 12px">'
            f'<table role="presentation" width="{WIDTH}" cellpadding="0" cellspacing="0" '
            f'style="width: {WIDTH}px; max-width: 100%; font-family: {self.font}; color: {fmt.text_color}">'
            f'<tr><td style="padding: 0 24px">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}{button}</table>'
            f"</td></tr>"
            f'<tr><td style="padding: 16px 24px 0; border-top: 1px solid {fmt.border_color}; font-size: 12px; '
            f'color: {fmt.muted_color}">{footer}Made with briefing {__version__}</td></tr>'
            "</table></td></tr></table></body></html>\n"
        )


def to_html(digest: Digest, formatting: Formatting | None = None) -> tuple[str, list[Picture]]:
    """The digest's HTML body, and the PNG images it shows with ``cid:`` (attach each with its Content-ID).

    Args:
        digest: The :class:`Digest`.
        formatting: The theme's colours and font; the default theme without it.

    Example::

        body, pictures = bf.email.to_html(digest)
    """
    writer = _Writer(digest, formatting or Formatting())
    return writer.document(), writer.pictures


# ── plain text ────────────────────────────────────────────────────────────────


def _plain(block: Block) -> list[str]:
    from briefing.renderers.html import _computed_change, _shown
    from briefing.renderers.inline import inline_plain

    if isinstance(block, Text):
        return [re.sub(r"\s*\{#[a-zA-Z][\w-]*\}[ \t]*$", "", block.content, flags=re.M), ""]
    if isinstance(block, BigNumber):
        change = block.change
        if block.prev_value is not None:
            change = _computed_change(block)[0]
        tail = f" ({change})" if change else ""
        return [f"{inline_plain(str(block.heading))}: {_shown(block, block.value)}{tail}"]
    if isinstance(block, Alert):
        title = f"{inline_plain(block.title)}: " if block.title else ""
        return [f"[{str(block.level).title()}] {title}{inline_plain(block.message)}", ""]
    if isinstance(block, Group):
        return [line for child in block.blocks for line in _plain(child)] + [""]
    if isinstance(block, Plot):
        return [f"[Chart: {inline_plain(block.caption or '') or 'see the full report'}]", ""]
    frame = _frame(t.cast(Table, block))
    caption = [inline_plain(block.caption)] if isinstance(block, Table) and block.caption else []
    return [*caption, frame.to_string(index=False), ""]


def to_text(digest: Digest) -> str:
    """The digest as plain text, for mail apps that show no HTML.

    Args:
        digest: The :class:`Digest`.

    Example::

        print(bf.email.to_text(digest))
    """
    lines = [line for block in digest.blocks for line in _plain(block)]
    if digest.link:  # #anchors lead into the full report, as in the HTML
        base = digest.link.split("#")[0]
        lines = [re.sub(r"\]\(#([^)\s]*)\)", lambda m: f"]({base}#{m.group(1)})", line) for line in lines]
    if digest.link:
        lines += [f"Full report: {digest.link}", ""]
    lines.append(f"{digest.footer + ' · ' if digest.footer else ''}Made with briefing {__version__}")
    return "\n".join(lines).strip() + "\n"


# ── the message ───────────────────────────────────────────────────────────────


def to_message(digest: Digest, subject: str, sender: str | None = None, to: str | Sequence[str] | None = None,
               formatting: Formatting | None = None) -> EmailMessage:
    """The digest as an email: plain text and HTML alternatives, charts attached as PNG images.

    Sending stays yours (SMTP, the Gmail API, SES…).

    Args:
        digest: The :class:`Digest`.
        subject: The email's subject.
        sender: The ``From`` address, if you set it here.
        to: The ``To`` address, or a list of them.
        formatting: The theme's colours and font.

    Example::

        message = bf.email.to_message(digest, subject="Daily digest", to="team@example.com")
        with smtplib.SMTP("localhost") as smtp:
            smtp.send_message(message)
    """
    body, pictures = to_html(digest, formatting)
    message = EmailMessage()
    message["Subject"] = subject
    if sender:
        message["From"] = sender
    if to:
        message["To"] = to if isinstance(to, str) else ", ".join(to)
    message.set_content(to_text(digest))
    message.add_alternative(body, subtype="html")
    html_part = t.cast(EmailMessage, message.get_payload()[1])  # type: ignore[index]
    for picture in pictures:
        html_part.add_related(picture.png, maintype="image", subtype="png", cid=f"<{picture.cid}>")
    return message


def to_eml(digest: Digest, path: str | Path, subject: str, **options: t.Any) -> Path:
    """Write the digest as a ``.eml`` file, to open in a mail app before sending.

    Args:
        digest: The :class:`Digest`.
        path: Where to write it.
        subject: The email's subject.
        **options: ``sender``, ``to`` and ``formatting``, as for :func:`to_message`.

    Example::

        bf.email.to_eml(digest, "digest.eml", subject="Daily digest")
    """
    out = Path(path).expanduser()
    out.write_bytes(bytes(to_message(digest, subject, **options)))
    return out



__all__ = ["ALLOWED", "Digest", "Picture", "to_eml", "to_html", "to_message", "to_text"]
