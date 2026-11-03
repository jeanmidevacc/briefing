# briefing

Build beautiful, self-contained reports from Python, authored by a person, a coding agent, or both.

## Why briefing exists

Three things led me here:

- **Coding agents are good at making something to show you, not at making it consistently.** A few months of building with coding agents surfaced the same gap every time: they're happy to produce an artifact, but each one comes out with its own structure, and nothing tracks how a piece of content evolved across a project. There was no shared grammar a person and an agent could both build reports from as the report generation was opaque.
- **[datapane](https://github.com/datapane/datapane) was the cleanest report builder I'd used.** Block-based, self-contained HTML output, a dead-simple API. I relied on it constantly to turn Python analysis into reports for stakeholders and to monitor pipelines. It was decommissioned in 2023 when the SaaS behind it shut down, and nothing since has replaced it.
- **No visualization tool covers everything, and the ones that push furthest often don't stick around.** Years of building visualizations taught me that every tool, however good, eventually falls short of the next thing you want to show. The niche packages that *do* push past that, like [Facets](https://github.com/PAIR-code/facets) (PAIR / Google) and its Facets Dive explorer, bring real value but rarely stay maintained. I wanted a place of my own to keep building and sharing that kind of custom, interactive visualization, without depending on someone else's side project staying alive.

briefing is built to close all three gaps at once: a block grammar solid enough for me *and* my coding agents to build reports from consistently, with datapane's simplicity and a home for the custom, interactive visualization that inspired it. All of it self-contained, offline, with no cloud account required.

```python
import briefing as bf

report = bf.Briefing(
    bf.Text("# Sales Analysis, Q1 2024"),
    bf.Group(
        bf.BigNumber("Revenue", "$4.2M", change="-12%", is_upward_change=False),
        bf.BigNumber("Active Users", "142K", change="+3%", is_upward_change=True),
        columns=2,
    ),
    bf.Select(
        bf.Plot(fig, label="Trend"),
        bf.DataTable(df, label="Raw Data"),
        bf.lab.DataProfile(df, label="Profile"),
    ),
    bf.lab.DataDive(df),
)

bf.save(report, "q1_analysis.html")
```

## Features

- **One block vocabulary, for you or your agent**: `bf.Text`, `bf.Table`, `bf.Plot`, `bf.Group`, … the same small set of blocks composes every report, so output stays consistent whether you write the Python yourself or a coding agent does.
- **Self-contained HTML**: zero CDN, works offline forever
- **No plotting or dataframe dependencies in the core**: the report grammar
  renders with a few small pure-Python libraries (Jinja2, markdown-it-py,
  Pygments, latex2mathml). Charts and dataframes are opt-in (see below).
- **Bring-your-own-figure `Plot`**: hand it a Plotly, Altair, Matplotlib or
  Bokeh figure; briefing imports that library only when you pass its figure.
- **Interactive tables**: sortable, searchable DataTable with client-side pagination
- **`briefing.lab`**: richer custom visualisations (`DataProfile` column stats,
  `DataDive` Facets-style dot explorer), all hand-rolled SVG + vanilla JS, no CDN
- **Themes**: five built-in presets plus full CSS token control
- **Dataframes**: pandas 2 and 3 first-class; polars, pyarrow and anything with the
  dataframe interchange protocol are converted for you; for PySpark, call `.toPandas()` first

## Installation

```bash
pip install briefing                # core grammar + HTML renderer, no viz deps
```

| Extra | Adds |
| --- | --- |
| `briefing[pandas]` | pandas engine for `Table` / `DataTable` |
| `briefing[lab]` | `briefing.lab` custom-visualisation blocks (`DataProfile`, `DataDive`) |
| `briefing[plotly]` `[altair]` `[bokeh]` `[matplotlib]` | the matching backend for `Plot` (`[altair]` also installs `vl-convert-python`, which supplies the Vega runtime embedded in the report) |
| `briefing[charts]` | all four `Plot` backends at once |
| `briefing[email]` | reserved for the upcoming email digest ([#42](https://github.com/jeanmidevacc/briefing/issues/42)); it installs its future dependencies (premailer, kaleido), but there is no email feature yet |

`Plot` never imports a plotting library unless you actually pass it a figure from
that library, so the extras only need to be installed for the backends you use.

---

## Quick start

```python
import pandas as pd
import briefing as bf

df = pd.read_csv("sales.csv")

bf.save(
    bf.Briefing(
        bf.Text("# My Report"),
        bf.DataTable(df),
    ),
    path="report.html",
    open=True,          # opens in browser immediately
)
```

To get the HTML as a string instead of writing a file, use `bf.stringify(report)`.

In a notebook (Jupyter, JupyterLab, VS Code), any block or `Briefing` previews itself when it is the last expression of a cell. Each preview is the complete report in its own frame, sized to its content, so previews never affect each other or the notebook. That is the natural way to build a report cell by cell: create one block, see it in place, keep going, then combine everything you built into one `Briefing` at the end. See [`examples/notebook_walkthrough.ipynb`](examples/notebook_walkthrough.ipynb) for the full walkthrough, or open the [finished report](examples/sales_report.html) it produces.

---

## API

The examples below assume `import briefing as bf`, a pandas DataFrame `df` (with
columns such as `region`, `revenue` and `margin_pct`) and a chart `fig`;
`tests/test_readme.py` runs every one of them, offline.

### `bf.save`

```python
bf.save(
    report,                  # a Briefing, a list of blocks, or a single block
    "report.html",           # destination file
    open=False,              # open in the default browser after saving
    name="Report",           # browser tab title and report header
    formatting=None,         # a Formatting instance: the theme
    now=None,                # pin the header timestamp (or set SOURCE_DATE_EPOCH)
)
```

### `bf.stringify`

```python
html = bf.stringify(report, name="Report", formatting=None)   # the same page, as a string
```

Same input, same `now` (or `SOURCE_DATE_EPOCH`): byte-identical output.

---

## Block reference

### Text blocks

#### `bf.Text`: Markdown

```python
bf.Text("# Heading\n\nSome **bold** and *italic* text.")

# From a .md file
bf.Text(file="notes.md")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `str` | Markdown string (dedented automatically) |
| `file` | `str \| Path` | Path to a `.md` file (alternative to `text`) |
| `label` | `str` | Tab/selector label when used inside `Select` |

Supports CommonMark (headings, bold, italics, links, inline code, code blocks,
blockquotes, lists) plus pipe tables. Raw HTML inside the markdown is passed through
as-is, like `bf.HTML`.

---

#### `bf.Code`: Syntax-highlighted code

```python
bf.Code("SELECT * FROM orders LIMIT 10", language="sql")
bf.Code(
    "import briefing as bf\nbf.save(bf.Briefing(bf.Text('# Hi')), 'out.html')",
    language="python",
    caption="Minimal report",
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `code` | `str` | required | Source code string |
| `language` | `str` | `"python"` | Syntax highlighting language |
| `caption` | `str` | `None` | Optional caption shown below the block |

---

#### `bf.Formula`: LaTeX equation

```python
bf.Formula(r"\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i", caption="Sample mean")
```

Converted to MathML when the report is rendered, so browsers typeset it natively:
no JavaScript, no network. Supported LaTeX is what
[`latex2mathml`](https://github.com/roniemartinez/latex2mathml) handles: fractions,
roots, sub/superscripts, sums and integrals, Greek letters and common symbols,
`\mathbb`/`\mathrm`-style fonts, accents (`\bar`, `\hat`, …), `\left…\right`, and
matrix environments (`pmatrix`, `bmatrix`, `cases`, `align`, …). A formula that can't
be converted (a typo, unbalanced braces, an unknown command, `\href`, or markup in
`\text{}`) shows its LaTeX source with a note, and Python emits a `UserWarning`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `formula` | `str` | required | LaTeX expression (without `$$` delimiters) |
| `caption` | `str` | `None` | Optional caption |

---

#### `bf.HTML`: Raw HTML fragment

```python
bf.HTML("<p style='color:#4F46E5'>Custom <strong>HTML</strong>.</p>")
```

Inserted into the report as-is, inside a plain `<div>`. It is **not** sandboxed or
sanitised: inline styles work and any `<script>` it contains runs, so only pass HTML
you trust. Paragraphs, lists and headings get the same typography as `Text`.

---

#### `bf.BigNumber`: KPI metric

```python
bf.BigNumber("Revenue", "$4.2M", change="-12%", is_upward_change=False)
bf.BigNumber("Accuracy", 0.924)   # no change indicator
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `heading` | `str` | required | Metric label |
| `value` | `str \| int \| float` | required | Headline value |
| `change` | `str` | `None` | Delta string, e.g. `"+3.1%"` |
| `is_upward_change` | `bool` | `None` | The arrow: `True` = ▲, `False` = ▼. Required if `change` is set. |
| `is_positive_intent` | `bool` | `None` | The colour, when it shouldn't follow the arrow: `True` = green, `False` = red. `None`: ▲ green, ▼ red. |

> If `change` is provided without `is_upward_change`, a warning is issued and the change
> shows with a red ▼ ([#71](https://github.com/jeanmidevacc/briefing/issues/71) decides
> what it should do). Pass `is_upward_change` whenever you pass `change`.

---

#### `bf.Alert`: Callout box

```python
bf.Alert("Pipeline completed successfully.", level=bf.AlertLevel.SUCCESS)
bf.Alert("Margin erosion in South region.", level="warning", title="Watch")
bf.Alert("Legacy source decommissioned.", level=bf.AlertLevel.ERROR, title="Breaking change")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `message` | `str` | required | Alert body text |
| `level` | `AlertLevel \| str` | `"info"` | One of `info`, `success`, `warning`, `error` |
| `title` | `str` | `None` | Optional bold title above the message |

`bf.AlertLevel` values: `INFO`, `SUCCESS`, `WARNING`, `ERROR`.

---

### Layout blocks

#### `bf.Group`: Grid layout

Arranges child blocks in a responsive column grid.

```python
bf.Group(plot_a, plot_b, columns=2)
bf.Group(a, b, c, columns=3, widths=[2, 1, 1])   # relative column widths
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `*blocks` | `Block` | required | Child blocks (positional) |
| `columns` | `int` | `1` | Number of columns |
| `widths` | `list[int \| float]` | `None` | Relative column widths, must match `columns` |
| `valign` | `VAlign \| str` | `"top"` | Vertical alignment: `top`, `center`, `bottom` |
| `label` | `str` | `None` | Tab label when used inside `Select` |

---

#### `bf.Select`: Tabbed or dropdown panel switcher

Shows one child block at a time. Each child's `label` becomes the tab title.

```python
bf.Select(
    bf.Plot(fig, label="Chart"),
    bf.DataTable(df, label="Data"),
    bf.lab.DataProfile(df, label="Profile"),
    type=bf.SelectType.TABS,       # or bf.SelectType.DROPDOWN
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `*blocks` | `Block` | required | Child blocks, each should have a `label` |
| `type` | `SelectType \| str` | `"tabs"` | `"tabs"` or `"dropdown"` |

> Warns if fewer than 2 children are provided.

---

#### `bf.Toggle`: Collapsible section

Collapsed by default; click the label to expand.

```python
bf.Toggle(
    bf.Text("Methodology notes (hidden by default)."),
    bf.Code("SELECT * FROM sales\n", language="sql"),
    label="Query details",
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `*blocks` | `Block` | required | Content blocks (multiple are auto-wrapped in a `Group`) |
| `label` | `str` | `None` | Clickable toggle label |

---

#### `bf.Page`: Top-level page tab

Use at the root of `Briefing` to create multi-page reports. Pages are converted to a top-level tab bar during rendering.

```python
bf.Briefing(
    bf.Page(summary_group, title="Summary"),
    bf.Page(detail_group, title="Detail"),
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `*blocks` | `Block` | required | Page content |
| `title` | `str` | `None` | Tab title |

> Nested `Page` blocks are not supported. Use `Select` and `Group` instead.

---

#### `bf.Briefing`: Root document container

Top-level wrapper passed to `save`. Accepts any combination of blocks.

```python
report = bf.Briefing(
    bf.Text("# My Report"),
    bf.Plot(fig),
    bf.DataTable(df),
)
bf.save(report, "report.html")
```

---

### Asset blocks

#### `bf.Plot`: Chart / figure

Library-agnostic chart block. Auto-detects the figure type at render time:

| Library | Output |
|---------|--------|
| **Plotly** | Interactive chart; the Plotly runtime is embedded once per report |
| **Altair / Vega-Lite** | Interactive chart; the Vega runtime is embedded once per report (`briefing[altair]`) |
| **Matplotlib / Seaborn / Plotnine** | Inline SVG |
| **Bokeh** | Interactive chart in an iframe, with Bokeh's resources inlined |

```python
bf.Plot(plotly_fig, caption="Revenue over time")
bf.Plot(altair_chart, label="Chart", responsive=True)
bf.Plot(mpl_fig)  # size it in Matplotlib: plt.subplots(figsize=(8, 4))
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `figure` | any | required | Figure object from Plotly, Altair, Matplotlib, or Bokeh |
| `caption` | `str` | `None` | Caption shown below the chart |
| `responsive` | `bool` | `True` | Scale chart to fill container width |
| `scale` | `float` | `None` | **Deprecated**, no effect, removed after 0.2. Size the figure in its library (e.g. Matplotlib `figsize`) |

---

#### `bf.Table`: Static table (pandas Styler)

Best for formatted DataFrames where you want to preserve Styler rules.

```python
bf.Table(df)
bf.Table(
    df.style
      .format({"revenue": "€ {:,.0f}"})
      .bar(subset=["revenue"], color="#c7d2fe")
      .set_caption("Top 20 by revenue"),
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | `DataFrame \| Styler` | required | DataFrame or styled DataFrame |
| `caption` | `str` | `None` | Optional caption |

---

#### `bf.DataTable`: Interactive table

Sortable, searchable, paginated table. Handles large datasets gracefully.

```python
bf.DataTable(df, caption="Full sales dataset")
bf.DataTable(df, max_rows=500)   # cap at 500 rows
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `df` | `DataFrame` | required | Source data |
| `caption` | `str` | `None` | Optional caption |
| `max_rows` | `int` | `10 000` | Rows beyond this are truncated with a warning |

---

### Lab blocks (`briefing.lab`)

#### `bf.lab.DataProfile`: Column statistics

Renders one card per column with its dtype, row count, missing count and %, and a
mini-chart.

- **Numeric**: unique count, mean, std, min, median, max + inline histogram
- **Categorical**: unique count, top values + inline bar chart
- **Datetime**: earliest and latest value + a range chart

No extra dependencies: mini-charts are pure SVG.

```python
bf.lab.DataProfile(df)
bf.lab.DataProfile(df, missing_threshold=0.05)   # red highlight at >5% missing
bf.lab.DataProfile(df, max_categories=10)        # cap top-N bars for categoricals
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `df` | `DataFrame` | required | Source data |
| `missing_threshold` | `float` | `0.20` | Missing % above which the cell is highlighted red |
| `max_categories` | `int` | `20` | Max top-value bars for categorical columns |

---

#### `bf.lab.DataDive`: Interactive dot explorer

Each DataFrame row becomes a dot. Dropdowns let the viewer dynamically change which columns drive X, Y and colour, similar to Google Facets Dive. (Faceting into rows
and columns is planned for DataDive v2.)

```python
bf.lab.DataDive(df)                                              # auto-selects axes
bf.lab.DataDive(df, x="revenue", y="margin_pct", color="region")
bf.lab.DataDive(df, x="region", y="channel", color="product", layout="tile")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `df` | `DataFrame` | required | Source data |
| `x` | `str` | `None` | Initial X-axis column |
| `y` | `str` | `None` | Initial Y-axis column |
| `color` | `str` | `None` | Initial colour column |
| `layout` | `str` | `"scatter"` | `"scatter"` (2-D axes) or `"tile"` (packed dot grid) |
| `max_rows` | `int` | `10 000` | Rows beyond this are sampled with a warning |

---

## Theming

Pass a `Formatting` instance to `save` to control the visual style.

### Built-in presets

```python
bf.save(blocks, "out.html", formatting=bf.Formatting.dark())
bf.save(blocks, "out.html", formatting=bf.Formatting.corporate())
bf.save(blocks, "out.html", formatting=bf.Formatting.minimal())
bf.save(blocks, "out.html", formatting=bf.Formatting.ocean())
bf.save(blocks, "out.html", formatting=bf.Formatting.warm())
```

| Preset | Description |
|--------|-------------|
| `dark()` | Slate dark, easy on the eyes, great for dashboards |
| `corporate()` | Clean blue corporate, neutral tones, sharp corners |
| `minimal()` | Ultra-clean, white space, black text, hairline borders |
| `ocean()` | Deep teal, rich mid-dark, emerald accent |
| `warm()` | Cream backgrounds, amber accent, serif font |

### Fine-tuning a preset

Every preset accepts keyword overrides:

```python
formatting=bf.Formatting.dark(accent_color="#f43f5e")   # dark theme, rose accent
formatting=bf.Formatting.corporate(width=bf.Width.FULL) # full-width corporate
```

### Building from scratch

```python
formatting=bf.Formatting(
    accent_color="#0369a1",
    bg_color="#f8fafc",
    surface_color="#e2e8f0",
    border_color="#cbd5e1",
    text_color="#0f172a",
    muted_color="#64748b",
    radius="0.25rem",
    width=bf.Width.NARROW,
)
```

### `Formatting` token reference

| Token | Default | Controls |
|-------|---------|---------|
| `accent_color` | `#4F46E5` | Tab underlines, active borders, links, focus rings |
| `bg_color` | `#ffffff` | Page background |
| `text_color` | `#111827` | Body and heading text |
| `muted_color` | `#6b7280` | Labels, captions, axis text, icons |
| `border_color` | `#e5e7eb` | Table borders, card borders, dividers |
| `surface_color` | `#f9fafb` | Card / table-header / code-block backgrounds |
| `font` | `Inter, ui-sans-serif, …` | CSS font-family stack |
| `radius` | `0.5rem` | Border-radius on cards, badges, buttons |
| `width` | `Width.MEDIUM` | Container max-width (`NARROW` / `MEDIUM` / `FULL` or raw CSS) |
| `text_alignment` | `left` | Paragraph text alignment |

`bf.Width` values: `NARROW` (768 px), `MEDIUM` (1200 px), `FULL` (100%).

---

## Recipes

### KPI dashboard with tabbed detail

```python
import briefing as bf

bf.save(
    bf.Briefing(
        bf.Text("# Sales Analysis, 2023"),

        bf.Group(
            bf.BigNumber("Total Revenue", "€ 1 260 000", change="+12.4%", is_upward_change=True),
            bf.BigNumber("Units Sold",    "12 640",      change="+3.1%",  is_upward_change=True),
            bf.BigNumber("Avg Margin",    "31.2 %",      change="-0.8%",  is_upward_change=False),
            bf.BigNumber("Return Rate",   "8.0 %",       change="+0.2%",  is_upward_change=True,
                         is_positive_intent=False),  # up, but bad news: ▲ in red
            columns=4,
        ),

        bf.Alert("South region margin dropped below 25% in December.",
                 level=bf.AlertLevel.WARNING, title="Action needed"),

        bf.Select(
            bf.Group(bf.DataTable(by_region, caption="Region summary"), columns=1, label="By Region"),
            bf.Group(bf.DataTable(monthly,   caption="Monthly aggregates"), columns=1, label="Monthly"),
            bf.Group(bf.DataTable(df,        caption="All transactions"), columns=1, label="Raw Data"),
        ),

        bf.Text("## Column Profile"),
        bf.lab.DataProfile(df),

        bf.Text("## Interactive Explorer"),
        bf.lab.DataDive(df, x="revenue", y="margin_pct", color="region"),

        bf.Toggle(
            bf.Text("**Refresh cadence**: nightly at 02:00 UTC."),
            bf.Code("SELECT * FROM sales WHERE date >= '2023-01-01'\n", language="sql"),
            label="Methodology & sources",
        ),
    ),
    path="sales_2023.html",
    name="Sales Analysis, 2023",
    formatting=bf.Formatting(accent_color="#0f766e"),
)
```

### Multi-library charts in one report

```python
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.express as px
import briefing as bf

fig_plotly = px.scatter(df, x="revenue", y="margin_pct", color="region")

fig_mpl, ax = plt.subplots()
ax.hist(df["revenue"].dropna(), bins=30)

bf.save(
    bf.Briefing(
        bf.Text("# Chart comparison"),
        bf.Group(
            bf.Plot(fig_plotly, caption="Interactive (Plotly)"),
            bf.Plot(fig_mpl,    caption="Static SVG (Matplotlib)"),
            columns=2,
        ),
    ),
    path="charts.html",
)
```

### Hiding methodology behind a toggle

```python
bf.Toggle(
    bf.Text("""
        **Data source**: internal data warehouse.
        **Contact**: analytics@example.com
    """),
    bf.Code("SELECT date, region, revenue FROM dw.sales\n", language="sql"),
    label="Methodology & sources",
)
```

### Tile layout (Facets Dive style)

```python
# Each (region × channel) cell is a group of packed dots coloured by product
bf.lab.DataDive(df, x="region", y="channel", color="product", layout="tile")
```

### Jupyter inline display

```python
bf.lab.DataProfile(df)            # last expression of a cell: previews itself

# with the name and theme you will save with
bf.preview(
    bf.Briefing(bf.Text("# Quick look"), bf.lab.DataProfile(df)),
    name="Quick look",
    formatting=bf.Formatting.dark(),
)
```

Previews run in their own frame. In a notebook that isn't trusted yet (for example one you just cloned), Jupyter hides frames: run the cell, or trust the notebook, to see it.

---

## Examples

The [`examples/`](examples/) folder holds:

| File | Contents |
|------|----------|
| [`notebook_walkthrough.ipynb`](examples/notebook_walkthrough.ipynb) | Build a report cell by cell in a notebook, then save it |
| [`sales_report.html`](examples/sales_report.html) | The report that notebook saves: open it in any browser, offline |
