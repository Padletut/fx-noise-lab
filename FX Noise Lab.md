# FX Noise Lab 🎧📈

## Overview
FX Noise Lab er et eksperimentelt verktøy for å "høre" finansielle markeder ved å konvertere backtest-data til lyd (sonification).

Målet er ikke trading edge, men:
- Visualisere signal vs støy (SNR)
- Lage en morsom og intuitiv demo
- Utforske alternative representasjoner av markedsdata

---

## Features (MVP v0.1)

### Playback
- Load backtest CSV
- Play / Pause / Stop
- Playback speed:
  - 0.25x
  - 0.5x
  - 1x
  - 2x
  - 4x
  - 8x
- Loop playback

### Audio Modes
- Single pair (mono)
- Dual pair (stereo: left/right)

### Controls
- Volume
- Base Pitch
- Noise Sensitivity
- Smoothness (smoothing filter)
- Gate Threshold (mute low-quality signal)
- Trust → Volume toggle
- Spread mute toggle
- Regime mute toggle

### Recording
- Record output to WAV
- Record exactly what user hears
- Start/Stop recording button

### Safety
- Safe audio limiter (protect ears/headphones)
- Frequency clamp (e.g. 200–1200 Hz)

---

## GUI Layout

### Left Panel (Pair A)
- Pair selector
- Volume
- Pitch sensitivity
- Noise sensitivity

### Right Panel (Pair B)
- Same as left
- Stereo toggle

### Center / Bottom
- Play / Pause / Stop
- Playback speed selector
- Mode selector:
  - Single
  - Stereo
- Record button
- API key field (future use)
- Status box:
  - Current timestamp
  - Current spread
  - Trade eligible
  - Trust value

---

## Data Flow

---

## Sonification Mapping

| Market Feature | Audio Mapping |
|---------------|--------------|
| Quality Score | Pitch (Hz) |
| Volatility    | Vibrato / jitter |
| Trade Eligible| Mute / unmute |
| Trust         | Volume |
| Spread        | Distortion / mute |
| Trade events  | Beep / chime |

---

## Audio Design Rules

- Keep frequencies within safe range
- Avoid spikes (limiter required)
- One parameter per sound dimension
- Avoid over-complex mapping

---

## Playback Modes

### 1. Step Mode
- One datapoint per tick
- Debug-friendly

### 2. Continuous Mode
- Interpolated between datapoints
- Smoother audio

---

## Recording

- Output format: WAV
- Captures stereo output if enabled
- Includes all filters and mappings
- Used for demo/video export

---

## Tech Stack

- Python 3.14+
- CustomTkinter (GUI)
- NumPy (math)
- sounddevice (audio)
- scipy (optional processing)
- matplotlib (optional visualization)

---

## Folder Structure
x_noise_lab/
app.py
gui/
main_window.py
controls.py
audio/
engine.py
recorder.py
mapper.py
data/
loader.py
playback.py
presets/
default.json


---

## Future Features (v0.2+)

- Waveform visualization
- Trade event sounds
- Presets (Calm / Volatile / Scalper)
- Video export helper
- Multi-pair correlation mode
- Live streaming (Finnhub API)

---

## Disclaimer

This tool is for:
- Visualization
- Experimentation
- Entertainment

It is NOT:
- A trading system
- A source of financial advice
- A predictive model

---

## Demo Idea 
Content:
- Show chart + audio
- Demonstrate noise vs clean signal
- Add humor

---

## Tagline

"Dude... I can hear market correlate." 🎧
