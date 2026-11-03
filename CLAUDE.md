# briefing

Python package that turns analysis into one self-contained HTML file built from a small
grammar of blocks (`Text`, `Group`, `Plot`, `DataTable`, …). Built by a person and coding
agents together, so keep the grammar small, the output predictable and every change tested.

## Commands

```bash
pip install -e ".[dev]"                 # Python 3.11+
pytest                                  # full suite with coverage (addopts in pyproject.toml)
pytest -m browser                       # browser tests only; `playwright install chromium` once
pytest -o addopts="" -q tests/test_lab  # quick run of one area, no coverage
ruff check src tests                    # lint; line length 120
mypy src/briefing tests                 # strict mode, tests included
nox                                     # tests on 3.11–3.13 × pandas 2/3 + lint + typecheck, as CI
```

Run `ruff`, `mypy` and `pytest` before saying a change is done. CI runs the same three on
Python 3.11, 3.12 and 3.13 (tests against both pandas 2 and 3), then builds the package
and runs `twine check --strict`.

## How it works

1. **Blocks** (`src/briefing/blocks/`) are plain data holders. Constructors validate input and
   convert dataframes with `to_pandas()` (`_frames.py`); they never produce HTML.
2. **Normalize** (`renderers/normalize.py`) copies the tree; top-level `Page`s become one
   tabbed `Select` of `Group`s.
3. **Render** (`renderers/html.py`): each block type has a function registered with
   `@renderer_for(BlockClass)` in `renderers/registry.py`; lookup walks the MRO. Renderers
   take `(block, idgen)` and return an HTML fragment string.
4. **Assemble**: `templates/report.html.j2` inlines `static/report.css`, `static/report.js`,
   the theme's CSS variables (`Formatting.to_css_vars()`) and any runtime a block needs.

`briefing.lab` (`DataProfile`, `DataDive`) plugs in the same way: `lab/__init__.py` calls
`register_renderer(..., js_asset=...)`, so `lab.js` is inlined only when a lab block is
present. New lab blocks follow that pattern: class in `lab/_blocks.py`, renderer in
`lab/_render_<name>.py`, JavaScript in `lab/static/`.

## Rules that must hold

- **Self-contained and offline.** No CDN, no network request, no external URL in `src` or
  `href`. Everything a report needs is inlined.
- **Lazy optional imports.** `import briefing` must not import pandas or any plotting
  library; import them inside functions. `Plot` detects the library from the figure's
  module and imports only that one. `tests/test_no_viz_deps.py` enforces this for
  plotting libraries.
- **Deterministic output.** Same input + `SOURCE_DATE_EPOCH` (or `now=`) gives byte-identical
  HTML. DOM ids come from `IdGen`; never use `uuid`, `random` or the wall clock.
- **Escape user text.** Every value from the user goes through `html.escape` unless it is
  markdown in `Text` or raw markup in `HTML`. Embedded JSON goes in
  `<script type="application/json">`, never inline JavaScript.
- **Lab stays out of the core report.** A report without a `DataDive` must not contain
  `lab.js`; `tests/test_lab/test_lab_boundary.py` checks it.
- **Errors and warnings.** Raise `BriefingError` (`_error.py`) for invalid input, with a
  message that says what to pass instead. Recoverable problems (truncated rows, sampling)
  use `warnings.warn(..., stacklevel=2)`.

## Code conventions

- `from __future__ import annotations`, full type hints, `typing as t`; mypy is strict.
- Choice parameters are `StrEnum`s that also accept their string value (`SelectType`,
  `AlertLevel`, `VAlign`).
- Blocks take `name=` and `label=` as their last parameters; captions and labels are
  shortened with `_truncate`.
- Docstrings: one summary line, then Google-style `Args:` and an `Example::` block using
  the `bf.` prefix. Some old docstrings still say `fl.`; fix them when you touch them.
- Static JavaScript is vanilla ES5 inside an IIFE (`var`, `function`), with no build step
  and no dependency. CSS uses the `--bf-*` variables so every theme applies.
- Renaming or removing public API: keep the old name in `__init__.__getattr__` with a
  `DeprecationWarning` that says when it goes away, and add a test in
  `tests/test_deprecations.py`.

## Tests

- Mirror the source layout: `tests/test_blocks/`, `tests/test_renderers/`, `tests/test_lab/`.
- Shared dataframes live in `tests/conftest.py` (`df_mixed`, `df_empty`, `df_large`, …).
  Use them before writing new ad hoc frames.
- Check HTML structure with BeautifulSoup, not substring matching. bs4 types `find()` as
  `Tag | None` and attributes as `str | AttributeValueList`, so use the typed helpers in
  `tests/html_helpers.py` (`parse`, `find_one`, `attr`, `classes`) or mypy fails.
- `tests/contract.py` holds the rules every report must follow (offline, unique ids, valid
  embedded JSON, escaped user text, deterministic output, …); `tests/test_contract.py` runs
  them over a scenario per block. A new block needs a scenario there, or
  `test_every_block_type_is_covered` fails. Known failures are strict `xfail`s naming their
  issue: remove the entry in `KNOWN_FAILURES` when you fix it.
- Every bug fix comes with a test that fails without the fix.
- JavaScript behaviour (sorting, tabs, toggles, DataDive) can't be verified from HTML alone.
  After changing `static/` or `lab/static/`, add or update a test in `tests/test_browser/`
  (marked `browser` automatically; the `viewer` fixture opens a report offline and fails on
  any network request or JavaScript error), and look at a rendered report yourself.
  CI runs them in a separate `browser` job and uploads screenshots of failures.

## Releases and changelog

- The version lives in `src/briefing/__init__.py` (`__version__`); the publish workflow
  fails if the release tag doesn't match it.
- Add every user-visible change to `## [Unreleased]` in `CHANGELOG.md` (Keep a Changelog).
- `hatchling` is pinned below 1.27 and `license` is a text table on purpose: both keep the
  metadata at version 2.3, which `twine check` accepts. Don't "modernise" them.

## Working on issues

- The backlog lives in GitHub issues (#1–#46). Read the issue's Problem, Proposal and
  "Done when" first; a "Decision" section is settled and not to be reopened. Issues
  labelled `needs spec` need a short agreed spec before code.
- The README describes some features that 0.1.0 doesn't implement yet (see #13). Trust the
  code and tests over the README.
- Reference the issue in commits (`Fix DataTable sort order (#1)`) and keep one issue per
  pull request.
