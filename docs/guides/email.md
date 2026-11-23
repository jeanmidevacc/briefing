# Email digests

A report can't go into an email as it is: mail apps run no script, many drop SVG and
images written into the HTML, and Outlook on Windows lays HTML out with Word. So the email
is a **digest**: a few blocks that say what matters today, built for mail apps, with a
button to the full report.

```python
import smtplib
import briefing as bf

digest = bf.email.Digest(
    bf.Text("## Daily collection, Oct 24\n\n**2 sources** below target. See [the detail](#detail/sources)."),
    bf.Group(
        bf.BigNumber("Calls", 1284, prev_value=1247),
        bf.BigNumber("Failed", "2.1%", change="+0.4 pts", is_upward_change=True),
        columns=2,
    ),
    bf.Alert("News collection missed 3 runs.", level="warning"),
    bf.Plot(fig, caption="Calls per day, last 30 days"),
    link="https://example.com/report.html",
    footer="Data team",
)

message = bf.email.to_message(digest, subject="Daily collection digest", to="team@example.com")
with smtplib.SMTP("localhost") as smtp:  # or the Gmail API, SES…: sending is yours
    smtp.send_message(message)
```

- **Blocks:** `Text`, `BigNumber`, `Alert`, `Group`, `Plot` and `Table` (up to 30 rows).
  Anything interactive (`DataTable`, `Select`, `Toggle`, lab blocks) is an error: link to
  the full report for it.
- **Links:** `link=` adds an "Open the full report" button, and `#anchor` links in `Text`
  lead into that report (`report.html#detail/sources`); see the links guide.
- **Charts** become PNG images attached to the email. Matplotlib draws them itself,
  Altair through the `vl-convert` that `briefing[altair]` installs, and Plotly needs
  `pip install kaleido`. Bokeh needs a browser to draw, so it can't go in an email.
- **Layout:** tables 640 px wide, every style inline, no script, no SVG; the theme's
  colours come from `formatting=`. Raw HTML in `Text` is shown as text. A `BigNumber`'s
  sparkline is left out, as mail apps don't draw SVG.
- **Plain text:** every message carries a plain-text version too, for mail apps that show
  no HTML.

`bf.email.to_eml(digest, "digest.eml", subject=...)` writes the message to a file you can
open in a mail app before sending, and `bf.email.to_html(digest)` gives the HTML and its
images, for delivery code of your own.

## From a report (experimental)

```{admonition} Experimental
:class: warning

`bf.email.from_report` is experimental: what it returns may change in any release, without a
deprecation period. It warns `bf.ExperimentalWarning` once per session; silence it with
`warnings.filterwarnings("ignore", category=bf.ExperimentalWarning)`.
```

`bf.email.from_report(report, link=...)` turns one page of a report into a first draft of a
digest: an ordinary `Digest`, to adjust before sending.

```python
digest = bf.email.from_report(report, link="https://example.com/q3.html", page="summary")
message = bf.email.to_message(digest, subject="Q3 review", to="team@example.com")
```

| In the report | In the digest |
| --- | --- |
| `Text`, `BigNumber`, `Alert`, `Plot` | Kept |
| `Group` | Kept, with only what an email shows |
| `DataTable`, a long `Table` | A `Table` of the first 30 rows (formats applied), and a line saying it was cut |
| `Select` | Its first panel |
| `Card`, `Banner`, `Chips` | Their text (a card's title in bold, then its blocks) |
| `Toggle`, `Image`, `Attachment`, `Code`, `Formula`, `HTML`, lab blocks | Left out, named in one warning |

`page=` picks the page (an index, a title or a name; the first by default), since a digest is
short. Without `link=`, links into the report keep only their words; with it, they lead into
the full report.
