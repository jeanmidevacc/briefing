# Changelog

All notable changes to `briefing` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- At release time: rename [Unreleased] to the version, add the date, and
     open a fresh [Unreleased] section above it. -->

## [Unreleased]

### Added

- `bf.deck`: slide decks written from briefing's blocks (#197). `bf.deck.Deck(*slides,
  footer=)` holds `bf.deck.Slide(*blocks, title=, name=)` objects, each holding any block
  but a `Page`; a slide with only a title is a section slide. A deck has a JSON form,
  `{"briefing": 1, "slides": [{"title": ..., "blocks": [...]}]}`: `bf.to_spec(deck)` writes
  it, `bf.deck.from_spec(spec, data)` reads it, and `bf.validate` and
  `python -m briefing validate` check it. A named slide scopes names as a page does
  (`#summary/margin`).
- `bf.deck.save(deck, path)` and `bf.deck.to_html(deck)`: a deck as one self-contained HTML
  page in the report's theme, every block drawn by its own renderer (#197). Slides are
  drawn at 1280 × 720 and scaled to the window; the arrow keys, space and Page Up/Down move
  between them, `O` shows every slide, `F` goes full screen, and the address bar holds the
  slide's number (`#3`) or a name. What doesn't fit a slide shrinks, down to 70%, then
  scrolls with a "Doesn't fit" mark; a slide with more than about 120 words of text warns.
  A DataTable on a slide shows 10 rows a page.
- Printing a deck gives one slide per page, each 1280 × 720 (13.33 × 7.5 in, a 16:9
  slide), every slide as it shows: its chosen tab, its table's page (#197).
  `bf.deck.save_pdf(deck, path, slide=)` writes that PDF and `bf.deck.save_image(deck,
  path, slide=, scale=)` one image per slide (`q3_01.png`, …), from a `Deck` or a saved
  deck. `python -m briefing render` builds a deck from JSON with `"slides"`, and
  `python -m briefing pdf` and `image` export a saved deck, picking slides with `--slide`.

### Changed

- The JSON Schema's root accepts a report or a deck: the report's definition moved to
  `$defs/report`, next to `$defs/deck` and `$defs/slide`. Report JSON is unchanged and still
  format 1.

## [0.6.1] - 2026-11-22

### Added

