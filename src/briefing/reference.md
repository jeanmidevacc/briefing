# briefing: reference for agents

briefing (`pip install briefing`, `import briefing as bf`) turns analysis into one
self-contained HTML report: text, numbers, charts, tables and layout, in a single file that
works offline. It is newer than your training data and its API changes between versions:
trust this file, which ships with the installed version, over what you remember.

## How to work

1. Write the report as JSON (the format is below), for instance in `report.json`.
2. Check it: `python -m briefing validate report.json`. Each problem comes with the JSON
   Pointer of where it is and, often, a hint. Fix them and check again until there is no
   error (exit status 0).
3. Render it: `python -m briefing render report.json -o report.html --name "Q1 sales"`.

Tables an agent can't paste into the JSON go by reference: `{"ref": "sales"}` in the JSON,
and `--data sales=sales.csv` (CSV or Parquet) for `validate` and `render`.

From Python, the same steps:

```python
import json
import pandas as pd
import briefing as bf

sales = pd.DataFrame({"region": ["North", "South"], "revenue": [412000, 287500]})
spec = {"briefing": 1, "blocks": [
    {"type": "Text", "text": "# Q1 sales"},
    {"type": "DataTable", "df": {"ref": "sales"}},
]}
problems = bf.validate(spec, data={"sales": sales})  # a list of bf.Diagnostic; [] when all is well
assert not [p for p in problems if p.severity == "error"], problems
report = bf.from_spec(spec, data={"sales": sales})
bf.save(report, "q1.html", name="Q1 sales")
spec_again, data = bf.to_spec(report)  # any report as JSON, and the objects it names
```

Python reports can be written directly too: each JSON block is the class of the same name
with the same keyword arguments (`{"type": "Group", "columns": 2, "blocks": [...]}` is
`bf.Group(..., columns=2)`; `lab.X` is `bf.lab.X`), and `bf.validate(report)` checks them.

## The format

