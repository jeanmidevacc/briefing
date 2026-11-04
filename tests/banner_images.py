"""Small images for Banner tests: a solid-colour SVG, and the magic bytes of other formats."""
from __future__ import annotations

RED_SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400">'
           b'<rect width="100%" height="100%" fill="#ff0000"/></svg>')
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP_MAGIC = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 32
