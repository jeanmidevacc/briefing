"""Formatting and theming configuration for briefing reports."""
from __future__ import annotations

import math
import typing as t
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from briefing._error import BriefingError


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
    ``up_color``       — a BigNumber's ▲, ``"up"`` chips and accents
    ``down_color``     — a BigNumber's ▼, ``"down"`` chips and accents
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
        up_color: Things that went up: a BigNumber's ▲, and ``"up"`` chips and accents.
        down_color: Things that went down: a BigNumber's ▼, and ``"down"`` chips and accents.
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
    up_color: str = "#16a34a"
    down_color: str = "#dc2626"

    # ── typography & shape ────────────────────────────────────────────────────
    #: Fonts every system has (#28): each preset's stack names a font from macOS, Windows and
    #: Linux before its generic family, so a preset looks the same to every reader.
    font: str = "system-ui, -apple-system, 'Segoe UI', Roboto, 'Noto Sans', 'Liberation Sans', Arial, sans-serif"
    radius: str = "0.5rem"

    # ── layout ────────────────────────────────────────────────────────────────
    width: Width | str = Width.MEDIUM
    text_alignment: TextAlignment | str = TextAlignment.LEFT

    # ── helpers ───────────────────────────────────────────────────────────────

    def to_css_vars(self, selector: str = ":root") -> str:
        """Render the theme as a CSS rule that sets the ``--bf-*`` variables.

        Args:
            selector: The CSS selector the variables are set on. ``:root`` themes the
                whole page; an element's selector (``#revenue``) themes only that element,
                so outputs with different themes can share a page.

        Example::

            bf.Formatting.dark().to_css_vars("#revenue")  # a "#revenue { --bf-bg: ...; }" rule
        """
        try:
            w = _WIDTH_CSS[Width(self.width)]
        except ValueError:
            w = self.width  # caller passed a raw CSS value like "60rem"
        return (
            f"{selector} {{\n"
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
            f"  --bf-up:         {self.up_color};\n"
            f"  --bf-down:       {self.down_color};\n"
            f"  --bf-radius:     {self.radius};\n"
            "}\n"
        )

    # ── built-in presets ──────────────────────────────────────────────────────

    # ── charts that follow the theme (#39) ────────────────────────────────────

    #: Seven hues for light pages and seven for dark ones, chosen to stay apart for normal vision,
    #: protanopia and deuteranopia, with 3:1 contrast against a white (or slate) page.
    CATEGORICAL_LIGHT: t.ClassVar[tuple[str, ...]] = (
        "#005b8b", "#ee5e23", "#00a16e", "#b56ae7", "#9f0051", "#a44d00", "#6c4bcc")
    CATEGORICAL_DARK: t.ClassVar[tuple[str, ...]] = (
        "#00c3fc", "#ee5e23", "#4ca77b", "#a670f3", "#fcdf00", "#ff89bf", "#ffa10e")

    def categorical(self) -> list[str]:
        """The theme's categorical palette: its accent, then the hues that stay apart from it.

        Example::

            px.bar(df, x="region", y="sales", color="channel",
                   color_discrete_sequence=bf.Formatting.dark().categorical())
        """
        from briefing import color

        dark = color.lightness(color.check_hex(self.bg_color, "bg_color")) < 0.5
        base = self.CATEGORICAL_DARK if dark else self.CATEGORICAL_LIGHT
        accent = color.check_hex(self.accent_color, "accent_color")

        def apart(a: str, b: str) -> bool:
            return color.distance(a, b) >= 14 and all(
                color.distance(color.simulate(a, k), color.simulate(b, k)) >= 10
                for k in ("protanopia", "deuteranopia"))

        return [accent, *(c for c in base if apart(accent, c))]

    def _palette(self, palette: t.Any) -> list[str]:
        from briefing import color
        from briefing.scale import Scale

        if palette is None:
            return self.categorical()
        if isinstance(palette, Scale):
            return list(palette.colors)
        if isinstance(palette, str) or not isinstance(palette, Sequence) or not palette:
            raise BriefingError(f"palette is a bf.Scale or a list of hex colours, not {palette!r}.")
        return [color.check_hex(c, "palette: each colour") for c in palette]

    def plotly_template(self, palette: t.Any = None) -> t.Any:
        """A Plotly template in the report's theme: its font, text and border colours, see-through
        backgrounds, and ``palette`` (or :meth:`categorical`) as the colours of the traces.

        Args:
            palette: A :class:`~briefing.Scale` (a named palette) or a list of hex colours.

        Example::

            fmt = bf.Formatting.dark()
            fig = px.line(df, x="day", y="sales", color="region", template=fmt.plotly_template())
        """
        import plotly.graph_objects as go
        import plotly.io as pio

        axis = {"gridcolor": self.border_color, "linecolor": self.border_color,
                "zerolinecolor": self.border_color, "tickcolor": self.border_color}
        template = go.layout.Template(pio.templates["plotly_white"])
        template.layout.update(
            font={"family": self.font, "color": self.text_color},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            colorway=self._palette(palette), xaxis=axis, yaxis=axis,
            hoverlabel={"bgcolor": self.surface_color, "bordercolor": self.border_color,
                        "font": {"family": self.font, "color": self.text_color}},
            legend={"bgcolor": "rgba(0,0,0,0)"},
        )
        return template

    def mpl_style(self, palette: t.Any = None) -> dict[str, t.Any]:
        """Matplotlib settings in the report's theme, for ``plt.rc_context(...)`` or ``plt.style.use(...)``.

        Args:
            palette: A :class:`~briefing.Scale` (a named palette) or a list of hex colours.

        Example::

            with plt.rc_context(bf.Formatting.dark().mpl_style()):
                fig, ax = plt.subplots()
        """
        from cycler import cycler

        families = [f.strip().strip("'\"") for f in self.font.split(",")]
        generic = "serif" if families[-1] == "serif" else "sans-serif"
        named = [f for f in families if f not in ("serif", "sans-serif", "system-ui", "-apple-system")]
        text, border = self.text_color, self.border_color
        fallback = "DejaVu Serif" if generic == "serif" else "DejaVu Sans"  # Matplotlib's own, always there
        return {
            "font.family": generic, f"font.{generic}": [*named, fallback],
            "text.color": text, "axes.labelcolor": text, "axes.titlecolor": text,
            "xtick.color": text, "ytick.color": text, "axes.edgecolor": border, "grid.color": border,
            "figure.facecolor": "none", "axes.facecolor": "none", "savefig.facecolor": "none",
            "legend.frameon": False, "axes.prop_cycle": cycler(color=self._palette(palette)),
        }

    @classmethod
    def from_accent(cls, accent: str, dark: bool = False, **overrides: str) -> Formatting:
        """A whole theme from one brand colour (#179).

        The background, surfaces, borders and text are neutrals tinted a little toward the
        accent's hue; the accent keeps its hue, its lightness moved until it reads as a
        link (4.5:1 against the background). Text reaches 7:1 and muted text 4.5:1.

        Args:
            accent: The brand colour, as hex.
            dark: A near-black page instead of a near-white one.
            **overrides: Any token to set by hand, as for the presets.

        Example::

            bf.Formatting.from_accent("#f5479a", dark=True)
        """
        from briefing import color

        lightness, a, b = color.to_oklab(color.check_hex(accent, "Formatting.from_accent: accent"))
        chroma = math.hypot(a, b)
        da, db = (a / chroma, b / chroma) if chroma > 1e-6 else (0.0, 0.0)

        def tint(level: float, amount: float) -> str:
            return color.from_oklab((level, da * amount, db * amount))

        def reach(level: float, amount: float, against: str, ratio: float, step: float) -> str:
            """Move *level* by *step* until the tinted colour has *ratio* contrast against *against*."""
            for _ in range(200):
                candidate = tint(level, amount)
                if color.contrast(candidate, against) >= ratio:
                    return candidate
                level = min(1.0, max(0.0, level + step))
            return candidate

        if dark:
            bg, surface, border = tint(0.18, 0.012), tint(0.22, 0.015), tint(0.32, 0.018)
            text = reach(0.93, 0.008, bg, 7.0, 0.01)
            muted = reach(0.72, 0.014, bg, 4.5, 0.01)
            step = 0.01
        else:
            bg, surface, border = tint(0.995, 0.003), tint(0.975, 0.006), tint(0.91, 0.01)
            text = reach(0.24, 0.02, bg, 7.0, -0.01)
            muted = reach(0.54, 0.02, bg, 4.5, -0.01)
            step = -0.01
        level = lightness
        brand = color.from_oklab((level, a, b))
        for _ in range(200):  # same hue and chroma, lighter or darker until it reads as a link
            if color.contrast(brand, bg) >= 4.5:
                break
            level = min(1.0, max(0.0, level + step))
            brand = color.from_oklab((level, a, b))
        return cls(**{
            "bg_color": bg, "surface_color": surface, "border_color": border,
            "text_color": text, "muted_color": muted, "accent_color": brand,
            **overrides,
        })

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
            "font": "'Helvetica Neue', Helvetica, Arial, 'Nimbus Sans', 'Liberation Sans', sans-serif",
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
            "font": "Avenir, 'Avenir Next', Corbel, 'URW Gothic', 'URW Gothic L', sans-serif",
            **overrides,
        })

    @classmethod
    def ocean(cls, **overrides: str) -> Formatting:
        """Deep teal ocean theme — rich mid-dark, emerald accent."""
        return cls(**{
            "bg_color": "#0d2137", "surface_color": "#112d45",
            "border_color": "#1e4060", "text_color": "#e0f2fe",
            "muted_color": "#7ab8d4", "accent_color": "#10b981",
            "font": "Seravek, 'Gill Sans Nova', Calibri, Ubuntu, 'DejaVu Sans', sans-serif",
            **overrides,
        })

    @classmethod
    def warm(cls, **overrides: str) -> Formatting:
        """Warm sand theme — cream backgrounds, amber accent."""
        return cls(**{
            "bg_color": "#fefce8", "surface_color": "#fef9c3",
            "border_color": "#fde68a", "text_color": "#1c1917",
            "muted_color": "#78716c", "accent_color": "#b45309",
            "font": "Charter, 'Bitstream Charter', 'Sitka Text', Cambria, Georgia, 'DejaVu Serif', serif",
            **overrides,
        })


__all__ = ["Formatting", "TextAlignment", "Width"]
