"""Regenerate the sample images and PDF shown in guides/export.md.

The documentation build has no browser, so these files are committed. Run
``nox -s docs-assets`` (or this script, with ``briefing[image]`` installed and
``playwright install chromium`` done) after changing the print or export code.
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import briefing as bf  # noqa: E402
from briefing.export._render import open_report  # noqa: E402

OUT = Path(__file__).parent / "_static" / "export"


def sample_report(*, export: tuple[str, ...] = ()) -> bf.Briefing:
    rng = np.random.default_rng(6)
    days = np.arange(60)
    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.plot(days, 300 + days * 2 + rng.normal(0, 10, 60).cumsum(), color="#4F46E5")
    ax.set(xlabel="Day", ylabel="Orders")
    ax.spines[["top", "right"]].set_visible(False)
    orders = pd.DataFrame({
        "region": ["North", "South", "East", "West"],
        "orders": [3_120, 2_410, 2_870, 1_650],
        "revenue": [412_000, 287_500, 351_200, 198_300],
    })
    return bf.Briefing(
        bf.Page(
            bf.Group(
                bf.BigNumber("Revenue", "$1.25M", change="+8%", is_upward_change=True),
                bf.BigNumber("Orders", "10,050", change="+3%", is_upward_change=True),
                bf.BigNumber("Margin", "29.6 %", change="-0.4 pt", is_upward_change=False),
                columns=3,
            ),
            bf.Plot(fig, caption="Daily orders"),
            title="Summary",
            name="summary",
        ),
        bf.Page(
            bf.DataTable(orders, caption="By region"),
            bf.Toggle(bf.Text("Revenue is recognised on shipment."), label="Method"),
            title="Detail",
            name="detail",
        ),
        export=export,
    )


def main() -> None:
    os.environ.setdefault("SOURCE_DATE_EPOCH", "1704067200")
    OUT.mkdir(parents=True, exist_ok=True)
    report = sample_report()
    name = "Q1 review"

    bf.save_image(report, OUT / "page.png", page="summary", width=1000, scale=1, name=name)
    bf.save_image(report, OUT / "og.png", page="summary", size="og", width=1000, scale=1, name=name)
    bf.save_pdf(report, OUT / "sample.pdf", name=name)

    # What a printed sheet looks like: the print layout at A4 width (794 CSS px).
    with open_report(report, width=794, scale=1, name=name) as session:
        session.page.emulate_media(media="print")
        session.page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
        session.wait_drawn()
        session.page.screenshot(path=str(OUT / "print.png"), full_page=True)

    # The opt-in export menu in the report header.
    with open_report(sample_report(export=("png", "pdf")), width=1000, scale=1, name=name) as session:
        session.page.locator(".bf-report__header").screenshot(path=str(OUT / "menu.png"))

    for path in sorted(OUT.iterdir()):
        print(f"{path.relative_to(Path(__file__).parent)}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
