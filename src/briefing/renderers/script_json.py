"""JSON that can sit inside ``<script type="application/json">`` safely.

The HTML parser ends a script element at the first ``</script``, and ``<!--``
inside one changes how it is parsed, whatever the JSON means. So every JSON
payload a block embeds writes ``<``, ``>`` and ``&`` as ``\\u003c``, ``\\u003e``
and ``\\u0026``: valid JSON that parses back to exactly the same value.
"""
from __future__ import annotations

import json
import typing as t


def escape_script_json(text: str) -> str:
    """Make already-serialised JSON *text* safe to place inside a ``<script>`` element."""
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def script_json(value: t.Any) -> str:
    """Serialise *value* to compact JSON that is safe inside a ``<script>`` element."""
    return escape_script_json(json.dumps(value, separators=(",", ":")))


__all__ = ["escape_script_json", "script_json"]
