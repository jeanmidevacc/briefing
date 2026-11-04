"""Formatting and theming configuration for briefing reports."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Width(StrEnum):
    """Content width of a report; :class:`Formatting` also accepts any CSS width.

    Example::

        bf.Formatting(width=bf.Width.NARROW)  # or width="narrow", or width="60rem"
    """

    NARROW = "narrow"   # max-width: 48rem  (768px)
    MEDIUM = "medium"   # max-width: 75rem  (1200px)
    FULL = "full"       # max-width: 100%


class TextAlignment(StrEnum):
    """Paragraph alignment in ``Text`` blocks.

    Example::

        bf.Formatting(text_alignment=bf.TextAlignment.JUSTIFY)
    """

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


_WIDTH_CSS: dict[Width, str] = {
    Width.NARROW: "48rem",
    Width.MEDIUM: "75rem",
    Width.FULL: "100%",
}


def _rgb_triplet(color: str) -> str:
    """``"#0f172a"`` → ``"15, 23, 42"``, for ``rgba(var(--bf-bg-rgb), a)`` veils (Banner)."""
    import re
    import warnings

    c = color.strip()
    hexes = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", c)
    if hexes:
        h = hexes.group(1)
        h = "".join(ch * 2 for ch in h) if len(h) == 3 else h
        return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"
    rgb = re.fullmatch(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+).*\)", c)
    if rgb:
        return ", ".join(rgb.groups())
    warnings.warn(f"Formatting: bg_color {color!r} isn't a hex or rgb() colour; banner veils use white.", stacklevel=3)
    return "255, 255, 255"


@dataclass
class Formatting:
    """Controls the visual theme of a briefing report.

    All values are injected as CSS custom properties on ``:root``.  The full
    set of tokens maps to every visual decision in the built-in stylesheet —
    colours, typography, spacing and shape.

    Quick start — built-in presets::

        bf.save(blocks, "dark.html",      formatting=bf.Formatting.dark())
        bf.save(blocks, "corp.html",      formatting=bf.Formatting.corporate())
        bf.save(blocks, "minimal.html",   formatting=bf.Formatting.minimal())
        bf.save(blocks, "ocean.html",     formatting=bf.Formatting.ocean())

    Fine-tuning a preset::

        fmt = bf.Formatting.dark(accent_color="#f43f5e")
        bf.save(blocks, "out.html", formatting=fmt)

    Building from scratch::

        bf.save(
            blocks, "out.html",
            formatting=bf.Formatting(
                accent_color="#0369a1",
                bg_color="#f8fafc",
                surface_color="#e2e8f0",
                border_color="#cbd5e1",
                text_color="#0f172a",
                muted_color="#64748b",
                radius="0.25rem",
                width=bf.Width.NARROW,
            ),
        )

    Token reference
    ---------------
    ``accent_color``   — tab underlines, active borders, links, focus rings
    ``bg_color``       — page background
    ``text_color``     — body / heading text
    ``muted_color``    — labels, captions, axis text, icons
    ``border_color``   — table borders, card borders, dividers
    ``surface_color``  — card / table-header / code-block backgrounds
    ``font``           — CSS font-family stack
    ``radius``         — border-radius applied to cards, badges, buttons
    ``width``          — report container max-width (NARROW / MEDIUM / FULL or CSS value)
    ``text_alignment`` — paragraph text alignment

    Args:
        accent_color: Tab underlines, active borders, links and focus rings.
        bg_color: Page background (hex or ``rgb()``; banner veils use it).
        text_color: Body and heading text.
        muted_color: Labels, captions, axis text and icons.
        border_color: Table, card and divider borders.
        surface_color: Card, table-header and code-block backgrounds.
        font: CSS ``font-family`` stack.
        radius: Corner radius of cards, badges and buttons.
        width: Content width: a :class:`Width` (``NARROW``, ``MEDIUM``, ``FULL``) or a CSS value.
        text_alignment: Paragraph alignment in ``Text`` blocks (a :class:`TextAlignment`).
    """

    # ── primary colours ───────────────────────────────────────────────────────
    accent_color: str = "#4F46E5"
    bg_color: str = "#ffffff"
    text_color: str = "#111827"
    muted_color: str = "#6b7280"
    border_color: str = "#e5e7eb"
    surface_color: str = "#f9fafb"

    # ── typography & shape ────────────────────────────────────────────────────
    font: str = "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif"
    radius: str = "0.5rem"

    # ── layout ────────────────────────────────────────────────────────────────
    width: Width | str = Width.MEDIUM
    text_alignment: TextAlignment | str = TextAlignment.LEFT

    # ── helpers ───────────────────────────────────────────────────────────────

    def to_css_vars(self) -> str:
        """Render theme values as a CSS ``:root { }`` block."""
        try:
            w = _WIDTH_CSS[Width(self.width)]
        except ValueError:
            w = self.width  # caller passed a raw CSS value like "60rem"
        return (
            ":root {\n"
            f"  --bf-bg:         {self.bg_color};\n"
            f"  --bf-bg-rgb:     {_rgb_triplet(self.bg_color)};\n"
            f"  --bf-accent:     {self.accent_color};\n"
            f"  --bf-font:       {self.font};\n"
            f"  --bf-max-width:  {w};\n"
            f"  --bf-text-align: {self.text_alignment};\n"
            f"  --bf-text:       {self.text_color};\n"
            f"  --bf-muted:      {self.muted_color};\n"
            f"  --bf-border:     {self.border_color};\n"
            f"  --bf-surface:    {self.surface_color};\n"
            f"  --bf-radius:     {self.radius};\n"
            "}\n"
        )

    # ── built-in presets ──────────────────────────────────────────────────────

    @classmethod
    def dark(cls, **overrides: str) -> Formatting:
        """Slate dark theme — easy on the eyes, great for dashboards."""
        return cls(**{
            "bg_color": "#0f172a", "surface_color": "#1e293b",
            "border_color": "#334155", "text_color": "#e2e8f0",
            "muted_color": "#94a3b8", "accent_color": "#818cf8",
            **overrides,
        })

    @classmethod
    def corporate(cls, **overrides: str) -> Formatting:
        """Clean blue corporate style — neutral tones, blue accent."""
        return cls(**{
            "bg_color": "#f8fafc", "surface_color": "#f1f5f9",
            "border_color": "#e2e8f0", "text_color": "#0f172a",
            "muted_color": "#64748b", "accent_color": "#0369a1",
            "radius": "0.25rem",
            "font": "'Segoe UI', ui-sans-serif, system-ui, sans-serif",
            **overrides,
        })

    @classmethod
    def minimal(cls, **overrides: str) -> Formatting:
        """Ultra-clean minimal style — white space, black text, hairline borders."""
        return cls(**{
            "bg_color": "#ffffff", "surface_color": "#fafafa",
            "border_color": "#d4d4d4", "text_color": "#171717",
            "muted_color": "#737373", "accent_color": "#171717",
            "radius": "0.125rem",
            "font": "'DM Sans', ui-sans-serif, system-ui, sans-serif",
            **overrides,
        })

    @classmethod
    def ocean(cls, **overrides: str) -> Formatting:
        """Deep teal ocean theme — rich mid-dark, emerald accent."""
        return cls(**{
            "bg_color": "#0d2137", "surface_color": "#112d45",
            "border_color": "#1e4060", "text_color": "#e0f2fe",
            "muted_color": "#7ab8d4", "accent_color": "#10b981",
            "font": "'IBM Plex Sans', ui-sans-serif, system-ui, sans-serif",
            **overrides,
        })

    @classmethod
    def warm(cls, **overrides: str) -> Formatting:
        """Warm sand theme — cream backgrounds, amber accent."""
        return cls(**{
            "bg_color": "#fefce8", "surface_color": "#fef9c3",
            "border_color": "#fde68a", "text_color": "#1c1917",
            "muted_color": "#78716c", "accent_color": "#b45309",
            "font": "'Lora', Georgia, serif",
            **overrides,
        })


__all__ = ["Formatting", "TextAlignment", "Width"]
