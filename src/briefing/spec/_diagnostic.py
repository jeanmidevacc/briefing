"""One problem :func:`~briefing.validate` found in a report (#31)."""
from __future__ import annotations

import typing as t
from dataclasses import asdict, dataclass

Severity = t.Literal["error", "warning"]

#: Every code :func:`~briefing.validate` reports, with its severity and what it means; the
#: agent reference lists them from here (``tests/test_spec/test_reference.py`` keeps it whole).
CODES: dict[str, tuple[Severity, str]] = {
    "invalid-json": ("error", "The text isn't valid JSON."),
    "unreadable-file": ("error", "The file can't be read."),
    "not-a-spec": ("error", 'The JSON isn\'t a report object {"briefing": 1, "blocks": [...]}.'),
    "missing-version": ("error", 'There is no "briefing": 1.'),
    "unsupported-version": ("error", "A format this briefing doesn't read: upgrade briefing."),
    "unknown-type": ("error", "No block has this type; the hint suggests the closest."),
    "missing-type": ("error", 'A block without "type".'),
    "not-a-block": ("error", "Something in a blocks list that isn't an object."),
    "unknown-option": ("error", "The block has no such option; the hint suggests the closest."),
    "missing-option": ("error", "A required option is missing."),
    "wrong-type": ("error", "An option's value has the wrong type; the message says what it takes."),
    "unknown-ref": ("error", "A reference to an object not passed in data."),
    "invalid-data": ("error", "An inline table, chart or image can't be read."),
    "invalid-value": ("error", "The block itself rejects a value (widths that don't match columns, "
                               "a column missing from the table...)."),
    "mixed-pages": ("error", "Page blocks mixed with other blocks at the top level."),
    "misplaced-page": ("error", "A Page inside another block: pages only go at the top."),
    "empty-container": ("error", "A report, Page or Toggle without blocks."),
    "duplicate-name": ("error", "A name (or a heading's {#name}) used twice in one page."),
    "name-clash": ("error", "A name that matches an id briefing makes up, such as sel-1."),
    "render-error": ("error", "A block fails to render, or a Plot can't draw its figure."),
    "too-deep": ("error", "Blocks nested too deeply to check."),
    "internal-error": ("error", "A bug in briefing itself; please report it."),
    "too-few-panels": ("warning", "A Select with fewer than two panels."),
    "missing-label": ("warning", "A Select panel without a label, or a Page without a title."),
    "deprecated": ("warning", "An option that will go away; the message says what to use."),
    "block-warning": ("warning", "What a block warns about: rows dropped, a sample drawn, LaTeX it "
                                 "can't convert..."),
    "placeholder": ("warning", "A block with nothing to draw shows a warning box instead."),
}


@dataclass(frozen=True)
class Diagnostic:
    """A problem in a report or its JSON form, as :func:`~briefing.validate` returns it.

    An error stops the report from being built or rendered; a warning is worth a look
    but the report renders. ``str(diagnostic)`` gives one readable line.

    Args:
        severity: ``"error"`` or ``"warning"``.
        code: What kind of problem, a stable short name such as ``"unknown-option"``,
            ``"wrong-type"`` or ``"duplicate-name"``.
        path: Where, as a JSON Pointer into the JSON form: ``"/blocks/1/blocks/0"`` is the
            first child of the second block, ``"/blocks/1/columns"`` its ``columns``
            option, ``""`` the report itself.
        message: What is wrong.
        hint: What to do about it, when there is something to say.

    Example::

        for problem in bf.validate(spec):
            print(problem)  # error unknown-option at /blocks/0/colums: Group has no option "colums". ...
    """

    severity: Severity
    code: str
    path: str
    message: str
    hint: str | None = None

    def __str__(self) -> str:
        where = self.path or "the report"
        return f"{self.severity} {self.code} at {where}: {self.message}" + (f" {self.hint}" if self.hint else "")

    def to_dict(self) -> dict[str, str | None]:
        """The diagnostic as a plain dict, ready for ``json.dumps``."""
        return asdict(self)
