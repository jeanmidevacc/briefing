# Links

Every named block, page, slide and heading has a link: an address that opens the report (or
the deck) at that place, from another page, an email or a chat message.

## In a report

A block's `name` is also its link. Links come only from names, never from titles, so
rewording a title breaks no link:

| What | Name it | Its link |
| --- | --- | --- |
| A page | `bf.Page(..., name="detail")` | `q1.html#detail` |
| A tab, or any block, in that page | `bf.Text(..., label="By region", name="by-region")` | `q1.html#detail/by-region` |
| A heading in a `Text` in that page | `## Methodology {#methodology}` | `q1.html#detail/methodology` |

Outside a named page, a name links as itself: `q1.html#by-region`.

Opening a link selects its page and tab, opens any `Toggle` around it and scrolls to
it, also in a file opened offline. Choosing a tab puts its link in the address bar,
without adding a step to the browser's history, so a reload keeps the tab open and the
address can be shared. A named heading shows a link icon on hover that copies its link.
A Markdown link such as `[the method](#detail/methodology)` jumps there.

A name must be unique within its page: two blocks or headings with the same name in one
page raise an error when the report is rendered. Different pages may reuse a name.

## In a slide deck

A slide's `name` is its link (`q3-deck.html#summary`), and the slide's number works too
(`q3-deck.html#3`). A named slide scopes names as a page does: a block named `margin` in
the slide named `summary` links as `#summary/margin`. Opening a link shows its slide. See
{doc}`decks`.

## In an email digest

A digest's Markdown links into the report, such as `[the detail](#detail/regions)`, lead
into the full report at the address the digest's `link=` gives
(`https://example.com/q3.html#detail/regions`). Without `link=`, `bf.email.Digest` refuses
them, and `bf.email.from_report` keeps only their words. See {doc}`email`.

## Comparing runs

`bf.diff` matches the blocks of two runs by their links, so name the blocks you want
compared from run to run. See {doc}`diff`.
