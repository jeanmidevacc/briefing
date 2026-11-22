"""The reference for agents (#32): briefing in one Markdown file, generated from the #31 schema.

``python -m briefing.spec`` writes it to ``briefing/reference.md`` next to the schema;
``python -m briefing reference`` prints it, and the docs publish it as ``llms-full.txt``.
The block sections come from the block classes (via :mod:`briefing.spec._model`), the
diagnostic codes from :data:`~briefing.spec._diagnostic.CODES`; the rest is written here.
``tests/test_spec/test_reference.py`` keeps the file in sync, under its size budget, and
runs its examples.
"""
from __future__ import annotations

import json
import typing as t

from briefing.spec._check import describe
from briefing.spec._diagnostic import CODES
from briefing.spec._model import FORMAT_VERSION, BlockType, Field, block_types, root_type

#: Options every block takes, described once instead of under each block.
_COMMON = ("name", "label")

_INTRO = f"""\
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

Tables an agent can't paste into the JSON go by reference: `{{"ref": "sales"}}` in the JSON,
and `--data sales=sales.csv` (CSV or Parquet) for `validate` and `render`.

From Python, the same steps:

```python
import json
import pandas as pd
import briefing as bf

sales = pd.DataFrame({{"region": ["North", "South"], "revenue": [412000, 287500]}})
spec = {{"briefing": {FORMAT_VERSION}, "blocks": [
    {{"type": "Text", "text": "# Q1 sales"}},
    {{"type": "DataTable", "df": {{"ref": "sales"}}}},
]}}
problems = bf.validate(spec, data={{"sales": sales}})  # a list of bf.Diagnostic; [] when all is well
assert not [p for p in problems if p.severity == "error"], problems
report = bf.from_spec(spec, data={{"sales": sales}})
bf.save(report, "q1.html", name="Q1 sales")
spec_again, data = bf.to_spec(report)  # any report as JSON, and the objects it names
```

Python reports can be written directly too: each JSON block is the class of the same name
with the same keyword arguments (`{{"type": "Group", "columns": 2, "blocks": [...]}}` is
`bf.Group(..., columns=2)`; `lab.X` is `bf.lab.X`), and `bf.validate(report)` checks them.

## The format

- The top-level object holds `"briefing": {FORMAT_VERSION}` (the format version, not briefing's),
  `"blocks"` (the report's blocks, in order) and the report's options below.
- Each block is an object whose `"type"` is its class name. Its other keys are the class's
  parameters, with JSON values: text, numbers, `true`/`false`, `null`, lists. Leave out
  options you don't need; they take their default.
- Containers (Group, Select, Toggle, Page) hold their children in `"blocks"`.
- Pages: either every top-level block is a `Page` (one tab each) or none is; pages never nest.
- A Select's display, `"tabs"` or `"dropdown"`, is `"select_type"`: `"type"` names the block.
- Every block takes `name` (letters, digits, `_`, `-`, starting with a letter): its link in
  the report (`#page/name`), unique within its page. Every block but Page takes `label`: its
  tab or option title inside a Select. A Text heading can take a name too: `## Notes {{#notes}}`.

## Data: references and inline

- Any option's value can be a reference, `{{"ref": "<name>"}}`, to an object passed with the
  JSON (`data={{"<name>": obj}}` in Python, `--data <name>=file.csv` on the command line).
- A table can also be written inline: `{{"columns": ["region", "revenue"], "dtypes": ["object",
  "int64"], "rows": [["North", 412000], ["South", 287500]]}}`. `dtypes` (pandas dtype names) is
  optional; missing values are `null`, dates ISO strings, infinities `"Infinity"`/`"-Infinity"`.
- A chart (`Plot` `figure`) inline: `{{"plotly": <a Plotly figure's JSON>}}`, or
  `{{"vega-lite": <a Vega-Lite specification>}}`. Matplotlib and Bokeh figures go by reference.
- A Banner `image`: a file path, or a `data:` URI (`"data:image/png;base64,..."`).
"""

