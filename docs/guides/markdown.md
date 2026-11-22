# Markdown-first reports

A report often starts as an outline in Markdown, with notes such as "[Add the chart of
calls here]". {func}`~briefing.from_markdown` makes that outline the report: the prose
stays in the `.md` file, and Python supplies only the values and the blocks.

```markdown
## Daily collection {#auto}

The {sources} sources made {calls:,} calls yesterday.

::: block kpis
[Add the KPIs: calls and failures]
:::

{failing} sources are below target.
```

```python
report = bf.from_markdown(
    "report.md",
    values={"sources": 12, "calls": 1284, "failing": 2},
    blocks={"kpis": bf.Group(bf.BigNumber("Calls", 1284), bf.BigNumber("Failed", "2.1%"), columns=2)},
)
bf.save(report, "report.html", name="Daily collection")
```

- **Prose** is Markdown, as in `Text`, filled from `values` as `Text(values=)` fills it:
  `{name}` and `{name:spec}`, each value shown exactly as written, and code left alone.
  `{#name}` and `{#auto}` give headings their link names.
- **A slot** is a `::: block <name>` line closed by `:::`. `blocks[name]` fills it: a block,
  a list of blocks, a string or a dataframe. What the fence holds is a note for the author
  and isn't shown, so the outline's notes become its placeholders.
- **Pages:** `pages=True` starts a page at each `# Heading`; `{#name}` or `{#auto}` names it.
- **Errors say where:** `report.md:3: no value for {calls}`,
  `report.md:5: no block for the slot 'kpis'`; a block given but never used is an error
  too, so a renamed slot isn't missed.
- The report's own options (`footer`, `header`, `export`, `tabs`) go to `from_markdown`
  as they would to `Briefing`.

Plain Markdown with named slots is also what an agent edits best: the prose can change
without touching the Python, and the Python without touching the prose.

```{briefing-example}
:title: A report from Markdown
:height: 360

import briefing as bf

outline = """
## Daily collection {#auto}

The {sources} sources made {calls:,} calls yesterday.

::: block kpis
[Add the KPIs: calls and failures]
:::

{failing} sources are below target.
"""
report = bf.from_markdown(
    outline,
    values={"sources": 12, "calls": 1284, "failing": 2},
    blocks={"kpis": bf.Group(bf.BigNumber("Calls", 1284, prev_value=1247),
                             bf.BigNumber("Failed", "2.1%"), columns=2)},
)
bf.save(report, "markdown-first.html", name="Daily collection")
```
