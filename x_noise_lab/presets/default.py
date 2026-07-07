#!/usr/bin/env python3
"""FX Noise Lab - Preset Loader."""
# pylint: disable=duplicate-code

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

DEFAULT_PRESET_PATH = Path(__file__).with_name("default.json")
FALLBACK_DEFAULT_PRESET = {
    "name": "default",
    "base_pitch": 440,
    "min_hz": 200,
    "max_hz": 1200,
    "volume": 0.8,
    "smoothness": 0.1,
    "gate_threshold": 0.0,
    "trust_volume_enabled": True,
    "spread_muted": False,
    "regime_muted": False,
    "noise_sensitivity": 1.0,
    "pitch_sensitivity": 1.0,
}


def _read_preset_file(preset_path: Path) -> Dict:
    """Read a preset JSON file from disk."""
    with open(preset_path, "r", encoding="utf-8") as preset_file:
        return json.load(preset_file)


def get_default_preset() -> Dict:
    """Get the default preset configuration."""
    if DEFAULT_PRESET_PATH.exists():
        return _read_preset_file(DEFAULT_PRESET_PATH)

    return FALLBACK_DEFAULT_PRESET.copy()


def load_preset(preset_name: str) -> Dict:
    """Load a named preset, falling back to the default preset."""
    preset_path = Path(__file__).with_name(f"{preset_name}.json")
    if preset_path.exists():
        return _read_preset_file(preset_path)

    return get_default_preset()
