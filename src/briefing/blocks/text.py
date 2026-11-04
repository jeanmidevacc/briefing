"""Text and KPI blocks: Text, HTML, Code, Formula, BigNumber, Alert."""
from __future__ import annotations

import textwrap
from enum import StrEnum
from pathlib import Path

from briefing._error import BriefingError
from briefing.blocks.base import _MAX_CAPTION_LEN, Block, BlockId, _truncate

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

    Raw HTML inside the markdown is passed through as-is, like :class:`HTML`.

    Example::

        bf.Text("# Hello world")
        bf.Text(\"\"\"
            ## Multi-line markdown
            - item one
            - item two
        \"\"\")
        bf.Text(file="notes.md")
    """

    def __init__(
        self,
        text: str | None = None,
        *,
        file: str | Path | None = None,
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

        super().__init__(content=content, name=name, label=label)


class HTML(EmbeddedTextBlock):
    """Raw HTML fragment block.

    The content is injected into the report verbatim, inside a plain
    ``<div>`` — it is **not** sandboxed or sanitised. Only pass HTML you
    trust; any ``<script>`` it contains will run.

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

    Example::

        bf.BigNumber("Revenue", "$4.2M", change="-12%", is_upward_change=False)
        bf.BigNumber("Return Rate", "8.0 %", change="+0.2%", is_upward_change=True, is_positive_intent=False)
        bf.BigNumber("Users", "142K", change="+3%")   # neutral: no arrow, muted
        bf.BigNumber("Accuracy", 0.924)
    """

    def __init__(
        self,
        heading: str,
        value: str | int | float,
        change: str | None = None,
        is_upward_change: bool | None = None,
        is_positive_intent: bool | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(name=name, label=label)
        self.heading = heading
        self.value = value
        self.change = change
        self.is_upward_change = is_upward_change
        self.is_positive_intent = is_positive_intent


class AlertLevel(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Alert(Block):
    """Styled callout / alert block.

    Example::

        bf.Alert("Data drift detected in feature 'age'.", level="warning")
        bf.Alert("Pipeline completed successfully.", level=bf.AlertLevel.SUCCESS)
    """

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
