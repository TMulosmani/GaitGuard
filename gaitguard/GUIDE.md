# GaitGuard — Complete Project Guide

GaitGuard is a wearable gait rehabilitation system. It uses 3 IMU sensors (thigh, shin, foot)
to monitor knee and ankle motion in real time, builds a personalised healthy "digital twin"
using an LSTM, computes a Gait Health Score (GHS) per stride, and triggers haptic feedback
when deviations are detected.

---

## 1. First-Time Setup

> Only run these once on a new machine. Skip if `.venv/` already exists.

### Step 1 — Create the Python environment

```bash
cd /path/to/gaitguard
/opt/homebrew/bin/python3.12 -m venv .venv
```

> Requires Python 3.12. The system Python (3.9) is incompatible with NumPy 2.x / SciPy.

### Step 2 — Install dependencies

```bash
.venv/bin/pip install -r requirements.txt
```

**What gets installed:**

| Package | Version | Purpose |
|---------|---------|---------|
| numpy | ≥1.24 | All numerical arrays, angle computation |
| scipy | ≥1.10 | Butterworth filter (`filtfilt`) |
| torch | ≥2.0 | LSTM twin model (PyTorch) |
| matplotlib | ≥3.7 | Overlay, GHS trend, heatmap charts |
| pandas | ≥2.0 | CSV logging and dataset loading |
| reportlab | ≥4.0 | PDF session report generation |
| tqdm | ≥4.65 | Training progress bar |

---

## 2. How the Pipeline Works

Every run goes through 4 sequential phases:

```
Phase 0  Stand still (2 s)
  ↓      Calibrates the complementary filter baseline for each joint
Phase 1  Walk normally (≥ 20 strides)
  ↓      Detects heel-strikes, segments strides, builds your personal gait profile
Phase 2  LSTM generates Digital Twin (automatic, ~1 s)
  ↓      Feeds your first 20 gait-cycle points into the LSTM → predicts the healthy 80
Phase 3  Real-time monitoring (remaining strides)
         Scores each stride against the twin → GHS + haptic feedback
```

**Gait Health Score (GHS)**
- `≥ 80` — Green — normal gait
- `50–79` — Yellow — moderate deviation
- `< 50` — Red — significant deviation, haptic fires

**Haptic patterns**
- `TWO_SHORT` — knee extension problem at heel strike
- `ONE_LONG` — reduced foot clearance during swing
- `THREE_SHORT` — general high deviation

---

## 3. All Runnable Commands

All commands must be run from inside the `gaitguard/` directory:

```bash
cd /path/to/gaitguard
```

---

### Command 1 — Synthetic Healthy Gait

```bash
.venv/bin/python run_pipeline.py --source synthetic --pathology healthy --n-strides 80
```

**What it does:** Generates 80 strides of normal gait (no pathology). Runs all 4 phases.

**Expected output:**
- GHS mostly green (≥ 80)
- No haptic triggers
- Use this to verify the system has no false positives

---

### Command 2 — Synthetic Mixed Pathology *(primary demo)*

```bash
.venv/bin/python run_pipeline.py --source synthetic --pathology mixed --n-strides 80
```

**What it does:** Injects two simultaneous pathologies into the synthetic gait:
- Reduced knee extension at heel strike → `TWO_SHORT` haptic
- Reduced foot clearance (push-off) → `ONE_LONG` haptic

**Expected output:**
- GHS in yellow/red range (40–65)
- Both haptic patterns fire
- This is the core clinical demo

---

### Command 3 — Reduced Extension Only

```bash
.venv/bin/python run_pipeline.py --source synthetic --pathology reduced_extension --n-strides 80
```

**What it does:** Injects only the knee extension deficit. Heel-strike knee flex is near 0°
instead of the healthy ~2°.

**Expected output:** `TWO_SHORT` haptic dominant, GHS yellow/red.

---

### Command 4 — Reduced Clearance Only

