# Changelog

All notable changes to `briefing` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- At release time: rename [Unreleased] to the version, add the date, and
     open a fresh [Unreleased] section above it. -->

## [Unreleased]

### Fixed

- pandas 3: `DataDive` trims long strings to 64 characters again. pandas 3's
  default `str` dtype (and the `"string"` dtype on pandas 2) skipped the trim,
  which only looked at `object` columns. CI now tests pandas 2 and 3 (#11).

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
