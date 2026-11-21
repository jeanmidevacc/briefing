# Reports as JSON

Python and JSON are two ways of writing the same report. A coding agent, a script in
another language or a person can write the JSON, check it with {func}`briefing.validate`,
fix what it reports, and render it with {func}`briefing.from_spec`. A report written in
Python turns into JSON with {func}`briefing.to_spec`. Either way, it is the same report.

```python
import briefing as bf

spec = {
    "briefing": 1,
    "blocks": [
        {"type": "Text", "text": "# Weekly sales"},
        {"type": "Group", "columns": 2, "blocks": [
            {"type": "BigNumber", "heading": "Revenue", "value": "$1.2M", "change": "+4%", "is_upward_change": True},
            {"type": "BigNumber", "heading": "Orders", "value": 8421},
        ]},
        {"type": "DataTable", "df": {"ref": "orders"}},
    ],
}
problems = bf.validate(spec, data={"orders": orders})   # [] : nothing to fix
bf.save(bf.from_spec(spec, data={"orders": orders}), "sales.html")
```

## The format

- **`"briefing": 1`** says which format the JSON is in. It is not briefing's version: it
  changes only when JSON written for an older format would stop working. A newer briefing
  still reads format 1; an older one says to upgrade.
- **`"type"`** names each block by its class: `"Text"`, `"Group"`, `"DataTable"`, and
  `"lab.DataDive"` for the {doc}`lab` blocks.
- **Every other key is the constructor's parameter**, with its value as in Python:
  `"columns": 2`, `"valign": "center"`, `"widths": [2, 1]`, `"focus": [20, 80]`. Options
  left at their default can be left out. The one exception is a `Select`'s `type`, which
  is `"select_type"` (`"tabs"` or `"dropdown"`), because `"type"` already names the block.
- **Children go in `"blocks"`**, a list, in containers (`Group`, `Select`, `Toggle`,
  `Page`). The report's own options, `"export"` and `"footer"`, sit at the top, next to
  its `"blocks"`.

```json
{
  "briefing": 1,
  "footer": "Analytics team",
  "export": ["png"],
  "blocks": [
    {"type": "Page", "title": "Summary", "name": "summary", "blocks": [
      {"type": "Text", "text": "# Q1\n\nRevenue grew."},
      {"type": "Plot", "figure": {"ref": "trend"}, "caption": "Weekly revenue"}
    ]},
    {"type": "Page", "title": "Detail", "name": "detail", "blocks": [
      {"type": "DataTable", "df": {"ref": "sales"}},
      {"type": "lab.DataProfile", "df": {"columns": ["n"], "dtypes": ["int64"], "rows": [[1], [2]]}}
    ]}
  ]
}
```

## Tables, charts and images

Data goes into the JSON in one of two ways.

**By reference.** `{"ref": "sales"}` names an object passed alongside the JSON:
`bf.from_spec(spec, data={"sales": df})`. Anything works this way: a dataframe of a
million rows, a Matplotlib figure, a styled table. An agent can't paste a big table into
its JSON; it names it. Any option can be a reference.

**Inline.** Small data can be written into the JSON itself:

| What | JSON |
| --- | --- |
| A table (`df=`, `data=`) | `{"columns": ["region", "sales"], "dtypes": ["object", "int64"], "rows": [["North", 3], ["South", 4]]}`. `"dtypes"` (pandas dtype names) is optional; missing values are `null`, dates ISO strings, infinities `"Infinity"` and `"-Infinity"`. |
| A Plotly chart (`figure=`) | `{"plotly": {"data": [...], "layout": {...}}}`, a figure's own JSON |
| An Altair chart (`figure=`) | `{"vega-lite": {...}}`, a Vega-Lite specification |
| A `Banner` image (`image=`) | a file path, as in Python, or a `data:` URI (`"data:image/png;base64,..."`) |

Matplotlib and Bokeh figures and styled tables have no JSON form: they only go by
reference.

## Checking a report

{func}`briefing.validate` returns every problem it finds as a list of
{class}`briefing.Diagnostic`, and never raises. Each has a severity, a code, a message, a
hint, and a **path**: a JSON Pointer to the block or option at fault.

```python
for problem in bf.validate(spec, data):
    print(problem)
# error unknown-option at /blocks/1/colums: Group has no option "colums". Did you mean "columns"?
# error wrong-type at /blocks/2/level: Alert "level" must be one of "info", "success", "warning", "error", not "warn". ...
# warning missing-label at /blocks/3/blocks/1: This panel has no label, so its tab shows "Tab 2". Add "label": "...".
```

An **error** means the report can't be built or rendered; a **warning** means it renders
but is worth a look. When there is no error, the report renders: `validate` builds it and
renders its blocks to be sure.

