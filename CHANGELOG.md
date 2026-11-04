# Changelog

All notable changes to `briefing` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- At release time: rename [Unreleased] to the version, add the date, and
     open a fresh [Unreleased] section above it. -->

## [Unreleased]

### Added

- `lab.CalendarHeatmap`: hovering a day, an hour or an event band shows a tooltip at once,
  styled with the theme: the date (now with its weekday) in bold, the exact value, "below
  target …" and the day's events. It also opens on keyboard focus and on tap, stays inside
  the window, and never prints. The browser's slower built-in tooltip no longer doubles up;
  without JavaScript it is still there (#109).

### Deprecated

- `lab.CalendarHeatmap`'s hour view, `views=("hours",)` or `("days", "hours")`, raises a
  `DeprecationWarning`. It still works; a dedicated time-pattern heatmap (weekday × hour,
  weekday × month, …) is planned to replace it, and the hour view will be removed in 0.4.0
  at the earliest, never before that replacement ships (#111).

### Fixed

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

[Unreleased]: https://github.com/jeanmidevacc/briefing/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/jeanmidevacc/briefing/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jeanmidevacc/briefing/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/jeanmidevacc/briefing/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/jeanmidevacc/briefing/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jeanmidevacc/briefing/releases/tag/v0.1.0
