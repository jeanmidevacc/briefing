"""Command line: ``python -m briefing reference|validate|render|skill|image|pdf``.

``reference``, ``validate``, ``render`` and ``skill`` are for agents writing report JSON
(#32, built on #31); ``image`` and ``pdf`` export saved reports (#49).
"""
from __future__ import annotations

import argparse
import json
import sys
import typing as t
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from briefing._error import BriefingError
from briefing.export import PAPERS, PRESETS, save_image, save_pdf
from briefing.renderers.size import DEFAULT_MAX_SIZE, parse_size

_FORMATS = ("png", "jpg", "webp")


def _max_size(value: str) -> str | None:
    """``--max-size``: a size such as "25 MB", or "none"."""
    if value.strip().lower() in ("none", "off"):
        return None
    try:
        parse_size(value)
    except BriefingError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value


def _page(value: str) -> str | int:
    """``--page``: "all", a 0-based index, or a page title or name."""
    return int(value) if value.isdigit() else value


def _output(source: Path, output: Path | None, suffix: str) -> Path:
    """Where to write: the given file, inside the given directory, or next to the input."""
    if output is None:
        return source.with_suffix(suffix)
    if output.is_dir():
        return output / source.with_suffix(suffix).name
    return output


def _parser() -> argparse.ArgumentParser:
    from briefing import __version__

    parser = argparse.ArgumentParser(
        prog="python -m briefing",
        description="Check and render report JSON, print the reference for agents, or export a saved "
        "report as images or a PDF.",
    )
    parser.add_argument("--version", action="version", version=f"briefing {__version__}")
    commands = parser.add_subparsers(dest="command", required=True,
                                     metavar="{new,reference,validate,render,skill,image,pdf}")

    new = commands.add_parser("new", help="start a report project: a build script, its Markdown and its theme",
                              description="Write a small report project that runs as it is: build_report.py, "
                              "report.md, theme.py and a README.")
    new.add_argument("folder", type=Path, help="the project's folder (created if needed)")
    new.add_argument("--title", help="the report's title (default: from the folder's name)")
    new.add_argument("--force", action="store_true", help="replace the project's files if they are there")

    commands.add_parser("reference", help="print the reference for agents: the JSON format, every block and option",
                        description="Print briefing's reference for agents, for the version installed here.")

    data_help = "an object the JSON names by reference, as name=file.csv or name=file.parquet (repeatable)"
    size_help = 'warn when the report is bigger than this, such as "25 MB" (default: 10 MB; "none": never)'
    validate = commands.add_parser("validate", help="check a report's JSON and list its problems",
                                   description="Check a report's JSON (see bf.validate). Exits with status 1 "
                                   "when there is an error.")
    validate.add_argument("spec", help='the report\'s JSON file, or "-" to read it from standard input')
    validate.add_argument("--data", action="append", default=[], metavar="NAME=FILE", help=data_help)
    validate.add_argument("--json", action="store_true", help="print the problems as a JSON list")
    validate.add_argument("--max-size", type=_max_size, default=DEFAULT_MAX_SIZE, metavar="SIZE", help=size_help)

    render = commands.add_parser("render", help="render a report's JSON to an HTML file",
                                 description="Build a report from its JSON (see bf.from_spec) and save it as HTML.")
    render.add_argument("spec", help='the report\'s JSON file, or "-" to read it from standard input')
    render.add_argument("-o", "--output", type=Path, help="the HTML file to write (default: next to the JSON)")
    render.add_argument("--name", default="Report", help="the report's title (default: Report)")
    render.add_argument("--data", action="append", default=[], metavar="NAME=FILE", help=data_help)
    render.add_argument("--max-size", type=_max_size, default=DEFAULT_MAX_SIZE, metavar="SIZE", help=size_help)

    skill = commands.add_parser("skill", help="print, or install, a Claude Code skill that points to the reference",
                                description="Print a Claude Code skill for briefing, or install it into "
                                "a project's .claude/skills/briefing/.")
    skill.add_argument("--install", action="store_true", help="write it to .claude/skills/briefing/SKILL.md")
    skill.add_argument("--dir", type=Path, default=None, help="the project to install it in (default: here)")
    skill.add_argument("--force", action="store_true", help="replace a SKILL.md that differs")

    image = commands.add_parser("image", help="save report pages as PNG, JPEG or WebP images",
                                description="Save report pages as images (see bf.save_image), in headless "
                                'Chromium, offline. Needs pip install "briefing[image]" and, once, '
                                "playwright install chromium.")
    image.add_argument("report", type=Path, help="a saved report .html file")
    image.add_argument("-o", "--output", type=Path,
                       help="output file, or a directory (default: next to the report, same name)")
    image.add_argument("--page", type=_page, default="all",
                       help='"all" (default: one image per page), a page title or name, or a 0-based index')
    image.add_argument("--format", choices=_FORMATS, default=None,
                       help="image format when --output is a directory or omitted (default: png)")
    image.add_argument("--size", choices=sorted(PRESETS), default=None,
                       help="social-card size: og 1200x630, square 1080x1080, portrait 1080x1350 "
                       "(default: full height)")
    image.add_argument("--width", type=int, default=1200, help="layout width in CSS pixels (default: 1200)")
    image.add_argument("--scale", type=float, default=2.0, help="device pixels per CSS pixel (default: 2)")
    image.add_argument("--no-expand", dest="expand", action="store_false", help="leave toggles closed")

    pdf = commands.add_parser("pdf", help="save the report as one PDF",
                              description="Save a report as a PDF (see bf.save_pdf).")
    pdf.add_argument("report", type=Path, help="a saved report .html file")
    pdf.add_argument("-o", "--output", type=Path, help="output .pdf file, or a directory (default: next to the report)")
    pdf.add_argument("--page", type=_page, default="all",
                     help='"all" (default), a page title or name, or a 0-based index')
    pdf.add_argument("--paper", choices=sorted(PAPERS), default="a4", help="paper size (default: a4)")
    pdf.add_argument("--landscape", action="store_true", help="turn the paper sideways")
    return parser


