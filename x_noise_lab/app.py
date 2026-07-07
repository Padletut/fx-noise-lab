#!/usr/bin/env python3
"""
FX Noise Lab - Main Entry Point
"""

import os
from pathlib import Path
import sys
from tkinter import TclError

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
    app = None
    force_process_exit = False
    exit_code = 0
    try:
        app = create_main_window(controller=controller)
        force_process_exit = True
        if app is not None:
            app.mainloop()
    except KeyboardInterrupt:
        force_process_exit = True
        exit_code = 130
    except Exception:
        force_process_exit = False
        raise
    finally:
        controller.shutdown()
        if app is not None:
            try:
                app.destroy()
            except TclError:
                pass
        if force_process_exit:
            sys.stdout.flush()
            sys.stderr.flush()
            # PortAudio/sounddevice can segfault during interpreter teardown on
            # some Linux backends. Runtime resources are already stopped above.
            os._exit(exit_code)


if __name__ == "__main__":
    main()
