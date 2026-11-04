"""Export reports out of the browser as images and PDFs (``pip install "briefing[image]"``).

Importing this package doesn't import Playwright; the export functions do, when called.
"""
from __future__ import annotations

from briefing.export._image import PRESETS, save_image
from briefing.export._pdf import PAPERS, save_pdf

__all__ = ["PAPERS", "PRESETS", "save_image", "save_pdf"]
