#!/usr/bin/env python3
"""FX Noise Lab - Project Structure Test."""

from __future__ import annotations

# pylint: disable=wrong-import-position

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from x_noise_lab.project_checks import run_structure_checks


def main():
    """Run structure-only validation."""
    print("=" * 60)
    print("FX Noise Lab - Project Structure Test")
    print("=" * 60)

    passed = run_structure_checks()

    print("\n" + "=" * 60)
    print("Result:")
    print("=" * 60)
    if passed:
        print("\n✓ All structure checks passed!")
        print("\nProject is ready to use.")
        print("Run: python -m x_noise_lab")
        return 0

    print("\n✗ Some files are missing. Please review the project structure.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