- `bf.from_markdown(path_or_text, values=, blocks=, pages=)`: a report written in Markdown,
  with `::: block <name>` slots that Python fills and `{name}` values; errors name their
  line, and `pages=True` starts a page at each `# Heading` (#191).
- `python -m briefing new <folder>`: a small report project that runs as it is (a build
  script, its Markdown and its theme), and `bf.run(build, out=...)`, which gives a build
  script its command line: `--open`, `--max-size`, `--spec` to save its JSON, and `--diff`
  to show what changed since a saved run (#193).

## [0.6.0] - 2026-11-22

### Added

- `bf.Scale(colors, domain=, center=, steps=)`: a colour scale whose colours mean the same
  values in every block that uses it, mixed in OKLab so equal steps in value look like
  equal steps in colour; the heatmaps take it as `colors=`, and calling it with a value
  gives that value's colour. `bf.color` has the OKLab helpers (`ramp`, `mix`,
  `lightness`, …) (#175).
- `bf.Legend(scale, title=, events=)`: one legend for the blocks that share a `Scale`, and
  `legend=False` on `CalendarHeatmap` and `TimeHeatmap` to hide their own (#177).
- `bf.color.check(colors, background=, kind=)`: what makes a palette hard to read (low
  contrast, colours too close, colour-blind clashes, lightness that doesn't rise), with
  `bf.color.contrast`, `simulate` and `distance`; and `Formatting.from_accent(colour,
  dark=)`, a whole theme from one brand colour at WCAG contrast levels (#179).
- Charts in the report's theme: `Formatting.plotly_template()` and `Formatting.mpl_style()`
  give Plotly and Matplotlib the theme's font, colours and a categorical palette
  (`Formatting.categorical()`, checked for colour-blind readers). A `Scale` whose domain
  names categories is a named palette, such as party colours: `scale.mapping` feeds
  Plotly's `color_discrete_map`, and a `Legend` lists it (#39).
- `Text(text, values={...})` fills `{name}` and `{name:spec}` fields, each value shown exactly
  as written; `bf.fmt.date`, `span`, `percent` and `number` format values for prose; a
  heading ending in `{#auto}` links by a slug of its text, and `bf.slug` is public (#184).
- `Image` and `Banner` take `max_width=`, `format=` (`"webp"`, `"jpeg"`, `"png"`) and
  `quality=` to scale a picture down and re-encode it on the way in, with Pillow from a new
  extra, `briefing[pillow]`; the size warning suggests them when a picture is the heaviest
  part (#186).
- `bf.diff(old, new, keys=)`: what changed between two runs, as a report: numbers with their
  change, table rows added, removed and changed, text line by line, and blocks added or
  removed, matched by their link names. A run can be a `Briefing` or the JSON an earlier
  run saved (#30).
- `bf.email.Digest(...)` and `bf.email.to_message(digest, subject=...)`: a short digest of a
  few blocks built for mail apps (inline styles, charts as attached PNG images, a plain-text
  part, a button to the full report), as a standard `EmailMessage` you send your own way;
  `to_eml` writes it to a file to preview (#42).

### Changed

- The agent reference (`python -m briefing reference`, `llms-full.txt`) may now grow to
  100 KB, up from 25 KB, so every block keeps its full option list as the grammar grows.

### Deprecated

- The heatmaps' `center=`: pass `colors=bf.Scale([below, at, above], center=...)` instead.
  It warns from 0.6.0 and goes in 0.8.0 (#175).

## [0.5.0] - 2026-11-22

### Added

- `DataTable(wrap=["Note"])` (or `wrap=True`): long text wraps within a readable width
  instead of making the table scroll sideways (#151).
- `CalendarHeatmap` events take an optional `color` column (any CSS colour) for their dot,
  band, outline and legend entry; without it they keep the theme's accent (#152).
- `CalendarHeatmap(start=, end=)`: the first and last day shown, whatever the data covers,
  so calendars side by side line up week for week. Rows outside the span are left out with
  a warning naming how many; events outside it aren't drawn (#153).
- `group_order=[...]` on `CalendarHeatmap` and `TimeHeatmap`: the listed groups first, in
  that order, then the others by name (#154).
- `Banner(kicker="Data through Nov 20, 2026")`: one short muted line of plain text above
  the banner's text (#155).
- `bf.TabStyle(layout=, full_width=, sticky=, size=, variant=)`: how tabs look, for the
  page tabs (`Briefing(tabs=...)`) or one Select (`Select(style=...)`). Tabs can be
  centred or stretched to equal shares, run their line edge to edge, stay at the top while
  scrolling, come in three sizes, and be underlined, pills or boxed. Reports that set no
  style render as before (#22).
- `Briefing(header=bf.Header(subtitle=, author=, logo=, as_of=, tz=))`: a subtitle with
  inline Markdown, an author, an embedded logo, a "Data as of" date beside the render time,
  and a time zone for the times shown (#25).
- `BigNumber(prev_value=, change_as=, higher_is_better=, format=, sparkline=)`: the change,
  its arrow and its colour computed from the previous value (as a percent, an absolute
  difference or percentage points), the numbers formatted, and a small trend line (#35).
- `Group(min_width="16rem")`: as many cells per row as fit, each at least that wide, up to
  `columns` (#27).
- `bf.Chips([...])`: a wrapping row of pills, each text or a `bf.Chip(text, tooltip=, color=)`;
  `BigNumber(accent=)` puts a colour stripe on the card. Both take `"up"`, `"down"`,
  `"accent"` or a CSS colour; `Formatting(up_color=, down_color=)` set the theme's up and
  down colours, which a BigNumber's ▲ and ▼ now use too (#27).
- `bf.Card(*blocks, title=, icon=, tags=, link=)`: a framed box with a heading line around
  blocks stacked in one column; with `link=` the whole card leads to a block or heading
  (#27).

### Changed

- Captions, `Alert` titles and messages, and `BigNumber` headings render inline Markdown
  (bold, italics, code, links); raw HTML in them stays escaped, and block syntax stays text.
  A caption that already holds `*`, backticks or `[…](…)` may now be formatted: write `\*`
  to keep it literal (#26).
- The default report name, "Report", is no longer shown as a title: a report with an export
  menu and no name shows only the date and the menu (#25).
- On tablets (641–960 px wide, on screen), a `Group` of three or more columns shows two per
  row instead of squeezing every column; phones still stack, and print keeps every column
  (#27).
- Theme presets use only fonts every system has, so a preset looks the same to every reader
  (#28). Inter, DM Sans, IBM Plex Sans and Lora were named but never embedded, so most
  readers saw a fallback. The default is now the system UI font; `corporate()` a
  Helvetica-style sans, `minimal()` a geometric sans (Avenir, Corbel, URW Gothic),
  `ocean()` a humanist sans (Seravek, Calibri, Ubuntu) and `warm()` a serif (Charter,
  Cambria). Each stack names a font from macOS, Windows and Linux.

### Removed

- `CalendarHeatmap`'s hour view (`views=("hours",)` or `("days", "hours")`), deprecated
  since 0.2.2: it raises an error that points to `bf.lab.TimeHeatmap(df, date=...,
  rows="weekday", columns="hour")`. `views=("days",)` still works (#111).

### Fixed

- Alerts in dark themes: their backgrounds and text were fixed light colours; each level now
  keeps its hue mixed with the theme's background and text, readable (4.5:1) in every preset
  (#167).
- Dropdown Selects are accessible: the menu is named after the Select's `label` ("Choose a
  view" without one, not "Select view"), each panel is a region named after its option and
  tied to the menu with `aria-controls`, the keyboard switches panels as it moves through
  the options, and nested dropdowns keep to their own panels (#29).
- Tables read in dark themes: their stripes and the DataTable header hover were fixed light
  greys (`#fafafa`, `#f0f0f0`); they now take the theme's surface and border colours (#150).
- `CalendarHeatmap`: a multi-day event no longer outlines every day it covers, which hid the
  data under it; its band says where it runs, and its days still name it in their tooltip (#152).

## [0.4.1] - 2026-11-20

### Fixed

- A wide `DataTable` (long text, many columns) inside a `Group` or a `Page` widened the
  whole report instead of scrolling in its own box, since every page is a `Group`; a
  `Group`'s cells may now shrink below their content's width.
- `lab.TimeHeatmap`'s legend said "no such date" for grids with no blank cell, such as month
  by year; it now does only when a cell can't exist.

## [0.4.0] - 2026-11-20

### Added

- A copy-embed button for readers (#124). `bf.Briefing(..., export="embed")` puts a `</>`
  button on each page, labelled group, chart, table, text, number, alert, banner and lab
  block: it copies that part as an embed fragment (as `bf.stringify(..., full_html=False)`
  makes), CSS, scripts and chart runtime included, to paste into another page. What is
  copied is the report as it was made, not as clicks left it: the report carries a
  compressed copy of its untouched blocks. Where copying is refused, the code shows in a
  dialog. The buttons never print or export. A report without `"embed"` is unchanged.
- Reports as JSON (#31). `bf.to_spec(report)` gives a report's JSON form (each block as
  `{"type": "Text", ...}` with the constructor's parameters as keys) and the dataframes and
  figures it names by reference; `bf.from_spec(spec, data)` builds the report back, byte for
  byte the same. With `to_spec(..., inline=True)`, tables, Plotly and Altair charts and
  images go into the JSON when they come back exactly the same. `bf.validate(spec, data)`
  (or `bf.validate(report)`) returns every problem as a `bf.Diagnostic` with a code, a JSON
  Pointer to where it is, a message and a hint, and never raises: unknown types and
  options, wrong types, unknown references, duplicate names, empty containers, a block's
  own checks and warnings, and whatever stops the report from rendering. `bf.schema()`
  returns the format's JSON Schema, which also ships as `briefing/schema/v1.json`. A
  `Select`'s `type` is written `"select_type"` in JSON, since `"type"` names the block.
- A reference for agents, shipped with the package (#32). `python -m briefing reference`
  prints it: how to write, check and render a report's JSON, every block and option with
  its type, default and description, the diagnostic codes and a complete example. It is
  generated from the block classes, so it matches the installed version. The command line
  gains `validate` (exit status 1 on an error, `--json` for a JSON list) and `render` for
  report JSON, both taking referenced tables as `--data name=file.csv` (or `.parquet`), and
  `skill --install`, which writes a Claude Code skill pointing to the reference into
  `.claude/skills/briefing/`. The docs publish the reference as `llms-full.txt`, with an
  `llms.txt` index.
- A size budget (#38). `bf.save` and `bf.stringify` warn when a report is bigger than
  `max_size`, 10 MB by default, and name its largest parts with their place in the
  report: `DataTable "orders" at /blocks/2 (9.1 MB), the Plotly runtime (2.0 MB)`. Chart
  runtimes and the copy-embed data count. `max_size="25 MB"` or a number of bytes changes
  it, `None` turns it off. `bf.validate` and `python -m briefing validate --max-size`
  report it as a `too-big` warning.
- Big tables weigh less (#38). A `DataTable` of more than 1,000 rows keeps its first page
  in the HTML and its rows compressed, unpacked by the page's script as the report opens:
  10,000 rows × 10 columns of decimals go from 5.0 MB to 1.8 MB, of whole numbers from
  1.3 MB to 0.3 MB. It sorts, searches, pages and prints as before; without JavaScript it
  shows its first 25 rows and says how many more there are. Up to 1,000 rows, nothing
  changes.
- Chart runtimes are compressed (#38). Plotly's and Vega's runtimes are stored deflated
  and unpacked by the report as it opens, before any chart draws, with no network and no
  newer browser feature: a report with one Plotly chart goes from 4.9 MB to 2.0 MB, one
  with an Altair chart from 0.9 MB to 0.5 MB. Fragments, `embed_assets` and copy-embed
  copies carry them the same way, and charts look and behave as before.
- Number formats and links in `DataTable` cells (#33). `formats={"revenue": "€ {:,.0f}",
  "share": "{:.1%}", "day": "{:%d %b %Y}"}` shows a column with a Python format string or a
  function, while cells still sort by their value. `links={"doi": "https://doi.org/{}",
  "title": "{url}"}` makes a column's cells links, from the cell's value or another column
  of the row; only `http(s)://` and `mailto:` URLs become links (the rest stays text, with
  a warning), and they open in a new tab. Big tables pack the formatted text and the links.
- A CSV download for `DataTable` (#34). `download=True` puts a "CSV" button above the table:
  it downloads the rows matching the reader's search, in their order, every page, with raw
  values rather than the formatted text, as UTF-8 with a byte-order mark; formula-like text
  is escaped. Off by default; it never prints or appears in exports.
- `Image` and `Attachment` blocks (#36). `bf.Image(path_or_bytes, caption=, alt=, width=)`
  embeds a PNG, JPEG, GIF, WebP or SVG as a data URI, at its natural size or `width`,
  described by `alt` or its caption. `bf.Attachment(path)`, `bf.Attachment(data,
  filename=)` or `bf.Attachment(dataframe, filename="orders.csv")` puts a file in the report
  for readers to download, with no server: any file type, text files stored compressed, a
  dataframe as the same CSV as a `DataTable`'s button. Both have a JSON form, a copy-embed
  button, and count towards the size budget.
- `lab.TimeHeatmap`, for time patterns (#111). `bf.lab.TimeHeatmap(df, date=, rows="weekday",
  columns="hour")` crosses two units of one date column (`hour`, `weekday`, `day`, `week`,
  `month`, `quarter`, `year`): when runs happen, seasonality, month-end effects, year over
  year. Counts and sums are averaged per occurrence of their cell, so a weekday that
  appears more often doesn't count double; cells that can't exist (31 February) are left
  blank. It shares the calendar's options, legend, tooltip, width fitting and
  `on_click="rows"`.

### Changed

- pandas is a core dependency (#40): `Table`, `DataTable`, the lab blocks and tables written
  in JSON need it, even for polars data. `import briefing` still imports it only when a
  table needs it. A chart from a library older than briefing supports (Plotly 5, Altair 5,
  Matplotlib 3.7, Bokeh 3) shows which version it needs in place of the chart.

- `Banner` no longer warns about images over 2 MB on its own: the size budget names a
  heavy image when the report is over it (#38). `Banner.MAX_IMAGE_BYTES` is gone.

### Deprecated

- `CalendarHeatmap`'s hour view (`views=("hours",)`), deprecated since 0.2.2, now has its
  replacement, `lab.TimeHeatmap(rows="weekday", columns="hour")`, and goes in 0.5.0 (#111).

### Removed

- The extras that added nothing (#40): `[pandas]` (pandas is in the core), `[plotly]`, `[bokeh]`,
  `[matplotlib]` and `[charts]` (`Plot` uses the library you already have), and `[email]`
  (there is no email feature yet; it comes back with it). An old `pip install
  "briefing[plotly]"` still installs briefing, with a warning from pip. `[altair]`, `[lab]`,
  `[image]`, `[docs]` and `[dev]` stay.

- `Briefing(export="pdf")`, deprecated since 0.2.4, now raises an error that says what to use
  instead: Ctrl+P (or ⌘P) to print, with the same print layout, or `bf.save_pdf` for a file.

## [0.3.0] - 2026-11-20

### Added

- Every report says which version of briefing made it: a footer line, "Made with briefing
  0.3.0", and `<meta name="generator">` in the page head. `Briefing(footer="Analytics team")`
  puts text before that line; the line itself can't be turned off (#23).
- Fragments to embed in other pages, like Plotly's `full_html=False` (#122).
  `bf.stringify(chart, full_html=False)` (and `bf.save(..., full_html=False)`) gives one
  `<div class="bf-embed">` that carries its theme, scopes every CSS rule to itself, starts
  every id with its `embed_id` and initialises only its own scripts, so several fragments,
  dark and light, share a page. `include_assets=False` with `bf.embed_assets(blocks)` sends
  the CSS, scripts and chart runtimes once. A host's rules for plain elements and a changed
  root font size don't reach the fragment. New guide: "Embed in other pages".
- Links to pages, tabs and headings (#24). A block's `name=` is now its link:
  `report.html#detail` opens the page named `detail`, `#detail/by-region` a tab or block
  named `by-region` in it, and `## Methodology {#methodology}` names a heading
  (`#detail/methodology`). Opening a link selects its page and tab, opens any toggle around it
  and scrolls to it, also offline. Choosing a tab puts its link in the address bar without a
  history entry, so a reload keeps it open. Named headings show a copy-link icon on hover. A
  name used twice in one page raises an error.
- `Formatting.to_css_vars(selector=":root")` takes the selector to put the theme on, so a
  theme can apply to one element instead of the whole page (#123).

### Changed

- The report's scripts now work inside the root they are given instead of on the whole page:
  `window.briefing.init(root)` wires up tabs, toggles, tables, calendars and the export menu
  in that root, once. A full report calls `briefing.init(document)`, so it behaves as before;
  this lets two briefing outputs share a page later (#123).

### Removed

- The names deprecated in 0.2 are gone, as their warnings announced: `bf.Blocks`,
  `bf.BaseBlock`, `bf.save_report` and `bf.stringify_report` (use `bf.Briefing`, `bf.Block`,
  `bf.save` and `bf.stringify`), and `bf.DataProfile` / `bf.DataDive` at the top level (use
  `bf.lab.DataProfile` / `bf.lab.DataDive`). Each old name now raises an `AttributeError` that
  says what to use instead. `Plot(scale=...)`, which had no effect, is removed too: size the
  figure in its plotting library.

### Fixed

- A `Text` or `HTML` block that leaves a comment, a tag or a `<script>`, `<style>` or
  `<textarea>` open, such as a line starting with `<!-- draft note`, no longer hides
  everything after it: the later blocks, the footer and the report's script, so tabs stopped
  working. briefing closes what is left open at the end of the block. Found by the new
  property tests (#45).
- `bf.lab.DataProfile` no longer fails with "cannot convert float NaN to integer" on a
  numeric column whose values span more than the largest float, such as -1e308 and 1e308.
  The new property tests found it (#45).

## [0.2.4] - 2026-11-17

### Fixed

- The export menu's "Save as PNG" keeps a 32 px margin of page background around the report,
  so content no longer touches the edge of the image (#119).

### Deprecated

- `bf.Briefing(..., export="pdf")` no longer adds a "Print" button: it only opened the
  browser's print dialog, which Ctrl+P / ⌘P opens with the same print layout. It still runs,
  with a `DeprecationWarning`; from 0.4.0 it raises an error. Use `export="png"` for the
  "Save as PNG" button, and `bf.save_pdf` for a PDF file (#119).

## [0.2.3] - 2026-11-07

### Fixed

- `Group` rejects a `columns` that isn't a whole number of 1 or more, and `widths` that
  aren't positive numbers, with a `BriefingError`. They used to be accepted and wrote invalid
  CSS, so the browser dropped the layout without saying so (#98).
- `Table` with a pandas `Styler` gives the same bytes on every run: its ids and CSS selectors
  come from the report instead of the random uuid pandas picks. The `Styler` you pass keeps
  its own uuid (#101).

## [0.2.2] - 2026-11-04

### Added

- `lab.CalendarHeatmap`: hovering a day, an hour or an event band shows a tooltip at once,
  styled with the theme: the date (now with its weekday) in bold, the exact value, "below
  target …" and the day's events. It also opens on keyboard focus and on tap, stays inside
  the window, and never prints. The browser's slower built-in tooltip no longer doubles up;
  without JavaScript it is still there (#109).

### Changed

- `lab.CalendarHeatmap` names every weekday row of the day calendar, not just Mon, Wed
  and Fri (#113).

### Deprecated

- `lab.CalendarHeatmap`'s hour view, `views=("hours",)` or `("days", "hours")`, raises a
  `DeprecationWarning`. It still works; a dedicated time-pattern heatmap (weekday × hour,
  weekday × month, …) is planned to replace it, and the hour view will be removed in 0.4.0
  at the earliest, never before that replacement ships (#111).

### Fixed

- `lab.CalendarHeatmap(week_start="sunday")` put each weekday label one row off ("Sun"
  on the Monday row); every label now sits on its own row (#113).
- `lab.CalendarHeatmap` shows values exactly: a non-integer of 10,000 or more read
  `1.235e+04` in the tooltip and the legend; it now reads `12,345.67` (#109).

## [0.2.1] - 2026-11-04

### Changed

- `lab.CalendarHeatmap` fits the width available to it, the report's or its `Group`
  column's, instead of a fixed size: a year fills a full-width report, and in a column it
  shrinks to fit instead of widening the column and overflowing the page. Cells stay
  between 0.6× and 2× their natural 11 px (a short range stops at 2×; below 0.6× the
  calendar scrolls inside its block); labels change size at half that rate and legend
  swatches follow the cells. When printed it shrinks to fit the sheet instead of being cut
  off (#106).

## [0.2.0] - 2026-11-04

### Added

- Printing a report (or saving it as PDF from the browser) shows everything: every
  page and tab prints under its label, with each top-level `Page` on a new sheet;
  toggles print open; search boxes, pagination, tab bars, dropdowns and DataDive
  selectors are hidden; a `DataTable` prints up to 1,000 rows matching its search,
  with a note giving the total; charts are resized to the paper's width and KPI
  groups, charts and alerts avoid splitting across sheets; colours print. The
  screen layout is restored afterwards (#37).
- `bf.save_image(report, "q1.png", page="all")` renders report pages as PNG, JPEG or
  WebP in headless Chromium, offline: one image per top-level `Page` (named after it),
  or one page by title, `name` or index; `width` and `scale` set the pixel size;
  `size="og" | "square" | "portrait"` shrinks the page to fit a social-card size
  without cropping; `expand=True` opens toggles first. Accepts a `Briefing` or a saved
  `.html`. New extra: `pip install "briefing[image]"` (Playwright), then
  `playwright install chromium` (#49).
- `bf.save_pdf(report, "q1.pdf", page="all", paper="a4", landscape=False)` writes the
  report as one PDF with the print layout: each top-level page on a new sheet, text
  selectable, links clickable, charts vector. One page by title, `name` or index;
  `paper` is `a4`, `letter`, `legal`, `a3` or `a5` (#49).
- Command line for saved reports: `python -m briefing image report.html --page all -o out/`
  and `python -m briefing pdf report.html -o report.pdf`, with the same options as
  `save_image` / `save_pdf` and `--help` (#49).
- Opt-in export menu: `bf.Briefing(..., export=("png", "pdf"))` adds "Save as PNG" (the
  open page, drawn in the reader's browser at 2×, no library, no network) and "Print"
  to the report header. Reports without `export=` contain no export code. Best effort:
  Bokeh's iframe charts and WebGL Plotly traces come out blank in the PNG. The menu
  never appears in prints, PDFs or `save_image` images (#49, #100).
- `bf.lab.CalendarHeatmap(df, date="run_at", value=None, agg="sum")`: a GitHub-style
  calendar, one cell per day and weeks as columns, drawn as SVG in Python. It counts
  rows or aggregates a value per day; runs continuously across year boundaries with
  month labels and a year marker; shows days without data differently from zeros;
  `group=` stacks one calendar per group on a shared scale; `colors=` replaces the
  GitHub greens and `center=` gives a diverging scale; `expected=` (a number, a
  date-indexed Series or a DataFrame) flags days below target; `events=` marks single
  days and multi-day spans; each day has a tooltip (#19).
- `CalendarHeatmap(views=("days", "hours"))` adds a 7 × 24 weekday-by-hour grid, with
  tabs between the views, and `tz="America/Montreal"` converts timezone-aware timestamps
  (naive timestamps and plain dates are left on their own day) (#19).
- `CalendarHeatmap(on_click="rows")`: clicking a day or an hour (or pressing Enter on
  it) lists the rows behind it in a panel, shown as plain text, up to 50 per cell with a
  note when there are more (#19).
- `bf.Banner(md, image=..., text_position=50, opacity=80, side="right", fade=True)`: markdown
  text over a background image, as a report cover or section opener. The text sits on a
  veil of the theme background that eases in over 20 % of the width; `height`, `focus`
  and `alt` are optional; at phone width the image stacks above the text. The image (a
  path or bytes) is embedded once; files over 2 MB warn. `Formatting` gains a
  `--bf-bg-rgb` token for the veil (#50).
- `bf.Banner(..., fade=False)`: one uniform veil at `opacity` over the whole image, for
  full-width backgrounds and textures; the text still follows `text_position` (#50).
- API reference documentation, built with Sphinx (`nox -s docs`): every public block
  and function in `briefing` and `briefing.lab` documents each argument and gives an
  example. New extra: `pip install "briefing[docs]"` (#41).
- Documentation guides with a live gallery: a quick start, one guide per block family,
  themes, notebooks, printing and export, the lab, recipes and the changelog. Every
  example runs when the docs are built and is embedded as the report it saves; a test
  runs the same examples against the report contract (#41).
- The documentation is at https://briefing.readthedocs.io; the README is now a short
  pitch and quick start that links to it, and the package metadata gains a
  `Documentation` URL (#41).

## [0.1.2] - 2026-11-03

Bug fixes after 0.1.1, plus one rendering change: a `BigNumber` change with no
direction is now shown neutral.

### Changed

- `BigNumber`: a `change` without `is_upward_change` is now shown neutral (no arrow, muted
  colour) instead of a red ▼, matching what the docs and the warning said; the warning is
  gone. `is_positive_intent` alone now colours a change without adding an arrow (#71).

### Fixed

- A hovered `Toggle` header is readable in dark themes: its background now comes from the
  theme instead of a hard-coded light grey (#73).
- Two Matplotlib figures in one report no longer share DOM ids: each inline SVG's ids
  (and the clip-path, marker and glyph references to them) get the figure's own prefix,
  so no reference resolves into another figure (#56).
- `bf.preview(...)` has a readable `repr` instead of one with a memory address, so
  notebook outputs are stable from one run to the next (#82).

## [0.1.1] - 2026-11-03

Makes the README true: every feature it describes now works as described,
offline, and is covered by HTML contract tests and browser tests. Also fixes
two script-injection bugs and two crashes on infinite values found by those
tests. New core dependencies: Pygments and latex2mathml.

### Security

- The report `name` (tab title and header) is now HTML-escaped. Before, markup in it
  was inserted as-is, so a name such as `<img src=x onerror=...>` ran script (#54).
- `DataDive` escapes the JSON it embeds, so a column name or value containing
  `</script>` or `<!--` can no longer end its `<script>` tag and inject markup (#55).

### Added

- Notebook previews: every block and `Briefing` has a `_repr_html_`, so it displays itself
  as the last expression of a cell, as a complete report in its own `srcdoc` iframe that
  grows to fit its content. Previews no longer share ids, CSS or scripts with each other
  or the notebook. `bf.preview(blocks, name=, formatting=)` previews with a name or
  theme (#12).
- `BigNumber(is_positive_intent=...)` sets the change colour apart from the arrow, so
  "went up, and that's bad" shows ▲ in red. Calls without it render as before (#14).

### Deprecated

- `Plot(scale=...)` never had an effect. It now emits a `DeprecationWarning` and will be
  removed after 0.2: size the figure in its plotting library instead, for example
  Matplotlib's `figsize` (#7).

### Fixed

- `DataTable` no longer crashes on infinite values: `inf` and `-inf` display as such and
  sort at the ends of the column (#60).
- `DataProfile` no longer crashes on infinite values: min/max show `inf` / `-inf`, an
  `infinite` row counts them, and the histogram is built from the finite values (#79).
- `mypy src/briefing tests` passes again with beautifulsoup4's own type hints;
  the `dev` extra now requires `beautifulsoup4>=4.14` (#48).
- pandas 3: `DataDive` trims long strings to 64 characters again. pandas 3's
  default `str` dtype (and the `"string"` dtype on pandas 2) skipped the trim,
  which only looked at `object` columns. CI now tests pandas 2 and 3 (#11).
- `DataTable`: clicking a column header now reorders the rows. Before, sorting only
  changed which rows landed on the current page, in their original order (#1).
- `DataTable` sorts by value: dates chronologically, numbers by their full value
  (also when shown as `1.23457e+06` or with thousands separators), and empty cells
  last in both directions. Cells carry a `data-sort` key where the text isn't enough (#2).
- Reports with Plotly or Matplotlib charts are now byte-identical from one render to
  the next (with `now=` or `SOURCE_DATE_EPOCH`): Plotly div ids and Matplotlib SVG
  id salts come from the render, and the SVG no longer embeds its creation date (#10).
- `Text` renders markdown pipe tables, styled like `Table` blocks (#4).
- `HTML` blocks get the same paragraph, list, heading, link, code, blockquote and
  table spacing as `Text`, instead of none at all; inline styles still win (#47).
- `Code` blocks are syntax-highlighted with Pygments (new core dependency). Token
  colours and the block itself follow the theme, light or dark, instead of a fixed
  dark palette; an unknown language shows plain text (#5).
- A Plotly chart inside a `Toggle` fills its width when the toggle opens, instead of
  staying at Plotly's 700 px default. Charts are also resized when a tab or dropdown
  panel is shown (#9).
- Altair charts work offline: the Vega runtime is embedded once per report (about
  880 KB) and charts are drawn in the page instead of a CDN-loading iframe. The
  `altair` and `charts` extras now include `vl-convert-python`, which supplies the
  runtime; without it an Altair chart shows an install hint. The offline warning is
  gone (#8).
- `DataDive` warns when `facet_row` or `facet_col` is passed: they were validated, then
  silently ignored. Faceting is planned for DataDive v2; the README no longer lists them (#6).
- The README and docstrings match the code (#13):
  - `HTML` (and raw HTML in `Text`) is inserted as-is; scripts run.
  - `[email]` is reserved for the upcoming email digest; there is no email feature yet.
  - `DataProfile` lists the stats it actually shows (median, not quartiles; no gap
    detection).
  - The missing `demo/` section is replaced by `examples/`.
  - No docstring uses the old `fl.` prefix.
  - Every README example now runs as written, offline, in the test suite.
- `Formula` now displays typeset math: LaTeX is converted to MathML when the report is
  rendered, with no JavaScript. Before, readers saw the raw `\(...\)` source.
  LaTeX that can't be converted shows its source with a visible note and a
  `UserWarning`. New core dependency: `latex2mathml` (#3).

## [0.1.0] - 2026-09-09

First public release.

### Added

- **Block grammar + self-contained HTML renderer.** `Briefing` document root
  composed of blocks: `Text`, `HTML`, `Code`, `Formula`, `BigNumber`, `Alert`,
  `Group`, `Select`, `Toggle`, `Page`, `Plot`, `Table`, `DataTable`. Output is
  a single `.html` file with all CSS/JS inlined — no CDN, works offline.
- **`briefing.lab`** subpackage for richer custom visualisations —
  `DataProfile` (per-column stats, inline SVG) and `DataDive` (Facets-style
  interactive dot explorer). `pip install briefing[lab]`.
- **Zero visualisation-library dependencies in the core.** `Plot` accepts a
  Plotly / Altair / Matplotlib / Bokeh figure and imports that library only
  when handed one of its figures. Opt-in extras: `briefing[plotly]`,
  `[altair]`, `[bokeh]`, `[matplotlib]`, and `[charts]` for all four.
- **Dataframe-agnostic intake.** `Table` / `DataTable` accept polars, pyarrow,
  `__dataframe__` objects and plain dicts; pandas is an optional extra
  (`pip install briefing[pandas]`) used as the internal engine.
- **Theming** — five presets plus full CSS-token control via `Formatting`.
- **Byte-reproducible output** — `render_report(now=...)` /
  `SOURCE_DATE_EPOCH`, so rendered files diff cleanly.
- **Renderer registry** (`@renderer_for` + MRO lookup) so a block subclass
  inherits its base's renderer.
- Ships inline type hints (`py.typed`). Python 3.11+.

[Unreleased]: https://github.com/jeanmidevacc/briefing/compare/v0.6.1...HEAD
[0.6.1]: https://github.com/jeanmidevacc/briefing/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/jeanmidevacc/briefing/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/jeanmidevacc/briefing/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/jeanmidevacc/briefing/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/jeanmidevacc/briefing/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jeanmidevacc/briefing/compare/v0.2.4...v0.3.0
[0.2.4]: https://github.com/jeanmidevacc/briefing/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/jeanmidevacc/briefing/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/jeanmidevacc/briefing/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/jeanmidevacc/briefing/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jeanmidevacc/briefing/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/jeanmidevacc/briefing/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/jeanmidevacc/briefing/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jeanmidevacc/briefing/releases/tag/v0.1.0
