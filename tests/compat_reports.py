"""Reference reports whose <body> must stay as 0.1.2 rendered it (0.2.0 definition of done).

Only the shared CSS/JS and the theme variables may grow; the markup a reader sees may not.
Regenerate the golden files only with the released 0.1.2 package:
``python tests/compat_reports.py tests/snapshots/compat_0_1_2`` in a venv with briefing==0.1.2.
"""
from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

NOW = datetime(2024, 1, 2, 3, 4, tzinfo=UTC)


def reports() -> dict[str, object]:
    import pandas as pd

    import briefing as bf

    df = pd.DataFrame({"region": ["North", "South", "East"], "revenue": [1200.5, 980.0, 1530.25]})
    blocks = bf.Briefing(
        bf.Text("# Sales\n\nSome **markdown** and a table:\n\n| a | b |\n| --- | --- |\n| 1 | 2 |"),
        bf.Group(
            bf.BigNumber("Revenue", "$4.2M", change="+12%", is_upward_change=True),
            bf.BigNumber("Users", "142K", change="+3%"),
            columns=2,
        ),
        bf.Alert("Margin dropped.", level="warning", title="Heads up"),
        bf.Code("SELECT 1", language="sql"),
        bf.Select(bf.DataTable(df, label="Data"), bf.Table(df, label="Static")),
        bf.Select(bf.Text("one", label="One"), bf.Text("two", label="Two"), type="dropdown"),
        bf.Toggle(bf.HTML("<p>raw</p>"), label="More"),
    )
    pages = bf.Briefing(bf.Page(bf.Text("# Summary"), title="Summary"), bf.Page(bf.DataTable(df), title="Detail"))
    return {"blocks": blocks, "pages": pages}


def body_markup(html: str) -> str:
    """The <body> of a report without its trailing report script."""
    body = html[html.index("<body>"):html.rindex("</body>")]
    return re.sub(r"<script>(?:(?!</script>).)*</script>\s*$", "", body, flags=re.S)


if __name__ == "__main__":
    import briefing as bf

    out = Path(sys.argv[1])
    for name, report in reports().items():
        (out / f"{name}.body.html").write_text(body_markup(bf.stringify(report, name="Reference", now=NOW)))
        print("wrote", out / f"{name}.body.html", "with briefing", bf.__version__)
