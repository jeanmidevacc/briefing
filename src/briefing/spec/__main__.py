"""``python -m briefing.spec``: write the files built from the block classes.

``briefing/schema/v1.json`` (the JSON Schema, #31) and ``briefing/reference.md`` (the
reference for agents, #32). Run it after changing a block's parameters or its ``Args:``
docstring; ``tests/test_spec/test_schema.py`` and ``test_reference.py`` fail until the
checked-in files match.
"""
from __future__ import annotations

import json
from pathlib import Path

from briefing.spec._model import FORMAT_VERSION, build_schema
from briefing.spec._reference import build_reference

PACKAGE = Path(__file__).resolve().parent.parent


def schema_text() -> str:
    """The schema file's exact text."""
    return json.dumps(build_schema(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    schema = PACKAGE / "schema" / f"v{FORMAT_VERSION}.json"
    schema.parent.mkdir(exist_ok=True)
    for target, text in ((schema, schema_text()), (PACKAGE / "reference.md", build_reference())):
        target.write_text(text, encoding="utf-8")
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
