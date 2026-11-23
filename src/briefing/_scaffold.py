"""``python -m briefing new`` (#193): a small report project that runs as it is."""
from __future__ import annotations

from pathlib import Path

from briefing._error import BriefingError

_BUILD = '''"""__TITLE__: build the report.

    python build_report.py                       # -> reports/index.html
    python build_report.py --open                # and open it in the browser
    python build_report.py --spec                # also save its JSON (reports/index.json)
    python build_report.py --diff reports/index.json   # and what changed since that run
    python build_report.py --deck                # and a first draft of a slide deck (experimental)
"""
from pathlib import Path

import numpy as np
import pandas as pd

import briefing as bf
from theme import ACTIVITY, THEME

HERE = Path(__file__).parent
TITLE = __TITLE_REPR__


def load() -> pd.DataFrame:
    """The data. Replace this with your own: a CSV, a Parquet file, a database query."""
    rng = np.random.default_rng(7)
    days = pd.date_range(end="2026-11-20", periods=120, freq="D")
    return pd.DataFrame({
        "day": days,
        "rows": rng.normal(1200, 300, len(days)).clip(0).round(),
        "status": rng.choice(["ok", "ok", "ok", "failed"], len(days)),
    })


def build(df: pd.DataFrame) -> bf.Briefing:
    """The report: the prose lives in report.md; this fills its values and its blocks."""
    failed = int((df["status"] == "failed").sum())
    facts = {
        "through": bf.fmt.date(df["day"].max()),
        "runs": len(df),
        "failed": failed,
    }
    kpis = bf.Group(
        bf.BigNumber("Runs", len(df), format="{:,}", name="runs-count"),
        bf.BigNumber("Failure rate", failed / len(df), format="{:.1%}", name="failure-rate"),
        bf.BigNumber("Rows, last day", df["rows"].iloc[-1], prev_value=df["rows"].iloc[-2], format="{:,.0f}",
                     sparkline=df["rows"].tail(30), name="last-day"),
        min_width="12rem",
    )
    calendar = bf.lab.CalendarHeatmap(df, date="day", value="rows", colors=ACTIVITY, name="calendar")
    newest = df.sort_values("day", ascending=False).reset_index(drop=True)
    runs = bf.DataTable(newest, caption="Every run, newest first", name="runs")
    return bf.from_markdown(HERE / "report.md", values=facts,
                            blocks={"kpis": kpis, "calendar": calendar, "runs": runs})


if __name__ == "__main__":
    bf.run(lambda: build(load()), out=HERE / "reports" / "index.html", name=TITLE, formatting=THEME)
'''

_REPORT = '''## Summary {#auto}

Data through **{through}**: {runs:,} runs, {failed} of them failed.

::: block kpis
The headline numbers: runs, failure rate, rows on the last day.
:::

## Day by day {#auto}

Each square is a day; the darker it is, the more rows were loaded. Hover a day to see them.

::: block calendar
The calendar of rows per day.
:::

## The runs {#auto}

::: block runs
Every run, to search and sort.
:::
'''

_THEME = '''"""The report's look: a theme from one brand colour, and a colour scale for the calendar."""
import briefing as bf

BRAND = "#4f46e5"

#: The whole theme from the brand colour, at readable contrast (try dark=True).
THEME = bf.Formatting.from_accent(BRAND)

#: Rows per day: the same colour means the same number in every calendar that uses it.
ACTIVITY = bf.Scale(["#e0e7ff", "#818cf8", "#4f46e5", "#1e1b4b"], domain=(0, 2000))
'''

_README = '''# __TITLE__

A report built with [briefing](https://pypi.org/project/briefing/).

```bash
pip install "briefing[lab]"
python build_report.py --open
```

| File | What it holds |
| --- | --- |
| `report.md` | The prose, with `{values}` and `::: block` slots. Edit the words here. |
| `build_report.py` | `load()` reads the data, `build()` fills the values and the blocks. |
| `theme.py` | The colours: a theme from one brand colour, and a scale for the calendar. |
| `reports/` | What the build writes: `index.html`, and with `--spec` its JSON. |

`python build_report.py --help` lists the options: `--open`, `--max-size`, `--spec`, and
`--diff reports/index.json` to see what changed since the last saved run, and `--deck` for a
first draft of a slide deck from the report (experimental: `reports/index-deck.html`).

For an agent: `python -m briefing reference` prints every block and option.
'''

FILES = ("build_report.py", "report.md", "theme.py", "README.md")


def new_project(folder: str | Path, title: str | None = None, force: bool = False) -> list[Path]:
    """Write a small report project into *folder*; returns the files written.

    Args:
        folder: The project's folder; created if needed.
        title: The report's title (default: the folder's name).
        force: Replace the project's files if they are already there.
    """
    root = Path(folder).expanduser()
    title = (title or root.resolve().name.replace("-", " ").replace("_", " ").strip().capitalize() or "Report")
    plain = title.replace('"', "'").replace("\\", "/")  # safe in a docstring and in Markdown
    there = [name for name in FILES if (root / name).exists()]
    if there and not force:
        raise BriefingError(f"{root} already holds {', '.join(there)}: choose another folder, or pass --force "
                            "to replace them.")
    root.mkdir(parents=True, exist_ok=True)
    contents = {
        "build_report.py": _BUILD.replace("__TITLE_REPR__", repr(title)).replace("__TITLE__", plain),
        "report.md": _REPORT,
        "theme.py": _THEME,
        "README.md": _README.replace("__TITLE__", plain),
    }
    written = []
    for name in FILES:
        path = root / name
        path.write_text(contents[name], encoding="utf-8")
        written.append(path)
    return written


__all__ = ["FILES", "new_project"]
