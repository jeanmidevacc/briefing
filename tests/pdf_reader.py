"""A minimal reader for the PDFs headless Chromium writes, for tests only.

Chromium's PDFs keep every object at top level (no object streams), compress
page content with zlib, draw text as hex glyph ids (``<0036> Tj``) and give
each font a ``ToUnicode`` map back to characters. That is enough to count
pages, list link targets and pull each page's text, without a PDF library.
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass

_OBJ = re.compile(rb"(\d+) 0 obj(.*?)endobj", re.S)
_REF = rb"(\d+) 0 R"


@dataclass
class Pdf:
    pages: list[str]  # text of each page, in order
    links: list[str]  # URI link targets, in order


def _stream(body: bytes, objs: dict[int, bytes] | None = None) -> bytes:
    """The decoded data of a stream object, read by its /Length (data may end in a newline)."""
    start = re.search(rb"stream\r?\n", body)
    length = re.search(rb"/Length\s+(\d+)(\s+0\s+R)?", body)
    if start is None or length is None:
        return b""
    n = int(length.group(1))
    if length.group(2) and objs is not None:  # an indirect length: "/Length 12 0 R"
        n = int(objs[n].strip())
    data = body[start.end():start.end() + n]
    return zlib.decompress(data) if b"/FlateDecode" in body else data


def _cmap(data: bytes) -> dict[str, str]:
    table: dict[str, str] = {}
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            table[src.decode().upper()] = bytes.fromhex(dst.decode()).decode("utf-16-be")
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for lo, hi, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            start, width = int(dst, 16), len(lo)
            for i, code in enumerate(range(int(lo, 16), int(hi, 16) + 1)):
                table[f"{code:0{width}X}"] = chr(start + i)
    return table


def read_pdf(pdf: bytes) -> Pdf:
    """Return the text of every page and the link targets of a Chromium PDF."""
    objs = {int(n): body for n, body in _OBJ.findall(pdf)}
    # Pages form a tree (Skia groups them by eight): start at the root, walk it in order.
    root = next(body for body in objs.values()
                if re.search(rb"/Type\s*/Pages\b", body) and b"/Parent" not in body)
    texts = []
    for page in _leaves(root, objs):
        fonts: dict[bytes, dict[str, str]] = {}
        res = re.search(rb"/Resources\s*(?:" + _REF + rb"|<<(.*)>>)", page, re.S)
        resources = objs[int(res.group(1))] if res and res.group(1) else (res.group(2) if res else b"")
        font_dict = re.search(rb"/Font\s*(?:" + _REF + rb"|<<(.*?)>>)", resources, re.S)
        entries = (objs[int(font_dict.group(1))] if font_dict and font_dict.group(1)
                   else (font_dict.group(2) if font_dict else b""))
        for name, ref in re.findall(rb"/(\w+)\s+" + _REF, entries):
            to_unicode = re.search(rb"/ToUnicode\s+" + _REF, objs[int(ref)])
            fonts[name] = _cmap(_stream(objs[int(to_unicode.group(1))], objs)) if to_unicode else {}
        contents = re.search(rb"/Contents\s*(?:\[(.*?)\]|" + _REF + rb")", page, re.S)
        refs = re.findall(_REF, contents.group(1)) if contents and contents.group(1) else (
            [contents.group(2)] if contents else [])
        content = b"\n".join(_stream(objs[int(r)], objs) for r in refs)
        texts.append(_decode_text(content, fonts))
    links = [u.decode() for u in re.findall(rb"/URI\s*\(([^)]*)\)", pdf)]
    return Pdf(pages=texts, links=links)


def _leaves(node: bytes, objs: dict[int, bytes]) -> list[bytes]:
    """The page objects under a /Pages node, in document order."""
    kids = re.search(rb"/Kids\s*\[(.*?)\]", node, re.S)
    assert kids is not None, "page tree node without /Kids"
    pages: list[bytes] = []
    for ref in re.findall(_REF, kids.group(1)):
        kid = objs[int(ref)]
        pages.extend(_leaves(kid, objs) if re.search(rb"/Type\s*/Pages\b", kid) else [kid])
    return pages


def _decode_text(content: bytes, fonts: dict[bytes, dict[str, str]]) -> str:
    out: list[str] = []
    cmap: dict[str, str] = {}
    for token in re.finditer(rb"/(\w+)\s+[\d.]+\s+Tf|<([0-9A-Fa-f]*)>|\bET\b", content):
        if token.group(1) is not None:
            cmap = fonts.get(token.group(1), {})
        elif token.group(2) is not None:
            hexs = token.group(2).decode().upper()
            out.append("".join(cmap.get(hexs[i:i + 4], "") for i in range(0, len(hexs), 4)))
        else:  # end of a text object: separate it from the next one
            out.append("\n")
    return re.sub(r"[ \t]+", " ", "".join(out)).strip()
