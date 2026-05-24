#!/usr/bin/env python3
"""FX Noise Lab - Audio Mapper."""

from __future__ import annotations

from typing import Dict

import numpy as np


class AudioMapper:
    """Map market features onto simple audio synthesis parameters."""

    def __init__(self, base_pitch: int = 440, min_hz: int = 200, max_hz: int = 1200):
        self.base_pitch = base_pitch
        self.min_hz = min_hz
        self.max_hz = max_hz

    def configure(self, settings: Dict):
        """Update the mapper range from runtime settings."""
        self.base_pitch = int(settings.get("base_pitch", self.base_pitch))
        self.min_hz = int(settings.get("min_hz", self.min_hz))
        self.max_hz = int(settings.get("max_hz", self.max_hz))

    def map_quality_to_pitch(
        self, quality_score: float, pitch_sensitivity: float = 1.0
    ) -> int:
        """Map a normalized quality score to a clamped pitch."""
        clamped_quality = float(np.clip(quality_score, 0.0, 1.0))
        lower_span = max(self.base_pitch - self.min_hz, 0)
        upper_span = max(self.max_hz - self.base_pitch, 0)

        if clamped_quality <= 0.5:
            pitch = self.base_pitch - (0.5 - clamped_quality) * 2 * lower_span
        else:
            pitch = self.base_pitch + (clamped_quality - 0.5) * 2 * upper_span

        centered_pitch = self.base_pitch + (pitch - self.base_pitch) * pitch_sensitivity
        return int(np.clip(centered_pitch, self.min_hz, self.max_hz))

    def map_volatility_to_vibrato(
        self, volatility: float, noise_sensitivity: float = 1.0
    ) -> float:
        """Map volatility to vibrato frequency in hertz."""
        vibrato_frequency = 4 + max(volatility, 0.0) * 8 * noise_sensitivity
        return float(np.clip(vibrato_frequency, 1.0, 40.0))

    def map_trust_to_volume(self, trust_value: float) -> float:
        """Map trust to a normalized amplitude multiplier."""
        return float(np.clip(trust_value, 0.0, 1.0))

    def map_spread_to_distortion(
        self, spread_value: float, spread_muted: bool = False
    ) -> float:
        """Map spread to a distortion amount."""
        if spread_muted:
            return 0.0
        return float(np.clip(spread_value, 0.0, 1.0))

    def map_regime_to_filter(
        self, regime: str, regime_muted: bool = False
    ) -> Dict[str, float]:
        """Map regime to a simple voicing profile."""
        if regime_muted:
            return {"mute": False, "harmonic": 0.0, "subharmonic": 0.0}

        normalized_regime = regime.lower()
        if normalized_regime == "bull":
            return {"mute": False, "harmonic": 0.25, "subharmonic": 0.0}
        if normalized_regime == "bear":
            return {"mute": False, "harmonic": 0.0, "subharmonic": 0.2}
        return {"mute": False, "harmonic": 0.1, "subharmonic": 0.05}

    def generate_sound_event(
        self, event_type: str, duration_ms: int = 100, sample_rate: int = 44100
    ) -> np.ndarray:
        """Generate a short audio cue for UI or trade events."""
        duration_seconds = duration_ms / 1000.0
        timeline = np.arange(int(duration_seconds * sample_rate)) / sample_rate

        frequency = 880.0
        if event_type == "chime":
            frequency = 523.25
        elif event_type == "alert":
            frequency = 440.0

        sound = np.sin(2 * np.pi * frequency * timeline)
        peak = np.max(np.abs(sound))
        if peak > 0:
            sound = sound / peak
        return sound.astype(np.float32)

    def map_data_to_audio(
        self,
        market_data: Dict,
        settings: Dict,
        duration_ms: int = 150,
        sample_rate: int = 44100,
    ) -> np.ndarray:
        """Convert a market-data row into a short playable audio buffer."""
        # pylint: disable=too-many-locals
        self.configure(settings)

        quality_score = float(market_data.get("quality", 0.5))
        volatility = float(market_data.get("volatility", 0.5))
        trust = float(market_data.get("trust", 0.5))
        spread = float(market_data.get("spread", 0.5))
        trade_eligible = bool(market_data.get("trade_eligible", True))
        regime = str(market_data.get("regime", "neutral"))
        gate_threshold = float(settings.get("gate_threshold", 0.0))

        sample_count = max(1, int(sample_rate * duration_ms / 1000))
        if not trade_eligible or quality_score < gate_threshold:
            return np.zeros(sample_count, dtype=np.float32)

        regime_profile = self.map_regime_to_filter(
            regime,
            settings.get("regime_muted", False),
        )
        pitch = self.map_quality_to_pitch(
            quality_score,
            settings.get("pitch_sensitivity", 1.0),
        )
        vibrato_frequency = self.map_volatility_to_vibrato(
            volatility,
            settings.get("noise_sensitivity", 1.0),
        )
        trust_factor = (
            self.map_trust_to_volume(trust)
            if settings.get("trust_volume_enabled", True)
            else 1.0
        )
        volume = trust_factor * float(settings.get("volume", 0.8))
        distortion = self.map_spread_to_distortion(
            spread,
            settings.get("spread_muted", False),
        )

        timeline = np.arange(sample_count) / sample_rate
        vibrato_depth = max(2.0, pitch * 0.015)
        frequency_modulation = vibrato_depth * np.sin(
            2 * np.pi * vibrato_frequency * timeline
        )
        carrier_frequency = pitch + frequency_modulation
        audio = np.sin(2 * np.pi * carrier_frequency * timeline)

        if regime_profile["harmonic"] > 0:
            audio += regime_profile["harmonic"] * np.sin(
                2 * np.pi * carrier_frequency * 2 * timeline
            )
        if regime_profile["subharmonic"] > 0:
            audio += regime_profile["subharmonic"] * np.sin(
                2 * np.pi * np.maximum(carrier_frequency / 2, 1.0) * timeline
            )

        attack_length = max(1, sample_count // 20)
        release_length = max(1, sample_count // 12)
        envelope = np.ones(sample_count, dtype=np.float32)
        envelope[:attack_length] = np.linspace(0.0, 1.0, attack_length)
        envelope[-release_length:] = np.linspace(1.0, 0.0, release_length)
        audio = audio * envelope

        if distortion > 0:
            drive = 1.0 + distortion * 4.0
            audio = np.tanh(audio * drive)

        audio = np.clip(audio * volume, -1.0, 1.0)
        return audio.astype(np.float32)


def create_audio_mapper(
    base_pitch: int = 440, min_hz: int = 200, max_hz: int = 1200
) -> AudioMapper:
    """Factory function to create an audio mapper."""
    return AudioMapper(base_pitch, min_hz, max_hz)
