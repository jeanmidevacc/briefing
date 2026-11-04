# Themes and `Formatting`

Pass a {class}`~briefing.Formatting` to `bf.save` (or `stringify`, `preview`,
`save_image`, `save_pdf`) to set colours, font, corner radius and width. Every
block, the lab blocks included, follows the theme.

## Presets

| Preset | Look |
| --- | --- |
| `Formatting()` | the default: white, indigo accent |
| `Formatting.dark()` | slate dark, for dashboards |
| `Formatting.corporate()` | clean blue, neutral tones, sharp corners |
| `Formatting.minimal()` | white space, black text, hairline borders |
| `Formatting.ocean()` | deep teal, emerald accent |
| `Formatting.warm()` | cream background, amber accent, serif font |

```{briefing-example}
:title: The dark preset

import briefing as bf

report = [
    bf.Text("# Dark preset\n\nEvery block follows the theme."),
    bf.Group(
        bf.BigNumber("Uptime", "99.94 %", change="+0.02 pt", is_upward_change=True),
        bf.BigNumber("Incidents", 3, change="-2", is_upward_change=False, is_positive_intent=True),
        columns=2,
    ),
    bf.Alert("Maintenance window on Sunday, 02:00–04:00 UTC.", level="warning"),
    bf.Select(bf.Text("First tab", label="One"), bf.Text("Second tab", label="Two")),
]
bf.save(report, "dark.html", name="Dark preset", formatting=bf.Formatting.dark())
```

Every preset accepts the same keywords as `Formatting`, to adjust it:

```python
bf.Formatting.dark(accent_color="#f43f5e")      # dark, with a rose accent
bf.Formatting.corporate(width=bf.Width.FULL)    # corporate, full width
```

## Your own theme

```{briefing-example}
:title: A custom theme

import briefing as bf

brand = bf.Formatting(
    accent_color="#0f766e",
    bg_color="#f8fafc",
    surface_color="#e2e8f0",
    border_color="#cbd5e1",
    text_color="#0f172a",
    muted_color="#64748b",
    radius="0.25rem",
    width=bf.Width.NARROW,
)
report = [
    bf.Text("# Custom theme\n\nA narrow, teal report with square-ish corners."),
    bf.Alert("Accent, surfaces and borders all come from `Formatting`.", title="Note"),
]
bf.save(report, "custom.html", name="Custom theme", formatting=brand)
```

## Tokens

| Argument | Default | Controls |
| --- | --- | --- |
| `accent_color` | `#4F46E5` | tab underlines, active borders, links, focus rings |
| `bg_color` | `#ffffff` | page background (banner veils use it too) |
| `text_color` | `#111827` | body and heading text |
| `muted_color` | `#6b7280` | labels, captions, axis text, icons |
| `border_color` | `#e5e7eb` | table, card and divider borders |
| `surface_color` | `#f9fafb` | card, table-header and code backgrounds |
| `font` | `Inter, ui-sans-serif, …` | CSS `font-family` stack |
| `radius` | `0.5rem` | corner radius of cards, badges, buttons |
| `width` | `Width.MEDIUM` | content width: `NARROW` (768 px), `MEDIUM` (1200 px), `FULL`, or any CSS width |
| `text_alignment` | `left` | paragraph alignment in `Text` |

The font must be installed on the reader's machine; reports embed no web fonts, so
the stack should end with a generic family such as `sans-serif`.
