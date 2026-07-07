#!/usr/bin/env python3
"""Application orchestration for FX Noise Lab."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .audio.engine import create_audio_engine
from .audio.recorder import create_audio_recorder
from .controls import create_controls_manager
from .data.loader import create_data_loader
from .mapper import create_audio_mapper
from .playback import create_playback_manager
from .presets.default import get_default_preset


class SonificationController:
    """Coordinate loading, mapping, playback, and recording."""
    # pylint: disable=too-many-instance-attributes,too-many-public-methods

    def __init__(
        self,
        project_root: Optional[Path] = None,
        sample_rate: int = 44100,
        buffer_size: int = 1024,
    ):
        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parent
        )
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size

        default_settings = get_default_preset()
        self.controls = create_controls_manager()
        self.controls.apply_settings(default_settings)
        self.data_loader = create_data_loader()
        self.mapper = create_audio_mapper()
        self.audio_engine = create_audio_engine(sample_rate=self.sample_rate)
        self.playback = create_playback_manager(
            sample_rate=self.sample_rate,
            buffer_size=self.buffer_size,
        )
        self.recorder = create_audio_recorder()
        self.playback.set_data_callback(self._handle_played_chunk)
        self.playback.set_completion_callback(self._handle_playback_complete)

        default_pair_settings = {
            "volume": float(default_settings.get("volume", 0.8)),
            "pitch_sensitivity": float(default_settings.get("pitch_sensitivity", 1.0)),
            "noise_sensitivity": float(default_settings.get("noise_sensitivity", 1.0)),
        }
        self.pair_settings = {
            "A": default_pair_settings.copy(),
            "B": default_pair_settings.copy(),
        }

        self.current_file: Optional[Path] = None
        self.raw_dataframe: Optional[pd.DataFrame] = None
        self.processed_data: Optional[Dict] = None
        self.last_audio_buffer = np.array([], dtype=np.float32)
        self.last_recording_path: Optional[str] = None
        self.playback_mode = "Single"
        self.render_mode = "Step"
        self.loop_enabled = True
        self.right_channel_enabled = True
        self.api_key = ""
        self.selected_pairs = {"A": "All", "B": "All"}
        self._playback_events = []
        self._event_duration_seconds = 0.0
        self.current_event_index = 0
        self._is_shutdown = False
        self.current_playback_snapshot = self._empty_playback_snapshot()

        self.playback.set_loop(self.loop_enabled)

    def _empty_playback_snapshot(self) -> Dict[str, str]:
        """Return an empty runtime-status payload."""
        return {
            "timestamp": "-",
            "spread": "-",
            "trade_eligible": "-",
            "trust": "-",
            "playback_time": "0.00s",
        }

    def _handle_played_chunk(self, chunk_data: np.ndarray):
        """Append played chunks to the active recording buffer and advance status."""
        self.recorder.append_frames(chunk_data)

        playback_time = self.playback.get_current_timestamp()
        if self._playback_events and self._event_duration_seconds > 0:
            event_index = min(
                int(playback_time / self._event_duration_seconds),
                len(self._playback_events) - 1,
            )
            self.current_event_index = event_index
            self.current_playback_snapshot = self._playback_events[event_index].copy()

        self.current_playback_snapshot["playback_time"] = f"{playback_time:.2f}s"

    def _handle_playback_complete(self):
        """Finalize recording after playback stops naturally."""
        if self.recorder.is_recording():
            self.last_recording_path = self.recorder.stop_recording()

        self.current_playback_snapshot["playback_time"] = (
            f"{self.playback.get_current_timestamp():.2f}s"
        )

    def get_settings(self) -> Dict:
        """Return the current global control settings."""
        return self.controls.get_settings()

    def get_pair_settings(self, slot: str) -> Dict:
        """Return the current settings for one stereo slot."""
        return self.pair_settings[slot].copy()

    def get_runtime_status(self) -> Dict[str, str]:
        """Return the latest playback status for the GUI."""
        snapshot = self.current_playback_snapshot.copy()
        snapshot["playback_time"] = f"{self.playback.get_current_timestamp():.2f}s"
        snapshot["event_index"] = self.current_event_index
        return snapshot

    def _to_numeric_array(self, values, default_value: float = 0.0) -> np.ndarray:
        """Convert values to a finite float array."""
        numeric = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(
            dtype=float
        )
        return np.nan_to_num(
            numeric,
            nan=default_value,
            posinf=default_value,
            neginf=default_value,
        )

    def _get_chart_series(self, raw_dataframe: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Return OHLC-style chart arrays for the processed dataset."""
        source_format = (
            self.processed_data.get("source_format", "features")
            if self.processed_data is not None
            else "features"
        )

        if source_format == "tick" and "mid_price" in raw_dataframe.columns:
            close_values = self._to_numeric_array(raw_dataframe["mid_price"])
            return {
                "open": self._to_numeric_array(
                    raw_dataframe.get("mid_open", raw_dataframe["mid_price"])
                ),
                "high": self._to_numeric_array(
                    raw_dataframe.get("mid_max", raw_dataframe["mid_price"])
                ),
                "low": self._to_numeric_array(
                    raw_dataframe.get("mid_min", raw_dataframe["mid_price"])
                ),
                "close": close_values,
                "chart_type": "candles",
            }

        has_ohlc = all(
            column in raw_dataframe.columns
            for column in ("open", "high", "low", "close")
        )
        if has_ohlc:
            return {
                "open": self._to_numeric_array(raw_dataframe["open"]),
                "high": self._to_numeric_array(raw_dataframe["high"]),
                "low": self._to_numeric_array(raw_dataframe["low"]),
                "close": self._to_numeric_array(raw_dataframe["close"]),
                "chart_type": "candles",
            }

        quality_values = (
            self.processed_data["quality"]
            if self.processed_data is not None
            else np.array([], dtype=float)
        )
        quality_values = np.asarray(quality_values, dtype=float)
        return {
            "open": quality_values,
            "high": quality_values,
            "low": quality_values,
            "close": quality_values,
            "chart_type": "bars",
        }

    def get_chart_data(self) -> Dict:
        """Return chart-ready data synchronized with the current playback index."""
        if self.processed_data is None:
            return {
                "points": [],
                "current_index": 0,
                "source_format": "none",
                "chart_type": "bars",
            }

        raw_dataframe = self.processed_data["raw_df"]
        chart_series = self._get_chart_series(raw_dataframe)
        close_values = np.asarray(chart_series["close"], dtype=float)
        row_count = len(close_values)
        if row_count == 0:
            return {
                "points": [],
                "current_index": 0,
                "source_format": self.processed_data.get("source_format", "features"),
                "chart_type": chart_series["chart_type"],
            }

        trust = np.asarray(self.processed_data["trust"], dtype=float)
        spread = np.asarray(self.processed_data["spread"], dtype=float)
        volatility = np.asarray(self.processed_data["volatility"], dtype=float)
        trade_eligible = np.asarray(self.processed_data["trade_eligible"], dtype=bool)
        intensity = np.clip((trust * 0.45) + (volatility * 0.35) + (spread * 0.20), 0, 1)
        intensity = np.where(trade_eligible, intensity, 0.0)

        timestamps = (
            raw_dataframe["timestamp"].tolist()
            if "timestamp" in raw_dataframe.columns
            else [None] * row_count
        )
        points = []
        for index in range(row_count):
            points.append(
                {
                    "timestamp": self._format_timestamp(timestamps[index]),
                    "open": float(chart_series["open"][index]),
                    "high": float(chart_series["high"][index]),
                    "low": float(chart_series["low"][index]),
                    "close": float(chart_series["close"][index]),
                    "spread": float(spread[index]),
                    "volatility": float(volatility[index]),
                    "trust": float(trust[index]),
                    "intensity": float(intensity[index]),
                    "trade_eligible": bool(trade_eligible[index]),
                }
            )

        return {
            "points": points,
            "current_index": min(self.current_event_index, row_count - 1),
            "source_format": self.processed_data.get("source_format", "features"),
            "chart_type": chart_series["chart_type"],
        }

    def set_pair_volume_percent(self, slot: str, value: float):
        """Map a 0-100 UI slider to a slot-specific volume multiplier."""
        self.pair_settings[slot]["volume"] = float(np.clip(value / 100.0, 0.0, 1.0))

    def set_pair_pitch_slider_value(self, slot: str, value: float):
        """Map a 1-10 UI slider to slot-specific pitch sensitivity."""
        sensitivity = 0.5 + ((float(value) - 1.0) * (2.5 / 9.0))
        self.pair_settings[slot]["pitch_sensitivity"] = sensitivity

    def set_pair_noise_percent(self, slot: str, value: float):
        """Map a 0-100 UI slider to slot-specific noise sensitivity."""
        sensitivity = float(value) / 100.0 * 3.0
        self.pair_settings[slot]["noise_sensitivity"] = sensitivity

    def set_base_pitch(self, value: float):
        """Set the shared base pitch."""
        self.controls.set_base_pitch(int(value))

    def set_smoothness_percent(self, value: float):
        """Map a 0-100 UI slider to smoothing strength."""
        self.controls.set_smoothness(float(value) / 100.0)

    def set_gate_threshold_percent(self, value: float):
        """Map a 0-100 UI slider to gate threshold."""
        self.controls.set_gate_threshold(float(value) / 100.0)

    def set_trust_volume_enabled(self, enabled: bool):
        """Enable or disable trust-based volume scaling."""
        self.controls.set_trust_volume_enabled(enabled)

    def set_spread_muted(self, muted: bool):
        """Enable or disable spread-based coloration."""
        self.controls.set_spread_muted(muted)

    def set_regime_muted(self, muted: bool):
        """Enable or disable regime-based coloration."""
        self.controls.set_regime_muted(muted)

    def set_playback_mode(self, mode: str):
        """Set the current audio mode."""
        self.playback_mode = mode

    def set_render_mode(self, mode: str):
        """Set the current playback rendering mode."""
        self.render_mode = mode

    def set_loop_enabled(self, enabled: bool):
        """Enable or disable loop playback."""
        self.loop_enabled = enabled
        self.playback.set_loop(enabled)

    def set_right_channel_enabled(self, enabled: bool):
        """Enable or disable the Pair B stereo channel."""
        self.right_channel_enabled = enabled

    def set_playback_speed(self, label: str):
        """Set the playback speed from a UI label such as '2x'."""
        normalized = label.lower().replace("x", "").strip()
        self.playback.set_playback_rate(float(normalized))

    def set_api_key(self, value: str):
        """Store an API key for future live-data integrations."""
        self.api_key = value.strip()

    def set_pair_selection(self, slot: str, pair_name: str):
        """Store the selected pair value for a UI slot."""
        self.selected_pairs[slot] = pair_name

    def _get_pair_column(self, slot: str, dataframe: pd.DataFrame) -> Optional[str]:
        """Return the most relevant pair column for a slot."""
        if slot == "A" and "pair_a" in dataframe.columns:
            return "pair_a"
        if slot == "B" and "pair_b" in dataframe.columns:
            return "pair_b"
        if "pair" in dataframe.columns:
            return "pair"
        return None

    def get_pair_options(self) -> Dict[str, list[str]]:
        """Return pair options derived from the loaded dataset."""
        options = {"A": ["All"], "B": ["All"]}
        if self.raw_dataframe is None:
            return options

        for slot in ("A", "B"):
            pair_column = self._get_pair_column(slot, self.raw_dataframe)
            if pair_column is None:
                continue

            pair_values = sorted(
                self.raw_dataframe[pair_column].dropna().astype(str).unique()
            )
            options[slot] = ["All", *pair_values]

        return options

    def load_csv(self, filepath: str) -> Dict:
        """Load a CSV file and return metadata for the UI."""
        dataframe = self.data_loader.load_csv(filepath)

        self.current_file = Path(filepath).resolve()
        self.raw_dataframe = dataframe
        self.processed_data = self.data_loader.process_backtest_data(dataframe)
        self.last_audio_buffer = np.array([], dtype=np.float32)
        self.selected_pairs = {"A": "All", "B": "All"}
        self.current_event_index = 0
        self.current_playback_snapshot = self._empty_playback_snapshot()
        processed_rows = int(
            self.processed_data.get("processed_rows", len(dataframe))
        )

        return {
            "file_path": self.current_file.name,
            "rows": len(dataframe),
            "processed_rows": processed_rows,
            "source_format": self.processed_data.get("source_format", "features"),
            "tick_bucket_ms": self.processed_data.get("tick_bucket_ms"),
            "columns": list(dataframe.columns),
            "pair_options": self.get_pair_options(),
        }

    def _get_filtered_dataframe_for_slot(self, slot: str) -> pd.DataFrame:
        """Filter the loaded dataframe by the selected pair value for one slot."""
        if self.raw_dataframe is None:
            raise RuntimeError("Load a CSV file before starting playback.")

        dataframe = self.raw_dataframe.copy()
        selected_pair = self.selected_pairs[slot]
        pair_column = self._get_pair_column(slot, dataframe)

        if pair_column is not None and selected_pair != "All":
            dataframe = dataframe[dataframe[pair_column].astype(str) == selected_pair]

        if dataframe.empty:
            raise RuntimeError(f"Pair {slot} selection did not match any rows.")

        return dataframe

    def _get_processed_data_for_slot(self, slot: str) -> Dict:
        """Return processed data for a slot, reusing full-data processing."""
        if self.raw_dataframe is None:
            raise RuntimeError("Load a CSV file before starting playback.")

        selected_pair = self.selected_pairs[slot]
        pair_column = self._get_pair_column(slot, self.raw_dataframe)
        if selected_pair == "All" and self.processed_data is not None:
            return self.processed_data

        if pair_column is None and self.processed_data is not None:
            return self.processed_data

        filtered_dataframe = self._get_filtered_dataframe_for_slot(slot)
        return self.data_loader.process_backtest_data(filtered_dataframe)

    def _build_market_row(self, processed: Dict, index: int) -> Dict:
        """Build a renderable market-data row from processed arrays."""
        raw_dataframe = processed["raw_df"]
        timestamp = None
        if "timestamp" in raw_dataframe.columns:
            timestamp = raw_dataframe["timestamp"].iloc[index]

        return {
            "timestamp": timestamp,
            "quality": float(processed["quality"][index]),
            "volatility": float(processed["volatility"][index]),
            "trust": float(processed["trust"][index]),
            "spread": float(processed["spread"][index]),
            "trade_eligible": bool(processed["trade_eligible"][index]),
            "regime": str(processed["regime"][index]),
        }

    def _interpolate_timestamp(self, start_value, end_value, alpha: float):
        """Interpolate timestamps for continuous playback mode."""
        if pd.isna(start_value):
            return end_value
        if pd.isna(end_value):
            return start_value
        if isinstance(start_value, pd.Timestamp) and isinstance(end_value, pd.Timestamp):
            delta = end_value - start_value
            return start_value + (delta * alpha)
        return start_value if alpha < 0.5 else end_value

    def _interpolate_market_rows(
        self, start_row: Dict, end_row: Dict, alpha: float
    ) -> Dict:
        """Interpolate between two market rows for continuous playback."""
        return {
            "timestamp": self._interpolate_timestamp(
                start_row["timestamp"],
                end_row["timestamp"],
                alpha,
            ),
            "quality": start_row["quality"] + (end_row["quality"] - start_row["quality"]) * alpha,
            "volatility": start_row["volatility"]
            + (end_row["volatility"] - start_row["volatility"]) * alpha,
            "trust": start_row["trust"] + (end_row["trust"] - start_row["trust"]) * alpha,
            "spread": start_row["spread"] + (end_row["spread"] - start_row["spread"]) * alpha,
            "trade_eligible": (
                start_row["trade_eligible"] if alpha < 0.5 else end_row["trade_eligible"]
            ),
            "regime": start_row["regime"] if alpha < 0.5 else end_row["regime"],
        }

    def _expand_rows_for_render_mode(self, rows: list[Dict]) -> list[Dict]:
        """Expand rows according to the selected playback rendering mode."""
        if self.render_mode.lower() != "continuous" or len(rows) < 2:
            return rows

        expanded_rows = []
        interpolation_steps = 4
        for index, row in enumerate(rows[:-1]):
            next_row = rows[index + 1]
            for alpha in np.linspace(0.0, 1.0, interpolation_steps, endpoint=False):
                expanded_rows.append(self._interpolate_market_rows(row, next_row, alpha))
        expanded_rows.append(rows[-1])
        return expanded_rows

    def _build_slot_settings(self, slot: str) -> Dict:
        """Merge global settings with slot-specific sensitivity settings."""
        settings = self.controls.get_settings()
        settings.update(self.pair_settings[slot])
        return settings

    def _format_timestamp(self, timestamp_value) -> str:
        """Format a timestamp value for the status box."""
        if timestamp_value is None or pd.isna(timestamp_value):
            return "-"
        if isinstance(timestamp_value, pd.Timestamp):
            return timestamp_value.strftime("%Y-%m-%d %H:%M:%S")
        return str(timestamp_value)

    def _build_slot_status(self, slot: str, row: Optional[Dict]) -> Dict[str, str]:
        """Build a status payload for one slot."""
        if row is None:
            return {
                "timestamp": f"{slot}: -",
                "spread": f"{slot}: -",
                "trade_eligible": f"{slot}: -",
                "trust": f"{slot}: -",
            }

        return {
            "timestamp": f"{slot}: {self._format_timestamp(row['timestamp'])}",
            "spread": f"{slot}: {row['spread']:.3f}",
            "trade_eligible": f"{slot}: {'Yes' if row['trade_eligible'] else 'No'}",
            "trust": f"{slot}: {row['trust']:.2f}",
        }

    def _combine_status_rows(
        self,
        left_row: Optional[Dict],
        right_row: Optional[Dict],
    ) -> Dict[str, str]:
        """Combine left/right slot statuses for the runtime status box."""
        if right_row is None:
            left_status = self._build_slot_status("A", left_row)
            return {
                "timestamp": left_status["timestamp"][3:],
                "spread": left_status["spread"][3:],
                "trade_eligible": left_status["trade_eligible"][3:],
                "trust": left_status["trust"][3:],
                "playback_time": f"{self.playback.get_current_timestamp():.2f}s",
            }

        left_status = self._build_slot_status("A", left_row)
        right_status = self._build_slot_status("B", right_row)
        return {
            "timestamp": f"{left_status['timestamp']} | {right_status['timestamp']}",
            "spread": f"{left_status['spread']} | {right_status['spread']}",
            "trade_eligible": (
                f"{left_status['trade_eligible']} | {right_status['trade_eligible']}"
            ),
            "trust": f"{left_status['trust']} | {right_status['trust']}",
            "playback_time": f"{self.playback.get_current_timestamp():.2f}s",
        }

    def _build_slot_events(
        self,
        slot: str,
        duration_ms: int,
    ) -> list[tuple[np.ndarray, Dict]]:
        """Render all chunk events for one slot."""
        processed = self._get_processed_data_for_slot(slot)
        slot_settings = self._build_slot_settings(slot)
        slot_rows = [
            self._build_market_row(processed, index)
            for index in range(len(processed["quality"]))
        ]
        slot_rows = self._expand_rows_for_render_mode(slot_rows)

        events = []
        for row in slot_rows:
            audio_chunk = self.mapper.map_data_to_audio(
                row,
                slot_settings,
                duration_ms=duration_ms,
                sample_rate=self.sample_rate,
            )
            events.append((audio_chunk, row))
        return events

    def _apply_safety_processing(self, audio_buffer: np.ndarray) -> np.ndarray:
        """Apply smoothing, filtering, and limiting to the generated audio buffer."""
        settings = self.controls.get_settings()
        smoothness = settings.get("smoothness", 0.1)

        if audio_buffer.ndim == 1:
            audio_buffer = self.data_loader.apply_smoothing(audio_buffer, smoothness)
        else:
            smoothed_channels = [
                self.data_loader.apply_smoothing(audio_buffer[:, channel_index], smoothness)
                for channel_index in range(audio_buffer.shape[1])
            ]
            audio_buffer = np.column_stack(smoothed_channels)

        filtered_audio = self.audio_engine.apply_filter(
            audio_buffer,
            lowcut=int(settings.get("min_hz", 200)),
            highcut=int(settings.get("max_hz", 1200)),
        )
        limited_audio = self.audio_engine.apply_limiter(filtered_audio, threshold=0.9)
        return np.clip(limited_audio, -1.0, 1.0).astype(np.float32)

    def build_audio_buffer(self) -> np.ndarray:
        """Build an audio buffer from the currently loaded market data."""
        # pylint: disable=too-many-locals
        chunk_duration_ms = 140 if self.render_mode.lower() == "step" else 55
        self._event_duration_seconds = chunk_duration_ms / 1000.0
        left_events = self._build_slot_events("A", chunk_duration_ms)

        if not left_events:
            raise RuntimeError("No audio could be generated from the loaded data.")

        if self.playback_mode.lower() != "stereo":
            self._playback_events = [
                self._combine_status_rows(row, None) for _, row in left_events
            ]
            audio_buffer = np.concatenate([chunk for chunk, _ in left_events], axis=0)
            self.last_audio_buffer = self._apply_safety_processing(audio_buffer)
            return self.last_audio_buffer

        if self.right_channel_enabled:
            right_events = self._build_slot_events("B", chunk_duration_ms)
        else:
            right_events = []

        max_event_count = max(len(left_events), len(right_events))
        if max_event_count == 0:
            raise RuntimeError("No stereo audio could be generated from the loaded data.")

        stereo_chunks = []
        status_events = []
        sample_count = max(1, int(self.sample_rate * chunk_duration_ms / 1000))

        for index in range(max_event_count):
            left_chunk, left_row = (
                left_events[index]
                if index < len(left_events)
                else (np.zeros(sample_count, dtype=np.float32), None)
            )
            right_chunk, right_row = (
                right_events[index]
                if index < len(right_events)
                else (np.zeros(sample_count, dtype=np.float32), None)
            )

            chunk_length = max(len(left_chunk), len(right_chunk))
            padded_left = np.pad(left_chunk, (0, max(0, chunk_length - len(left_chunk))))
            padded_right = np.pad(
                right_chunk,
                (0, max(0, chunk_length - len(right_chunk))),
            )
            stereo_chunks.append(np.column_stack([padded_left, padded_right]))
            status_events.append(self._combine_status_rows(left_row, right_row))

        audio_buffer = np.concatenate(stereo_chunks, axis=0)
        self._playback_events = status_events
        self.last_audio_buffer = self._apply_safety_processing(audio_buffer)
        return self.last_audio_buffer

    def play(self):
        """Start playback or resume a paused session."""
        if self.playback.is_paused():
            self.playback.resume()
            return

        audio_buffer = self.build_audio_buffer()
        duration_ms = len(audio_buffer) / self.sample_rate * 1000.0
        self.last_recording_path = None
        if self._playback_events:
            self.current_event_index = 0
            self.current_playback_snapshot = self._playback_events[0].copy()
            self.current_playback_snapshot["playback_time"] = "0.00s"
        else:
            self.current_playback_snapshot = self._empty_playback_snapshot()
        self.playback.start(audio_buffer, duration_ms)

    def refresh_active_playback(self) -> bool:
        """Re-render audio with current settings and keep the playback position."""
        if self.raw_dataframe is None or not self.playback.is_playing():
            return False
        if self.playback.is_paused():
            return False

        playback_time = self.playback.get_current_timestamp()
        previous_events = self._playback_events
        previous_event_duration_seconds = self._event_duration_seconds
        previous_audio_buffer = self.last_audio_buffer
        previous_event_index = self.current_event_index
        previous_snapshot = self.current_playback_snapshot.copy()

        audio_buffer = self.build_audio_buffer()
        duration_ms = len(audio_buffer) / self.sample_rate * 1000.0

        if self._playback_events and self._event_duration_seconds > 0:
            self.current_event_index = min(
                int(playback_time / self._event_duration_seconds),
                len(self._playback_events) - 1,
            )
            self.current_playback_snapshot = self._playback_events[
                self.current_event_index
            ].copy()
            self.current_playback_snapshot["playback_time"] = f"{playback_time:.2f}s"

        did_replace = self.playback.replace_data(
            audio_buffer,
            duration_ms,
            start_seconds=playback_time,
        )
        if did_replace:
            return True

        self._playback_events = previous_events
        self._event_duration_seconds = previous_event_duration_seconds
        self.last_audio_buffer = previous_audio_buffer
        self.current_event_index = previous_event_index
        self.current_playback_snapshot = previous_snapshot
        return False

    def pause(self):
        """Pause the active playback session."""
        self.playback.pause()

    def stop(self) -> Optional[str]:
        """Stop playback and finalize any active recording."""
        self.playback.stop()
        self.current_event_index = 0
        if self.recorder.is_recording():
            self.last_recording_path = self.recorder.stop_recording()
        self.current_playback_snapshot["playback_time"] = (
            f"{self.playback.get_current_timestamp():.2f}s"
        )
        return self.last_recording_path

    def start_recording(self):
        """Start recording the generated playback buffers."""
        self.last_recording_path = None
        self.recorder.start_recording(sample_rate=self.sample_rate)

    def stop_recording(self) -> Optional[str]:
        """Stop recording and return the saved file path."""
        if not self.recorder.is_recording():
            return None

        self.last_recording_path = self.recorder.stop_recording()
        return self.last_recording_path

    def is_recording(self) -> bool:
        """Return whether recording is active."""
        return self.recorder.is_recording()

    def shutdown(self) -> Optional[str]:
        """Release runtime resources before the GUI or process exits."""
        if self._is_shutdown:
            return self.last_recording_path

        self._is_shutdown = True
        self.playback.stop(wait=False, abort=False)
        if self.recorder.is_recording():
            self.last_recording_path = self.recorder.stop_recording()
        recording_path = self.last_recording_path
        return recording_path
