#!/usr/bin/env python3
"""Shared project validation helpers for scripts and smoke tests."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Callable

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent

REQUIRED_PACKAGE_FILES = {
    "app.py": "Main entry point",
    "__main__.py": "Package entry point",
    "__init__.py": "Package init",
    "requirements.txt": "Dependencies",
}

REQUIRED_PACKAGE_DIRS = {
    "gui": "GUI module",
    "audio": "Audio module",
    "data": "Data module",
    "presets": "Presets directory",
}

MODULES_TO_TEST = [
    "x_noise_lab.app",
    "x_noise_lab.gui.main_window",
    "x_noise_lab.audio.engine",
    "x_noise_lab.audio.recorder",
    "x_noise_lab.controller",
    "x_noise_lab.mapper",
    "x_noise_lab.data.loader",
    "x_noise_lab.playback",
    "x_noise_lab.controls",
    "x_noise_lab.presets.default",
]


def ensure_repo_on_path():
    """Ensure the repository root is importable."""
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def run_structure_checks(printer: Callable[[str], None] = print) -> bool:
    """Print and evaluate required project files and directories."""
    printer("Testing FX Noise Lab project structure...\n")

    all_passed = True
    for filepath, description in REQUIRED_PACKAGE_FILES.items():
        path = PACKAGE_ROOT / filepath
        exists = path.exists()
        status = "✓" if exists else "✗"
        printer(f"{status} {filepath:30s} - {description}")
        if not exists:
            all_passed = False

    readme_path = REPO_ROOT / "README.md"
    readme_exists = readme_path.exists()
    readme_status = "✓" if readme_exists else "✗"
    printer(
        f"{readme_status} {'README.md':30s} - Documentation (repo root)"
    )
    if not readme_exists:
        all_passed = False

    printer("\nDirectories:")
    for dirname, description in REQUIRED_PACKAGE_DIRS.items():
        path = PACKAGE_ROOT / dirname
        exists = path.exists() and path.is_dir()
        status = "✓" if exists else "✗"
        printer(f"{status} {dirname + '/':30s} - {description}")
        if not exists:
            all_passed = False

    return all_passed


def run_import_checks(printer: Callable[[str], None] = print) -> bool:
    """Import the main package modules and report failures."""
    printer("\nTesting module imports...\n")
    ensure_repo_on_path()

    try:
        for module_name in MODULES_TO_TEST:
            importlib.import_module(module_name)
    except (ImportError, OSError) as exc:
        printer(f"✗ Import failed: {exc}")
        return False

    printer("✓ All modules imported successfully")
    return True
