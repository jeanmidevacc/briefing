"""Formula rendering — LaTeX to MathML at render time, no JavaScript.

Browsers render MathML natively, so a report shows typeset math offline and
without a math runtime. The conversion uses ``latex2mathml``; its output is
then checked against an allow-list, because the converter copies some input
through verbatim (``\\text{<script>…}``) and supports ``\\href``. Anything that
doesn't pass — invalid LaTeX, unknown commands, markup, links — returns
``None`` so the renderer can show the source instead.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

_MATHML_NS = "http://www.w3.org/1998/Math/MathML"

#: MathML Core presentation elements (no annotation-xml, no maction, no links).
_ELEMENTS = frozenset({
    "math", "menclose", "merror", "mfrac", "mi", "mmultiscripts", "mn", "mo", "mover", "mpadded",
    "mphantom", "mprescripts", "mroot", "mrow", "ms", "mspace", "msqrt", "mstyle", "msub", "msubsup",
    "msup", "mtable", "mtd", "mtext", "mtr", "munder", "munderover", "none",
})

#: Layout and styling attributes only — no href, event handlers, style, id or class.
_ATTRIBUTES = frozenset({
    "accent", "accentunder", "columnalign", "columnlines", "columnspacing", "depth", "display",
    "displaystyle", "fence", "form", "frame", "framespacing", "height", "largeop", "linebreak",
    "linethickness", "lspace", "mathbackground", "mathcolor", "mathsize", "mathvariant", "maxsize",
    "minsize", "movablelimits", "notation", "rowalign", "rowlines", "rowspacing", "rspace",
    "scriptlevel", "separator", "stretchy", "symmetric", "voffset", "width",
})

#: Attribute values are plain tokens: names, numbers with units, #hex colours.
_VALUE = re.compile(r"^[#\w\s.%+-]*$")


def latex_to_mathml(latex: str) -> str | None:
    """Return *latex* as a block-level MathML ``<math>`` element, or ``None`` if it can't be converted safely."""
    from latex2mathml.converter import convert

    try:
        raw = convert(latex, display="block")
        root = ET.fromstring(raw)
    except Exception:  # the converter raises a range of errors on invalid input
        return None
    for el in root.iter():
        namespace, _, tag = el.tag.rpartition("}")
        if namespace != "{" + _MATHML_NS or tag not in _ELEMENTS:
            return None
        if any(name not in _ATTRIBUTES or not _VALUE.match(value) for name, value in el.attrib.items()):
            return None
        if tag == "mi" and (el.text or "").startswith("\\"):  # an unknown \command, passed through as text
            return None
        el.tag = tag
    root.attrib = {"xmlns": _MATHML_NS, **root.attrib}
    return ET.tostring(root, encoding="unicode")


__all__ = ["latex_to_mathml"]
