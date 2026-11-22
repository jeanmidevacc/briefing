"""Text and KPI blocks: Text, HTML, Code, Formula, BigNumber, Alert."""
from __future__ import annotations

import math
import numbers
import textwrap
import typing as t
from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path

from briefing._colors import check_color
from briefing._error import BriefingError
from briefing.blocks.base import _MAX_CAPTION_LEN, Block, BlockId, _truncate

if t.TYPE_CHECKING:
    import pandas as pd

# ── embedded text base ───────────────────────────────────────────────────────


class EmbeddedTextBlock(Block):
    """Abstract base for blocks whose content is stored as a string directly
    in the document (not as an external asset reference)."""

    def __init__(
        self,
        content: str,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        self.content = content.strip()


# ── text blocks ───────────────────────────────────────────────────────────────


class Text(EmbeddedTextBlock):
    """Markdown text block (CommonMark plus pipe tables).

    Raw HTML inside the markdown is passed through as-is, like :class:`HTML`
    (and, like it, closed at the end of the block if left open).

    Args:
        text: Markdown; common leading indentation is removed.
        file: Path to a ``.md`` file to read instead of ``text``.
        values: Fills ``{name}`` and ``{name:spec}`` (such as ``{share:.1%}``) in the text.
            Each value shows exactly as written: Markdown and HTML in it are escaped. Other
            braces, and anything inside code, stay as they are; ``{{`` and ``}}`` are braces.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.Text("# Hello world")
        bf.Text(\"\"\"
            ## Multi-line markdown
            - item one
            - item two
        \"\"\")
        bf.Text(file="notes.md")
        bf.Text("Searches rose {change} from {span}.",
                values={"change": bf.fmt.percent(0.253, sign=True), "span": bf.fmt.span(start, end)})
    """

    embed_noun: t.ClassVar[str | None] = "text"

    def __init__(
        self,
        text: str | None = None,
        *,
        file: str | Path | None = None,
        values: Mapping[str, t.Any] | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        if not text and not file:
            raise BriefingError("Text block requires either 'text' or 'file'.")
        if text and file:
            raise BriefingError("Text block accepts 'text' or 'file', not both.")

        if text:
            content = textwrap.dedent(text).strip()
        else:
            path = Path(file).expanduser()  # type: ignore[arg-type]
            if not path.exists():
                raise BriefingError(f"File not found: {path}")
            content = path.read_text(encoding="utf-8")
        if values is not None:
            from briefing._prose import fill

            content = fill(content, values)  # kept filled: the JSON form is the text (#184)

        super().__init__(content=content, name=name, label=label)


class HTML(EmbeddedTextBlock):
    """Raw HTML fragment block.

    The content is injected into the report verbatim, inside a plain
    ``<div>`` — it is **not** sandboxed or sanitised. Only pass HTML you
    trust; any ``<script>`` it contains will run. A comment, tag or
    ``<script>``/``<style>`` element left open at its end is closed there,
    so it can't hide the blocks after it.

    Args:
        html: The HTML fragment, inserted as-is.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.HTML("<b>Bold text</b>")
    """

    def __init__(
        self,
        html: str,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(content=str(html), name=name, label=label)


class Code(EmbeddedTextBlock):
    """Syntax-highlighted code block.

    Args:
        code: The source code.
        language: Language for syntax highlighting (any Pygments lexer name, e.g.
            ``"python"``, ``"sql"``); an unknown language is shown as plain text.
        caption: Optional caption below the block.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.Code("SELECT * FROM orders LIMIT 10", language="sql")
    """

    def __init__(
        self,
        code: str,
        language: str = "python",
        caption: str | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(content=code, name=name, label=label)
        self.language = language
        self.caption = _truncate(caption, _MAX_CAPTION_LEN) if caption else caption


class Formula(EmbeddedTextBlock):
    r"""LaTeX formula block, converted to MathML when the report is rendered.

    Browsers display MathML natively, so the formula needs no JavaScript and
    no network. LaTeX that can't be converted is shown as source, with a
    visible note and a ``UserWarning``.

    Args:
        formula: A LaTeX expression, without ``$`` or ``\(`` delimiters.
        caption: Optional caption below the formula.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.Formula(r"\frac{1}{\sqrt{x^2 + 1}}")
    """

    def __init__(
        self,
        formula: str,
        caption: str | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(content=formula, name=name, label=label)
        self.caption = _truncate(caption, _MAX_CAPTION_LEN) if caption else caption


# ── KPI / metric blocks ───────────────────────────────────────────────────────


class BigNumber(Block):
    """KPI display block — shows a headline metric with optional change indicator.

    Args:
        heading: The metric's name.
        value: The headline value.
        change: Optional change to show under the value, e.g. ``"+3%"``.
        is_upward_change: The arrow: ``True`` shows ▲, ``False`` shows ▼, ``None``
            shows no arrow.
        is_positive_intent: The colour: ``True`` is green (good news), ``False``
            is red (bad news). Leave it ``None`` and the colour follows the arrow
            (▲ green, ▼ red); with neither flag the change is shown neutral, in
            the theme's muted colour.
        prev_value: The value to compare with: briefing computes the change, its
            arrow and its colour (instead of ``change``, ``is_upward_change`` and
            ``is_positive_intent``). Needs a numeric ``value``.
        change_as: How a computed change is shown: ``"percent"`` (``+10.5%``),
            ``"absolute"`` (the difference, in ``format``) or ``"points"`` (the
            difference of two rates in percentage points, ``-0.3 pt``).
        higher_is_better: With ``prev_value``: ``True`` shows a rise in green,
            ``False`` a fall (churn, cost, latency).
        format: How ``value`` is shown: a format string such as ``"{:,.0f}"``,
            ``"$ {:.1f}M"`` or ``"{:.1%}"``, or a function.
        sparkline: A short series of numbers drawn as a trend line under the value
            (a list, a Series or an array); missing values leave gaps.
        accent: A colour stripe on the card's left edge: ``"up"``, ``"down"`` or
            ``"accent"`` (the theme's colours) or a CSS colour.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.BigNumber("Revenue", "$4.2M", change="-12%", is_upward_change=False)
        bf.BigNumber("Return Rate", "8.0 %", change="+0.2%", is_upward_change=True, is_positive_intent=False)
        bf.BigNumber("Users", "142K", change="+3%")   # neutral: no arrow, muted
        bf.BigNumber("Accuracy", 0.924)
        bf.BigNumber("Revenue", 4_210_000, prev_value=3_810_000, format="${:,.0f}", sparkline=weekly)
        bf.BigNumber("Churn", 0.031, prev_value=0.034, format="{:.1%}", change_as="points",
                     higher_is_better=False)
    """

    embed_noun: t.ClassVar[str | None] = "number"

    def __init__(
        self,
        heading: str,
        value: str | int | float,
        change: str | None = None,
        is_upward_change: bool | None = None,
        is_positive_intent: bool | None = None,
        prev_value: float | None = None,
        change_as: str = "percent",
        higher_is_better: bool = True,
        format: str | Callable[[t.Any], str] | None = None,  # noqa: A002
        sparkline: Sequence[float | None] | pd.Series | None = None,
        accent: str | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        self.heading = heading
        self.value = value
        self.change = change
        self.is_upward_change = is_upward_change
        self.is_positive_intent = is_positive_intent
        if change_as not in self.CHANGE_AS:
            raise BriefingError(f"BigNumber: change_as must be one of {', '.join(map(repr, self.CHANGE_AS))}, "
                                f"not {change_as!r}.")
        if prev_value is None and (change_as != "percent" or higher_is_better is not True):
            raise BriefingError("BigNumber: change_as and higher_is_better shape a computed change: pass prev_value.")
        if prev_value is not None:
            if change is not None or is_upward_change is not None or is_positive_intent is not None:
                raise BriefingError("BigNumber: with prev_value the change, its arrow and its colour are computed; "
                                    "drop change, is_upward_change and is_positive_intent (use higher_is_better).")
            for role, number in (("value", value), ("prev_value", prev_value)):
                if not _is_number(number):
                    raise BriefingError(f"BigNumber: prev_value needs numbers; {role} is {number!r}.")
        self.prev_value, self.change_as, self.higher_is_better = prev_value, change_as, higher_is_better
        self.format = _check_format(format, value)
        self.sparkline = _check_sparkline(sparkline)
        self.accent = check_color(accent, "BigNumber: accent")

    #: How a computed change can be shown.
    CHANGE_AS: t.ClassVar[tuple[str, ...]] = ("percent", "absolute", "points")


def _is_number(value: object) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool) and math.isfinite(float(value))


def _check_format(how: object, value: object) -> str | Callable[[t.Any], str] | None:
    """A format for a BigNumber's value: a format string with one ``{}``, or a function, that fits *value*."""
    if how is None:
        return None
    if not (callable(how) or (isinstance(how, str) and "{" in how)):
        raise BriefingError(f"BigNumber: format is a format string such as '{{:,.0f}}' or a function, not {how!r}.")
    try:
        str(how(value)) if callable(how) else how.format(value)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise BriefingError(f"BigNumber: format {how!r} can't show the value {value!r}: {exc}.") from exc
    return t.cast("str | Callable[[t.Any], str]", how)


def _check_sparkline(series: object) -> list[float | None] | None:
    """A sparkline's points as plain numbers, ``None`` for a gap; at least two numbers."""
    if series is None:
        return None
    values = series.tolist() if hasattr(series, "tolist") else series
    if isinstance(values, str | bytes) or not isinstance(values, Sequence):
        raise BriefingError(f"BigNumber: sparkline is a sequence of numbers, not {type(series).__name__}.")
    points: list[float | None] = []
    for v in values:
        if v is None or (isinstance(v, numbers.Real) and not isinstance(v, bool) and not math.isfinite(float(v))):
            points.append(None)
        elif _is_number(v):
            points.append(float(v))
        else:
            raise BriefingError(f"BigNumber: sparkline holds numbers (or missing values), not {v!r}.")
    if sum(p is not None for p in points) < 2:
        raise BriefingError("BigNumber: a sparkline needs at least two numbers.")
    return points


class AlertLevel(StrEnum):
    """Colour and icon of an :class:`Alert`.

    Example::

        bf.Alert("Data is a day late", level=bf.AlertLevel.WARNING)  # or level="warning"
    """

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Alert(Block):
    """Styled callout / alert block.

    Args:
        message: The alert's text.
        level: ``"info"``, ``"success"``, ``"warning"`` or ``"error"`` (or an :class:`AlertLevel`).
        title: Optional bold title above the message.
        name: Stable block id (letters, digits, ``_`` and ``-``), its link in the report (``#page/name``).
        label: Tab or dropdown label when the block is inside a ``Select``.

    Example::

        bf.Alert("Data drift detected in feature 'age'.", level="warning")
        bf.Alert("Pipeline completed successfully.", level=bf.AlertLevel.SUCCESS)
    """

    embed_noun: t.ClassVar[str | None] = "alert"

    def __init__(
        self,
        message: str,
        level: AlertLevel | str = AlertLevel.INFO,
        title: str | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        self.message = message
        self.level = AlertLevel(level)
        self.title = title


# ── public re-exports ─────────────────────────────────────────────────────────

__all__: list[str] = [
    "AlertLevel",
    "Alert",
    "BigNumber",
    "Code",
    "EmbeddedTextBlock",
    "Formula",
    "HTML",
    "Text",
]
