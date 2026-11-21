"""The core package must import and render with no visualisation library present.

`plotly` / `altair` / `bokeh` / `matplotlib` are optional: the `Plot` block
imports one only when handed a figure from it, and the report grammar itself
(Text, Table, BigNumber, layout, ...) must not need any of them.

Run in a subprocess so the block on those imports is airtight regardless of what
the test session has already imported.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap

_VIZ_LIBS = ("plotly", "altair", "bokeh", "matplotlib", "seaborn", "plotnine")

_SCRIPT = textwrap.dedent(
    """
    import sys

    class _Blocked:
        def find_spec(self, name, path=None, target=None):
            root = name.split(".")[0]
            if root in {blocked!r}:
                raise ImportError(f"{{name}} is blocked for this test")
            return None

    sys.meta_path.insert(0, _Blocked())
    for _m in list(sys.modules):
        if _m.split(".")[0] in {blocked!r}:
            del sys.modules[_m]

    import datetime
    import briefing as bf

    for _m in {blocked!r}:
        assert _m not in sys.modules, f"importing briefing pulled in {{_m}}"

    report = bf.Briefing(
        bf.Text("# Offline report"),
        bf.Group(
            bf.BigNumber("Rows", 1234),
            bf.BigNumber("Cols", 7),
            columns=2,
        ),
        bf.Alert("No plotting library installed — core still renders.", level="info"),
        bf.Table({{"a": [1, 2, 3], "b": [4, 5, 6]}}),
    )
    html = bf.stringify(report, now=datetime.datetime(2020, 1, 1))
    assert "<table" in html
    assert "Offline report" in html
    print("OK", len(html))
    """
).format(blocked=set(_VIZ_LIBS))


def test_core_imports_and_renders_without_viz_libraries() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"core failed without visualisation libraries\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert result.stdout.startswith("OK ")


def test_importing_briefing_doesnt_import_pandas() -> None:
    # pandas is a core dependency (#40), but a report without tables never loads it.
    script = "import sys, briefing; assert 'pandas' not in sys.modules and 'numpy' not in sys.modules"
    subprocess.run([sys.executable, "-c", script], check=True)
