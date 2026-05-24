#!/usr/bin/env python3
"""FX Noise Lab - Project Test Script."""

from __future__ import annotations

# pylint: disable=wrong-import-position

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from x_noise_lab.project_checks import (
    ensure_repo_on_path,
    run_import_checks,
    run_structure_checks,
)


def main():
    """Run all smoke tests."""
    ensure_repo_on_path()

    print("=" * 60)
    print("FX Noise Lab - Project Test Suite")
    print("=" * 60)

    structure_passed = run_structure_checks()
    imports_passed = run_import_checks()

    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    print(f"Project Structure: {'PASSED' if structure_passed else 'FAILED'}")
    print(f"Module Imports: {'PASSED' if imports_passed else 'FAILED'}")

    if structure_passed and imports_passed:
        print("\n✓ All tests passed!")
        print("\nProject is ready to use.")
        print("\nRun the application with: python -m x_noise_lab")
        return 0

    print("\n✗ Some tests failed. Please review the project structure.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
