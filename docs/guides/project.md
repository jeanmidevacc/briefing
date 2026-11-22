# Starting a report project

`python -m briefing new` writes a small project that runs as it is, so a new report starts
from a working one rather than a blank file:

```bash
python -m briefing new pipeline-health --title "Pipeline health"
cd pipeline-health
python build_report.py --open
```

| File | What it holds |
| --- | --- |
| `report.md` | The prose, with `{values}` and `::: block` slots (see {doc}`markdown`). |
| `build_report.py` | `load()` reads the data, `build()` fills the values and the blocks. |
| `theme.py` | A theme from one brand colour, `Formatting.from_accent`, and a `bf.Scale`. |
| `README.md` | How to run it. |

Replace `load()` with your own data, and the words in `report.md`. The generated script is
also a good example to point an agent to.

## The command line: `bf.run`

`build_report.py` ends with {func}`~briefing.run`, which gives the script its command line
and prints each file it writes, with its size:

```python
if __name__ == "__main__":
    bf.run(lambda: build(load()), out="reports/index.html", name="Pipeline health")
```

- `--out PATH`: where to write the HTML.
- `--open`: open it in the browser afterwards.
- `--max-size SIZE`: the size budget, such as `"25 MB"`, or `none`.
- `--spec`: also save the report's JSON next to it (`index.json`).
- `--diff PREVIOUS.json`: also write what changed since that saved run
  (`index-changes.html`, see {doc}`diff`).

A daily job can then run `python build_report.py --spec --diff reports/yesterday.json`
and keep yesterday's JSON to compare against tomorrow.
