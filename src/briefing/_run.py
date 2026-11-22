"""bf.run (#193): a build script's command line, in one call."""
from __future__ import annotations

import argparse
import json
import typing as t
import warnings
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path

from briefing._error import BriefingError
from briefing.renderers.size import DEFAULT_MAX_SIZE, format_size, parse_size

if t.TYPE_CHECKING:
    from briefing.renderers.formatting import Formatting


def _max_size(text: str) -> int | None:
    if text.strip().lower() == "none":
        return None
    try:
        return parse_size(text)
    except BriefingError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def run(
    build: Callable[[], t.Any],
    out: str | Path = "reports/index.html",
    name: str = "Report",
    formatting: Formatting | None = None,
    argv: Sequence[str] | None = None,
) -> Path:
    """Build the report and save it, with a command line: ``--out``, ``--open``, ``--max-size``, ``--spec``, ``--diff``.

    Put it at the end of a build script; it prints each file it writes and its size.

    Args:
        build: A function that returns the report (a ``Briefing``, or what ``save`` takes).
        out: Where to write the HTML, unless ``--out`` says otherwise.
        name: The report's title.
        formatting: The theme.
        argv: The command line to read (by default, the script's own).

    Example::

        if __name__ == "__main__":
            bf.run(build, out="reports/index.html", name="Daily collection")
            # python build_report.py --open --spec --diff reports/yesterday.json
    """
    from briefing import save, stringify, to_spec
    from briefing.diff import diff

    parser = argparse.ArgumentParser(description=f"Build {name} and save it as HTML.")
    parser.add_argument("--out", type=Path, default=Path(out), help=f"the HTML file to write (default: {out})")
    parser.add_argument("--open", action="store_true", help="open it in the browser afterwards")
    parser.add_argument("--max-size", type=_max_size, default=DEFAULT_MAX_SIZE, metavar="SIZE",
                        help='warn when the report is bigger than this, such as "25 MB" (default: 10 MB; "none")')
    parser.add_argument("--spec", action="store_true",
                        help="also write the report's JSON next to it, to compare the next run with")
    parser.add_argument("--diff", type=Path, metavar="PREVIOUS.json",
                        help="also write what changed since that run, as <out>-changes.html")
    args = parser.parse_args(argv)

    from briefing.blocks.layout import Briefing

    report = Briefing.wrap(build())
    path: Path = args.out
    path.parent.mkdir(parents=True, exist_ok=True)
    save(report, str(path), name=name, formatting=formatting, max_size=args.max_size)
    print(f"{path}: {format_size(path.stat().st_size)}")
    if args.spec:
        spec_path = path.with_suffix(".json")
        spec, left_out = to_spec(report, inline=True)
        if left_out:  # objects JSON can't hold: the saved file isn't the whole report
            warnings.warn(f"--spec: {', '.join(sorted(left_out))} can't be written into JSON (a frame with an index "
                          "of its own, a Matplotlib figure…), so the saved JSON can't be compared alone. "
                          "reset_index() a frame to fix it.", stacklevel=2)
        spec_path.write_text(json.dumps(spec, indent=1), encoding="utf-8")
        print(f"{spec_path}: {format_size(spec_path.stat().st_size)}")
    if args.diff is not None:
        changes = path.with_name(f"{path.stem}-changes.html")
        changes.write_text(stringify(diff(args.diff, report), name=f"{name}: what changed", formatting=formatting),
                           encoding="utf-8")
        print(f"{changes}: {format_size(changes.stat().st_size)}")
    if args.open:
        webbrowser.open(path.resolve().as_uri())
    return path


__all__ = ["run"]
