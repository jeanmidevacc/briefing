"""``python -m briefing``: export saved reports (see :mod:`briefing._cli`)."""
from __future__ import annotations

import sys

from briefing._cli import main

if __name__ == "__main__":
    sys.exit(main())