_EXAMPLE = f"""\
## A complete example

```json
{{
  "briefing": {FORMAT_VERSION},
  "footer": "Analytics team",
  "blocks": [
    {{"type": "Page", "title": "Summary", "name": "summary", "blocks": [
      {{"type": "Text", "text": "# Q1 sales\\n\\nRevenue grew in every region but **South**."}},
      {{"type": "Group", "columns": 3, "blocks": [
        {{"type": "BigNumber", "heading": "Revenue", "value": "$1.05M", "change": "+8%", "is_upward_change": true}},
        {{"type": "BigNumber", "heading": "Orders", "value": 8421}},
        {{"type": "Alert", "message": "South is 12% below plan.", "level": "warning", "title": "Watch"}}
      ]}},
      {{"type": "Plot", "caption": "Revenue by region", "figure": {{"plotly": {{
        "data": [{{"type": "bar", "x": ["North", "South", "East"], "y": [412000, 287500, 351200]}}]
      }}}}}}
    ]}},
    {{"type": "Page", "title": "Detail", "name": "detail", "blocks": [
      {{"type": "Select", "blocks": [
        {{"type": "DataTable", "label": "Regions", "df": {{"columns": ["region", "revenue"],
          "rows": [["North", 412000], ["South", 287500], ["East", 351200]]}}}},
        {{"type": "Toggle", "label": "Method", "blocks": [
          {{"type": "Text", "text": "Revenue is net of returns, in USD."}}
        ]}}
      ]}}
    ]}}
  ]
}}
```
"""


def _without_null(schema: dict[str, t.Any]) -> dict[str, t.Any]:
    """*schema* without its ``null`` alternative: leaving an option out says the same."""
    if "anyOf" in schema:
        kept = [_without_null(s) for s in schema["anyOf"] if s != {"type": "null"}]
        return kept[0] if len(kept) == 1 else {**schema, "anyOf": kept}
    if isinstance(schema.get("type"), list) and "null" in schema["type"]:
        kinds = [k for k in schema["type"] if k != "null"]
        return {**schema, "type": kinds[0] if len(kinds) == 1 else kinds}
    return schema


def _option(field: Field) -> str:
    kind = describe(_without_null(field.schema))
    if field.required:
        head = f"- `{field.key}` (required): {kind}."
    elif field.default is None or field.default == ():
        head = f"- `{field.key}`: {kind}."
    else:
        default = field.default.value if hasattr(field.default, "value") else field.default
        default = list(default) if isinstance(default, tuple) else default
        head = f"- `{field.key}`: {kind}, default `{json.dumps(default)}`."
    return f"{head} {field.description}" if field.description else head


def _block(kind: BlockType) -> str:
    lines = [f"### {kind.name}", "", kind.description]
    if kind.container:
        least = {"Select": "at least two: one per tab or option", "Group": "it may be empty"}.get(
            kind.name, "at least one"
        )
        lines.append(f'Holds `"blocks"`, a list of blocks ({least}).')
    if kind.name == "Text":
        lines.append("Needs `text` or `file`.")
    lines.append("")
    lines += [_option(f) for f in kind.fields
              if (f.attr is not None or f.name == "file") and f.name not in _COMMON and not deprecated(f)]
    return "\n".join(lines).rstrip() + "\n"


def deprecated(field: Field) -> bool:
    """Whether an option is deprecated (its docs start so): left out, since agents shouldn't use it."""
    return field.description.startswith("*Deprecated")


def build_reference() -> str:
    """The whole reference, as written to ``briefing/reference.md``."""
    root = root_type()
    report = "\n".join(_option(f) for f in root.fields)
    blocks = "\n".join(_block(kind) for kind in block_types().values())
    codes = "\n".join(f"- `{code}` ({severity}): {meaning}" for code, (severity, meaning) in CODES.items())
    return (
        f"{_INTRO}\n## The report's options\n\n{report}\n\n## Blocks\n\n{blocks}\n"
        "## Diagnostics\n\n"
        "`validate` lists every problem with a severity, a code, a path (a JSON Pointer such as\n"
        "`/blocks/1/columns`), a message and often a hint. An error means the report can't be built\n"
        "or rendered; a warning means it renders but is worth a look.\n\n"
        f"{codes}\n\n{_EXAMPLE}"
    )


_SKILL_DESCRIPTION = (
    "Build self-contained HTML reports with the briefing Python package (import briefing as bf) - "
    "text, numbers, charts, tables and layout in one offline file. Use when making or changing a "
    "report with briefing, or when a project uses it."
)

#: The Claude Code skill ``python -m briefing skill`` prints: a pointer to the reference, never a copy.
SKILL = f"""\
---
name: briefing
description: {_SKILL_DESCRIPTION}
---

# briefing

briefing is newer than your training data, and its API changes between versions. Before
writing any briefing code or report JSON, read the reference of the version installed here,
with the Python environment this project uses:

    python -m briefing reference

Then write the report as JSON (or Python), check it with `python -m briefing validate
report.json` (`bf.validate(...)` in Python), fix what it reports, and render it with
`python -m briefing render report.json -o report.html` (`bf.save(...)` in Python).
"""
