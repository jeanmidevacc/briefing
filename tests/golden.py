"""Turn a rendered report into its golden snapshot text (#45).

A golden snapshot is the report's bytes with three kinds of content swapped for
a short marker, so that snapshots only change when briefing's own output does:

- **briefing's static files** (``static/report.css``, ``lab/static/lab.js``, …),
  inlined verbatim, become ``/* golden: static/report.js sha256 … */``. A change
  to the file still changes every snapshot that inlines it, by that one line.
- **chart libraries' output** (the Plotly and Vega runtimes, packed since #38,
  Matplotlib's SVG, a Plotly figure, an Altair spec) becomes a marker without a hash:
  it changes with the library's release, not with briefing. Ids that briefing gives a
  chart stay.
- **briefing's version** in ``<meta name="generator">`` and the footer becomes
  ``{version}``, so a release doesn't rewrite every snapshot.
- **the copy-embed data** (#124), gzip in base64, becomes a hash of its JSON with
  the same swaps, and the report's id prefix ``bf-r…`` (a hash that follows the
  charts' output) becomes ``bf-r{hash}``.
- **a big table's packed rows** (#38) and **a text attachment's packed file** (#36),
  deflate in base64, become a hash of what they unpack to, so a zlib release doesn't
  change the snapshot but the content does.

Each swap only applies to text that is exactly what it expects; anything else
stays in the snapshot, so a change to how a file or chart is inlined shows up.
"""
from __future__ import annotations

import base64
import functools
import gzip
import hashlib
import json
import re
from datetime import UTC, datetime
from importlib.resources import files

import briefing as bf

#: The header date of every golden report.
NOW = datetime(2024, 1, 2, 3, 4, tzinfo=UTC)

_FIGURE = re.compile(
    r'(?P<open><figure class="bf-block bf-plot">)(?P<inner>.*?)'
    r'(?P<close><figcaption class="bf-plot__caption">|</figure>)',
    re.S,
)
_ALTAIR_SPEC = re.compile(r'(<script type="application/json" class="bf-altair__spec">).*?(</script>)', re.S)
_MPL_ID = re.compile(r'\bid="(mpl-\d+-)?[^"]*"')
_PLOTLY_ID = re.compile(r'<div id="([^"]+)" class="plotly-graph-div"')


@functools.cache
def static_files() -> dict[str, str]:
    """briefing's CSS and JS files, as {path inside the package: content}."""
    found: dict[str, str] = {}
    for package, folder in (("briefing", "static"), ("briefing.lab", "lab/static")):
        for entry in sorted((files(package) / "static").iterdir(), key=lambda e: e.name):
            if entry.is_file() and entry.name.endswith((".css", ".js")):
                found[f"{folder}/{entry.name}"] = entry.read_text(encoding="utf-8")
    return found


def static_marker(path: str, content: str) -> str:
    """The line that stands for the static file at *path* in a snapshot."""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    return f"/* golden: {path} sha256 {digest} */"


@functools.cache
def _runtimes() -> tuple[tuple[str, str], ...]:
    """The chart runtimes a report can inline, as (exact text, marker), for the libraries installed.

    A runtime is inlined packed (#38): the text is its packed data, in quotes, and its size.
    """
    from briefing.renderers.plot import _vega_bundle, packed_runtime

    found: list[tuple[str, str]] = []
    try:
        from plotly.offline import get_plotlyjs
    except ImportError:
        pass
    else:
        data, size = packed_runtime(get_plotlyjs())
        found.append((f'"{data}", {size}', '"/* golden: plotly.js runtime, packed */", {size}'))
    vega = _vega_bundle()
    if vega is not None:
        data, size = packed_runtime(vega)
        found.append((f'"{data}", {size}', '"/* golden: Vega runtime from vl-convert-python, packed */", {size}'))
    return tuple(found)


def _figure_marker(match: re.Match[str]) -> str:
    inner = match["inner"]
    if inner.startswith("<svg"):
        # Every id briefing scoped shows as its prefix; an id it missed shows in full.
        ids = sorted({m.group(1) or m.group(0) for m in _MPL_ID.finditer(inner)})
        inner = f"<!-- golden: SVG from Matplotlib, ids {' '.join(ids)} -->"
    elif 'class="plotly-graph-div"' in inner:
        ids = _PLOTLY_ID.findall(inner)
        inner = f"<!-- golden: Plotly figure in div {' '.join(ids)} -->"
    elif inner.startswith('<div class="bf-altair"'):
        inner = _ALTAIR_SPEC.sub(r"\1/* golden: Vega-Lite spec from Altair */\2", inner)
    return f"{match['open']}{inner}{match['close']}"


_PACKED_TABLE = re.compile(
    r'(<script type="application/json" class="(?:bf-dt__data|bf-attachment__data)" data-size="(\d+)"(?: data-packed)?>)'
    r'"([A-Za-z0-9+/=]*)"(</script>)'
)


def _packed_table_marker(match: re.Match[str]) -> str:
    from briefing.renderers.pack import unpack

    if "bf-attachment__data" in match[1] and "data-packed" not in match[1]:
        return match[0]  # an attachment's bytes, base64 as they are: nothing to hide
    rows = unpack(match[3], int(match[2]))
    digest = hashlib.sha256(rows.encode()).hexdigest()[:12]
    return f"{match[1]}/* golden: packed, sha256 {digest} */{match[4]}"


_COPY_DATA = re.compile(r'(<script type="application/json" class="bf-copy-data">)"([A-Za-z0-9+/=]*)"(</script>)')
_REPORT_ID = re.compile(r"\bbf-r[0-9a-f]{8}-")


def _copy_data_marker(match: re.Match[str]) -> str:
    payload = json.loads(gzip.decompress(base64.b64decode(match[2])))
    payload["version"] = "{version}"
    payload["body"] = mask(payload["body"])
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
    return f"{match[1]}/* golden: copy-embed data for {len(payload['blocks'])} blocks, sha256 {digest} */{match[3]}"


def mask(html: str) -> str:
    """The golden snapshot text of *html*: see the module docstring for what is swapped."""
    html = _REPORT_ID.sub("bf-r{hash}-", _COPY_DATA.sub(_copy_data_marker, html))
    html = _PACKED_TABLE.sub(_packed_table_marker, html)
    for path, content in static_files().items():
        html = html.replace(content, static_marker(path, content))
    for text, marker in _runtimes():
        html = html.replace(text, marker)
    html = _FIGURE.sub(_figure_marker, html)
    return html.replace(f"briefing {bf.__version__}", "briefing {version}")
