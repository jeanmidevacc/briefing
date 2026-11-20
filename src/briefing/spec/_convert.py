"""A report and its JSON form, both ways (#31).

:class:`_Writer` turns blocks into JSON (``to_spec``). :class:`Reader` builds blocks from
JSON, reporting every problem it meets as a :class:`Diagnostic` with the JSON Pointer of
where it is, instead of stopping at the first: ``from_spec`` raises them together,
``validate`` returns them.
"""
from __future__ import annotations

import collections
import difflib
import enum
import json
import math
import numbers
import os
import typing as t
import warnings
from collections.abc import Mapping
from pathlib import Path

from briefing._error import BriefingError
from briefing.blocks.base import Block, ContainerBlock
from briefing.blocks.layout import Briefing, Select
from briefing.spec._check import check, describe, refs_in, show
from briefing.spec._data import decode_figure, decode_image, decode_table, encode_figure, encode_image, encode_table
from briefing.spec._diagnostic import Diagnostic, Severity
from briefing.spec._model import FORMAT_VERSION, BlockType, Field, block_types, root_type, type_name

#: The keys of the report object besides its options.
_ROOT_KEYS = ("briefing", "blocks")


class _NoJSON(Exception):
    """A value with no plain JSON form: it goes by reference."""


# ── to_spec ───────────────────────────────────────────────────────────────────


def _plain(value: object) -> t.Any:
    """*value* as plain JSON, or raise :class:`_NoJSON`."""
    if value is None or isinstance(value, bool | str):
        return value.value if isinstance(value, enum.Enum) else value
    if isinstance(value, enum.Enum):
        return _plain(value.value)
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        number = float(value)
        if not math.isfinite(number):
            raise _NoJSON
        return number
    if isinstance(value, tuple | list):
        return [_plain(v) for v in value]
    raise _NoJSON


def _same(a: object, b: object) -> bool:
    """JSON equality that tells ``true`` from ``1`` and ``"1"`` from ``1``."""
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, bool | str) or isinstance(b, bool | str):
        return type(a) is type(b) and a == b
    return a == b


def _is_default(value: object, field: Field) -> bool:
    if field.required:
        return False
    if value is None or field.default is None:
        return value is None and field.default is None
    try:
        return _same(_plain(value), _plain(field.default))
    except _NoJSON:
        return False


class _Writer:
    def __init__(self, inline: bool) -> None:
        self.inline = inline
        self.data: dict[str, t.Any] = {}
        self._seen: dict[int, str] = {}  # id(object) -> its reference, so an object shared by blocks is passed once
        self._counts: collections.Counter[str] = collections.Counter()

    def block(self, block: Block) -> dict[str, t.Any]:
        name = type_name(block)
        if name is None:
            raise BriefingError(
                f"{type(block).__name__} isn't one of briefing's blocks, so it has no JSON form; "
                "to_spec and validate only know the blocks briefing defines."
            )
        out: dict[str, t.Any] = {"type": name, **self.options(block, block_types()[name])}
        if isinstance(block, ContainerBlock):
            out["blocks"] = [self.block(child) for child in block.blocks]
        return out

    def options(self, block: Block, kind: BlockType) -> dict[str, t.Any]:
        out: dict[str, t.Any] = {}
        refs: list[str] = []  # this block's references so far
        for field in kind.fields:
            if field.attr is None:
                continue
            value = getattr(block, field.attr)
            if _is_default(value, field):
                continue
            try:
                out[field.key] = _plain(value)
            except _NoJSON:
                out[field.key] = self._data(value, field, block, kind, refs)
        return out

    def _data(self, value: object, field: Field, block: Block, kind: BlockType, refs: list[str]) -> t.Any:
        if self.inline:
            accepts = refs_in(field.schema)
            for target, encode in (("table", encode_table), ("figure", encode_figure), ("image", encode_image)):
                if target in accepts and (encoded := encode(value)) is not None:
                    return encoded
        if id(value) not in self._seen:
            if not refs:
                self._counts[kind.name] += 1
            base = block.name or f"{kind.name.removeprefix('lab.').lower()}-{self._counts[kind.name]}"
            key = base if not refs else f"{base}-{field.name}"
            unique, n = key, 1
            while unique in self.data:
                n += 1
                unique = f"{key}-{n}"
            self.data[unique] = value
            self._seen[id(value)] = unique
        refs.append(self._seen[id(value)])
        return {"ref": self._seen[id(value)]}


