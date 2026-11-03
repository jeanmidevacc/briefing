"""Text and KPI blocks: Text, HTML, Code, Formula, BigNumber, Alert."""
from __future__ import annotations

import textwrap
import warnings
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
    """Markdown text block.

    Example::

        fl.Text("# Hello world")
        fl.Text(\"\"\"
            ## Multi-line markdown
            - item one
            - item two
        \"\"\")
        fl.Text(file="notes.md")
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

        fl.HTML("<b>Bold text</b>")
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

        fl.Code("SELECT * FROM orders LIMIT 10", language="sql")
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

    Example::

        fl.BigNumber("Revenue", "$4.2M", change="-12%", is_upward_change=False)
        fl.BigNumber("Accuracy", 0.924)
    """

    def __init__(
        self,
        heading: str,
        value: str | int | float,
        change: str | None = None,
        is_upward_change: bool | None = None,
        name: BlockId | None = None,
        label: str | None = None,
    ) -> None:
        if change is not None and is_upward_change is None:
            warnings.warn(
                "BigNumber: 'change' is set but 'is_upward_change' is not. "
                "The change indicator arrow will not be shown.",
                stacklevel=2,
            )
        super().__init__(name=name, label=label)
        self.heading = heading
        self.value = value
        self.change = change
        self.is_upward_change = is_upward_change


class AlertLevel(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Alert(Block):
    """Styled callout / alert block.

    Example::

        fl.Alert("Data drift detected in feature 'age'.", level="warning")
        fl.Alert("Pipeline completed successfully.", level=fl.AlertLevel.SUCCESS)
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
