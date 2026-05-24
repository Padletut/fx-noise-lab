#!/usr/bin/env python3
"""
FX Noise Lab - Main Entry Point
"""

from pathlib import Path

from .controller import SonificationController
from .gui.main_window import create_main_window

PROJECT_ROOT = Path(__file__).resolve().parent


def main():
    """Application entry point."""
    # Ensure required directories exist
    directories = [
        PROJECT_ROOT / "data",
        PROJECT_ROOT / "presets",
        PROJECT_ROOT / "audio",
    ]

    for directory in directories:
        directory.mkdir(exist_ok=True)

    # Create and run main window
    controller = SonificationController(project_root=PROJECT_ROOT)
    app = create_main_window(controller=controller)

    if app is not None:
        app.mainloop()


if __name__ == "__main__":
    main()
