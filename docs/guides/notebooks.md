# Notebooks

In Jupyter, JupyterLab or VS Code, a block or a `Briefing` previews itself when it
is the last expression of a cell. Each preview is the complete report in its own
frame, sized to its content, so previews never affect each other or the notebook.

That makes a natural workflow: build one block per cell, look at it, keep going,
then combine everything into one `Briefing` at the end and save it.

```python
import briefing as bf

kpis = bf.Group(bf.BigNumber("Revenue", "$4.2M"), bf.BigNumber("Orders", 8_421), columns=2)
kpis                                   # previews the two numbers

table = bf.DataTable(df)
table                                  # previews the table

report = bf.Briefing(bf.Text("# Q1"), kpis, table)
bf.preview(report, name="Q1", formatting=bf.Formatting.dark())   # name and theme, as saved
bf.save(report, "q1.html", name="Q1", formatting=bf.Formatting.dark())
```

{func}`~briefing.preview` shows a block with the report name and theme you will
save with. In a notebook that isn't trusted yet, for example one you just cloned,
Jupyter hides frames: run the cell, or trust the notebook, to see the preview.

`bf.save_image` and `bf.save_pdf` work in a notebook too: they run Chromium in a
worker thread, because Playwright can't run inside the notebook's event loop.

The repository's
[notebook walkthrough](https://github.com/jeanmidevacc/briefing/blob/main/examples/notebook_walkthrough.ipynb)
builds a full report this way.
