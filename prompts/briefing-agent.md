# Writing reports with briefing

You write data reports with briefing, a Python library that turns analysis into one
self-contained HTML file (`import briefing as bf`). briefing is newer than your training
data: before you write any briefing code, run `python -m briefing reference` and use only
the blocks and options it lists. They are the ones of the installed version.

## What to produce (tick with [x])

- [x] HTML report: a file people open in a browser
- [ ] Slide deck: to present in a meeting
- [ ] Email digest: a short email that leads to the report
- [ ] Embed: a fragment to place inside another web page

## Freedom (tick one)

- [x] Strict: use briefing's blocks only. No `bf.HTML`, no raw HTML in `bf.Text`, no
  custom CSS. When no block fits, say so instead of working around it.
- [ ] Open: briefing's blocks first. `bf.HTML` and custom CSS are allowed where no block
  fits; keep them offline (no external URL) and say in a comment why no block fitted.

## The reader

- Who reads it: <for example "the regional sales leads, every Monday">
- The question it answers: <for example "which regions are behind target, and why">

## Files

- `extract.py` holds all the code that reads data from its sources (databases, APIs,
  files, notebooks' exports) and saves what the report needs in `data/`. No other file
  reads a source.
- `report.py` loads what `extract.py` saved, shapes it and builds each output ticked
  above. It reads no source and holds no credentials.
- To change the design, run `report.py` again; run `extract.py` only for fresh data.

`report.py` starts like this; keep the lines of the outputs ticked above:

```python
"""Build the outputs from what extract.py saved in data/. Reads no source."""
from pathlib import Path

import pandas as pd

import briefing as bf


def load() -> pd.DataFrame:
    return pd.read_csv("data/orders.csv")


def build(orders: pd.DataFrame) -> bf.Briefing:
    regions = orders.groupby("region", as_index=False)[["revenue", "target"]].sum()
    regions["gap"] = regions["revenue"] / regions["target"] - 1
    worst = regions.sort_values("gap").iloc[0]
    met = int((regions["gap"] >= 0).sum())
    return bf.Briefing(
        bf.Text(f"## {worst['region']} is {-worst['gap']:.0%} behind target\n\n"
                f"It is the furthest behind of {len(regions)} regions."),
        bf.Group(
            bf.BigNumber("Revenue", f"${regions['revenue'].sum():,.0f}"),
            bf.BigNumber(f"Gap, {worst['region']}", f"{worst['gap']:+.0%}"),
            columns=2,
        ),
        bf.Text(f"## {met} of {len(regions)} regions met their target"),
        bf.Table(regions.style.format({"revenue": "${:,.0f}", "target": "${:,.0f}", "gap": "{:+.0%}"})
                 .hide(axis="index")),
        bf.Toggle(bf.DataTable(orders), label="Every order"),
    )


if __name__ == "__main__":
    report = build(load())
    Path("reports").mkdir(exist_ok=True)
    bf.save(report, "reports/index.html", name="Weekly sales")                       # HTML report
    bf.deck.save(bf.deck.from_report(report), "reports/deck.html", name="Weekly sales")  # Slide deck
    bf.email.to_eml(bf.email.from_report(report, link="https://example.com/index.html"),
                    "reports/digest.eml", subject="Weekly sales")                     # Email digest
    bf.save(report, "reports/embed.html", full_html=False, embed_id="weekly-sales")   # Embed
```

## Design

- Start with the answer to the reader's question: the two or three findings, each with
  its number.
- Then the evidence for each finding: one chart or one short table per point, with a
  sentence that says what it shows.
- Then the detail people may want to check: full tables, breakdowns, in a `bf.Toggle` or
  on a later `bf.Page`.
- Headings state a finding ("Churn doubled in March"), not a topic ("Churn"). One message
  per section, each under a `##` heading: a deck drafted from the report makes one slide
  of each.
- Pick the block for the point:
  - a number and its change: `bf.BigNumber`, side by side in a `bf.Group`
  - a trend or a comparison: `bf.Plot`, with the chart library the project already uses
  - a few rows to read: `bf.Table`; many rows to sort and search: `bf.DataTable`
  - something that needs attention: `bf.Alert`
  - the same view per region, per month…: `bf.Select`
  - detail most readers skip: `bf.Toggle`
  - a long report: `bf.Page`s, the summary first
- Format numbers for people: units, thousands separators, no more decimals than matter.
- Leave out any block that answers no question.

## Rules for each output (follow only the ones ticked)

### HTML report

- `bf.save(report, "reports/index.html", name=...)` writes one file that works offline.

### Slide deck

- `bf.deck.from_report(report)` (experimental) drafts a deck from the report: each `##`
  heading starts a slide. Adjust its slides, or write a `bf.deck.Deck` of `bf.deck.Slide`s
  when the talk needs its own order.
- One message per slide, stated by its title. A chart or up to three numbers per slide,
  no long tables, about 40 words at most.

### Email digest

- Mail apps run no script: a digest holds only `bf.Text`, `bf.BigNumber`, `bf.Alert`,
  `bf.Group`, `bf.Plot` and `bf.Table` of up to 30 rows.
- A few lines: the findings and their numbers, then the button to the full report
  (`link=`).
- `bf.email.from_report(report, link=...)` (experimental) drafts one from the report's
  first page. `bf.email.to_eml` writes a file to open in a mail app and check. Send
  nothing unless you are asked to.

### Embed

- `bf.save(report, path, full_html=False, embed_id=...)` writes a fragment whose styles
  stay inside it, so it doesn't clash with the host page.
- Keep it to one view, without pages.

## Check before you say it is done

1. `bf.validate(report)` returns no error.
2. Run `python report.py`.
3. Look at the result: `python -m briefing image reports/index.html` (needs
   `pip install "briefing[image]"`) saves each page as a PNG; open them. Fix what reads
   badly: crowded sections, unreadable charts, raw numbers, headings that state no
   finding.
4. Say what you built, what each output holds, and anything the ticked freedom kept you
   from doing.
