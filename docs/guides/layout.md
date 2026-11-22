# Layout: columns, tabs, toggles and pages

Containers hold other blocks. A string passed where a block is expected becomes
a `Text`, and a dataframe becomes a `DataTable`.

## Columns with `Group`

`columns` sets the number of columns, `widths` their relative sizes, and `valign`
their vertical alignment. On a phone, columns stack; on a tablet (up to 960 px wide), a
Group of three or more columns shows two per row. Print keeps every column.

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

`min_width="16rem"` lets the width decide instead: as many cells per row as fit, each
at least that wide (up to `columns`, when it is above 1). It suits a row of KPIs or cards
that should reflow on any screen:

```{briefing-example}
:title: A Group that fits its cells
:height: 260

import briefing as bf

report = bf.Group(
    *(bf.BigNumber(region, f"{value:,}") for region, value in
      [("North", 4120), ("South", 2875), ("East", 3310), ("West", 1990), ("Online", 6045)]),
    min_width="11rem",
)
bf.save(report, "group-fit.html", name="Group with min_width")
```

## Framed sections with `Card`

A {class}`~briefing.Card` draws a frame and a heading line around blocks stacked in one
column, where a `Group` only lays blocks side by side. It takes a `title` (with inline
Markdown), an `icon` such as an emoji, `tags` shown as chips at the bottom, and a `link`
to a block or heading: the whole card then leads there, while links inside it keep their
own targets. Put cards in a `Group` with `min_width=` so they reflow on any screen.

```{briefing-example}
:title: Cards that lead to sections
:height: 320

import briefing as bf

report = bf.Briefing(
    bf.Page(
        bf.Group(
            bf.Card("Pizza, fast food, delivery and snacks", title="Food and delivery", icon="🍕",
                    tags=["Pizza", "Uber Eats", bf.Chip("DoorDash +18%", color="up")],
                    link="detail/food"),
            bf.Card(bf.BigNumber("Searches", 14, prev_value=11), title="Streaming", icon="📺",
                    link="detail/streaming"),
            bf.Card("Steam, Twitch and Discord", title="Gaming", icon="🎮"),
            min_width="15rem",
        ),
        title="Overview",
    ),
    bf.Page(
        bf.Text("## Food and delivery {#food}\n\nWhat moved, search by search."),
        bf.Text("## Streaming {#streaming}\n\nFilms and series."),
        title="Detail",
        name="detail",
    ),
)
bf.save(report, "cards.html", name="Cards")
```

## Tabs and dropdowns with `Select`

Each child's `label` is its tab title. `type="dropdown"` gives a menu instead of a
row of tabs, which suits long lists. A dropdown is named after the Select's own `label`
for screen readers ("Choose a view" without one), and each panel is announced by its
option's name.

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

## Tab styles

{class}`~briefing.TabStyle` sets how a row of tabs looks: pass it as
`Briefing(tabs=...)` for the page tabs, or as `Select(style=...)` for one Select.

- `layout`: `"start"` (default), `"center"`, or `"stretch"`, where each tab takes an
  equal share of the line.
- `full_width=True` runs the tab line edge to edge across the window; the tabs stay
  aligned with the content.
- `sticky=True` keeps the tab bar at the top of the window while the reader scrolls.
- `size`: `"sm"`, `"md"` (default) or `"lg"`.
- `variant`: `"underline"` (default), `"pills"` or `"boxed"`.

A report that sets no style looks as it always has. In the JSON form, a style is an
object such as `"tabs": {"layout": "stretch", "sticky": true}`.

```{briefing-example}
:title: Styled tabs
:height: 420

import briefing as bf

notes = [bf.Text(f"Section {i}. " * 30) for i in range(1, 6)]
report = bf.Briefing(
    bf.Page(
        bf.Select(
            bf.Text("The chart would go here.", label="Chart"),
            bf.Text("And the data here.", label="Data"),
            style=bf.TabStyle(variant="pills", size="sm"),
        ),
        *notes,
        title="Summary",
    ),
    bf.Page(*notes, title="Regional detail"),
    bf.Page(bf.Text("How the numbers were made."), title="Method"),
    tabs=bf.TabStyle(layout="stretch", full_width=True, sticky=True),
)
bf.save(report, "tab-style.html", name="Tab styles")
```

## Links to pages, tabs and headings

A block's `name` is also its link. Links come only from names, never from titles, so
rewording a title breaks no link:

| What | Name it | Its link |
| --- | --- | --- |
| A page | `bf.Page(..., name="detail")` | `q1.html#detail` |
| A tab, or any block, in that page | `bf.Text(..., label="By region", name="by-region")` | `q1.html#detail/by-region` |
| A heading in a `Text` in that page | `## Methodology {#methodology}` | `q1.html#detail/methodology` |

Outside a named page, a name links as itself: `q1.html#by-region`.

Opening a link selects its page and tab, opens any `Toggle` around it and scrolls to
it, also in a file opened offline. Choosing a tab puts its link in the address bar,
without adding a step to the browser's history, so a reload keeps the tab open and the
address can be shared. A named heading shows a link icon on hover that copies its link.
A Markdown link such as `[the method](#detail/methodology)` jumps there.

A name must be unique within its page: two blocks or headings with the same name in one
page raise an error when the report is rendered. Different pages may reuse a name.

## The report header

The header shows the report's name (`bf.save(report, path, name=...)`) and when it was
rendered. {class}`~briefing.Header` adds a subtitle (with inline Markdown), an author, a
logo embedded in the report, the date the data runs to, and the time zone for the times
it shows (UTC without one):

```{briefing-example}
:title: A report header
:height: 260

import briefing as bf

logo = (b'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
        b'<circle cx="32" cy="32" r="28" fill="#4f46e5"/></svg>')
report = bf.Briefing(
    bf.Text("Search interest rose after the release."),
    header=bf.Header(
        subtitle="Weekly search interest, **worldwide** and US",
        author="Analytics team",
        logo=logo,
        as_of="2026-11-20",
        tz="America/Montreal",
    ),
)
bf.save(report, "header.html", name="Search report")
```

The header shows when the report has a name, a `header=` or an export menu. The default
name, "Report", is never shown as a title.

## The report footer

Every report ends with a line saying which version of briefing made it, and names the
same version in a `<meta name="generator">` tag in the page head. `footer=` puts text
before that line, such as a team name. The line itself can't be turned off.

```python
report = bf.Briefing(bf.Text("# Q1 review"), footer="Analytics team")
# Analytics team · Made with briefing 0.4.1
```