def _export(args: argparse.Namespace) -> int:
    if args.command == "image":
        suffix = "." + (args.format or (args.output.suffix.lstrip(".") if args.output and args.output.suffix
                                        and not args.output.is_dir() else "png"))
        written = save_image(
            args.report, _output(args.report, args.output, suffix),
            page=args.page, width=args.width, scale=args.scale, size=args.size, expand=args.expand,
        )
    else:
        written = [save_pdf(args.report, _output(args.report, args.output, ".pdf"),
                            page=args.page, paper=args.paper, landscape=args.landscape)]
    for path in written:
        print(path)
    return 0


# ── report JSON, for agents (#32) ─────────────────────────────────────────────


def _reference(_: argparse.Namespace) -> int:
    sys.stdout.write((files("briefing") / "reference.md").read_text(encoding="utf-8"))
    return 0


def _spec(source: str) -> str:
    """The JSON's text from standard input (``-``), or its path as given."""
    return sys.stdin.read() if source == "-" else source


def _data(pairs: list[str]) -> dict[str, t.Any] | None:
    """``--data name=file.csv`` (or ``.parquet``) as ``{name: DataFrame}``; ``None`` when none is given."""
    if not pairs:
        return None
    import pandas as pd

    data: dict[str, t.Any] = {}
    for pair in pairs:
        name, sep, path = pair.partition("=")
        if not sep or not name or not path:
            raise BriefingError(f"--data takes name=file.csv or name=file.parquet, not {pair!r}.")
        file = Path(path).expanduser()
        if not file.is_file():
            raise BriefingError(f"--data {name}: there is no file {path!r}.")
        suffix = file.suffix.lower()
        if suffix == ".csv":
            data[name] = pd.read_csv(file)
        elif suffix in (".parquet", ".pq"):
            try:
                data[name] = pd.read_parquet(file)
            except ImportError as exc:
                raise BriefingError("reading Parquet needs pyarrow: pip install pyarrow") from exc
        else:
            raise BriefingError(f"--data {name}: read .csv and .parquet files, not {file.name!r}.")
    return data


def _references(value: object) -> list[str]:
    """The names a report's JSON refers to, in order."""
    if isinstance(value, dict):
        if set(value) == {"ref"} and isinstance(value["ref"], str):
            return [value["ref"]]
        return [name for item in value.values() for name in _references(item)]
    if isinstance(value, list):
        return [name for item in value for name in _references(item)]
    return []


def _validate(args: argparse.Namespace) -> int:
    from briefing.spec import validate
    from briefing.spec._convert import load

    spec = _spec(args.spec)
    data = _data(args.data)
    problems = validate(spec, data, max_size=args.max_size)
    if args.json:
        print(json.dumps([p.to_dict() for p in problems], indent=2, ensure_ascii=False))
    else:
        for problem in problems:
            print(problem)
        if not problems:
            print("No problems found.")
    loaded, _ = load(spec)
    names = list(dict.fromkeys(_references(loaded)))
    if data is None and names:
        print(f"note: without --data, the reference{'s' if len(names) > 1 else ''} {', '.join(names)} and the "
              "rendering weren't checked; pass --data name=file.csv to check them.", file=sys.stderr)
    return 1 if any(p.severity == "error" for p in problems) else 0


def _render(args: argparse.Namespace) -> int:
    from briefing import from_spec, save

    if args.output is None and args.spec == "-":
        raise BriefingError("pass --output report.html when the JSON comes from standard input.")
    output = args.output or Path(args.spec).with_suffix(".html")
    try:
        report = from_spec(_spec(args.spec), _data(args.data))
    except BriefingError as exc:
        if "was passed in data" in str(exc):
            raise BriefingError(f"{exc}\nPass referenced tables as --data name=file.csv.") from exc
        raise
    save(report, str(output), name=args.name, max_size=args.max_size)
    print(output)
    return 0


def _skill(args: argparse.Namespace) -> int:
    from briefing.spec._reference import SKILL

    if not args.install:
        sys.stdout.write(SKILL)
        return 0
    target = (args.dir or Path.cwd()) / ".claude" / "skills" / "briefing" / "SKILL.md"
    if target.is_file() and target.read_text(encoding="utf-8") != SKILL and not args.force:
        raise BriefingError(f"{target} exists and differs from briefing's; pass --force to replace it.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SKILL, encoding="utf-8")
    print(target)
    return 0


def _new(args: argparse.Namespace) -> int:
    from briefing._scaffold import new_project

    written = new_project(args.folder, title=args.title, force=args.force)
    for path in written:
        print(f"wrote {path}")
    print(f"next: cd {args.folder} && python build_report.py --open")
    return 0


_COMMANDS: dict[str, t.Callable[[argparse.Namespace], int]] = {
    "reference": _reference,
    "new": _new,
    "validate": _validate,
    "render": _render,
    "skill": _skill,
    "image": _export,
    "pdf": _export,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; returns the exit status."""
    args = _parser().parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except BriefingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
