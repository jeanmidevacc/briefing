# Layout: columns, tabs, toggles and pages

Containers hold other blocks. A string passed where a block is expected becomes
a `Text`, and a dataframe becomes a `DataTable`.

## Columns with `Group`

`columns` sets the number of columns, `widths` their relative sizes, and `valign`
their vertical alignment. On a phone, columns stack.

```{briefing-example}
:title: A Group in columns

import briefing as bf

report = bf.Group(
    bf.Text("### Wide column\n\nTwo thirds of the width: room for a chart or a table."),
    bf.Alert("One third: a note beside it.", title="Side note"),
    columns=2,
    widths=[2, 1],
)
bf.save(report, "group.html", name="Group")
```

## Tabs and dropdowns with `Select`

Each child's `label` is its tab title. `type="dropdown"` gives a menu instead of a
row of tabs, which suits long lists.

```{briefing-example}
:title: A Select with tabs

import pandas as pd
import briefing as bf

by_region = pd.DataFrame({"region": ["North", "South"], "revenue": [412_000, 287_500]})

report = bf.Select(
    bf.Text("Revenue grew in every region but the South.", label="Summary"),
    bf.DataTable(by_region, label="By region"),
    bf.Code("SELECT region, SUM(revenue) FROM sales GROUP BY 1", language="sql", label="Query"),
)
bf.save(report, "select.html", name="Select")
```

## Hidden detail with `Toggle`

A `Toggle` starts closed; its `label` is the clickable title. Several children are
wrapped in a `Group` for you.

```{briefing-example}
:title: A Toggle

import briefing as bf

report = [
    bf.Text("Revenue is recognised on shipment."),
    bf.Toggle(
        bf.Text("**Source**: the orders warehouse, refreshed nightly at 02:00 UTC."),
        bf.Code("SELECT * FROM dw.orders WHERE shipped_at IS NOT NULL", language="sql"),
        label="Methodology",
    ),
]
bf.save(report, "toggle.html", name="Toggle")
```

## Pages

`Page` blocks at the top of a `Briefing` become the report's pages, with a tab bar
at the top. Pages can't be nested: use `Select` and `Group` inside a page. When the
report is printed or exported, each page starts on a new sheet.

```{briefing-example}
:title: A report with pages

import briefing as bf

report = bf.Briefing(
    bf.Page(
        bf.Group(bf.BigNumber("Revenue", "$1.25M"), bf.BigNumber("Orders", 8_421), columns=2),
        title="Summary",
        name="summary",
    ),
    bf.Page(bf.Text("## Detail\n\nThe numbers behind the summary."), title="Detail"),
)
bf.save(report, "pages.html", name="Q1 review")
```

A page's `name` lets {func}`~briefing.save_image` and {func}`~briefing.save_pdf`
pick it with `page="summary"`.

## The report footer

Every report ends with a line saying which version of briefing made it, and names the
same version in a `<meta name="generator">` tag in the page head. `footer=` puts text
before that line, such as a team name. The line itself can't be turned off.

```python
report = bf.Briefing(bf.Text("# Q1 review"), footer="Analytics team")
# Analytics team · Made with briefing 0.3.0
```
