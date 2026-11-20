"""``python -m briefing.spec``: write the JSON Schema built from the block classes to ``briefing/schema/``.

Run it after changing a block's parameters or its ``Args:`` docstring;
``tests/test_spec/test_schema.py`` fails until the checked-in file matches.
"""
from __future__ import annotations

import json
from pathlib import Path

from briefing.spec._model import FORMAT_VERSION, build_schema


def schema_text() -> str:
    """The schema file's exact text."""
    return json.dumps(build_schema(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    target = Path(__file__).resolve().parent.parent / "schema" / f"v{FORMAT_VERSION}.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(schema_text(), encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
