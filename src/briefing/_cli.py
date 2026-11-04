"""Command line for saved reports: ``python -m briefing image|pdf report.html``."""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from briefing._error import BriefingError
from briefing.export import PAPERS, PRESETS, save_image, save_pdf

_FORMATS = ("png", "jpg", "webp")


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
        description="Export a saved briefing report as images or a PDF, in headless Chromium, offline. "
        'Needs pip install "briefing[image]" and, once, playwright install chromium.',
    )
    parser.add_argument("--version", action="version", version=f"briefing {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="{image,pdf}")

    image = commands.add_parser("image", help="save report pages as PNG, JPEG or WebP images",
                                description="Save report pages as images (see bf.save_image).")
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; returns the exit status."""
    args = _parser().parse_args(argv)
    try:
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
    except BriefingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(path)
    return 0