def to_spec(report: object, *, inline: bool = False) -> tuple[dict[str, t.Any], dict[str, t.Any]]:
    """The JSON form of *report*, and the objects its references name (see :func:`briefing.to_spec`)."""
    root = Briefing.wrap(report)
    writer = _Writer(inline)
    spec: dict[str, t.Any] = {"briefing": FORMAT_VERSION, **writer.options(root, root_type())}
    spec["blocks"] = [writer.block(b) for b in root.blocks]
    return spec, writer.data


# ── reading ───────────────────────────────────────────────────────────────────


def load(spec: object) -> tuple[t.Any, Diagnostic | None]:
    """The JSON of *spec* (a dict, JSON text or a file path), or a diagnostic saying why not."""
    if isinstance(spec, Mapping):
        return spec, None
    if isinstance(spec, str) and spec.lstrip().startswith(("{", "[")):
        return _parse(spec, "the JSON text")
    if isinstance(spec, str | os.PathLike):
        path = Path(spec).expanduser()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return None, Diagnostic("error", "unreadable-file", "", f"Can't read {str(path)!r}: {exc}.",
                                    "Pass a report's JSON as a dict, as JSON text, or as the path of a .json file.")
        return _parse(text, repr(str(path)))
    return None, Diagnostic(
        "error", "not-a-spec", "", f"Can't read a report from {type(spec).__name__}.",
        "Pass a briefing block or report, or its JSON form as a dict, JSON text or a file path.",
    )


def _parse(text: str, what: str) -> tuple[t.Any, Diagnostic | None]:
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, Diagnostic("error", "invalid-json", "",
                                f"{what} isn't valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}.")


def _suggest(word: object, choices: t.Iterable[str]) -> str | None:
    if not isinstance(word, str):
        return None
    close = difflib.get_close_matches(word, list(choices), n=1, cutoff=0.6)
    return f'Did you mean "{close[0]}"?' if close else None


def _join(path: str, key: str | int) -> str:
    return f"{path}/{str(key).replace('~', '~0').replace('/', '~1')}"


