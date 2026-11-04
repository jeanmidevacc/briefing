"""The ``briefing-example`` directive: show code, run it, embed the report it saves.

Usage, from MyST Markdown::

    ```{briefing-example}
    :height: 420

    import briefing as bf
    bf.save(bf.Text("# Hello"), "hello.html", name="Hello")
    ```

The code runs at build time (see :mod:`gallery`) with ``SOURCE_DATE_EPOCH``
pinned. The report is copied to ``_examples/`` in the built site and shown in
an iframe that grows to the report's height, with an "Open full page" link.
An exception or a warning while running an example stops the build.
"""
from __future__ import annotations

import html
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.errors import ExtensionError
from sphinx.util.docutils import SphinxDirective

sys.path.insert(0, str(Path(__file__).parent))
from gallery import ExampleError, run_example  # noqa: E402

OUTPUT_DIR = "_examples"


class BriefingExample(SphinxDirective):
    has_content = True
    option_spec = {
        "height": directives.positive_int,  # iframe height before the report loads, in px
        "title": directives.unchanged,  # accessible title of the iframe
    }

    def run(self) -> list[nodes.Node]:
        code = "\n".join(self.content).rstrip() + "\n"
        docname = self.env.docname
        where = f"{self.env.doc2path(docname)}:{self.lineno}"
        target = f"{docname.replace('/', '-')}-{self.env.new_serialno('briefing-example') + 1}.html"
        with tempfile.TemporaryDirectory(prefix="briefing-example-") as tmp:
            try:
                report = run_example(code, Path(tmp), where=where)
            except ExampleError as exc:
                raise ExtensionError(str(exc)) from exc
            out = Path(self.env.app.outdir) / OUTPUT_DIR
            out.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(report, out / target)
        self.env.note_dependency(__file__)

        literal = nodes.literal_block(code, code)
        literal["language"] = "python"
        src = html.escape("../" * docname.count("/") + f"{OUTPUT_DIR}/{target}")
        title = html.escape(self.options.get("title", "Rendered report"))
        height = self.options.get("height", 360)
        frame = nodes.raw(
            "",
            f'<div class="bf-example">'
            f'<iframe class="bf-example__frame" src="{src}" title="{title}" loading="lazy" '
            f'style="height: {height}px"></iframe>'
            f'<a class="bf-example__open" href="{src}" target="_blank" rel="noopener">Open full page ↗</a>'
            f"</div>",
            format="html",
        )
        return [literal, frame]


def setup(app: Sphinx) -> dict[str, Any]:
    app.add_directive("briefing-example", BriefingExample)
    app.add_css_file("briefing-example.css")
    app.add_js_file("briefing-example.js")
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
