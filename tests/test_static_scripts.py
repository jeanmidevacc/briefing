"""briefing's scripts work inside the root they are given, never on the whole page (#123).

Each script registers a part with the runtime in ``report.js`` (``window.briefing``).
A part queries from its root, adds page-wide listeners only through the runtime's
``runtime.on`` and does its print work through ``runtime.onPrint``; the runtime adds the
``beforeprint``/``afterprint`` listeners once per page. This is what lets two
outputs share a page (#122) without one driving the other.
"""
from __future__ import annotations

import re

import pytest

import briefing as bf
from tests.golden import static_files
from tests.html_helpers import parse

SCRIPTS = {path: text for path, text in static_files().items() if path.endswith(".js")}

#: ``document.<anything>`` other than making new nodes reaches outside the root.
_DOCUMENT_ACCESS = re.compile(r"(?<![\w.$])document\s*\.\s*(?!create(?:Element|DocumentFragment|TextNode)\b)(\w+)")
#: A listener added on the page itself, or an ``on…`` handler set on it.
_PAGE_LISTENER = re.compile(r"(?<![\w.$])(?:window|document)\s*\.\s*(?:addEventListener|on\w+\s*=)")
_REGISTERS = re.compile(r"window\.briefing\.register\('([\w-]+)'")


def test_every_script_is_checked() -> None:
    assert sorted(SCRIPTS) == [
        "lab/static/calendar.js", "lab/static/lab.js", "static/copy-embed.js", "static/export.js", "static/report.js",
        "static/unpack.js",
    ]


#: Scripts that define a function and touch no element, so they register no part.
FUNCTIONS = {"static/unpack.js"}


@pytest.mark.parametrize("path", sorted(SCRIPTS))
def test_no_script_reaches_into_the_page(path: str) -> None:
    assert _DOCUMENT_ACCESS.findall(SCRIPTS[path]) == []
    assert _PAGE_LISTENER.findall(SCRIPTS[path]) == []


@pytest.mark.parametrize("path", sorted(SCRIPTS))
def test_each_script_registers_one_part(path: str) -> None:
    assert len(_REGISTERS.findall(SCRIPTS[path])) == (0 if path in FUNCTIONS else 1)


@pytest.mark.parametrize("path", sorted(FUNCTIONS))
def test_a_function_script_touches_no_element(path: str) -> None:
    assert not re.search(r"querySelector|getElement|\.(?:append|insert|remove)\w*\(", SCRIPTS[path])


def test_only_the_runtime_listens_to_the_page() -> None:
    # runtime.on is the one place a listener is added to a target the caller passes in.
    calls = {path: text.count("target.addEventListener") for path, text in SCRIPTS.items()}
    assert calls == {path: int(path == "static/report.js") for path in SCRIPTS}


def test_a_full_report_initialises_the_document_once() -> None:
    soup = parse(bf.stringify(bf.Briefing(bf.Text("x"))))
    script = soup.select("body > script")[-1].get_text()
    assert script.rstrip().endswith("briefing.init(document);")
    assert script.count("briefing.init(document)") == 1
