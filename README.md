# FX Noise Lab

FX Noise Lab is an experimental sonification tool for backtest-style market data. It loads CSV data, maps signal features onto audio, and lets you play or record the generated result from a small desktop GUI.

## Current Capabilities

- Load CSV files from the GUI with an `Open CSV` button
- Map `quality`, `volatility`, `trust`, `spread`, `trade_eligible`, and `regime` into audio
- Load OHLCV candles or dense ask/bid tick CSVs
- View a synchronized market chart with playhead and audio-intensity overlay
- Filter rows by `pair`, `pair_a`, and `pair_b` when those columns exist
- Play generated audio in `Single` or `Stereo` mode
- Change playback speed from `0.25x` to `8x`
- Adjust master volume, pitch sensitivity, and noise sensitivity
- Record the generated playback buffer to WAV files in `recordings/`

## Installation

Requirements:
- Python 3.10+
- A working audio backend for `sounddevice`

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r x_noise_lab/requirements.txt
```

## Usage

Start the app:

```bash
source .venv/bin/activate
python -m x_noise_lab
```

Basic flow:
1. Click `Open CSV` and choose a dataset.
2. Optionally filter by pair using the left and right selectors.
3. Adjust playback mode, speed, and sensitivities.
4. Press `Play`.
5. Press `Record` before or during playback to save the generated audio to `recordings/`.

## Supported CSV Columns

Recognized fields:

- `timestamp`
- OHLCV: `open`, `high`, `low`, `close`, `volume`
- Tick: `askPrice`, `bidPrice`, `askVolume`, `bidVolume`
- `quality` or `quality_score`
- `volatility`
- `trust` or `trust_value`
- `spread`
- `trade_eligible` or `eligible`
- `regime`
- `pair`
- `pair_a`
- `pair_b`

Boolean fields such as `trade_eligible` accept values like `true`, `false`, `1`, and `0`.

Tick CSVs are compressed into time buckets before audio rendering so large files do not
create one audio event per tick.

## Audio Mapping

| Market Feature | Audio Effect |
| --- | --- |
| Quality | Pitch |
| Volatility | Vibrato / motion |
| Trust | Amplitude |
| Spread | Distortion amount |
| Trade eligible | Gate / mute |
| Regime | Voicing / harmonic color |

## Example CSV

```csv
timestamp,quality_score,volatility,trust_value,spread,eligible,regime
2024-01-01 00:00:00,0.75,0.5,0.8,0.20,1,bull
2024-01-01 00:00:01,0.80,0.6,0.85,0.35,1,bull
2024-01-01 00:00:02,0.65,0.8,0.7,0.60,0,neutral
2024-01-01 00:00:03,0.90,0.4,0.9,0.15,1,bear
```

## Notes

- Importing `x_noise_lab` no longer starts GUI-related work; GUI modules are loaded lazily when the app starts.
- In headless or sandboxed environments, `customtkinter` can warn about font installation. That does not affect the package structure checks.
