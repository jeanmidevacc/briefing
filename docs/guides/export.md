# Printing, images and PDF

A report is a web page, but it often needs to end up as a slide, a social card or an
attachment. There are four ways out, from the simplest to the most controlled.

## Printing

Print the report from the browser (Ctrl+P or ⌘P, or "Save as PDF" in the print
dialog) and it prints *everything*, not just what is on screen:

- every page and every tab prints under its label, and each top-level `Page` starts
  on a new sheet;
- toggles print open; tab bars, dropdowns, search boxes and pagination are hidden;
- a `DataTable` prints up to 1,000 rows matching its search, with a note giving the
  total;
- charts are resized to the paper's width; KPI groups, charts and alerts avoid
  splitting across sheets; colours print.

The screen layout comes back after printing. This is what a printed sheet looks
like ({download}`the whole sample PDF <../_static/export/sample.pdf>`):

```{image} ../_static/export/print.png
:alt: The print layout of a two-page report, with both pages under their titles.
:width: 480px
```

## `save_image` and `save_pdf`

For files you can attach, post or rebuild in a pipeline, {func}`~briefing.save_image`
and {func}`~briefing.save_pdf` render the report in headless Chromium, with every
network request blocked. They need an extra and, once, a browser download:

```bash
pip install "briefing[image]"
playwright install chromium
```

Both accept a `Briefing`, a block or a list of blocks, or the path to a saved
report `.html`, and both work in a notebook.

### Images

```python
import briefing as bf

bf.save_image(report, "q1.png")                       # one PNG per page: q1_summary.png, q1_detail.png
bf.save_image(report, "summary.png", page="summary")  # one page, by name, title or index
bf.save_image(report, "summary.jpg", page=0, width=1000, scale=1)   # .jpg and .webp work too
bf.save_image(report, "card.png", page=0, size="og")  # a 1200×630 social card
```

`width` is the layout width in CSS pixels and `scale` the pixels per CSS pixel, so
the default `width=1200, scale=2` gives 2,400-pixel-wide images. Toggles are opened
first unless `expand=False`.

A full page, `page="summary", width=1000, scale=1`:

```{image} ../_static/export/page.png
:alt: The summary page of the sample report as an image.
:width: 560px
```

`size="og"`, `"square"` (1080×1080) or `"portrait"` (1080×1350) lays the page out at
`width`, then shrinks it to fit the card, centred on the theme background, and never
crops it. Below half size, a warning suggests `size=None`. For square and portrait
cards a narrower `width`, around 800, fills the card better.

```{image} ../_static/export/og.png
:alt: The summary page shrunk into a 1200 by 630 social card.
:width: 560px
```

### PDF

```python
bf.save_pdf(report, "q1.pdf")                               # every page, each on a new sheet
bf.save_pdf(report, "summary.pdf", page="summary", paper="letter", landscape=True)
```

The PDF uses the print layout above. Text stays selectable, links stay clickable,
and SVG charts stay vector. `paper` is `"a4"` (default), `"letter"`, `"legal"`, `"a3"`
or `"a5"`.

## From the command line

The same exports run on a saved report, with `python -m briefing`:

```bash
python -m briefing image report.html --page all -o out/       # one PNG per page in out/
python -m briefing image report.html --size og -o card.png
python -m briefing pdf report.html -o report.pdf --paper letter
python -m briefing image --help                                # every option
```

## An export menu in the report

`bf.Briefing(..., export=("png", "pdf"))` adds buttons to the report header, so
readers can export it themselves. "Save as PNG" draws the open page in the reader's
browser at 2× and downloads it; "Print" opens the print dialog. It is opt-in: a
report without `export=` contains no export code.

```{briefing-example}
:title: A report with the export menu

import briefing as bf

report = bf.Briefing(
    bf.Text("# Q1 review\n\nUse the buttons in the header to save this page."),
    bf.Group(bf.BigNumber("Revenue", "$1.25M"), bf.BigNumber("Orders", "10,050"), columns=2),
    export=("png", "pdf"),
)
bf.save(report, "export-menu.html", name="Q1 review")
```

"Save as PNG" is best effort: charts drawn in a frame (Bokeh) and WebGL Plotly
traces come out blank, and fonts are whatever the reader's machine has. For exact,
reproducible files, use `save_image` and `save_pdf`. Inside this page's frame, your
browser may block the download; open the full page to try it.
