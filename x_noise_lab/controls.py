#!/usr/bin/env python3
"""
FX Noise Lab - Control Module
"""

from typing import Dict, Tuple

import numpy as np


class ControlsManager:
    """Manages user controls and settings."""

    def __init__(self):
        """Initialize controls manager."""
        self._settings = {
            "volume": 0.8,
            "base_pitch": 440,
            "min_hz": 200,
            "max_hz": 1200,
            "noise_sensitivity": 1.0,
            "pitch_sensitivity": 1.0,
            "smoothness": 0.1,
            "gate_threshold": 0.3,
            "trust_volume_enabled": True,
            "spread_muted": False,
            "regime_muted": False,
        }

    def get_settings(self) -> Dict:
        """Get current settings.

        Returns:
            Dictionary with current settings
        """
        return self._settings.copy()

    def set_volume(self, value: float):
        """Set volume level.

        Args:
            value: Volume level (0.0 to 1.0)
        """
        self._settings["volume"] = float(np.clip(value, 0.0, 1.0))

    def set_base_pitch(self, value: int):
        """Set base pitch.

        Args:
            value: Base pitch in Hz
        """
        self._settings["base_pitch"] = value

    def set_min_hz(self, value: int):
        """Set the minimum playback frequency."""
        self._settings["min_hz"] = int(value)

    def set_max_hz(self, value: int):
        """Set the maximum playback frequency."""
        self._settings["max_hz"] = int(value)

    def set_noise_sensitivity(self, value: float):
        """Set noise sensitivity.

        Args:
            value: Sensitivity multiplier
        """
        self._settings["noise_sensitivity"] = float(np.clip(value, 0.0, 3.0))

    def set_pitch_sensitivity(self, value: float):
        """Set pitch sensitivity.

        Args:
            value: Sensitivity multiplier
        """
        self._settings["pitch_sensitivity"] = float(np.clip(value, 0.5, 3.0))

    def set_smoothness(self, value: float):
        """Set smoothing factor.

        Args:
            value: Smoothing factor (0.0 to 1.0)
        """
        self._settings["smoothness"] = float(np.clip(value, 0.0, 1.0))

    def set_gate_threshold(self, value: float):
        """Set gate threshold.

        Args:
            value: Gate threshold (0.0 to 1.0)
        """
        self._settings["gate_threshold"] = float(np.clip(value, 0.0, 1.0))

    def set_spread_muted(self, muted: bool):
        """Set spread mute state.

        Args:
            muted: True to mute spread, False otherwise
        """
        self._settings["spread_muted"] = muted

    def set_trust_volume_enabled(self, enabled: bool):
        """Enable or disable trust-based volume scaling."""
        self._settings["trust_volume_enabled"] = enabled

    def set_regime_muted(self, muted: bool):
        """Set regime mute state.

        Args:
            muted: True to mute regime, False otherwise
        """
        self._settings["regime_muted"] = muted

    def apply_settings(self, settings: Dict):
        """Apply a preset or external settings dictionary."""
        if "volume" in settings:
            self.set_volume(settings["volume"])
        if "base_pitch" in settings:
            self.set_base_pitch(settings["base_pitch"])
        if "min_hz" in settings:
            self.set_min_hz(settings["min_hz"])
        if "max_hz" in settings:
            self.set_max_hz(settings["max_hz"])
        if "noise_sensitivity" in settings:
            self.set_noise_sensitivity(settings["noise_sensitivity"])
        if "pitch_sensitivity" in settings:
            self.set_pitch_sensitivity(settings["pitch_sensitivity"])
        if "smoothness" in settings:
            self.set_smoothness(settings["smoothness"])
        if "gate_threshold" in settings:
            self.set_gate_threshold(settings["gate_threshold"])
        if "trust_volume_enabled" in settings:
            self.set_trust_volume_enabled(bool(settings["trust_volume_enabled"]))
        if "spread_muted" in settings:
            self.set_spread_muted(bool(settings["spread_muted"]))
        if "regime_muted" in settings:
            self.set_regime_muted(bool(settings["regime_muted"]))

    def get_control_values(self) -> Tuple[float, int, int, int, float, float]:
        """Get current control values.

        Returns:
            Tuple of (volume, base_pitch, min_hz, max_hz, noise_sensitivity, pitch_sensitivity)
        """
        return (
            self._settings["volume"],
            self._settings["base_pitch"],
            self._settings["min_hz"],
            self._settings["max_hz"],
            self._settings["noise_sensitivity"],
            self._settings["pitch_sensitivity"],
        )


def create_controls_manager() -> ControlsManager:
    """Factory function to create controls manager.

    Returns:
        ControlsManager instance
    """
    return ControlsManager()
