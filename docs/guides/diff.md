# Comparing runs

A report that runs every day raises one question first: what changed since yesterday?
{func}`~briefing.diff` answers it with a report of its own, which you can save, embed or
send like any other.

```python
changes = bf.diff("yesterday.json", today, keys={"detail/ridings": "riding"})
bf.save(changes, "what-changed.html", name="What changed since yesterday")
```

Each run can be a `Briefing`, or the JSON form an earlier run saved: a `.json` file
written from `bf.to_spec(report, inline=True)`, a dict, or the `(spec, data)` pair
`bf.to_spec` returns. Keep yesterday's JSON next to its HTML, and tomorrow's run can
compare against it.

## How blocks are matched

Blocks are matched by their link names (see {doc}`layout`): `detail/ridings` in one run is
the same table as `detail/ridings` in the other. Blocks without a `name=` aren't compared;
the summary says how many there were. Pages and groups aren't compared as wholes: their
blocks are, one by one.

## What the result shows

- **A summary**: how many named blocks changed, were added, were removed or stayed the same.
- **Numbers**: each changed `BigNumber`, with the previous value as `prev_value=`, so its
  arrow and change are computed.
- **Tables**: each changed `DataTable` or `Table`. With a key column in `keys=`, the rows
  added, removed and changed, with `old → new` in the cells that differ; without one, the
  rows added and removed. Columns added or removed are named.
- **Text**: a line-by-line diff of each changed `Text`.
- **Other blocks**: each changed chart, image or other block, by name.
- **Added and removed**: the blocks only one run has.

```{briefing-example}
:title: What changed between two runs
:height: 560

import pandas as pd
import briefing as bf

def run(leaders, seats, note):
    ridings = pd.DataFrame({"riding": ["Outremont", "Laurier", "Rosemont"], "leader": leaders,
                            "margin": [12.4, 3.1, 8.0]})
    return bf.Briefing(
        bf.BigNumber("Seats won", seats, name="seats"),
        bf.Text(note, name="note"),
        bf.DataTable(ridings, name="ridings"),
    )

yesterday = run(["Liberal", "NDP", "Bloc"], 41, "Polls close at 8 p.m.\nResults from 9 p.m.")
today = run(["Liberal", "Liberal", "Bloc"], 44, "Polls close at 8 p.m.\nResults are in.")
bf.save(bf.diff(yesterday, today, keys={"ridings": "riding"}), "diff.html", name="What changed")
```