| Code | Severity | What |
| --- | --- | --- |
| `invalid-json`, `unreadable-file`, `not-a-spec` | error | The JSON can't be read, or isn't a report object |
| `missing-version`, `unsupported-version` | error | `"briefing"` is missing, or a format this briefing doesn't read |
| `unknown-type`, `missing-type`, `not-a-block` | error | A block whose type is unknown or missing, or that isn't an object |
| `unknown-option`, `missing-option`, `wrong-type` | error | An option that doesn't exist, is required, or has the wrong type |
| `unknown-ref` | error | A reference to an object not passed in `data` |
| `invalid-data` | error | An inline table, chart or image that can't be read |
| `invalid-value` | error | A value the block itself rejects (`widths` that don't match `columns`, a column that isn't in the table…) |
| `mixed-pages`, `misplaced-page` | error | `Page` blocks mixed with others at the top, or nested |
| `empty-container` | error | A report, `Page` or `Toggle` without blocks |
| `duplicate-name`, `name-clash` | error | A name used twice in a page, or that matches an id briefing makes up |
| `render-error` | error | A block that fails to render, or a `Plot` that can't draw its figure |
| `too-deep`, `internal-error` | error | Blocks nested too deeply to check, or a bug in briefing itself (please report it) |
| `too-few-panels`, `missing-label` | warning | A `Select` with fewer than two panels, or a panel or page without a label |
| `deprecated` | warning | An option that will go away |
| `block-warning`, `placeholder` | warning | What a block warns about (rows dropped, a sample drawn…), or a block with nothing to draw |
| `too-big` | warning | The rendered report is bigger than `max_size` (10 MB by default); the message names its largest parts |

Without `data`, references aren't checked, and neither is rendering: `validate(spec)`
checks the JSON alone. A Python report works too: `bf.validate(report)` checks it through
its JSON form, so the paths point into `bf.to_spec(report)`.

{func}`briefing.from_spec` raises a {class}`~briefing.BriefingError` listing the same
errors when the JSON can't be built.

## From Python to JSON

```python
spec, data = bf.to_spec(report)               # dataframes and figures by reference
spec, data = bf.to_spec(report, inline=True)  # into the JSON, when they come back the same
json.dumps(spec)
```

`to_spec` writes each option that isn't at its default, and puts dataframes, figures and
images into `data`, named after their block (`"sales"` for `DataTable(df, name="sales")`,
else `"datatable-1"`). With `inline=True`, tables, Plotly and Altair charts and images go
into the JSON instead, each only when reading it back gives exactly the same object; the
rest stay references. Either way, `bf.from_spec(spec, data)` renders the same report, byte
for byte (Plotly and Altair may order the keys of an inline chart differently).

## The schema

{func}`briefing.schema` returns the format's [JSON Schema](https://json-schema.org), which
also ships as `briefing/schema/v1.json`. It is generated from the block classes, so each
block and option carries its description and default from this documentation. Hand it
to an agent as the reference for what it can write, or check JSON with any JSON Schema
validator:

```python
import jsonschema

jsonschema.validate(spec, bf.schema())
```

`bf.validate` checks more than the schema can say (names, references, each block's own
checks, rendering), so prefer it when Python is at hand.

## For agents

briefing is newer than most models' training data. An agent can learn it from the
installed package instead, at the installed version:

| Command | What it does |
| --- | --- |
| `python -m briefing reference` | Prints the reference for agents: the format, every block and option with its type, default and description, the diagnostic codes and a complete example. |
| `python -m briefing validate report.json` | Lists the problems in a report's JSON, one per line (`--json`: as a JSON list), and exits with status 1 when there is an error. |
| `python -m briefing render report.json -o report.html --name "Q1"` | Builds the report and saves it. |
| `python -m briefing skill --install` | Writes a Claude Code skill to `.claude/skills/briefing/SKILL.md` in the current project. It tells Claude to read the reference before writing briefing code. |

`validate` and `render` take the tables a JSON names by reference as
`--data sales=sales.csv` (CSV or Parquet), and read the JSON from standard input when
given `-`. Without `--data`, `validate` checks the JSON alone and says which references it
left unchecked.

The documentation publishes the same reference as
[llms-full.txt](https://briefing.readthedocs.io/en/stable/llms-full.txt), with an index in
[llms.txt](https://briefing.readthedocs.io/en/stable/llms.txt).

## An agent's loop

```{briefing-example}
:title: A report built from JSON

import json
import briefing as bf

draft = json.loads('''
{
  "briefing": 1,
  "blocks": [
    {"type": "Text", "text": "# Regions, Q1"},
    {"type": "Group", "colums": 2, "blocks": [
      {"type": "BigNumber", "heading": "Revenue", "value": "$1.05M", "change": "+8%", "is_upward_change": true},
      {"type": "BigNumber", "heading": "Regions", "value": 3}
    ]},
    {"type": "DataTable", "df": {"columns": ["region", "revenue"],
                                 "rows": [["North", 412000], ["South", 287500], ["East", 351200]]}}
  ]
}
''')

problems = bf.validate(draft)
assert [p.code for p in problems] == ["unknown-option"]  # "colums": Did you mean "columns"?
draft["blocks"][1]["columns"] = draft["blocks"][1].pop("colums")

assert bf.validate(draft) == []
bf.save(bf.from_spec(draft), "regions.html", name="Regions, Q1")
```
