#!/usr/bin/env python3
"""
FX Noise Lab - Playback Manager
"""

import importlib
import threading
import time
from typing import Callable, Optional

import numpy as np


def _get_sounddevice():
    """Import sounddevice lazily to keep package imports side-effect free."""
    return importlib.import_module("sounddevice")


class PlaybackManager:
    """Manages audio playback for sonification."""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, sample_rate: int = 44100, buffer_size: int = 256):
        """Initialize playback manager.

        Args:
            sample_rate: Audio sample rate
            buffer_size: Audio buffer size
        """
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self._is_playing = False
        self._is_paused = False
        self._current_timestamp = 0.0
        self._loop = True
        self._playback_rate = 1.0
        self._data_index = 0
        self._data_length = 0
        self._audio_data = np.array([], dtype=np.float32)
        self._source_progress_seconds = 0.0

        # Callback for data updates
        self._data_callback: Optional[Callable] = None
        self._completion_callback: Optional[Callable] = None

        # Lock for thread safety
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._stream_thread = None

    def set_data_callback(self, callback: Callable):
        """Set callback for data updates.

        Args:
            callback: Function to call when data is ready
        """
        self._data_callback = callback

    def set_completion_callback(self, callback: Callable):
        """Set a callback to run when playback finishes or is stopped."""
        self._completion_callback = callback

    def set_playback_rate(self, rate: float):
        """Set playback speed.

        Args:
            rate: Playback rate (0.25x to 8x)
        """
        self._playback_rate = max(rate, 0.25)
        self._data_index = 0

    def _resample_for_playback_rate(self, audio_data: np.ndarray) -> np.ndarray:
        """Resample the buffer to approximate faster or slower playback."""
        if self._playback_rate == 1.0 or len(audio_data) < 2:
            return audio_data

        target_length = max(1, int(round(len(audio_data) / self._playback_rate)))
        source_positions = np.linspace(0, len(audio_data) - 1, len(audio_data))
        target_positions = np.linspace(0, len(audio_data) - 1, target_length)

        if audio_data.ndim == 1:
            return np.interp(target_positions, source_positions, audio_data).astype(
                np.float32
            )

        resampled_channels = [
            np.interp(target_positions, source_positions, audio_data[:, channel_index])
            for channel_index in range(audio_data.shape[1])
        ]
        return np.stack(resampled_channels, axis=1).astype(np.float32)

    def start(self, data: np.ndarray, duration_ms: float):
        """Start playback.

        Args:
            data: Audio data array
            duration_ms: Playback duration in milliseconds
        """
        self.stop()

        audio_data = np.asarray(data, dtype=np.float32)
        if audio_data.size == 0:
            return

        requested_samples = (
            int(duration_ms * self.sample_rate / 1000) if duration_ms > 0 else 0
        )
        if requested_samples > 0:
            audio_data = audio_data[:requested_samples]

        audio_data = self._resample_for_playback_rate(audio_data)

        with self._lock:
            self._audio_data = audio_data.copy()
            self._data_length = len(self._audio_data)
            self._data_index = 0
            self._is_playing = self._data_length > 0
            self._is_paused = False
            self._current_timestamp = 0.0
            self._source_progress_seconds = 0.0
            self._stop_event.clear()
            if not self._is_playing:
                return
            self._stream_thread = threading.Thread(
                target=self._playback_loop, daemon=True
            )
            self._stream_thread.start()

    def _playback_loop(self):
        """Main playback loop."""
        try:
            while not self._stop_event.is_set():
                if self._is_paused:
                    time.sleep(0.01)
                    continue

                if not self._is_playing:
                    break

                self._process_audio_chunk()
        finally:
            if self._completion_callback is not None:
                self._completion_callback()
            with self._lock:
                if self._stream_thread is threading.current_thread():
                    self._stream_thread = None

    def _process_audio_chunk(self):
        """Process one audio chunk."""
        # Calculate chunk duration
        chunk_duration = self.buffer_size / self.sample_rate

        # Get data for this chunk
        start_idx = self._data_index
        end_idx = min(
            start_idx + int(chunk_duration * self.sample_rate), self._data_length
        )

        if start_idx >= end_idx:
            if self._loop and self._data_length > 0:
                self._data_index = 0
                self._current_timestamp = 0.0
            else:
                self._stop_event.set()
                self._is_playing = False
            return

        # Get audio data for this chunk
        chunk_data = self._get_chunk_data(start_idx, end_idx - start_idx)

        if chunk_data is not None and len(chunk_data) > 0:
            # Play the chunk
            try:
                sounddevice = _get_sounddevice()
            except ModuleNotFoundError as error:  # pragma: no cover - env-specific
                print(f"Playback error: {error}")
                self._stop_event.set()
                self._is_playing = False
                return

            try:
                sounddevice.play(chunk_data, self.sample_rate, blocking=True)
            except sounddevice.PortAudioError as error:  # pragma: no cover
                print(f"Playback error: {error}")
                self._stop_event.set()
                self._is_playing = False
                return

            self._data_index = end_idx
            self._source_progress_seconds += chunk_duration * self._playback_rate
            self._current_timestamp = self._source_progress_seconds
            if self._data_callback is not None:
                self._data_callback(chunk_data)

    def _get_chunk_data(self, start_idx: int, length: int) -> np.ndarray:
        """Get audio data for a chunk.

        Args:
            start_idx: Start index in data array
            length: Number of samples

        Returns:
            Audio data array
        """
        end_idx = start_idx + length
        return self._audio_data[start_idx:end_idx]

    def pause(self):
        """Pause playback."""
        with self._lock:
            if self._is_playing:
                self._is_paused = True

    def resume(self):
        """Resume playback."""
        with self._lock:
            if self._is_playing:
                self._is_paused = False

    def stop(self):
        """Stop playback."""
        stream_thread = None
        with self._lock:
            self._stop_event.set()
            self._is_playing = False
            self._is_paused = False
            self._data_index = 0
            self._current_timestamp = 0.0
            self._source_progress_seconds = 0.0
            stream_thread = self._stream_thread
            self._stream_thread = None
        try:
            _get_sounddevice().stop()
        except ModuleNotFoundError:  # pragma: no cover - env-specific
            pass
        if (
            stream_thread is not None
            and stream_thread.is_alive()
            and stream_thread is not threading.current_thread()
        ):
            stream_thread.join(timeout=0.5)

    def is_playing(self) -> bool:
        """Check if playback is active.

        Returns:
            True if playing
        """
        with self._lock:
            return self._is_playing

    def is_paused(self) -> bool:
        """Check if playback is paused.

        Returns:
            True if paused
        """
        with self._lock:
            return self._is_paused

    def get_current_timestamp(self) -> float:
        """Get current playback timestamp.

        Returns:
            Current timestamp in seconds
        """
        with self._lock:
            return self._current_timestamp

    def set_loop(self, loop: bool):
        """Set playback loop mode.

        Args:
            loop: True for loop, False for stop at end
        """
        self._loop = loop


def create_playback_manager(
    sample_rate: int = 44100, buffer_size: int = 256
) -> PlaybackManager:
    """Factory function to create playback manager.

    Args:
        sample_rate: Audio sample rate
        buffer_size: Buffer size

    Returns:
        PlaybackManager instance
    """
    return PlaybackManager(sample_rate, buffer_size)
