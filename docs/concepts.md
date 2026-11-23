# How briefing works

briefing is a small **grammar of blocks**, and three **outputs** built from it. Learn the
blocks once; then the same blocks make a report, a slide deck or an email digest.

## Blocks

A block is one thing on the page: a paragraph (`Text`), a number (`BigNumber`), a chart
(`Plot`), a table (`DataTable`), a callout (`Alert`), a picture (`Image`), and a few more.
Each block is a Python class whose options are keyword arguments, and only holds data: it
never writes HTML itself.

```python
bf.BigNumber("Revenue", 4.2e6, prev_value=3.9e6, format="${:,.0f}")   # ▲ +7.7%, in green
```

**Containers** hold other blocks and lay them out:

| Container | Lays its blocks out as |
| --- | --- |
| `Group` | Columns, which stack on a phone |
| `Card` | A framed box with a title |
| `Select` | Tabs, or a dropdown, one panel at a time |
| `Toggle` | Hidden detail, opened on click |
| `Page` | Pages of a report, as tabs at the top |

Where a block is expected, a string becomes a `Text` and a dataframe a `DataTable`, so
`bf.Group("**Note**: provisional", df)` works as it reads. See the {doc}`guides/layout`.

## Names and links

Any block can take a `name`: a stable id such as `"by-region"`. A name is the block's link
(`report.html#detail/by-region`), what `bf.diff` matches from one run to the next, and how
the JSON form refers to the block. Titles can change without breaking anything; names
shouldn't. See {doc}`guides/links`.

## The theme

One {class}`~briefing.Formatting` styles the whole output: colours, fonts, width. It can
come from one brand colour (`bf.Formatting.from_accent("#0f766e")`), and charts can follow
it. Every block reads the same `--bf-*` variables, so nothing needs CSS of its own. See
{doc}`guides/theming`.

## Three outputs

|  | Report | Slide deck | Email digest |
| --- | --- | --- | --- |
| **For** | Exploring and reference | Presenting, or sending round as a PDF | A short summary in the inbox |
| **Holds** | Every block: pages, tabs, links | Every block, one slide at a time | Text, numbers, alerts, charts as images, short tables |
| **Interactive** | Yes | Yes in the browser, as it shows in a PDF | No: mail apps run no script |
| **Made with** | `bf.Briefing` → `bf.save` | `bf.deck.Deck` → `bf.deck.save` | `bf.email.Digest` → `bf.email.to_message` |
| **From a report** | — | `bf.deck.from_report` (experimental) | `bf.email.from_report` (experimental) |

Each output is **one self-contained file**: every script, style, font choice and image is
inside it, so it opens offline, forever, with no server or account. The report and the deck
are HTML pages that also print and export to PDF and images; the digest is a standard email
message, with its charts attached as images.

## Ways to write it

The same blocks can be written four ways:

- **In Python**, as above. See the {doc}`quickstart`.
- **In Markdown**, with Python filling in values and blocks. See {doc}`guides/markdown`.
- **As a project**, with a build script, its Markdown and its theme. See {doc}`guides/project`.
- **As JSON**, which coding agents write and `bf.validate` checks. See {doc}`guides/json`.

Whichever way it's written, a report has the same JSON form (`bf.to_spec`), so a person
and an agent can work on the same report.
