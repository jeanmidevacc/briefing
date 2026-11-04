# Images, raw HTML and report size

Everything a report shows is inside its one HTML file. That is what makes it work
offline, forever, but it also means every image and every runtime counts towards
its size.

## Images

- **Charts**: pass the figure to {class}`~briefing.Plot`. Matplotlib figures become
  SVG, so they stay sharp.
- **A cover or section image**: use {doc}`banner`, which takes a path or bytes.
- **Any other image**: put it in `bf.HTML` or `bf.Text` as a data URI. A link to a
  file or a URL wouldn't survive the report being emailed or moved, and briefing's
  own tests reject reports that load anything from the network.

```{briefing-example}
:title: An inline SVG image

import base64
import briefing as bf

logo = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40">
  <rect width="120" height="40" rx="8" fill="#4F46E5"/>
  <text x="60" y="26" font-size="16" font-family="sans-serif" fill="#fff" text-anchor="middle">ACME</text>
</svg>"""
src = "data:image/svg+xml;base64," + base64.b64encode(logo.encode()).decode()

report = [
    bf.HTML(f'<img src="{src}" alt="ACME logo" width="120" height="40">'),
    bf.Text("Any image can be embedded this way: read the file, base64-encode it, "
            "and use a `data:` URI."),
]
bf.save(report, "image.html", name="Images")
```

For a PNG or JPEG file it's the same, with its own MIME type:

```python
from pathlib import Path

data = base64.b64encode(Path("photo.jpg").read_bytes()).decode()
bf.HTML(f'<img src="data:image/jpeg;base64,{data}" alt="..." style="max-width:100%">')
```

## Raw HTML

`bf.HTML` inserts markup as-is. Inline styles work, and so does any `<script>` it
contains: it isn't sandboxed or sanitised, so only pass HTML you trust. Paragraphs,
lists and headings in it get the same typography as `Text`.

## Report size

A report with text, tables and Matplotlib charts weighs tens to a few hundred
kilobytes. The chart runtimes are embedded once per report, and only in reports that use them:

| In the report | Adds about |
| --- | --- |
| The base report (styles and scripts for tabs, tables, toggles, print) | 40 KB |
| A Plotly chart (the runtime, once) | 4.6 MB |
| An Altair chart (the Vega runtime, once) | 0.9 MB |
| A `DataTable` | its rows, as JSON |
| A `Banner` or a data-URI image | the image file, plus a third for base64 |

`DataTable` keeps at most `max_rows` rows (10,000 by default), and `lab.DataDive`
samples down to its `max_rows`; both warn when they drop rows.