```bash
.venv/bin/python run_pipeline.py --source synthetic --pathology reduced_clearance --n-strides 80
```

**What it does:** Injects only reduced ankle push-off plantarflexion (−15° vs −20° healthy).

**Expected output:** `ONE_LONG` haptic dominant, GHS yellow.

---

### Command 5 — COMPWALK-ACL Dataset (synthetic fallback)

```bash
.venv/bin/python run_pipeline.py --source compwalk --condition acl
```

**What it does:** Uses the COMPWALK-ACL dataset adapter. If no real CSV files are on disk,
it automatically generates synthetic packets that mimic ACL-injured gait:
- Slower cadence (~1200 ms stride vs ~1090 ms)
- Reduced peak knee flexion (~45° vs ~60°)
- Increased compensatory push-off

**Expected output:** GHS red range (~40–44), `TWO_SHORT` dominant.

---

### Command 6 — COMPWALK-ACL with Real Data Files

```bash
.venv/bin/python run_pipeline.py \
  --source compwalk \
  --condition acl \
  --data-root /path/to/compwalk_acl \
  --subject S01
```

**What it does:** Same as Command 5 but reads real Xsens Awinda CSV exports from disk.
The adapter maps sensor columns (`Acc_X_RUL` → thigh, `Acc_X_RLL` → shin, `Acc_X_RF` → foot)
and converts m/s² to g.

**When to use:** After downloading the COMPWALK dataset from Zenodo.

---

### Command 7 — Skip Plots

Add `--no-plots` to any command above to skip chart generation:

```bash
.venv/bin/python run_pipeline.py --source synthetic --pathology mixed --no-plots
```

Useful for quick terminal-only runs or automated testing.

---

### Command 8 — Retrain LSTM Only (via pipeline runner)

```bash
.venv/bin/python run_pipeline.py --train-only
```

**What it does:** Skips the full pipeline. Generates 3000 synthetic healthy strides and
retrains the 2-layer LSTM (hidden=64, epochs=60). Saves model to `models/lstm_twin.pt`.

**When to use:** After changing the LSTM architecture or normative waveform templates.

---

### Command 9 — Retrain LSTM with Custom Settings

```bash
.venv/bin/python -m ml.train --n 5000 --epochs 100
```

**What it does:** Same as Command 8 but with tunable flags. Bypasses `run_pipeline.py`
entirely — useful for hyperparameter experiments.

**Flags:**
- `--n` — number of synthetic training strides (default: 3000)
- `--epochs` — training epochs (default: 60)
- `--batch` — batch size (default: 64)
- `--lr` — learning rate (default: 0.001)
- `--data path/to/file.npy` — train on a real `.npy` dataset instead of synthetic data

---

### Command 10 — Generate a Large Training Dataset

```bash
.venv/bin/python generate_training_data.py --n 10000
```

**What it does:** Pre-generates 10,000 healthy strides and saves them as
`training_data/healthy_strides.npy` (shape: `N × 100 × 2`). Each stride includes
per-subject amplitude scaling and timing jitter for realistic variation.

**When to use:** Before training on a large dataset so you don't regenerate it each run.

---

### Command 11 — Train on Pre-generated Dataset

```bash
.venv/bin/python -m ml.train --data training_data/healthy_strides.npy --epochs 100
```

**What it does:** Trains the LSTM on the pre-generated `.npy` file instead of producing
strides on the fly. Faster iteration when tuning epochs.

---

## 4. Output Files

Every pipeline run creates a timestamped folder in `sessions/`:

```
sessions/
└── 20260328_162441/
    ├── strides.csv          ← per-stride: GHS, deviation scores, haptic, color
    ├── session_meta.json    ← run config, source, n_strides, phase timing
    ├── overlay.png          ← Chart 1: observed vs. twin waveforms
    ├── ghs_trend.png        ← Chart 2: GHS bar chart per stride
    ├── deviation_heatmap.png← Chart 3: stride × timepoint deviation matrix
    └── session_report.pdf   ← 5-page PDF summary of all charts + explanations
```