class Reader:
    """Builds blocks from a report's JSON, collecting every problem as a :class:`Diagnostic`.

    With *data* ``None``, references are left unchecked and the blocks holding them (and so
    the report) aren't built. With *capture_warnings*, the warnings blocks give become
    diagnostics too; otherwise they are raised as usual.
    """

    def __init__(self, data: Mapping[str, t.Any] | None, *, capture_warnings: bool) -> None:
        self.data = data
        self.capture = capture_warnings
        self.diagnostics: list[Diagnostic] = []
        self.paths: dict[int, str] = {}  # id(block) -> the JSON Pointer it was built from
        self._links: dict[str, str] = {}  # link id -> path of the block that has it

    # ── diagnostics ──

    def _add(self, severity: Severity, code: str, path: str, message: str, hint: str | None = None) -> None:
        self.diagnostics.append(Diagnostic(severity, code, path, message, hint))

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)

    # ── the report ──

    def report(self, spec: object) -> Briefing | None:
        """The report *spec* describes, or ``None`` when it can't be built."""
        if not isinstance(spec, Mapping):
            self._add("error", "not-a-spec", "", f"A report's JSON is an object, not {show(spec)}.",
                      'Write {"briefing": 1, "blocks": [...]}.')
            return None
        if not self._version(spec):
            return None
        root = root_type()
        self._unknown_keys(spec, "", "The report", [*_ROOT_KEYS, *(f.key for f in root.fields)])
        options, ok = self._options(spec, root, "", "The report")
        if "blocks" not in spec:
            self._add("error", "missing-option", "", 'The report has no "blocks".',
                      'Add "blocks": [...], the list of its blocks.')
            return None
        blocks = spec["blocks"]
        if not isinstance(blocks, list):
            self._add("error", "wrong-type", "/blocks", f'"blocks" must be a list of blocks, not {show(blocks)}.')
            return None
        if not blocks:
            self._add("error", "empty-container", "/blocks", "The report has no blocks.", "Add at least one block.")
            return None
        pages = [isinstance(b, Mapping) and b.get("type") == "Page" for b in blocks]
        if any(pages) and not all(pages):
            self._add("error", "mixed-pages", "/blocks",
                      "The report mixes Page blocks with other blocks at the top level.",
                      "Put every top-level block in a Page, or use no Page at all.")
        tabs = len(blocks) == 1 and isinstance(blocks[0], Mapping) and blocks[0].get("type") == "Select"
        children = []
        for i, child in enumerate(blocks):
            path = _join("/blocks", i)
            if all(pages) and not child.get("title"):
                self._missing_label(path, "page", "title", "Tab")
            children.append(self.block(child, path, page=None, top=True, is_page=all(pages), panels_are_pages=tabs))
        if not ok or None in children or self.has_errors:
            return None
        return t.cast(Briefing | None, self._construct(Briefing, {"blocks": children, **options}, "", "The report"))

    def _version(self, spec: Mapping[str, t.Any]) -> bool:
        """Check ``"briefing"``; ``False`` when the rest can't be read (a newer format)."""
        if "briefing" not in spec:
            self._add("error", "missing-version", "", "The JSON doesn't say which format it is in.",
                      f'Add "briefing": {FORMAT_VERSION} at the top.')
            return True
        version = spec["briefing"]
        if not isinstance(version, int) or isinstance(version, bool):
            self._add("error", "wrong-type", "/briefing",
                      f'"briefing" is the format version, a whole number such as {FORMAT_VERSION}, '
                      f"not {show(version)}.")
            return True
        if version > FORMAT_VERSION:
            from briefing._version import __version__

            self._add("error", "unsupported-version", "/briefing",
                      f"This JSON is in format {version}; briefing {__version__} reads format {FORMAT_VERSION}.",
                      "Upgrade briefing: pip install -U briefing.")
            return False
        if version < 1:
            self._add("error", "unsupported-version", "/briefing",
                      f"There is no format {version}; formats start at 1.", f'Write "briefing": {FORMAT_VERSION}.')
        return True

    # ── blocks ──

    def block(
        self, spec: object, path: str, *, page: str | None, top: bool = False, is_page: bool = False,
        panels_are_pages: bool = False,
    ) -> Block | None:
        """The block *spec* describes, or ``None``. *page* is the name of the page it sits in."""
        if not isinstance(spec, Mapping):
            self._add("error", "not-a-block", path, f'A block is an object with a "type", not {show(spec)}.')
            return None
        type_ = spec.get("type")
        if type_ is None:
            self._add("error", "missing-type", path, 'This block has no "type".',
                      'Add "type": "Text" (or Group, Plot, DataTable…).')
            return None
        kinds = block_types()
        if not isinstance(type_, str) or type_ not in kinds:
            self._unknown_type(type_, path)
            return None
        kind = kinds[type_]
        if type_ == "Page" and not top:
            self._add("error", "misplaced-page", path, "A Page can only be at the top of the report.",
                      "Use a Group here, or a Select of Groups for tabs.")
            return None
        self._unknown_keys(spec, path, type_, ["type", *(f.key for f in kind.fields if f.attr or f.name == "file"),
                                               *(["blocks"] if kind.container else [])])
        options, ok = self._options(spec, kind, path, type_)
        name = spec.get("name")
        if isinstance(name, str) and check(name, {"$ref": "#/$defs/name"}):
            self._claim(name, None if is_page else page, path, type_)
        children: list[Block | None] = []
        if kind.container:
            children, ok = self._children(spec, kind, path, name if is_page else page, panels_are_pages, ok)
        if not ok or None in children:
            return None
        if kind.container:
            options["blocks"] = children
        return self._construct(kind.cls, options, path, type_)

    def _children(
        self, spec: Mapping[str, t.Any], kind: BlockType, path: str, page: object, panels_are_pages: bool, ok: bool,
    ) -> tuple[list[Block | None], bool]:
        raw = spec.get("blocks", [])
        if not isinstance(raw, list):
            self._add("error", "wrong-type", _join(path, "blocks"),
                      f'"blocks" must be a list of blocks, not {show(raw)}.')
            return [], False
        if kind.cls is Select and len(raw) < 2:
            self._add("warning", "too-few-panels", path,
                      f"This Select has {len(raw)} panel{'s' if len(raw) != 1 else ''}; it shows one at a time, "
                      "so it needs at least 2.", "Add panels, or use a Group.")
        elif kind.cls is not Select and len(raw) < kind.min_blocks:
            self._add("error", "empty-container", path, f"This {kind.name} has no blocks.",
                      'Add at least one block to its "blocks".')
        word = "Option" if spec.get("select_type") == "dropdown" else "Tab"
        children = []
        for i, child in enumerate(raw):
            child_path = _join(_join(path, "blocks"), i)
            if kind.cls is Select and isinstance(child, Mapping) and not child.get("label"):
                self._missing_label(child_path, "panel", "label", word)
            children.append(self.block(child, child_path, page=page if isinstance(page, str) else None,
                                       is_page=panels_are_pages))
        return children, ok

    def _missing_label(self, path: str, what: str, key: str, word: str) -> None:
        number = int(path.rsplit("/", 1)[-1]) + 1  # the path ends with its index in "blocks"
        self._add("warning", "missing-label", path,
                  f'This {what} has no {key}, so its {word.lower()} shows "{word} {number}".', f'Add "{key}": "...".')

    def _claim(self, name: str, page: str | None, path: str, type_: str) -> None:
        link = f"{page}/{name}" if page else name
        if link in self._links:
            where = f" in page {page!r}" if page else ""
            self._add("error", "duplicate-name", path,
                      f"Two blocks{where} are named {name!r}: the one at {self._links[link]} and this {type_}.",
                      f"A name must be unique within its page, so that the link #{link} leads to one place; "
                      "rename one of them.")
        else:
            self._links[link] = path

    def _unknown_type(self, type_: object, path: str) -> None:
        kinds = block_types()
        hint = _suggest(type_, kinds) or _suggest(f"lab.{type_}", kinds)
        if type_ == "Briefing":
            hint = 'The report\'s own options ("export", "footer") go at the top of the JSON, next to "blocks".'
        self._add("error", "unknown-type", _join(path, "type"), f"There is no block type {show(type_)}.",
                  hint or f"The types are: {', '.join(kinds)}.")

    def _unknown_keys(self, spec: Mapping[str, t.Any], path: str, what: str, known: list[str]) -> None:
        for key in spec:
            if key not in known:
                options = [k for k in known if k != "type"]
                self._add("error", "unknown-option", _join(path, key), f"{what} has no option {show(key)}.",
                          _suggest(key, options) or f"Its options are: {', '.join(options) or 'none'}.")

    # ── options ──

    def _options(
        self, spec: Mapping[str, t.Any], kind: BlockType, path: str, what: str
    ) -> tuple[dict[str, t.Any], bool]:
        options: dict[str, t.Any] = {}
        ok = True
        for field in kind.fields:
            if field.key not in spec:
                if field.required:
                    self._add("error", "missing-option", path, f'{what} needs "{field.key}".',
                              field.description or None)
                    ok = False
                continue
            value, field_ok = self._value(spec[field.key], field, _join(path, field.key), what)
            ok = ok and field_ok
            if field_ok:
                options[field.name] = value
        if kind.name == "Text" and "text" not in spec and "file" not in spec:
            self._add("error", "missing-option", path, 'Text needs "text" (or "file", the path of a .md file).')
            ok = False
        return options, ok

    def _value(self, value: object, field: Field, path: str, what: str) -> tuple[t.Any, bool]:
        if isinstance(value, Mapping) and set(value) == {"ref"}:
            return self._resolve(value["ref"], path)
        if not check(value, field.schema):
            self._add("error", "wrong-type", path,
                      f'{what} "{field.key}" must be {describe(field.schema)}, not {show(value)}.',
                      field.description or None)
            return None, False
        accepts = refs_in(field.schema)
        try:
            if isinstance(value, Mapping) and "table" in accepts and "rows" in value:
                return decode_table(dict(value)), True
            if isinstance(value, Mapping) and "figure" in accepts:
                return decode_figure(dict(value)), True
            if isinstance(value, str) and "image" in accepts and value.startswith("data:"):
                return decode_image(value), True
        except BriefingError as exc:
            self._add("error", "invalid-data", path, f'{what} "{field.key}": {exc}')
            return None, False
        return value, True

    def _resolve(self, name: object, path: str) -> tuple[t.Any, bool]:
        if not isinstance(name, str) or not name:
            self._add("error", "wrong-type", path, f'A reference is {{"ref": "<name>"}}, not {{"ref": {show(name)}}}.')
            return None, False
        if self.data is None:
            return None, False
        if name not in self.data:
            self._add("error", "unknown-ref", path, f"No object named {name!r} was passed in data.",
                      _suggest(name, self.data) or f"Pass it: from_spec(spec, data={{{name!r}: ...}}), "
                      "or write the value into the JSON.")
            return None, False
        return self.data[name], True

    # ── building ──

    def _construct(self, cls: type[Block], options: dict[str, t.Any], path: str, what: str) -> Block | None:
        if not self.capture:
            block = self._call(cls, options, path, what)
        else:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                block = self._call(cls, options, path, what)
            for warning in caught:
                message = str(warning.message)
                if cls is Select and message.startswith("Select has"):
                    continue  # reported as too-few-panels
                code = "deprecated" if issubclass(warning.category, DeprecationWarning) else "block-warning"
                self._add("warning", code, path, message)
        if block is not None:
            self.paths[id(block)] = path
        return block

    def _call(self, cls: type[Block], options: dict[str, t.Any], path: str, what: str) -> Block | None:
        try:
            return cls(**options)
        except BriefingError as exc:
            self._add("error", "invalid-value", path, str(exc))
        except Exception as exc:  # noqa: BLE001 — a library's own error on odd input is still the input's problem
            self._add("error", "invalid-value", path, f"{what} can't be built: {type(exc).__name__}: {exc}")
        return None


def from_spec(spec: object, data: Mapping[str, t.Any] | None = None) -> Briefing:
    """The report *spec* describes (see :func:`briefing.from_spec`)."""
    loaded, problem = load(spec)
    if problem is not None:
        raise BriefingError(str(problem))
    if data is not None and not isinstance(data, Mapping):
        raise BriefingError(f"data must be a dict of the objects the JSON names, not {type(data).__name__}.")
    reader = Reader(data if data is not None else {}, capture_warnings=False)
    report = reader.report(loaded)
    errors = [d for d in reader.diagnostics if d.severity == "error"]
    if errors or report is None:
        shown = "\n".join(f"- {d}" for d in errors[:10])
        more = f"\n…and {len(errors) - 10} more." if len(errors) > 10 else ""
        raise BriefingError(f"This JSON isn't a report briefing can build:\n{shown}{more}\n"
                            "bf.validate(spec, data) lists every problem.")
    return report
