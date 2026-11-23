# Slide decks

A deck puts briefing's blocks on slides, for a meeting or to send round: one
self-contained HTML file in the report's theme, or a PDF with one slide per page. A deck
runs in the browser like a report, so every block keeps what it does there: charts stay
interactive, tables sort and search, tabs switch.

```{briefing-example}
:title: A deck of four slides

import numpy as np
import pandas as pd
import plotly.express as px
import briefing as bf

months = pd.date_range("2026-01-01", periods=9, freq="MS")
revenue = pd.DataFrame({"month": months, "revenue": 3.6 + np.arange(9) * 0.08 + np.sin(np.arange(9)) * 0.05})
regions = pd.DataFrame({"region": ["North", "South", "East", "West"], "revenue": [1.42, 0.96, 1.21, 0.61]})
theme = bf.Formatting.from_accent("#0f766e")
chart = px.line(revenue, x="month", y="revenue", markers=True, labels={"revenue": "Revenue ($M)", "month": ""},
                template=theme.plotly_template())
chart.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10))

deck = bf.deck.Deck(
    bf.deck.Slide(title="Q3 review: sales and operations"),
    bf.deck.Slide(
        bf.Text("Revenue grew in **every** region; the West is still the smallest."),
        bf.Group(
            bf.BigNumber("Revenue", 4.2e6, prev_value=3.9e6, format="${:,.0f}"),
            bf.BigNumber("Orders", 8421, prev_value=8180, format="{:,}"),
            bf.BigNumber("Margin", 0.31, prev_value=0.33, format="{:.0%}"),
            columns=3,
        ),
        title="Summary",
        name="summary",
    ),
    bf.deck.Slide(bf.Plot(chart), title="Revenue by month"),
    bf.deck.Slide(bf.DataTable(regions, formats={"revenue": "${:.2f}M"}), title="By region"),
    footer="Sales analytics",
)
bf.deck.save(deck, "q3-review.html", name="Q3 review", formatting=theme)
```

Click the deck, then use the arrow keys. `O` shows every slide; `F` goes full screen. The
theme is a report's (see the theming guide), and `theme.plotly_template()` puts the chart in it.

## Slides

A {class}`~briefing.deck.Deck` holds {class}`~briefing.deck.Slide` objects, in order. A
slide holds any block but a `Page`, stacked top to bottom as in a report, under an
optional `title` (inline Markdown, as in captions). Strings become `Text` and dataframes
`DataTable`, as in a report.

- **Layout** uses the blocks that already do it: `Group` for columns, `Select` for tabs,
  `Card` for framed boxes. Slides add no layout options of their own.
- **A section slide** has a title and no blocks: the title shows large, alone.
- **A title slide** holds only a `Banner`: the banner fills the slide.
- **The footer** (`Deck(footer=...)`) goes on every slide, before "Made with briefing" and
  the slide's number.

## Size and fit

Every slide is drawn at 1280 × 720 pixels (16:9) and scaled to the window, so a chart
gets the same space on a laptop and on a projector. Text is larger than in a report, to
read from the back of a room.

Python can't measure rendered text, so the deck fits what it holds in the browser:

1. Content too tall for its slide shrinks, keeping the slide's width, down to 70%.
2. Below that, the slide scrolls and shows a "Doesn't fit" mark, so nothing is cut
   without anyone noticing. Split the slide in two.

In Python, a slide with more than about 120 words of text warns, naming the slide. A
`DataTable` on a slide shows 10 rows a page. A Plotly chart takes its figure's height:
about 430 pixels fills a slide under a title.

## Moving around

| Key | Does |
| --- | --- |
| → ↓ Space Page Down | Next slide |
| ← ↑ Shift+Space Page Up | Previous slide |
| Home, End | First, last slide |
| O | Every slide; click one (or Enter) to go there, Esc to leave |
| F | Full screen |

The buttons at the bottom do the same and fade out while the mouse rests; on a touch
screen, swipe. Keys typed into a search box or a tab list stay theirs.

The address bar holds the slide's number (`q3-review.html#3`), so a link opens a slide.
A slide's `name` is its link too (`#summary`), and it scopes names as a page does: a block
named `margin` in that slide links as `#summary/margin`. See {doc}`links`.

## Printing and PDF

Printing a deck gives one slide per page, each 13.33 × 7.5 inches (the usual 16:9 slide
size), so the browser's "Save as PDF" writes a PDF deck. Each slide prints as it shows: its
chosen tab, its table's page. The same, without a browser at hand
(`pip install "briefing[image]"`, then once `playwright install chromium`):

```python
bf.deck.save_pdf(deck, "q3-review.pdf")                  # every slide
bf.deck.save_image(deck, "q3.png")                       # q3_01.png, q3_02.png, ...
bf.deck.save_image("q3-review.html", "cover.webp", slide=1)
```

```bash
python -m briefing pdf q3-review.html
python -m briefing image q3-review.html --slide summary -o summary.png
```

A deck isn't exported to PowerPoint: that would need another library and lose everything
interactive.

## As JSON

A deck has a JSON form, as a report does: `"slides"` in place of `"blocks"`, each slide
with its own `"title"`, `"name"` and `"blocks"`.

```json
{"briefing": 1, "footer": "Sales analytics", "slides": [
  {"title": "Q3 review"},
  {"title": "Summary", "name": "summary", "blocks": [
    {"type": "Text", "text": "Revenue grew in **every** region."}
  ]}
]}
```

`bf.to_spec(deck)` writes it, {func}`briefing.deck.from_spec` reads it, and `bf.validate`
checks it. From the command line, `python -m briefing validate deck.json` checks it and
`python -m briefing render deck.json -o deck.html` builds it.

## From a report (experimental)

```{admonition} Experimental
:class: warning

`bf.deck.from_report` is experimental: what it returns may change in any release, without a
deprecation period. It warns `bf.ExperimentalWarning` once per session; silence it with
`warnings.filterwarnings("ignore", category=bf.ExperimentalWarning)`.
```

`bf.deck.from_report(report)` turns a report into a first draft of a deck: an ordinary
`Deck`, to adjust before saving.

```python
deck = bf.deck.from_report(report, title="Q3 review")   # title=: an opening section slide
del deck.slides[4]                                      # drop, reorder or retitle slides
deck.slides[2].title = "What changed"
bf.deck.save(deck, "q3-deck.html")
```

| In the report | On the slides |
| --- | --- |
| A `Banner` that opens the report | The title slide |
| Each `Page` | Starts a slide titled and named after the page |
| `# Heading` in a `Text` | A section slide |
| `## Heading` in a `Text` | Starts a slide with that title; its `{#name}` names the slide |
| `---` on its own line | Starts a slide that keeps the title |
| Every other block | Stays whole, in order: groups, tabs, tables, charts, lab blocks |

Headings inside code stay code. A slide that holds too much shows it: the deck shrinks it,
then marks it "Doesn't fit", and a slide with more than about 120 words warns. Split it
with a `##` heading or a `---` line in the report, or adjust the deck.

From a build script, `python build_report.py --deck` writes `reports/index-deck.html` next
to the report (see the project guide), and `python -m briefing render report.json --deck
deck.html` does the same from JSON.
