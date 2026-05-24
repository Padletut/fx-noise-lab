#!/usr/bin/env python3
"""FX Noise Lab - Audio Engine"""

import importlib
import threading
import time

import numpy as np
from scipy.signal import butter, filtfilt, resample


def _get_sounddevice():
    """Import sounddevice lazily to avoid import-time audio side effects."""
    return importlib.import_module("sounddevice")


class AudioEngine:
    """Audio engine for sonification."""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, sample_rate: int = 44100):
        """Initialize audio engine."""
        self.sample_rate = sample_rate
        self.stream = None
        self.is_playing = False
        self._stream_thread = None
        self._buffer = []
        self._buffer_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self.volume = 0.5

    def _start_stream(self):
        """Start audio stream in background thread."""
        if self._stream_thread is not None and self._stream_thread.is_alive():
            return

        self._stop_event.clear()
        self._pause_event.clear()
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()
        self.is_playing = True

    def _stream_loop(self):
        """Main audio stream loop."""
        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.01)
                continue

            with self._buffer_lock:
                data = self._buffer.pop(0) if self._buffer else None

            if data is None:
                time.sleep(0.01)
                continue

            try:
                output = np.clip(data * self.volume, -1.0, 1.0).astype(
                    np.float32, copy=False
                )
                sounddevice = _get_sounddevice()
            except ModuleNotFoundError as exc:  # pragma: no cover - env-specific
                print(f"Audio stream error: {exc}")
                time.sleep(0.1)
                continue

            try:
                sounddevice.play(output, self.sample_rate, blocking=True)
            except sounddevice.PortAudioError as exc:  # pragma: no cover
                print(f"Audio stream error: {exc}")
                time.sleep(0.1)

    def play(self, data: np.ndarray):
        """Play audio data."""
        audio_data = np.asarray(data, dtype=np.float32)
        if audio_data.size == 0:
            return

        with self._buffer_lock:
            self._buffer.append(audio_data.copy())

        self._start_stream()

    def stop(self):
        """Stop audio playback."""
        self._stop_event.set()
        self._pause_event.clear()
        try:
            _get_sounddevice().stop()
        except ModuleNotFoundError:  # pragma: no cover - env-specific
            pass
        if self._stream_thread is not None:
            self._stream_thread.join(timeout=0.5)
            self._stream_thread = None
        with self._buffer_lock:
            self._buffer.clear()
        self.is_playing = False

    def pause(self):
        """Pause audio playback."""
        if self.is_playing:
            self._pause_event.set()
            try:
                _get_sounddevice().stop()
            except ModuleNotFoundError:  # pragma: no cover - env-specific
                pass

    def resume(self):
        """Resume audio playback."""
        if self.is_playing:
            self._pause_event.clear()
        else:
            with self._buffer_lock:
                has_pending_audio = bool(self._buffer)
            if has_pending_audio:
                self._start_stream()

    def set_volume(self, volume: float):
        """Set volume level (0.0 to 1.0)."""
        self.volume = float(np.clip(volume, 0.0, 1.0))

    def apply_filter(self, data: np.ndarray, lowcut: int = 200, highcut: int = 1200):
        """Apply bandpass filter to audio data."""
        audio_data = np.asarray(data, dtype=np.float32)
        if audio_data.size == 0:
            return audio_data

        nyquist = self.sample_rate / 2
        low = lowcut / nyquist
        high = highcut / nyquist

        if low < 0 or high > 1 or low >= high:
            return audio_data

        b, a = butter(N=4, Wn=[low, high], btype="bandpass", analog=False)
        axis = 0 if audio_data.ndim > 1 else -1

        try:
            return filtfilt(b, a, audio_data, axis=axis)
        except ValueError:
            return audio_data

    def apply_limiter(self, data: np.ndarray, threshold: float = 0.95):
        """Apply soft limiter to prevent clipping."""
        audio_data = np.asarray(data, dtype=np.float32)
        if audio_data.size == 0:
            return audio_data

        max_val = np.max(np.abs(audio_data))
        if max_val > threshold > 0:
            audio_data = audio_data * (threshold / max_val)
        return audio_data

    def resample(self, data: np.ndarray, target_rate: int):
        """Resample audio to target sample rate."""
        audio_data = np.asarray(data, dtype=np.float32)
        if audio_data.size == 0 or target_rate <= 0:
            return audio_data

        target_samples = max(
            1, int(round(len(audio_data) * target_rate / self.sample_rate))
        )
        axis = 0 if audio_data.ndim > 1 else -1
        return resample(audio_data, target_samples, axis=axis)

    def get_audio_context(self):
        """Get current audio context."""
        return {
            "sample_rate": self.sample_rate,
            "is_playing": self.is_playing,
            "volume": self.volume,
        }


def create_audio_engine(sample_rate: int = 44100) -> AudioEngine:
    """Factory function to create audio engine."""
    return AudioEngine(sample_rate)
