#!/usr/bin/env python3
"""
FX Noise Lab - Main Package
"""

import importlib

__version__ = "0.1.0"
__author__ = "FX Noise Lab"


def main():
    """Run the application with lazy imports to avoid GUI side effects on package import."""
    run_main = importlib.import_module(".app", __name__).main

    return run_main()


__all__ = ["main", "__version__", "__author__"]
