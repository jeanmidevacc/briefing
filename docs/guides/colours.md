# Colours and scales

A colour in a report should mean something: the same value, the same category, the same
direction. briefing's colour tools keep that true across blocks, and readable for everyone.

## One colour per value: `bf.Scale`

A {class}`~briefing.Scale` says which colour a value gets. With a `domain`, a colour means
the same value in every block that uses the scale; colours are mixed in OKLab, so equal
steps in value look like equal steps in colour.

```python
interest = bf.Scale(["#1b2c80", "#9a3fc4", "#f5479a", "#ffc46b"], domain=(0, 100))
interest(42)                                              # the hex colour of 42
bf.lab.CalendarHeatmap(df, date="day", value="interest", colors=interest)

balance = bf.Scale(["#d73027", "#f7f7f7", "#1a9850"], center=0)   # diverging around 0
levels = bf.Scale(["#e0e7ff", "#4f46e5"], domain=(0, 100), steps=5)  # five flat classes
```

## Named palettes

A domain of category names makes a scale categorical: one colour per category, such as
party or product colours, the same in every chart.

```python
parties = bf.Scale(["#d71920", "#1a4782", "#f37021"], domain=["Liberal", "Conservative", "NDP"])
parties("NDP")                                            # '#f37021'
px.bar(df, x="riding", y="votes", color="party", color_discrete_map=parties.mapping)
```

## One legend for the page: `bf.Legend`

When several blocks share a scale, show its legend once with {class}`~briefing.Legend`
(and `legend=False` on the calendars), with the dates of events if you mark any:

```python
report = bf.Briefing(
    bf.Legend(interest, title="Search interest, 0 to 100"),
    bf.Group(*calendars, columns=2),   # each CalendarHeatmap(..., colors=interest, legend=False)
)
```

The {doc}`lab` guide shows scales and legends on calendars, live.

## Charts in the theme's colours

`Formatting.categorical()` is the theme's palette for categories: the accent, then hues
that stay apart for colour-blind readers. `Formatting.plotly_template()` and
`Formatting.mpl_style()` use it for Plotly and Matplotlib charts. See {doc}`charts`.

## Checking a palette

`bf.color.check(colors, background=..., kind=...)` lists what makes a palette hard to read:
colours below 3:1 contrast against the background, colours too close to tell apart, pairs
that look alike to colour-blind readers (protanopia and deuteranopia are warnings,
tritanopia, which is rare, a note), and a sequential palette whose lightness doesn't rise
all the way. `bf.color.contrast`, `bf.color.simulate` and `bf.color.distance` are there
for your own checks.

```python
import briefing as bf

for finding in bf.color.check(["#2dd4bf", "#60a5fa", "#a3e635"], background="#1a1a1a"):
    print(finding.level, finding.message)
```
