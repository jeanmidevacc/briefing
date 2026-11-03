# Changelog

All notable changes to `briefing` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- At release time: rename [Unreleased] to the version, add the date, and
     open a fresh [Unreleased] section above it. -->

## [Unreleased]

### Fixed

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

[Unreleased]: https://github.com/jeanmidevacc/briefing/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jeanmidevacc/briefing/releases/tag/v0.1.0
