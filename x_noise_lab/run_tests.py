#!/usr/bin/env python3
"""FX Noise Lab - Convenience test runner."""

from __future__ import annotations

# pylint: disable=wrong-import-position

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from x_noise_lab.test_project import main


if __name__ == "__main__":
    sys.exit(main())
