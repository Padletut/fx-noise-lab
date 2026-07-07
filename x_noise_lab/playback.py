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
        self._last_error: Optional[str] = None
        self._stream_start_event = threading.Event()
        self._active_stream = None
        self._suppress_completion_callback = False
        self._buffer_generation = 0
        self._channel_count = 0

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

    def get_last_error(self) -> Optional[str]:
        """Return and keep the latest playback backend error, if any."""
        with self._lock:
            return self._last_error

    def set_playback_rate(self, rate: float):
        """Set playback speed.

        Args:
            rate: Playback rate (0.25x to 8x)
        """
        with self._lock:
            self._playback_rate = max(rate, 0.25)

    def _resample_for_playback_rate(
        self,
        audio_data: np.ndarray,
        playback_rate: float,
    ) -> np.ndarray:
        """Resample the buffer to approximate faster or slower playback."""
        if playback_rate == 1.0 or len(audio_data) < 2:
            return audio_data

        target_length = max(1, int(round(len(audio_data) / playback_rate)))
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

    def _prepare_audio_data(
        self,
        data: np.ndarray,
        duration_ms: float,
        start_seconds: float = 0.0,
    ) -> tuple[np.ndarray, int, float]:
        """Normalize, trim, resample, and seek an audio buffer."""
        audio_data = np.asarray(data, dtype=np.float32)
        if audio_data.size == 0:
            return audio_data, 0, 0.0

        requested_samples = (
            int(duration_ms * self.sample_rate / 1000) if duration_ms > 0 else 0
        )
        if requested_samples > 0:
            audio_data = audio_data[:requested_samples]

        source_duration_seconds = len(audio_data) / self.sample_rate
        with self._lock:
            playback_rate = max(self._playback_rate, 0.25)
            loop_enabled = self._loop

        audio_data = self._resample_for_playback_rate(audio_data, playback_rate)
        start_seconds = max(0.0, float(start_seconds))
        if loop_enabled and source_duration_seconds > 0:
            start_seconds = start_seconds % source_duration_seconds
        else:
            start_seconds = min(start_seconds, max(source_duration_seconds - 0.001, 0.0))
        start_sample = int(round(start_seconds * self.sample_rate / playback_rate))
        start_sample = min(max(start_sample, 0), max(len(audio_data) - 1, 0))

        return audio_data.copy(), start_sample, start_seconds

    def _get_channel_count(self, audio_data: np.ndarray) -> int:
        """Return the stream channel count for an audio buffer."""
        return 1 if audio_data.ndim == 1 else int(audio_data.shape[1])

    def start(
        self,
        data: np.ndarray,
        duration_ms: float,
        start_seconds: float = 0.0,
        notify_previous_completion: bool = True,
    ):
        """Start playback.

        Args:
            data: Audio data array
            duration_ms: Playback duration in milliseconds
        """
        self.stop(notify_completion=notify_previous_completion)
        with self._lock:
            if self._stream_thread is not None and self._stream_thread.is_alive():
                raise RuntimeError("Previous audio stream is still stopping.")

        audio_data, start_sample, start_seconds = self._prepare_audio_data(
            data,
            duration_ms,
            start_seconds,
        )
        if audio_data.size == 0:
            return

        with self._lock:
            self._audio_data = audio_data
            self._data_length = len(self._audio_data)
            self._data_index = start_sample
            self._is_playing = self._data_length > 0
            self._is_paused = False
            self._current_timestamp = start_seconds
            self._source_progress_seconds = start_seconds
            self._last_error = None
            self._channel_count = self._get_channel_count(self._audio_data)
            self._buffer_generation += 1
            self._stop_event.clear()
            self._stream_start_event.clear()
            if not self._is_playing:
                return
            self._stream_thread = threading.Thread(
                target=self._playback_loop,
                daemon=True,
            )
            self._stream_thread.start()

        if not self._stream_start_event.wait(timeout=2.0):
            self.stop()
            raise RuntimeError(
                "Audio output did not initialize. Check the system output device."
            )

        last_error = self.get_last_error()
        if last_error is not None:
            raise RuntimeError(last_error)

    def replace_data(
        self,
        data: np.ndarray,
        duration_ms: float,
        start_seconds: float = 0.0,
    ) -> bool:
        """Replace the active playback buffer without reopening the audio stream."""
        audio_data, start_sample, start_seconds = self._prepare_audio_data(
            data,
            duration_ms,
            start_seconds,
        )
        if audio_data.size == 0:
            return False

        new_channel_count = self._get_channel_count(audio_data)
        with self._lock:
            stream_alive = (
                self._stream_thread is not None and self._stream_thread.is_alive()
            )
            if not self._is_playing or not stream_alive or self._active_stream is None:
                return False
            if self._channel_count and new_channel_count != self._channel_count:
                return False

            self._audio_data = audio_data
            self._data_length = len(self._audio_data)
            self._data_index = start_sample
            self._current_timestamp = start_seconds
            self._source_progress_seconds = start_seconds
            self._last_error = None
            self._channel_count = new_channel_count
            self._buffer_generation += 1
            return True

    def _playback_loop(self):
        """Main playback loop."""
        try:
            sounddevice = _get_sounddevice()
            with self._lock:
                channel_count = self._channel_count or self._get_channel_count(
                    self._audio_data
                )
            with sounddevice.OutputStream(
                samplerate=self.sample_rate,
                channels=channel_count,
                dtype="float32",
                blocksize=self.buffer_size,
            ) as stream:
                with self._lock:
                    self._active_stream = stream
                    self._channel_count = channel_count
                self._stream_start_event.set()
                while not self._stop_event.is_set():
                    with self._lock:
                        is_paused = self._is_paused
                        is_playing = self._is_playing

                    if is_paused:
                        time.sleep(0.01)
                        continue

                    if not is_playing:
                        break

                    self._process_audio_chunk(stream, channel_count)
        except ModuleNotFoundError as error:  # pragma: no cover - env-specific
            self._set_playback_error(f"Audio backend missing: {error}")
        except Exception as error:  # pragma: no cover - depends on PortAudio backend
            self._set_playback_error(f"Playback error: {error}")
        finally:
            self._stream_start_event.set()
            with self._lock:
                suppress_completion = self._suppress_completion_callback
                self._suppress_completion_callback = False

            if self._completion_callback is not None and not suppress_completion:
                self._completion_callback()
            with self._lock:
                self._is_playing = False
                self._is_paused = False
                self._active_stream = None
                if self._stream_thread is threading.current_thread():
                    self._stream_thread = None

    def _set_playback_error(self, message: str):
        """Store a playback error and stop the current stream loop."""
        with self._lock:
            self._last_error = message
            self._is_playing = False
            self._is_paused = False
            self._stop_event.set()

    def _process_audio_chunk(self, stream, channel_count: int):
        """Process one audio chunk."""
        with self._lock:
            start_idx = self._data_index
            end_idx = min(start_idx + self.buffer_size, self._data_length)

            if start_idx >= end_idx:
                if self._loop and self._data_length > 0:
                    self._data_index = 0
                    self._current_timestamp = 0.0
                    self._source_progress_seconds = 0.0
                else:
                    self._stop_event.set()
                    self._is_playing = False
                return

            chunk_data = self._audio_data[start_idx:end_idx].copy()
            generation = self._buffer_generation
            playback_rate = max(self._playback_rate, 0.25)

        if chunk_data is not None and len(chunk_data) > 0:
            output_chunk = (
                chunk_data[:, np.newaxis]
                if channel_count == 1 and chunk_data.ndim == 1
                else chunk_data
            )
            stream.write(output_chunk)
            with self._lock:
                if self._stop_event.is_set() or generation != self._buffer_generation:
                    return

                self._data_index = end_idx
                self._source_progress_seconds += (
                    len(chunk_data) / self.sample_rate * playback_rate
                )
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

    def stop(
        self,
        wait: bool = True,
        timeout: float = 1.0,
        abort: bool = True,
        notify_completion: bool = True,
    ):
        """Stop playback, optionally waiting for the backend thread to finish."""
        stream_thread = None
        with self._lock:
            self._stop_event.set()
            self._is_playing = False
            self._is_paused = False
            self._data_index = 0
            self._current_timestamp = 0.0
            self._source_progress_seconds = 0.0
            self._buffer_generation += 1
            active_stream = self._active_stream
            stream_thread = self._stream_thread
            self._suppress_completion_callback = (
                not notify_completion
                and stream_thread is not None
                and stream_thread.is_alive()
            )

        if abort and active_stream is not None:
            try:
                active_stream.abort()
            except Exception:  # pragma: no cover - backend-specific cleanup
                pass

        if (
            wait
            and
            stream_thread is not None
            and stream_thread.is_alive()
            and stream_thread is not threading.current_thread()
        ):
            stream_thread.join(timeout=timeout)

        with self._lock:
            if (
                self._stream_thread is stream_thread
                and stream_thread is not None
                and not stream_thread.is_alive()
            ):
                self._stream_thread = None
                self._active_stream = None

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
