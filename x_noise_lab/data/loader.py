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

    def process_backtest_data(self, dataframe: pd.DataFrame) -> Dict:
        """Process backtest data into sonification-ready arrays."""
        raw_dataframe = dataframe.copy()

        quality_series = self._coerce_numeric_series(
            self._get_series(raw_dataframe, "quality", "quality_score", default_value=0.5),
            0.5,
        )
        volatility_series = self._coerce_numeric_series(
            self._get_series(raw_dataframe, "volatility", default_value=0.5),
            0.5,
        )
        trust_series = self._coerce_numeric_series(
            self._get_series(raw_dataframe, "trust", "trust_value", default_value=0.5),
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
            raw_dataframe["timestamp"] = pd.to_datetime(
                raw_dataframe["timestamp"],
                errors="coerce",
            )

        processed_data = {
            "quality": quality_series.to_numpy(dtype=np.float32),
            "volatility": volatility_series.to_numpy(dtype=np.float32),
            "trust": trust_series.to_numpy(dtype=np.float32),
            "spread": spread_series.to_numpy(dtype=np.float32),
            "trade_eligible": trade_eligible_series.to_numpy(dtype=bool),
            "regime": regime_series.to_numpy(dtype=str),
            "raw_df": raw_dataframe,
        }
        self._processed_data = processed_data
        return processed_data

    def load_preset(self, preset_name: str) -> Dict:
        """Load preset configuration by delegating to the presets module."""
        return load_preset_config(preset_name)

    def apply_smoothing(self, data: np.ndarray, smoothness: float = 0.1) -> np.ndarray:
        """Apply a simple moving-average smoothing filter."""
        if smoothness <= 0.01:
            return data

        window_size = max(int(len(data) * smoothness), 3)
        if len(data) < window_size:
            return data

        return pd.Series(data).rolling(window=window_size, min_periods=1).mean().values

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
