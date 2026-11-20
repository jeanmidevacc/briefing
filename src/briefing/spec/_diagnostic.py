"""One problem :func:`~briefing.validate` found in a report (#31)."""
from __future__ import annotations

import typing as t
from dataclasses import asdict, dataclass

Severity = t.Literal["error", "warning"]


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