- The top-level object holds `"briefing": 1` (the format version, not briefing's),
  `"blocks"` (the report's blocks, in order) and the report's options below.
- Each block is an object whose `"type"` is its class name. Its other keys are the class's
  parameters, with JSON values: text, numbers, `true`/`false`, `null`, lists. Leave out
  options you don't need; they take their default.
- Containers (Group, Select, Toggle, Page) hold their children in `"blocks"`.
- Pages: either every top-level block is a `Page` (one tab each) or none is; pages never nest.
- A Select's display, `"tabs"` or `"dropdown"`, is `"select_type"`: `"type"` names the block.
- Every block takes `name` (letters, digits, `_`, `-`, starting with a letter): its link in
  the report (`#page/name`), unique within its page. Every block but Page takes `label`: its
  tab or option title inside a Select. A Text heading can take a name too: `## Notes {#notes}`.

## Data: references and inline

- Any option's value can be a reference, `{"ref": "<name>"}`, to an object passed with the
  JSON (`data={"<name>": obj}` in Python, `--data <name>=file.csv` on the command line).
- A table can also be written inline: `{"columns": ["region", "revenue"], "dtypes": ["object",
  "int64"], "rows": [["North", 412000], ["South", 287500]]}`. `dtypes` (pandas dtype names) is
  optional; missing values are `null`, dates ISO strings, infinities `"Infinity"`/`"-Infinity"`.
- A chart (`Plot` `figure`) inline: `{"plotly": <a Plotly figure's JSON>}`, or
  `{"vega-lite": <a Vega-Lite specification>}`. Matplotlib and Bokeh figures go by reference.
- A Banner `image`: a file path, or a `data:` URI (`"data:image/png;base64,..."`).

## The report's options

- `export`: one of "png", "embed" or a list of values from "png", "embed". Opt-in export menu in the report header: `"png"` adds "Save as PNG" (the open page with a margin around it, drawn in the reader's browser at 2×). Reports without it contain no export code. "Save as PNG" is best effort: charts drawn in iframes (Bokeh) and WebGL Plotly traces come out blank, and fonts are whatever the reader's machine has. For exact, reproducible files use save_image / save_pdf. To print, use the browser's own print (Ctrl+P or ⌘P): it gets the same print layout. `"embed"` puts a `</>` button on each page, labelled group, chart, table, text, number, alert and banner: it copies that part as an embed fragment, as stringify makes with `full_html=False`, to paste into another page. `"pdf"` (the "Print" button) was removed in 0.4.0: print with Ctrl+P, or save a file with save_pdf.
- `footer`: text. Text to put before the report's footer line, such as a team name. Every report ends with "Made with briefing" and its version; that line can't be turned off.
- `tabs`: a tab style {"layout": "stretch", "sticky": true, ...}. How the page tabs look, for a report made of Page blocks: a TabStyle such as `bf.TabStyle(layout="stretch", sticky=True)`.
- `header`: a header {"subtitle": "...", "author": "...", "as_of": "2026-11-20", ...}. What the header shows besides the name and render time: a Header with a subtitle, author, logo, "data as of" date and time zone.

## Blocks

### Text

Markdown text block (CommonMark plus pipe tables).
Needs `text` or `file`.

- `text`: text. Markdown; common leading indentation is removed.
- `file`: text. Path to a `.md` file to read instead of `text`.
- `values`: an object {"<column>": text or a number or true or false or null}. Fills `{name}` and `{name:spec}` (such as `{share:.1%}`) in the text. Each value shows exactly as written: Markdown and HTML in it are escaped. Other braces, and anything inside code, stay as they are; `{{` and `}}` are braces.

### Group

Grid layout container.
Holds `"blocks"`, a list of blocks (it may be empty).

- `columns`: a whole number, default `1`. Number of grid columns, a whole number of 1 or more.
- `widths`: a list of numbers. Relative column widths, positive numbers, one per column (e.g. `[2, 1]`).
- `valign`: one of "top", "center", "bottom", default `"top"`. Vertical alignment of the cells: `"top"`, `"center"` or `"bottom"`.
- `min_width`: text or a whole number. The narrowest a cell may be, such as `"16rem"` (or a number of pixels): as many cells per row as fit, up to `columns` when it is above 1. Not with `widths`.

### Card

A framed box with a title, around blocks stacked in one column.
Holds `"blocks"`, a list of blocks (at least one).

- `title`: text. The card's heading, with inline Markdown as in captions.
- `icon`: text. A short mark before the title, such as an emoji (up to 8 characters).
- `tags`: a list of texts or a chip {"texts": "...", "tooltip": "...", "color": "up"}. Pills at the bottom of the card: texts or Chip.
- `link`: text. A block or heading link such as `"page/name"` (see the links guide): the whole card leads there. Needs a `title`, which is the link's text.

### Select

Tab or dropdown selector — shows one child block at a time.
Holds `"blocks"`, a list of blocks (at least two: one per tab or option).

- `select_type`: one of "tabs", "dropdown", default `"tabs"`. `"tabs"` (default) or `"dropdown"` (or a SelectType).
- `style`: a tab style {"layout": "stretch", "sticky": true, ...}. How the tabs look: a TabStyle (layout, size, variant…). Tabs only.

### Toggle

Collapsible container — hidden by default, expanded on click.
Holds `"blocks"`, a list of blocks (at least one).

### Page

Top-level page tab.
Holds `"blocks"`, a list of blocks (at least one).

- `title`: text. The page's tab title.

### BigNumber

KPI display block — shows a headline metric with optional change indicator.

- `heading` (required): text. The metric's name.
- `value` (required): text or a number. The headline value.
- `change`: text. Optional change to show under the value, e.g. `"+3%"`.
- `is_upward_change`: true or false. The arrow: `True` shows ▲, `False` shows ▼, `None` shows no arrow.
- `is_positive_intent`: true or false. The colour: `True` is green (good news), `False` is red (bad news). Leave it `None` and the colour follows the arrow (▲ green, ▼ red); with neither flag the change is shown neutral, in the theme's muted colour.
- `prev_value`: a number. The value to compare with: briefing computes the change, its arrow and its colour (instead of `change`, `is_upward_change` and `is_positive_intent`). Needs a numeric `value`.
- `change_as`: one of "percent", "absolute", "points", default `"percent"`. How a computed change is shown: `"percent"` (`+10.5%`), `"absolute"` (the difference, in `format`) or `"points"` (the difference of two rates in percentage points, `-0.3 pt`).
- `higher_is_better`: true or false, default `true`. With `prev_value`: `True` shows a rise in green, `False` a fall (churn, cost, latency).
- `format`: text. How `value` is shown: a format string such as `"{:,.0f}"`, `"$ {:.1f}M"` or `"{:.1%}"`, or a function.
- `sparkline`: a list of numbers or null. A short series of numbers drawn as a trend line under the value (a list, a Series or an array); missing values leave gaps.
- `accent`: text. A colour stripe on the card's left edge: `"up"`, `"down"` or `"accent"` (the theme's colours) or a CSS colour.

### Alert

Styled callout / alert block.

- `message` (required): text. The alert's text.
- `level`: one of "info", "success", "warning", "error", default `"info"`. `"info"`, `"success"`, `"warning"` or `"error"` (or an AlertLevel).
- `title`: text. Optional bold title above the message.

### Chips

A wrapping row of pills: labels, tags, or values that rose or fell.

- `items` (required): a list of texts or a chip {"texts": "...", "tooltip": "...", "color": "up"}. The pills: text, or Chip for a tooltip or a colour.

### Legend

One legend for the blocks that share a Scale, such as a page of calendars.

- `scale` (required): a scale {"colors": ["#...", "#..."], "domain": [0, 100]}. A Scale with a `domain`: the values its colours stand for, or the categories of a named palette (one swatch each).
- `title`: text. A short line above the legend, with inline Markdown as in captions.
- `events`: a list of texts or a table {"columns": [...], "rows": [[...]]}. Dates to list, as `CalendarHeatmap(events=)` takes them, with their colours.

### Banner

Markdown text over a background image: a report cover, a section opener or a social card.

- `text` (required): text. Markdown, rendered exactly like Text.
- `image` (required): an image file path or a data: URI. A file path, or the image bytes (PNG, JPEG, GIF, WebP or SVG).
- `text_position`: a number, default `50`. 0–100: where the text column begins (`side="right"`) or ends (`side="left"`), in percent of the banner's width.
- `opacity`: a number, default `80`. 0–100: how much the veil covers the image under the text: 100 is a plain text panel, around 80 leaves the image faintly visible. No readability warning is given at any value; that is your call.
- `side`: one of "left", "right", default `"right"`. `"right"` (text on the right, image clear on the left) or `"left"`. Ignored when `fade=False`.
- `fade`: true or false, default `true`. `True` fades the veil in over 20 % of the width before the text; `False` covers the whole image with one veil at `opacity`.
- `height`: text or a whole number, default `"16rem"`. CSS height such as `"16rem"` (default) or a number of pixels.
- `focus`: a list of 2 numbers, default `[50, 50]`. `(x, y)` in percent: the point of the image kept in view when it is cropped.
- `alt`: text. A description of the image; by default it is decorative.
- `kicker`: text. One short line of plain text above `text`, smaller and in the theme's muted colour, such as `"Data through Nov 20, 2026"`. Escaped, never Markdown.
- `max_width`: a whole number. Scale the image down to this many pixels wide, if it is wider (needs `pip install "briefing[pillow]"`).
- `format`: one of "webp", "jpeg", "png". Re-encode the image as `"webp"`, `"jpeg"` or `"png"` (Pillow too).
- `quality`: a whole number, default `80`. 1 to 100, for WebP and JPEG.

### Image

A picture: a PNG, JPEG, GIF, WebP or SVG file, embedded in the report.

- `image` (required): an image file path or a data: URI. A file path, or the image's bytes (PNG, JPEG, GIF, WebP or SVG).
- `caption`: text. Optional caption below the image.
- `alt`: text. What the image shows, for readers who can't see it; by default the caption. With neither, the image is decorative.
- `width`: text or a whole number. A CSS width such as `"60%"` or `"20rem"`, or a number of pixels.
- `max_width`: a whole number. Scale the image down to this many pixels wide, if it is wider (needs `pip install "briefing[pillow]"`).
- `format`: one of "webp", "jpeg", "png". Re-encode the image as `"webp"`, `"jpeg"` or `"png"` (Pillow too).
- `quality`: a whole number, default `80`. 1 to 100, for WebP and JPEG.

### Attachment

A file readers download from the report: any file, some bytes, or a dataframe as CSV.

- `file` (required): a file path or a data: URI or a table {"columns": [...], "rows": [[...]]}. A file path (any type), bytes (then `filename` is needed), or a dataframe, which downloads as CSV in the format of `DataTable`'s CSV button: raw values, UTF-8 with a byte-order mark.
- `filename`: text. The name the file downloads as; by default the file's own name, or for a dataframe the block's `name` (else `data`) with `.csv`.

### Plot

Chart / figure block — library agnostic.

- `figure` (required): a chart {"plotly": {...}} or {"vega-lite": {...}}. A Plotly, Altair, Matplotlib (or Seaborn / Plotnine) or Bokeh figure.
- `caption`: text. Optional caption shown below the chart.
- `responsive`: true or false, default `true`. Let the chart fill the width of its container. Size the figure in its plotting library, e.g. Matplotlib's `figsize=(w, h)`.

### Table

Static HTML table rendered from a dataframe or a pandas Styler.

- `data` (required): a table {"columns": [...], "rows": [[...]]}. A dataframe (as for DataTable) or a pandas `Styler`, kept as-is.
- `caption`: text. Optional caption below the table.

### DataTable

Interactive, sortable and searchable table rendered from a pandas DataFrame.

- `df` (required): a table {"columns": [...], "rows": [[...]]}. The data: pandas, polars, pyarrow, anything with the dataframe interchange protocol, or a dict of columns.
- `caption`: text. Optional caption below the table.
- `max_rows`: a whole number, default `10000`. Rows beyond this are dropped with a warning.
- `formats`: an object {"<column>": text}. How to show a column's values: `{"revenue": "€ {:,.0f}", "share": "{:.1%}", "day": "{:%d %b %Y}"}`, Python format strings (as in pandas' `Styler.format`) or functions. Cells still sort by their raw value; missing values stay empty.
- `links`: an object {"<column>": text}. Columns whose cells link somewhere: `{"doi": "https://doi.org/{}", "title": "{url}"}`, a URL template where `{}` is the cell's value and `{url}` the value of the column `url` in the same row. Only `http(s)://` and `mailto:` URLs make links (anything else stays text, with a warning); they open in a new tab.
- `wrap`: true or false or a list of texts, default `false`. Columns whose text wraps onto several lines, instead of making the table scroll sideways: a list of column names, or `True` for every column.
- `download`: true or false, default `false`. Put a "CSV" button above the table: it downloads the rows matching the reader's search, in their order, with their raw values (not the formatted text), as a file named after the table's `name` or caption.

### Code

Syntax-highlighted code block.

- `code` (required): text. The source code.
- `language`: text, default `"python"`. Language for syntax highlighting (any Pygments lexer name, e.g. `"python"`, `"sql"`); an unknown language is shown as plain text.
- `caption`: text. Optional caption below the block.

### Formula

LaTeX formula block, converted to MathML when the report is rendered.

- `formula` (required): text. A LaTeX expression, without `$` or `\(` delimiters.
- `caption`: text. Optional caption below the formula.

### HTML

Raw HTML fragment block.

- `html` (required): text. The HTML fragment, inserted as-is.

### lab.DataProfile

Per-column statistical profiling block.

- `df` (required): a table {"columns": [...], "rows": [[...]]}. The data, as any dataframe briefing accepts.
- `missing_threshold`: a number, default `0.2`. Share of missing values (0–1) above which a column's missing count is highlighted in red.
- `max_categories`: a whole number, default `20`. Most frequent values shown for categorical columns.

### lab.DataDive

Interactive dot explorer — similar to Google's Facets Dive.

- `df` (required): a table {"columns": [...], "rows": [[...]]}. The data, as any dataframe briefing accepts.
- `x`: text. Column on the X axis at first (the viewer can change it).
- `y`: text. Column on the Y axis at first.
- `color`: text. Column that colours the dots at first.
- `facet_row`: text. Accepted but not drawn yet (a warning says so); planned for DataDive v2.
- `facet_col`: text. Accepted but not drawn yet (a warning says so); planned for DataDive v2.
- `layout`: one of "scatter", "tile", default `"scatter"`. `"scatter"` (two axes) or `"tile"` (packed dots per cell).
- `max_rows`: a whole number, default `10000`. Larger frames are sampled down to this many rows, with a warning.

### lab.CalendarHeatmap

GitHub-style calendar heatmap: one cell per day, weeks as columns.

- `df` (required): a table {"columns": [...], "rows": [[...]]}. The data, as any dataframe briefing accepts (pandas, polars, pyarrow…).
- `date` (required): text. Column holding the date or timestamp of each row.
- `value`: text. Column to aggregate per day; `None` counts the rows.
- `agg`: one of "sum", "mean", "median", "min", "max", "count", default `"sum"`. How to aggregate `value`: `"sum"`, `"mean"`, `"median"`, `"min"`, `"max"` or `"count"`.
- `group`: text. Column to split by: one calendar per group, stacked, on one shared colour scale.
- `views`: a list of values from "days", default `["days"]`. Only `("days",)`; the hour view was removed in 0.5.0 (use TimeHeatmap).
- `tz`: text. A time zone such as `"America/Montreal"`. Converts timezone-aware timestamps only; naive timestamps and plain dates are taken as already local.
- `colors`: text or a list of texts or a scale {"colors": ["#...", "#..."], "domain": [0, 100]}, default `"github"`. `"github"`, a list of CSS colours (low to high, spread over the data), or a Scale (the same colours for the same values everywhere).
- `week_start`: one of "monday", "sunday", default `"monday"`. `"monday"` or `"sunday"`: the first row of the grid.
- `expected`: a number or a table {"columns": [...], "rows": [[...]]}. A target per day, flagged when a day is below it (days with no data count as below): a number, a Series indexed by date, or a DataFrame with the `date` column, an `expected` column and, with `group`, the group column.
- `events`: a list of texts or a table {"columns": [...], "rows": [[...]]}. Dates to mark: a list of dates, or a DataFrame with `start` and optional `end`, `label` and `color` (a CSS colour; the accent by default) columns. A day is outlined and dotted, a span drawn as a band.
- `on_click`: one of "rows". `"rows"` lists the rows behind a day in a panel when it is clicked (up to `ROWS_PER_CELL` per cell); `None` for none.
- `start`: text. The first day shown (`"2026-05-19"` or a date), whatever the data covers; `None` starts at the first day with data or an event. Rows before it are left out, with a warning.
- `end`: text. The last day shown; `None` ends at the last day with data or an event. Rows after it are left out, with a warning. Calendars with the same `start` and `end` line up week for week.
- `group_order`: a list of texts. Group names to draw first, in this order (e.g. `["Worldwide", "United States"]`); other groups follow by name. Needs `group`; a name that isn't a group is an error.
- `legend`: true or false, default `true`. `False` hides this block's legend (show one Legend instead).

### lab.TimeHeatmap

When something usually happens: a grid that crosses two units of one date column.

- `df` (required): a table {"columns": [...], "rows": [[...]]}. The data, as any dataframe briefing accepts (pandas, polars, pyarrow…).
- `date` (required): text. Column holding the date or timestamp of each row.
- `rows` (required): one of "hour", "weekday", "day", "week", "month", "quarter", "year". The unit down the side: `"hour"` (0–23), `"weekday"`, `"day"` (of the month), `"week"` (ISO week), `"month"`, `"quarter"` or `"year"`.
- `columns` (required): one of "hour", "weekday", "day", "week", "month", "quarter", "year". The unit across the top, one of the same, and not the same as `rows`.
- `value`: text. Column to aggregate per cell; `None` counts the rows.
- `agg`: one of "sum", "mean", "median", "min", "max", "count", default `"sum"`. How to aggregate `value`: `"sum"`, `"mean"`, `"median"`, `"min"`, `"max"` or `"count"`. Sums and counts are averaged per occurrence.
- `group`: text. Column to split by: one grid per group, stacked, on one shared colour scale.
- `tz`: text. A time zone such as `"America/Montreal"`. Converts timezone-aware timestamps only; naive timestamps and plain dates are taken as already local.
- `colors`: text or a list of texts or a scale {"colors": ["#...", "#..."], "domain": [0, 100]}, default `"github"`. `"github"`, a list of CSS colours (low to high, spread over the data), or a Scale (the same colours for the same values everywhere).
- `week_start`: one of "monday", "sunday", default `"monday"`. `"monday"` or `"sunday"`: the first weekday of a `weekday` axis.
- `on_click`: one of "rows". `"rows"` lists the rows behind a cell in a panel when it is clicked (up to `ROWS_PER_CELL` per cell); `None` for none.
- `group_order`: a list of texts. Group names to draw first, in this order (e.g. `["Worldwide", "United States"]`); other groups follow by name. Needs `group`; a name that isn't a group is an error.
- `legend`: true or false, default `true`. `False` hides this block's legend (show one Legend instead).

## Decks

A deck (`bf.deck.Deck` in Python) puts the same blocks on slides. Its JSON has `"slides"` in
place of `"blocks"`; each slide is an object with its own `"blocks"`, written as in a report:

```json
{"briefing": 1, "footer": "Sales analytics", "slides": [
  {"title": "Q3 review"},
  {"title": "Summary", "name": "summary", "blocks": [
    {"type": "Text", "text": "Revenue grew in **every** region."},
    {"type": "Group", "columns": 2, "blocks": [
      {"type": "BigNumber", "heading": "Revenue", "value": 4200000, "prev_value": 3900000, "format": "${:,.0f}"},
      {"type": "BigNumber", "heading": "Margin", "value": 0.31, "format": "{:.0%}"}
    ]}
  ]}
]}
```

- A slide needs `"blocks"`, a `"title"`, or both; a slide with only a title is a section slide.
- Slides hold any block but a Page. Lay them out with Group (columns), Select (tabs) or Card.
- A slide's `name` is its link (`#summary`) and scopes names as a page does: a block named
  `margin` in that slide links as `#summary/margin`, unique within its slide.
- Check a deck as a report: `python -m briefing validate deck.json`, or `bf.validate(spec, data)`.
  Build it with `bf.deck.from_spec(spec, data)`; `bf.to_spec(deck)` writes it.

The deck's options:

- `footer`: text. Text before the "Made with briefing" line at the foot of every slide, such as a team name.

A slide's options:

- `title`: text. The slide's heading, with inline Markdown as in captions.
- `name`: a name (a letter, then letters, digits, _ or -). Stable slide id (letters, digits, `_` and `-`): its link in the deck (`#name`).

## Diagnostics

`validate` lists every problem with a severity, a code, a path (a JSON Pointer such as
`/blocks/1/columns`), a message and often a hint. An error means the report can't be built
or rendered; a warning means it renders but is worth a look.

- `invalid-json` (error): The text isn't valid JSON.
- `unreadable-file` (error): The file can't be read.
- `not-a-spec` (error): The JSON isn't a report object {"briefing": 1, "blocks": [...]}.
- `missing-version` (error): There is no "briefing": 1.
- `unsupported-version` (error): A format this briefing doesn't read: upgrade briefing.
- `unknown-type` (error): No block has this type; the hint suggests the closest.
- `missing-type` (error): A block without "type".
- `not-a-block` (error): Something in a blocks list that isn't an object.
- `unknown-option` (error): The block has no such option; the hint suggests the closest.
- `missing-option` (error): A required option is missing.
- `wrong-type` (error): An option's value has the wrong type; the message says what it takes.
- `unknown-ref` (error): A reference to an object not passed in data.
- `invalid-data` (error): An inline table, chart or image can't be read.
- `invalid-value` (error): The block itself rejects a value (widths that don't match columns, a column missing from the table...).
- `mixed-pages` (error): Page blocks mixed with other blocks at the top level.
- `misplaced-page` (error): A Page inside another block: pages only go at the top.
- `empty-container` (error): A report, Page or Toggle without blocks.
- `duplicate-name` (error): A name (or a heading's {#name}) used twice in one page.
- `name-clash` (error): A name that matches an id briefing makes up, such as sel-1.
- `render-error` (error): A block fails to render, or a Plot can't draw its figure.
- `too-deep` (error): Blocks nested too deeply to check.
- `internal-error` (error): A bug in briefing itself; please report it.
- `too-few-panels` (warning): A Select with fewer than two panels.
- `missing-label` (warning): A Select panel without a label, or a Page without a title.
- `deprecated` (warning): An option that will go away; the message says what to use.
- `block-warning` (warning): What a block warns about: rows dropped, a sample drawn, LaTeX it can't convert...
- `placeholder` (warning): A block with nothing to draw shows a warning box instead.
- `too-big` (warning): The rendered report is bigger than max_size (10 MB by default); the message names its largest parts.

## A complete example

```json
{
  "briefing": 1,
  "footer": "Analytics team",
  "blocks": [
    {"type": "Page", "title": "Summary", "name": "summary", "blocks": [
      {"type": "Text", "text": "# Q1 sales\n\nRevenue grew in every region but **South**."},
      {"type": "Group", "columns": 3, "blocks": [
        {"type": "BigNumber", "heading": "Revenue", "value": "$1.05M", "change": "+8%", "is_upward_change": true},
        {"type": "BigNumber", "heading": "Orders", "value": 8421},
        {"type": "Alert", "message": "South is 12% below plan.", "level": "warning", "title": "Watch"}
      ]},
      {"type": "Plot", "caption": "Revenue by region", "figure": {"plotly": {
        "data": [{"type": "bar", "x": ["North", "South", "East"], "y": [412000, 287500, 351200]}]
      }}}
    ]},
    {"type": "Page", "title": "Detail", "name": "detail", "blocks": [
      {"type": "Select", "blocks": [
        {"type": "DataTable", "label": "Regions", "df": {"columns": ["region", "revenue"],
          "rows": [["North", 412000], ["South", 287500], ["East", 351200]]}},
        {"type": "Toggle", "label": "Method", "blocks": [
          {"type": "Text", "text": "Revenue is net of returns, in USD."}
        ]}
      ]}
    ]}
  ]
}
```
