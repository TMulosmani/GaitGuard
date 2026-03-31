# GaitGuard

Real-time wearable gait rehabilitation system with haptic feedback, powered by a personalized LSTM digital twin.

Built at [YHack 2026](https://yhack.org).

## What It Does

GaitGuard turns any rehab exercise into a guided session — even when the therapist isn't in the room.

1. **Calibrate** — A therapist performs the target movement 20+ times to establish the patient's healthy baseline
2. **Learn** — An LSTM neural network builds a personalized "digital twin" of the patient's gait
3. **Monitor** — During home training, the system compares each stride against the twin in real-time
4. **Correct** — Haptic vibration patterns deliver immediate tactile feedback when form deviates

No screen needed. Patients get intuitive corrective cues without interpretation.

## Architecture

```
ESP32 #1 (Thigh/Shin)          ESP32 #2 (Foot/Display)
  2× MPU-6050 IMUs                QMI8658C IMU + TFT screen
  Haptic motor                    Score display
       │ UDP 50Hz                      │ UDP 50Hz
       └──────────┐    ┌──────────────┘
                  ▼    ▼
            Raspberry Pi 5
          ┌─────────────────┐
          │  Gait Pipeline  │  4-phase state machine
          │  LSTM Twin Gen  │  Personalized model
          │  Web Dashboard  │  React + Three.js
          │  Haptic Control │  Closed-loop feedback
          └─────────────────┘
                  │
            Browser (any device on local WiFi)
```

## Components

| Directory | What | Stack |
|-----------|------|-------|
| `gaitguard/` | Core Python pipeline — signal processing, ML model, scoring, reports | Python, PyTorch, NumPy, SciPy |
| `pi/` | Raspberry Pi runtime — live pipeline, WiFi receiver, C binary, web server + dashboard | Python, C, HTML/JS |
| `esp/` | ESP32 firmware — IMU streaming, haptic motor control, foot display | Arduino C++ |
| `slides/` | Project presentation website | React, TypeScript, Vite, Three.js |

## Pipeline

The gait analysis runs as a 4-phase state machine:

- **Phase 0 — Calibration** (2s): Stand still, record baseline joint angles
- **Phase 1 — Segmentation**: Walk normally for 20+ strides. Heel-strike detection segments gait cycles, each normalized to 100 points
- **Phase 2 — Digital Twin**: Feed the first 20% of each stride (anchor) into a 2-layer LSTM to predict the remaining 80%. This becomes the patient's personalized reference
- **Phase 3 — Monitoring**: Compare each live stride against the digital twin. Compute a Gait Health Score (GHS, 0–100) and fire haptic patterns when deviation is detected

### Scoring

```
z_knee  = mean(|observed - twin|) / std_knee
z_ankle = mean(|observed - twin|) / std_ankle
GHS     = clamp(100 - (0.6 × z_knee + 0.4 × z_ankle) × 25, 0, 100)
```

### Haptic Feedback Patterns

| Pattern | Vibration | Meaning |
|---------|-----------|---------|
| Two short buzzes | 100ms on, 80ms off, 100ms on | Knee extension issue |
| One long buzz | 400ms continuous | Reduced foot clearance |
| Three short buzzes | 80ms on, 60ms off ×3 | General high deviation |

## Hardware

- **ESP32 #1**: ESP32 dev board + 2× MPU-6050 IMUs (I2C 0x68/0x69) + haptic motor (GPIO 19) + LiPo battery
- **ESP32 #2**: ESP32-S3 Waveshare Touch-LCD-1.69 (QMI8658C IMU + ST7789V2 display)
- **Raspberry Pi 5**: Central hub running pipeline + web dashboard
- All devices on same local WiFi, communicating via UDP (ports 5001–5004)

## Setup

### Pi / Development Machine

```bash
cd gaitguard
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### ESP Firmware

1. Open `esp/config.h` and set your WiFi credentials and Pi IP
2. Flash `esp/esp_imu_haptic/` to ESP32 #1
3. Flash `esp/esp_foot_display/` to ESP32 #2

### Run

```bash
# On the Pi (live with hardware)
cd pi && python run_live.py

# Web dashboard
cd pi/web && python server.py
# Open http://<pi-ip>:8080

# Offline with synthetic data
cd gaitguard && python run_pipeline.py
```

## ML Model

2-layer LSTM (hidden=64) trained on synthetic gait waveforms parameterized from biomechanics literature. Given the first 20% of a gait cycle (anchor), predicts the remaining 80%. Personalized per patient — no population averages.

Weights: `gaitguard/models/lstm_norm.npz`

## Web Dashboard

Real-time browser interface served from the Pi:

- **Live Monitor**: GHS trend chart, 3D leg skeleton visualization, per-stride scoring
- **Sensor Calibration**: Axis alignment for each IMU, real-time sensor readouts
- **Connection Status**: ESP connection indicators, mode selection, start/stop controls

## Team

Built by Arsh, Jimmy, Paul, and Sam.

## License

MIT
