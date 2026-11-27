# Coding agents

briefing is built so that a person and a coding agent can write the same report. An agent
writes the report as JSON (see {doc}`json`), checks it with `validate`, fixes what it
reports, and renders it; a person can then open the same report in Python with
`bf.from_spec`, or the other way round with `bf.to_spec`.

To set up an agent for a whole project, start from {doc}`agent-prompt`: a prompt to copy
into `AGENTS.md`, `CLAUDE.md` or a system prompt, with the outputs and the freedom to tick.

## What an agent should read first

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

## An agent's loop, in Python

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

## A slide deck or an email, too

The JSON for a slide deck has `"slides"` in place of `"blocks"` (see {doc}`decks`), and
`validate`, `render`, `pdf` and `image` take it as they take a report. To draft a deck
from a report an agent already wrote, `python -m briefing render report.json --deck
deck.html` (experimental).
