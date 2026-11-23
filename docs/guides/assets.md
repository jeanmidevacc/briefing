# Images, raw HTML and report size

Everything a report shows is inside its one HTML file. That is what makes it work
offline, forever, but it also means every image and every runtime counts towards
its size.

## Images

- **Charts**: pass the figure to {class}`~briefing.Plot`. Matplotlib figures become
  SVG, so they stay sharp.
- **A cover or section image**: use {doc}`banner`, which takes a path or bytes.
- **Any other image**: use {class}`~briefing.Image`, with a PNG, JPEG, GIF, WebP or
  SVG file or its bytes. It is embedded once, as a data URI, so it survives the report
  being emailed or moved; a link to a file or a URL wouldn't, and briefing's own tests
  reject reports that load anything from the network.

```{briefing-example}
:title: An image
:height: 220

import briefing as bf

logo = b"""<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80">
  <rect width="240" height="80" rx="12" fill="#4F46E5"/>
  <text x="120" y="50" font-size="28" font-family="sans-serif" fill="#fff" text-anchor="middle">ACME</text>
</svg>"""

bf.save(bf.Image(logo, caption="The ACME logo", width=240), "image.html", name="Images")
```

`width` takes a CSS width (`"60%"`, `"20rem"`) or a number of pixels; by default the
image shows at its natural size, shrunk to fit its column. `alt` describes it for readers
who can't see it, and defaults to the caption; with neither, the image is decorative. An
SVG is shown as an image, so a script inside it never runs.

### Lighter pictures

A photo straight from a camera or a design tool can weigh more than the rest of the
report. `max_width=2400` scales an image down to that many pixels wide (a narrower one is
left alone), and `format="webp"` re-encodes it, with `quality=` from 1 to 100 (80 by
default). `Banner` takes the same options. They need Pillow:
`pip install "briefing[pillow]"`.

```python
bf.Image("site-photo.jpg", max_width=1600, format="webp", caption="The site in May")
bf.Banner("# Q1 review", image="cover.png", max_width=2400, format="webp")
```

An SVG is vector, so `max_width` leaves it alone and it can't be re-encoded. An animated
GIF can't be resized without losing its frames, so asking is an error.

## Files to download

{class}`~briefing.Attachment` puts a file in the report for readers to download: any
file by its path, some bytes with a `filename`, or a dataframe, which downloads as CSV in
the same format as a `DataTable`'s CSV button. It shows as a link with its label and
size, and downloads from the page itself, with no server; text files are stored
compressed.

```{briefing-example}
:title: Files to download
:height: 180

import pandas as pd
import briefing as bf

orders = pd.DataFrame({"region": ["North", "South"], "revenue": [412_000, 287_500]})
notes = "# Method\n\nRevenue is net of returns, in USD.\n"

bf.save(
    bf.Group(
        bf.Attachment(orders, filename="orders.csv", label="Orders"),
        bf.Attachment(notes.encode(), filename="method.md", label="Method"),
        columns=2,
    ),
    "attachments.html",
    name="Files",
)
```

## Raw HTML

`bf.HTML` inserts markup as-is. Inline styles work, and so does any `<script>` it
contains: it isn't sandboxed or sanitised, so only pass HTML you trust. Paragraphs,
lists and headings in it get the same typography as `Text`. A comment, tag or
`<script>`/`<style>` element left open at its end is closed there, so it can't hide
the rest of the report.

## Report size

How big a report is, and what to do when it's too big: see {doc}`reports`.
