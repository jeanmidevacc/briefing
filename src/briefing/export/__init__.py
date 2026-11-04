"""Export reports out of the browser: images now, PDFs next (``pip install "briefing[image]"``).

Importing this package doesn't import Playwright; the export functions do, when called.
"""
from __future__ import annotations

from briefing.export._image import PRESETS, save_image

__all__ = ["PRESETS", "save_image"]
