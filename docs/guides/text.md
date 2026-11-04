# Text, numbers and callouts

## Markdown with `Text`

`bf.Text` takes CommonMark plus pipe tables. Leading indentation is removed, so a
triple-quoted string can follow your code's indentation. `bf.Text(file="notes.md")`
reads a Markdown file instead.

```{briefing-example}
:title: Text blocks

import briefing as bf

report = [
    bf.Text("""
        # Weekly pipeline review

        Ingestion ran **6 of 7 days**. The Sunday run failed on a schema change;
        see the [runbook](https://example.com/runbook) for the fix.

        | Stage | Median time |
        | --- | ---: |
        | Extract | 4 min |
        | Load | 11 min |

        > Next review: Monday.
    """),
]
bf.save(report, "text.html", name="Text")
```

Raw HTML inside the Markdown is passed through, as with `bf.HTML`.

## Code and formulas

`bf.Code` highlights any language Pygments knows. `bf.Formula` turns LaTeX into
MathML when the report is rendered, so the browser typesets it with no script and
no network. A formula that can't be converted shows its LaTeX source with a note,
and Python warns.

```{briefing-example}
:title: Code and formula blocks

import briefing as bf

report = [
    bf.Code(
        "SELECT region, SUM(revenue)\nFROM sales\nGROUP BY region",
        language="sql",
        caption="The query behind the table",
    ),
    bf.Formula(r"\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i", caption="Sample mean"),
    bf.HTML("<p>Raw <abbr title='HyperText Markup Language'>HTML</abbr>, inserted as-is.</p>"),
]
bf.save(report, "code.html", name="Code and formulas")
```

`bf.HTML` is inserted as-is and is not sanitised: any `<script>` in it runs. Only
pass HTML you trust.

## KPIs with `BigNumber`

`is_upward_change` sets the arrow and `is_positive_intent` sets the colour, so
"returns went up" can show an up arrow in red. A `change` with neither flag is
shown neutral, without an arrow.

```{briefing-example}
:title: BigNumber blocks

import briefing as bf

report = bf.Group(
    bf.BigNumber("Revenue", "$4.2M", change="+12%", is_upward_change=True),
    bf.BigNumber("Margin", "31.2 %", change="-0.8 pt", is_upward_change=False),
    bf.BigNumber("Return rate", "8.0 %", change="+0.2 pt", is_upward_change=True,
                 is_positive_intent=False),
    bf.BigNumber("Stores", 112, change="+3"),
    columns=4,
)
bf.save(report, "kpis.html", name="KPIs")
```

## Callouts with `Alert`

```{briefing-example}
:title: Alert blocks

import briefing as bf

report = [
    bf.Alert("The nightly load finished at 02:14.", level="success"),
    bf.Alert("South region margin dropped below 25 %.", level="warning", title="Watch"),
    bf.Alert("The legacy source is gone from 1 March.", level="error", title="Breaking change"),
    bf.Alert("Figures are provisional until the month closes."),
]
bf.save(report, "alerts.html", name="Alerts")
```
