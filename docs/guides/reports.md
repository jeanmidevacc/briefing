# Reports

A report is the full output: every block, with pages, tabs, toggles and links, in one HTML
file that works offline. This page covers what belongs to the report itself; the blocks
are in the Blocks section, and the slide deck and email digest have guides of their own.

## Saving

```python
bf.save(report, "q1.html", name="Q1 review")             # the file
html = bf.stringify(report, name="Q1 review")            # the same HTML, as a string
bf.save(report, "q1.html", name="Q1 review", open=True)  # and open it in the browser
```

`bf.save` takes a {class}`~briefing.Briefing`, a list of blocks or a single block. The same
report gives the same bytes when `now=` (or the `SOURCE_DATE_EPOCH` environment variable)
pins the time it shows, so a report can be compared from run to run ({doc}`diff`) or kept
in version control. A build script can get its command line from `bf.run` ({doc}`project`).

## Pages

A report of {class}`~briefing.Page` blocks shows one page at a time, as tabs at the top.
See {doc}`layout` for pages and tab styles, and {doc}`links` for their links.

## The header

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

## The footer

Every report ends with a line saying which version of briefing made it, and names the
same version in a `<meta name="generator">` tag in the page head. `footer=` puts text
before that line, such as a team name. The line itself can't be turned off.

```python
report = bf.Briefing(bf.Text("# Q1 review"), footer="Analytics team")
# Analytics team · Made with briefing 0.7.1
```

## Size

A report with text, tables and Matplotlib charts weighs tens to a few hundred
kilobytes. The chart runtimes are embedded once per report, and only in reports that use them,
compressed: the report unpacks them as it opens, before any chart draws.

| In the report | Adds about |
| --- | --- |
| The base report (styles and scripts for tabs, tables, toggles, print) | 40 KB |
| A Plotly chart (the runtime, once, compressed) | 2.0 MB |
| An Altair chart (the Vega runtime, once, compressed) | 0.4 MB |
| A `DataTable` | its rows: in the HTML up to 1,000, compressed above |
| A `Banner`, an `Image` or a data-URI image | the image file, plus a third for base64 |
| An `Attachment` | the file, plus a third for base64; text files compressed |

`DataTable` keeps at most `max_rows` rows (10,000 by default), and `lab.DataDive`
samples down to its `max_rows`; both warn when they drop rows.

`bf.save` and `bf.stringify` warn when a report is bigger than 10 MB, and name its
largest parts with where they are in the report (the path `bf.to_spec` gives them):

```text
UserWarning: The report is 14.2 MB, over max_size (10.0 MB); its largest parts:
DataTable "orders" at /blocks/2 (9.1 MB), the Plotly runtime (2.0 MB), Banner at /blocks/0 (0.3 MB).
```

`max_size="25 MB"` (or a number of bytes) changes the limit, and `max_size=None` turns
the warning off. Chart runtimes and the copy-embed data count, since they are in the file.
`bf.validate(report)` reports the same as a `too-big` warning.

## Printing, PDF, embedding

Printing gives a layout made for paper; `bf.save_pdf` and `bf.save_image` write it as files
({doc}`export`). `bf.stringify(report, full_html=False)` gives a fragment to put in another
page ({doc}`embed`).
