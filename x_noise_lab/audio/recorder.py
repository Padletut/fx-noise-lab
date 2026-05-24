#!/usr/bin/env python3
"""FX Noise Lab - Audio Recorder."""

from __future__ import annotations

import datetime
import threading
import wave
from pathlib import Path
from typing import Optional

import numpy as np


class AudioRecorder:
    """Capture generated playback buffers and export them to WAV."""

    def __init__(self, output_path: Optional[str] = None):
        """Initialize the recorder."""
        self._configured_output_path = Path(output_path) if output_path else None
        self._is_recording = False
        self._lock = threading.Lock()
        self._frames = []
        self._sample_rate = 44100
        self._start_time = None

    def start_recording(self, sample_rate: int = 44100):
        """Start buffering audio frames for a future WAV export."""
        with self._lock:
            if self._is_recording:
                raise RuntimeError("Already recording")

            self._sample_rate = sample_rate
            self._start_time = datetime.datetime.now()
            self._frames = []
            self._is_recording = True

    def append_frames(self, audio_data: np.ndarray):
        """Append a playback chunk to the recording buffer."""
        with self._lock:
            if not self._is_recording:
                return

            frames = np.asarray(audio_data, dtype=np.float32)
            if frames.size == 0:
                return

            frames = np.clip(frames, -1.0, 1.0)
            if frames.ndim == 1:
                frames = frames[:, np.newaxis]

            self._frames.append(frames.copy())

    def stop_recording(self) -> Optional[str]:
        """Stop recording and persist buffered audio to a WAV file."""
        with self._lock:
            if not self._is_recording:
                return None

            self._is_recording = False
            if not self._frames:
                return None

            buffered_frames = [frame.copy() for frame in self._frames]
            self._frames = []
            sample_rate = self._sample_rate
            start_time = self._start_time

        all_data = np.concatenate(buffered_frames, axis=0)
        channel_count = all_data.shape[1]

        if self._configured_output_path is not None:
            output_path = self._configured_output_path
        else:
            output_dir = Path("recordings")
            output_dir.mkdir(exist_ok=True)
            timestamp = start_time.strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"fx_noise_lab_{timestamp}.wav"

        pcm_frames = (all_data * 32767).astype(np.int16)
        # pylint: disable=no-member
        with wave.open(str(output_path), "w") as wav_file:
            wav_file.setnchannels(channel_count)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_frames.tobytes())

        return str(output_path)

    def get_recording_duration(self) -> float:
        """Get the buffered recording duration in seconds."""
        with self._lock:
            if not self._is_recording:
                return 0.0

            total_samples = sum(len(frame) for frame in self._frames)
            return total_samples / self._sample_rate

    def is_recording(self) -> bool:
        """Return whether recording is currently active."""
        with self._lock:
            return self._is_recording


def create_audio_recorder(output_path: Optional[str] = None) -> AudioRecorder:
    """Factory function to create an audio recorder."""
    return AudioRecorder(output_path)