**Open the PDF after a run:**
```bash
open sessions/$(ls -t sessions/ | head -1)/session_report.pdf
```

---

## 5. Project Structure

```
gaitguard/
├── run_pipeline.py          ← Main entry point (all CLI flags here)
├── pipeline.py              ← 4-phase state machine
├── visualise.py             ← Chart generation (overlay, GHS, heatmap)
├── report.py                ← PDF report generator
├── generate_training_data.py← Pre-generate training .npy files
├── requirements.txt         ← Python dependencies
│
├── core/
│   ├── config.py            ← All tunable parameters (SystemConfig)
│   └── types.py             ← Immutable value objects (SensorPacket, StrideResult, …)
│
├── phases/
│   ├── phase0_calibration.py← Standing-still baseline
│   ├── phase1_segmentation.py← Heel-strike detection, stride building, profile
│   ├── phase2_twin.py       ← LSTM inference, boundary blend
│   └── phase3_monitoring.py ← Real-time scoring, haptic dispatch
│
├── ml/
│   ├── model.py             ← LSTMTwin architecture (2-layer, hidden=64)
│   └── train.py             ← Training loop + normative waveform generator
│
├── dsp/
│   ├── filters.py           ← Butterworth filter, complementary filter
│   └── angles.py            ← Joint angle computation from IMU readings
│
├── simulation/
│   └── synthetic.py         ← Synthetic IMU source (healthy + pathology modes)
│
├── adapters/
│   ├── base.py              ← DatasetAdapter abstract base
│   └── compwalk_acl.py      ← COMPWALK-ACL CSV adapter + synthetic fallback
│
├── scoring/
│   └── scorer.py            ← GHS formula, haptic trigger logic
│
├── data_io/
│   ├── source.py            ← IMUSource abstract base (Strategy pattern)
│   └── logger.py            ← CSV + JSON session logger (Observer pattern)
│
├── models/
│   ├── lstm_twin.pt         ← Trained LSTM weights (auto-generated on first run)
│   └── lstm_norm.npz        ← Normalisation stats (mean/std per channel)
│
└── sessions/                ← All session outputs (auto-created)
```

---

## 6. Key Configuration Parameters

Edit `core/config.py` to tune the system:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `sample_rate_hz` | 50 | IMU sampling rate |
| `calibration_duration_s` | 2.0 | Standing-still phase length |
| `min_strides_for_profile` | 20 | Strides needed before Phase 2 |
| `anchor_points` | 20 | Gait-cycle points used as LSTM input |
| `lstm_anchor_len` | 20 | Must match `anchor_points` |
| `lstm_hidden_size` | 64 | LSTM hidden units |
| `ghs_scale` | 25.0 | Sensitivity: higher = lower GHS for same deviation |
| `haptic_threshold_sd` | 2.0 | SDs above mean before haptic fires |
| `score_green` | 80.0 | GHS threshold for green |
| `score_yellow` | 50.0 | GHS threshold for yellow |

> After changing `anchor_points` or `lstm_*` parameters, delete `models/lstm_twin.pt`
> and retrain with Command 8 or 9.

---

## 7. Quick Reference

| Goal | Command |
|------|---------|
| Validate no false positives | `run_pipeline.py --source synthetic --pathology healthy` |
| Demo pathology detection | `run_pipeline.py --source synthetic --pathology mixed` |
| ACL dataset demo | `run_pipeline.py --source compwalk --condition acl` |
| Retrain model (quick) | `run_pipeline.py --train-only` |
| Retrain model (custom) | `python -m ml.train --n 5000 --epochs 100` |
| Generate training data | `python generate_training_data.py --n 10000` |
| Open latest PDF report | `open sessions/$(ls -t sessions/ \| head -1)/session_report.pdf` |
