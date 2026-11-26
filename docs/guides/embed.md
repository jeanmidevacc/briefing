# Embed in other pages

A report is a whole page. To put one chart, table or section into another page (a
docs site, a notebook next to other output, a wiki page) and keep its look and
interactivity, render it as a **fragment**: one `<div>` that carries its theme, keeps
its CSS and scripts to itself, and works next to other fragments on the same page.

```python
frag = bf.stringify(chart, full_html=False)          # one <div class="bf-embed">
bf.save(report, "q1-embed.html", full_html=False)     # the same, as a file
```

This is the fragment below, inserted into this page as it is, between the code and
the next heading:

```{briefing-example}
:title: A fragment in this page

import pandas as pd
import briefing as bf

by_region = pd.DataFrame({"region": ["North", "South", "East"], "revenue": [412_000, 287_500, 351_200]})

report = bf.Select(
    bf.Group(
        bf.BigNumber("Revenue", "$1.05M", change="+8%", is_upward_change=True),
        bf.BigNumber("Regions", 3),
        columns=2,
        label="Summary",
    ),
    bf.DataTable(by_region, label="By region"),
    name="q1",
)
bf.save(report, "q1-embed.html", full_html=False)
```

## Like Plotly's `full_html=False`

| Plotly | briefing |
| --- | --- |
| `fig.to_html(full_html=False)` | `bf.stringify(blocks, full_html=False)` |
| `fig.write_html(path, full_html=False)` | `bf.save(blocks, path, full_html=False)` |
| `include_plotlyjs=True` / `False` | `include_assets=True` / `False` |
| `plotly.offline.get_plotlyjs()` | `bf.embed_assets(blocks)` |
| `div_id=` | `embed_id=` |
| `include_plotlyjs="cdn"` | none: fragments stay offline, like reports |

- **`embed_id`** is the fragment's id, and every id inside it starts with it. It
  defaults to the name of the fragment's only block (`name="q1"` above), else to `bf-e`
  and 8 hex digits of a hash of the fragment. Two fragments on one page need two ids.
- **`header=True`** shows `name=` and the date above the fragment; by default it has
  none. Every fragment ends with the "Made with briefing" line, as a report does.
- **`formatting=`** themes one fragment, so a dark and a light one can share a page.
- **`now=`** and `SOURCE_DATE_EPOCH` work as for reports: the same input gives the same
  bytes.

## Several fragments on one page

Each fragment carries briefing's CSS and scripts, and the chart runtimes it needs
(Plotly, Vega). They define themselves once per page, so fragments that each bring
them still work together. To send them only once, put `bf.embed_assets` in the page's
`<head>` and render each fragment with `include_assets=False`:

```python
head = bf.embed_assets([chart, table])  # <style> and <script> tags, for the <head>
parts = [bf.stringify(b, full_html=False, include_assets=False) for b in (chart, table)]
```

## Copy a part of a report, without Python

A report built with `export="embed"` lets its readers do the same from the page: a `</>`
button on each page, labelled group, row of blocks side by side, chart, table, text,
number, alert, banner and lab block copies that part as a fragment, ready to paste into another page.

```python
report = bf.Briefing(
    bf.Page(bf.Text("# Summary"), bf.Plot(fig), title="Summary", name="summary"),
    bf.Page(bf.DataTable(df, name="rows"), title="Detail", name="detail"),
    export="embed",  # or ("png", "embed") with the "Save as PNG" button
)
```

- The button shows on hover and on keyboard focus, and says what it copies ("Copy embed
  code for the Summary page"). A note confirms the copy and its size.
- **What is copied is the report as it was made,** not as it looks after clicks: a sorted
  or searched table, a different tab or a zoomed chart come back as they were. The report
  carries a compressed copy of its untouched blocks for this.
- **One paste works on its own:** the fragment carries its CSS, scripts and chart runtime,
  as `include_assets=True` does. A copied Plotly chart is about 4.5 MB for that reason.
- Where the browser refuses to copy (some notebook frames), the code shows in a dialog,
  selected, to copy by hand.
- The buttons never print, and never show in `save_image`, `save_pdf`, "Save as PNG" or
  fragments. A report without `export="embed"` has none of this.
- It costs about 30 KB in a report of 100 KB.

## What a fragment keeps to itself

- **Nothing leaks out.** Every CSS rule starts with `.bf-embed` or the fragment's id,
  and its scripts work inside its `<div>` only.
- **Little leaks in.** The fragment sets every inherited property it relies on and
  paints its own background. The host's rules for plain elements (`p`, `table`, `*`)
  and a changed root font size don't reach it; rules more specific than one class and
  one element can.
- **Links** to its pages, tabs and headings ({doc}`layout`) open and scroll inside
  the fragment, and never change the address of the host page.
- **Printing** opens its toggles and labels its tabs, as in a report.

## Where it works

A fragment needs a page that accepts raw HTML with its scripts:

| Host | How |
| --- | --- |
| Docs sites and blogs (Sphinx, MkDocs, static sites) | Paste it into the page's HTML, as this page does. |
| Jupyter | `IPython.display.HTML(frag)` |
| Databricks | `displayHTML(frag)` |
| Streamlit | `streamlit.components.v1.html(frag, height=…)` |
| Confluence Data Center | The HTML macro, which an admin must enable. |
| Confluence Cloud | A Marketplace HTML app. |

It doesn't work where an editor cleans pasted HTML or inserts it without running its
scripts. To share a whole report there instead, attach the `.html` file or export an
image ({doc}`export`).
