#!/usr/bin/env python3
"""FX Noise Lab - Data Loader."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from x_noise_lab.presets.default import load_preset as load_preset_config


class DataLoader:
    """Load and process market data from CSV files."""

    TICK_TARGET_ROWS = 4000
    MIN_TICK_BUCKET_MS = 1000

    def __init__(self):
        """Initialize data loader."""
        self._csv_cache: Dict[str, pd.DataFrame] = {}
        self._processed_data: Optional[Dict] = None

    def load_csv(self, filepath: str) -> pd.DataFrame:
        """Load CSV file into a DataFrame."""
        path = Path(filepath).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        cache_key = str(path)
        if cache_key in self._csv_cache:
            return self._csv_cache[cache_key].copy()

        dataframe = pd.read_csv(path, dtype={"timestamp": str})
        self._csv_cache[cache_key] = dataframe
        return dataframe.copy()

    def load_csv_with_metadata(self, filepath: str) -> Dict:
        """Load CSV with basic file metadata."""
        dataframe = self.load_csv(filepath)
        metadata = {
            "file_path": str(Path(filepath).name),
            "rows": len(dataframe),
            "columns": list(dataframe.columns),
        }
        return {"data": dataframe, "metadata": metadata}

    def _get_series(
        self,
        dataframe: pd.DataFrame,
        *candidate_names: str,
        default_value,
    ) -> pd.Series:
        """Return the first available column as a Series, or a default-filled Series."""
        for column_name in candidate_names:
            if column_name in dataframe.columns:
                return dataframe[column_name]

        return pd.Series(
            [default_value] * len(dataframe),
            index=dataframe.index,
        )

    def _coerce_numeric_series(
        self, series: pd.Series, default_value: float
    ) -> pd.Series:
        """Convert a column to numeric data with a fallback value."""
        numeric_series = pd.to_numeric(series, errors="coerce")
        return numeric_series.fillna(default_value)

    def _get_column_name(
        self, dataframe: pd.DataFrame, *candidate_names: str
    ) -> Optional[str]:
        """Return an existing column name, matching case-insensitively."""
        normalized_columns = {column.lower(): column for column in dataframe.columns}
        for candidate_name in candidate_names:
            column_name = normalized_columns.get(candidate_name.lower())
            if column_name is not None:
                return column_name
        return None

    def _normalize_numeric_series(
        self,
        series: pd.Series,
        default_value: float = 0.5,
    ) -> pd.Series:
        """Normalize numeric data to 0-1, falling back for flat series."""
        numeric_series = pd.to_numeric(series, errors="coerce").replace(
            [np.inf, -np.inf],
            np.nan,
        )
        min_val = numeric_series.min(skipna=True)
        max_val = numeric_series.max(skipna=True)
        if pd.notna(min_val) and pd.notna(max_val) and max_val - min_val > 0:
            return ((numeric_series - min_val) / (max_val - min_val)).fillna(
                default_value
            )

        return pd.Series(default_value, index=series.index, dtype=float)

    def _coerce_boolean_series(
        self, series: pd.Series, default_value: bool = True
    ) -> pd.Series:
        """Convert a column to booleans while handling common CSV string values."""
        if pd.api.types.is_bool_dtype(series):
            return series.fillna(default_value).astype(bool)

        normalized = series.astype(str).str.strip().str.lower()
        truthy = {"1", "true", "yes", "y", "t"}
        falsy = {"0", "false", "no", "n", "f", ""}

        boolean_series = pd.Series(default_value, index=series.index, dtype=bool)
        truthy_mask = normalized.isin(truthy)
        falsy_mask = normalized.isin(falsy)

        boolean_series.loc[truthy_mask] = True
        boolean_series.loc[falsy_mask] = False

        unresolved_mask = ~(truthy_mask | falsy_mask)
        if unresolved_mask.any():
            numeric_fallback = pd.to_numeric(series[unresolved_mask], errors="coerce")
            boolean_series.loc[unresolved_mask] = (
                numeric_fallback.fillna(float(default_value)) > 0.5
            )

        return boolean_series

    def _coerce_timestamp_series(self, series: pd.Series) -> pd.Series:
        """Convert CSV timestamps while supporting epoch-millisecond OHLCV files."""
        numeric_series = pd.to_numeric(series, errors="coerce")
        if numeric_series.notna().any():
            parsed_timestamps = pd.to_datetime(
                numeric_series,
                unit="ms",
                errors="coerce",
            )
            text_mask = numeric_series.isna()
            if text_mask.any():
                parsed_timestamps.loc[text_mask] = pd.to_datetime(
                    series.loc[text_mask],
                    errors="coerce",
                )
            return parsed_timestamps

        return pd.to_datetime(series, errors="coerce")

    def _has_tick_columns(self, dataframe: pd.DataFrame) -> bool:
        """Return whether a dataframe looks like ask/bid tick data."""
        has_ask = (
            self._get_column_name(dataframe, "askPrice", "ask_price", "ask")
            is not None
        )
        has_bid = (
            self._get_column_name(dataframe, "bidPrice", "bid_price", "bid")
            is not None
        )
        return has_ask and has_bid

    def _get_optional_numeric_series(
        self,
        dataframe: pd.DataFrame,
        *candidate_names: str,
        default_value: float,
    ) -> pd.Series:
        """Return a numeric optional column or a default-filled Series."""
        column_name = self._get_column_name(dataframe, *candidate_names)
        if column_name is None:
            return pd.Series(default_value, index=dataframe.index, dtype=float)
        return self._coerce_numeric_series(dataframe[column_name], default_value)

    def _build_tick_bucketed_dataframe(
        self, tick_dataframe: pd.DataFrame
    ) -> tuple[pd.DataFrame, int]:
        """Aggregate dense tick data into a bounded number of audio events."""
        if tick_dataframe.empty:
            raise RuntimeError("Tick CSV did not contain usable ask/bid rows.")

        first_timestamp = tick_dataframe["timestamp"].min()
        last_timestamp = tick_dataframe["timestamp"].max()
        duration_ms = max(
            int((last_timestamp - first_timestamp).total_seconds() * 1000),
            0,
        )

        if duration_ms > 0:
            bucket_ms = max(
                self.MIN_TICK_BUCKET_MS,
                int(np.ceil(duration_ms / self.TICK_TARGET_ROWS)),
            )
            bucket_key = tick_dataframe["timestamp"].dt.floor(f"{bucket_ms}ms")
        else:
            bucket_ms = self.MIN_TICK_BUCKET_MS
            bucket_size = max(
                1,
                int(np.ceil(len(tick_dataframe) / self.TICK_TARGET_ROWS)),
            )
            bucket_key = np.arange(len(tick_dataframe)) // bucket_size

        bucketed = (
            tick_dataframe.assign(_bucket=bucket_key)
            .groupby("_bucket", sort=True)
            .agg(
                timestamp=("timestamp", "last"),
                askPrice=("askPrice", "last"),
                bidPrice=("bidPrice", "last"),
                askVolume=("askVolume", "sum"),
                bidVolume=("bidVolume", "sum"),
                mid_open=("mid_price", "first"),
                mid_price=("mid_price", "last"),
                mid_min=("mid_price", "min"),
                mid_max=("mid_price", "max"),
                spread_value=("spread_value", "mean"),
                total_volume=("total_volume", "sum"),
                tick_count=("mid_price", "size"),
            )
            .reset_index(drop=True)
        )

        return bucketed, bucket_ms

    def _process_tick_data(self, dataframe: pd.DataFrame) -> Dict:
        """Process ask/bid tick data into sonification-ready arrays."""
        raw_dataframe = dataframe.copy()
        ask_column = self._get_column_name(
            raw_dataframe,
            "askPrice",
            "ask_price",
            "ask",
        )
        bid_column = self._get_column_name(
            raw_dataframe,
            "bidPrice",
            "bid_price",
            "bid",
        )
        if ask_column is None or bid_column is None:
            raise RuntimeError("Tick CSV must include askPrice and bidPrice columns.")

        timestamp_series = (
            self._coerce_timestamp_series(raw_dataframe["timestamp"])
            if "timestamp" in raw_dataframe.columns
            else pd.Series(pd.NaT, index=raw_dataframe.index)
        )
        ask_price = self._coerce_numeric_series(raw_dataframe[ask_column], np.nan)
        bid_price = self._coerce_numeric_series(raw_dataframe[bid_column], np.nan)
        ask_volume = self._get_optional_numeric_series(
            raw_dataframe,
            "askVolume",
            "ask_volume",
            default_value=0.0,
        )
        bid_volume = self._get_optional_numeric_series(
            raw_dataframe,
            "bidVolume",
            "bid_volume",
            default_value=0.0,
        )

        tick_dataframe = pd.DataFrame(
            {
                "timestamp": timestamp_series,
                "askPrice": ask_price,
                "bidPrice": bid_price,
                "askVolume": ask_volume,
                "bidVolume": bid_volume,
            }
        ).dropna(subset=["timestamp", "askPrice", "bidPrice"])

        tick_dataframe = tick_dataframe.sort_values("timestamp").reset_index(
            drop=True
        )
        tick_dataframe["mid_price"] = (
            tick_dataframe["askPrice"] + tick_dataframe["bidPrice"]
        ) / 2.0
        tick_dataframe["spread_value"] = (
            tick_dataframe["askPrice"] - tick_dataframe["bidPrice"]
        ).clip(lower=0.0)
        tick_dataframe["total_volume"] = (
            tick_dataframe["askVolume"] + tick_dataframe["bidVolume"]
        )

        bucketed_dataframe, bucket_ms = self._build_tick_bucketed_dataframe(
            tick_dataframe
        )
        mid_range = bucketed_dataframe["mid_max"] - bucketed_dataframe["mid_min"]
        mid_delta = bucketed_dataframe["mid_price"].diff().abs().fillna(0.0)
        volatility_source = mid_range + mid_delta
        trust_default = 0.8 if bucketed_dataframe["total_volume"].max() > 0 else 0.5
        spread_default = (
            0.2 if bucketed_dataframe["spread_value"].max() > 0 else 0.0
        )

        quality_series = self._normalize_numeric_series(
            bucketed_dataframe["mid_price"],
            default_value=0.5,
        )
        volatility_series = self._normalize_numeric_series(
            volatility_source,
            default_value=0.1,
        )
        trust_series = self._normalize_numeric_series(
            np.log1p(bucketed_dataframe["total_volume"]),
            default_value=trust_default,
        )
        spread_series = self._normalize_numeric_series(
            bucketed_dataframe["spread_value"],
            default_value=spread_default,
        )
        price_delta = bucketed_dataframe["mid_price"].diff().fillna(0.0)
        regime_array = np.where(
            price_delta > 0,
            "bull",
            np.where(price_delta < 0, "bear", "neutral"),
        )

        processed_frame = bucketed_dataframe[
            [
                "timestamp",
                "askPrice",
                "bidPrice",
                "askVolume",
                "bidVolume",
                "mid_open",
                "mid_price",
                "spread_value",
                "mid_min",
                "mid_max",
                "tick_count",
            ]
        ].copy()

        processed_data = {
            "quality": quality_series.to_numpy(dtype=np.float32),
            "volatility": volatility_series.to_numpy(dtype=np.float32),
            "trust": trust_series.to_numpy(dtype=np.float32),
            "spread": spread_series.to_numpy(dtype=np.float32),
            "trade_eligible": np.full(len(processed_frame), True, dtype=bool),
            "regime": regime_array.astype(str),
            "raw_df": processed_frame,
            "source_format": "tick",
            "source_rows": len(raw_dataframe),
            "processed_rows": len(processed_frame),
            "tick_bucket_ms": bucket_ms,
        }
        self._processed_data = processed_data
        return processed_data

    def process_backtest_data(self, dataframe: pd.DataFrame) -> Dict:
        """Process backtest data into sonification-ready arrays."""
        raw_dataframe = dataframe.copy()

        if self._has_tick_columns(raw_dataframe):
            return self._process_tick_data(raw_dataframe)

        # Detect OHLCV format (timestamp, open, high, low, close, volume).
        has_ohlcv = "open" in raw_dataframe.columns and "close" in raw_dataframe.columns

        if has_ohlcv:
            close_values = self._coerce_numeric_series(
                self._get_series(raw_dataframe, "close", "price", default_value=1.0),
                1.0,
            )
            volume_values = self._coerce_numeric_series(
                self._get_series(raw_dataframe, "volume", default_value=1.0),
                1.0,
            )
            open_values = self._coerce_numeric_series(
                self._get_series(raw_dataframe, "open", default_value=1.0),
                1.0,
            )
            high_values = self._coerce_numeric_series(
                self._get_series(raw_dataframe, "high", default_value=1.0),
                1.0,
            )

            quality_series = self._normalize_numeric_series(close_values)
            volatility_series = self._normalize_numeric_series(volume_values)
            trust_series = self._normalize_numeric_series(open_values)
            spread_series = self._normalize_numeric_series(high_values)
        else:
            quality_series = self._coerce_numeric_series(
                self._get_series(
                    raw_dataframe,
                    "quality",
                    "quality_score",
                    default_value=0.5,
                ),
                0.5,
            )
            volatility_series = self._coerce_numeric_series(
                self._get_series(raw_dataframe, "volatility", default_value=0.5),
                0.5,
            )
            trust_series = self._coerce_numeric_series(
                self._get_series(
                    raw_dataframe,
                    "trust",
                    "trust_value",
                    default_value=0.5,
                ),
                0.5,
            )
            spread_series = self._coerce_numeric_series(
                self._get_series(raw_dataframe, "spread", default_value=0.5),
                0.5,
            )

        trade_eligible_series = self._coerce_boolean_series(
            self._get_series(
                raw_dataframe,
                "trade_eligible",
                "eligible",
                default_value=True,
            ),
            default_value=True,
        )
        regime_series = self._get_series(
            raw_dataframe,
            "regime",
            default_value="neutral",
        ).astype(str)

        if "timestamp" in raw_dataframe.columns:
            raw_dataframe["timestamp"] = self._coerce_timestamp_series(
                raw_dataframe["timestamp"]
            )

        # Ensure all arrays have the same length as the dataframe
        n_rows = len(raw_dataframe)

        quality_array = np.full(n_rows, 0.5, dtype=np.float32)
        volatility_array = np.full(n_rows, 0.5, dtype=np.float32)
        trust_array = np.full(n_rows, 0.5, dtype=np.float32)
        spread_array = np.full(n_rows, 0.5, dtype=np.float32)
        trade_eligible_array = trade_eligible_series.to_numpy(dtype=bool)
        regime_array = regime_series.to_numpy(dtype=str)

        quality_array[:] = quality_series.values
        volatility_array[:] = volatility_series.values
        trust_array[:] = trust_series.values
        spread_array[:] = spread_series.values

        processed_data = {
            "quality": quality_array,
            "volatility": volatility_array,
            "trust": trust_array,
            "spread": spread_array,
            "trade_eligible": trade_eligible_array,
            "regime": regime_array,
            "raw_df": raw_dataframe,
            "source_format": "ohlcv" if has_ohlcv else "features",
            "source_rows": len(dataframe),
            "processed_rows": len(raw_dataframe),
        }
        self._processed_data = processed_data
        return processed_data

    def load_preset(self, preset_name: str) -> Dict:
        """Load preset configuration by delegating to the presets module."""
        return load_preset_config(preset_name)

    def apply_smoothing(self, data: np.ndarray, smoothness: float = 0.1) -> np.ndarray:
        """Apply a simple moving-average smoothing filter."""
        if smoothness <= 0.01 or len(data) == 0:
            return data

        clamped_smoothness = float(np.clip(smoothness, 0.0, 1.0))
        window_size = 3 + int(round(clamped_smoothness * 28))
        if window_size % 2 == 0:
            window_size += 1
        window_size = min(window_size, len(data))
        if len(data) < window_size:
            return data

        return (
            pd.Series(data)
            .rolling(window=window_size, min_periods=1, center=True)
            .mean()
            .to_numpy(dtype=np.asarray(data).dtype)
        )

    def get_available_files(self, directory: Optional[str] = None) -> List[str]:
        """Get a list of available CSV files."""
        search_dir = (
            Path(directory).expanduser().resolve()
            if directory is not None
            else Path(__file__).resolve().parent
        )
        return [str(file) for file in search_dir.glob("*.csv")]


def create_data_loader() -> DataLoader:
    """Factory function to create a data loader."""
    return DataLoader()
