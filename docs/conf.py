"""Sphinx configuration for the briefing documentation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from briefing import __version__  # noqa: E402

project = "briefing"
author = "jeanmidevacc"
copyright = "2026, jeanmidevacc"
release = __version__
version = ".".join(__version__.split(".")[:2])

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
]

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
exclude_patterns = ["_build"]

# Autodoc: document what each page lists, in source order, with base classes.
autodoc_member_order = "bysource"
autodoc_default_options = {"members": True, "undoc-members": False, "show-inheritance": True}
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"

# Napoleon: the codebase uses Google-style docstrings only.
napoleon_google_docstring = True
napoleon_numpy_docstring = False

myst_enable_extensions = ["colon_fence"]

html_theme = "furo"
html_title = f"briefing {release}"
html_static_path = ["_static"]
