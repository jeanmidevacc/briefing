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
   `renderers/links.py` first gives each named block its link id (`page/name`) on the
   `IdGen`; `_render_block` puts it on the block's outer element, so a renderer never
   writes `block.name` into its HTML itself.
4. **Assemble**: `templates/report.html.j2` inlines `static/report.css`, `static/report.js`,
   the theme's CSS variables (`Formatting.to_css_vars()`) and any runtime a block needs.
   A fragment (`full_html=False`, `renderers/fragment.py`) uses `templates/fragment.html.j2`
   instead: report.css scoped to `.bf-embed` by `renderers/css_scope.py` between
   `static/embed-reset.css` and `static/embed.css`, ids prefixed with its `embed_id`, and
   `briefing.init(root)` on its `<div>`. `tests/test_fragments.py` runs the fragment
   contract over every scenario; full reports must not change (golden snapshots).
   `export=("embed",)` (#124, `renderers/copy_embed.py`) marks the blocks whose class sets
   `embed_noun` with `data-bf-embed`, prefixes made-up ids with a hash of the report and
   adds a gzip copy of the untouched blocks (`fragment.copy_data`); `static/copy-embed.js`
   cuts a block out of it as a fragment. Reports without it must not change.
   A `DataTable` above `DataTable.HTML_ROWS` (1,000) rows keeps its first page in the HTML
   and its rows packed (`renderers/pack.py`: raw deflate + base64) in a
   `script.bf-dt__data`; `static/unpack.js` (`window.briefingUnpack`, a function, not a
   part) unpacks them synchronously, and `block_scripts` ships it with any such table (#38).
   Chart runtimes are packed too: `plot.runtime_script` gives the `<script>` text that
   carries unpack.js and the packed runtime (shielded from RequireJS) and inserts it, once
   per page, right after itself; reports, fragments and copy-embed copies use it as is.

**The JSON form** (#31, `src/briefing/spec/`): `bf.to_spec`, `bf.from_spec`, `bf.validate`
and `bf.schema`. `spec/_model.py` reads each block's options from its constructor (names,
type hints, defaults, `Args:` docstring); `_TYPES` lists the block types, and `_ATTRS`,
`_KEYS`, `_CHOICES`, `_OVERRIDES` cover what a signature can't say. The JSON Schema built
from it is checked in as `src/briefing/schema/v1.json`, and the reference for agents built
from it (#32, `spec/_reference.py`) as `src/briefing/reference.md`: after changing a block's
parameters or their docstrings, run `python -m briefing.spec` and commit both files
(`tests/test_spec/test_schema.py` and `test_reference.py` fail until you do). A new block
type goes in `_TYPES`; a new diagnostic code in `CODES` (`spec/_diagnostic.py`) and the
guide's table. `python -m briefing reference|validate|render|skill` (`_cli.py`) serve agents;
`docs/_ext/llms.py` publishes the reference as `llms-full.txt`.
`validate` reads the JSON (`spec/_convert.py`), draws each block alone, then renders the
report with an `IdGen` that records name clashes (`spec/_validate.py`); it never raises.

`briefing.lab` (`DataProfile`, `DataDive`, `DataCompare`…) plugs in the same way: `lab/__init__.py`
calls `register_renderer(..., js_asset=..., css_asset=...)`, so `lab.js` (or `compare.js`,
`compare.css`) is inlined only when its block is present, in reports, fragments, copy-embed
copies and decks alike (`block_scripts`, `block_styles`). New lab blocks follow that pattern:
class in `lab/_blocks.py`, renderer in `lab/_render_<name>.py`, JavaScript and CSS in
`lab/static/`, not in report.css, which every report carries.

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
  markdown in `Text` or raw markup in `HTML`; those go through `close_open_markup`
  (`renderers/markup.py`), so nothing left open in them runs past their block. Embedded
  JSON goes in `<script type="application/json">`, never inline JavaScript.
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
  the `bf.` prefix (`tests/test_readme.py` rejects the old `fl.`).
- Static JavaScript is vanilla ES5 inside an IIFE (`var`, `function`), with no build step
  and no dependency. CSS uses the `--bf-*` variables so every theme applies.
- Each script registers a part with `window.briefing.register(name, make)` (the runtime at the
  top of `report.js`); `briefing.init(root)` then runs it on each root once. A part queries
  from its root, never from `document`, adds page-wide listeners only through `runtime.on`
  and does print work through `runtime.onPrint`. `tests/test_static_scripts.py` checks this,
  and `tests/test_browser/test_roots.py` checks two roots on one page.
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
  them over the scenarios in `tests/scenarios.py`, at least one per block. A new block needs
  a scenario there, or `test_every_block_type_is_covered` fails. Known failures are strict
  `xfail`s naming their issue: remove the entry in `KNOWN_FAILURES` when you fix it.
- **Golden snapshots** (`tests/test_golden.py`): every scenario must render byte for byte to
  `tests/snapshots/golden/<scenario>.html`. `tests/golden.py` first swaps briefing's static
  files for a hash line, chart libraries' output for a marker and the version for
  `{version}`. Any change to report HTML fails until you run
  `pytest tests/test_golden.py --snapshot-update` and commit the snapshots; read their diff
  and check it shows only the change you meant. A new scenario needs that run once; delete
  the file of a removed one.
- **Property tests** (`tests/test_properties.py`): Hypothesis renders random strings and
  dataframes in `Text`, `Table`, `DataTable`, `DataProfile` and `DataDive` and checks the
  contract. CI uses the fixed `ci` profile from `conftest.py`;
  `pytest --hypothesis-profile=thorough tests/test_properties.py` searches harder. A failure
  is a bug: fix it and add a plain regression test, rather than narrowing the strategy.
- **The JSON form** (`tests/test_spec/`): every scenario must round-trip through
  `from_spec(*to_spec(r))` byte for byte, by reference and inline, and `validate` must find
  no error in it (`test_round_trip.py`). `test_spec_properties.py` writes random report
  JSON, right and wrong, and checks that `validate` reports an error exactly when building
  or rendering fails.
- Every bug fix comes with a test that fails without the fix.
- JavaScript behaviour (sorting, tabs, toggles, DataDive) can't be verified from HTML alone.
  After changing `static/` or `lab/static/`, add or update a test in `tests/test_browser/`
  (marked `browser` automatically; the `viewer` fixture opens a report offline and fails on
  any network request or JavaScript error), and look at a rendered report yourself.
  CI runs them in a separate `browser` job and uploads screenshots of failures.

## Releases and changelog

- The version lives in `src/briefing/_version.py` (`__version__`) and nowhere else (examples
  say `<version>`); the publish workflow fails if the release tag doesn't match it.
- To release: `nox -s prepare -- X.Y.Z` (`tools/prepare_release.py`) sets the version and
  dates `## [Unreleased]` with its compare link; merge that as "Prepare X.Y.Z", then
  `gh release create vX.Y.Z --target main`.
- A GitHub Release runs `publish.yml`: PyPI (Trusted Publishing), then a smoke job installs the
  release from PyPI and builds a `python -m briefing new` project, and it starts
  `docs.yml` (a separate run, not a reusable-workflow call: the environment secret
  doesn't reach one), which rebuilds `stable` and `latest` on Read the Docs with the
  `RTD_TOKEN` secret of the `pypi` environment.
  `gh workflow run docs.yml` rebuilds them by hand.
- Add every user-visible change to `## [Unreleased]` in `CHANGELOG.md` (Keep a Changelog).
- `hatchling` is pinned below 1.27 and `license` is a text table on purpose: both keep the
  metadata at version 2.3, which `twine check` accepts. Don't "modernise" them.

## Working on issues

- The backlog lives in GitHub issues, grouped by milestone. Read the issue's Problem, Proposal and
  "Done when" first; a "Decision" section is settled and not to be reopened. Issues
  labelled `needs spec` need a short agreed spec before code.
- Documentation lives in `docs/` (Sphinx + MyST, built by `nox -s docs` with warnings as
  errors; published on Read the Docs). A new public name needs an `Args:` docstring
  (`tests/test_docstrings.py`), and a new block needs a live `briefing-example` in a guide
  (`tests/test_docs_gallery.py` runs every example against the contract). Export samples in
  `docs/_static/export/` are regenerated with `nox -s docs-assets`.
- Every ```python block in the README runs in `tests/test_readme.py`, offline, with the
  names its intro promises (`df`, `fig`, …). Keep README claims true to the code.
- Reference the issue in commits (`Fix DataTable sort order (#1)`) and keep one issue per
  pull request.
