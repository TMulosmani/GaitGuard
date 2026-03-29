Here's how each configuration maps to the GaitGuard system design:

---

## The 4-Phase Pipeline (context)

GaitGuard runs a sequential state machine: **Phase 0** (standing-still calibration) → **Phase 1** (stride segmentation, building a gait profile) → **Phase 2** (LSTM generates a "healthy digital twin") → **Phase 3** (real-time monitoring, scoring, haptic feedback). Configurations 1–3 all run this full pipeline end-to-end; they differ only in *where the IMU data comes from*.

---

## Configuration 1 — Synthetic Healthy

```
run_pipeline.py --source synthetic --pathology healthy --n-strides 80
```

Uses `SyntheticIMUSource` to generate 80 fake gait cycles with **normal** knee flexion (~60° peak swing) and ankle mechanics. No pathology is injected. All 4 phases run. Expected outcome: GHS stays in the **green zone (80–100)**, no haptic triggers. This is the **baseline demo** — it validates that the pipeline doesn't produce false positives on healthy gait.

---

## Configuration 2 — Synthetic Mixed (Pathological)

```
run_pipeline.py --source synthetic --pathology mixed --n-strides 80
```

Same synthetic generator, but injects **both pathologies simultaneously**:
- `reduced_extension`: heel-strike knee flex near 0° (should be ~2°) → triggers `TWO_SHORT` haptic (knee extension cue)
- `reduced_clearance`: reduced ankle push-off plantarflexion (−15° vs −20°) → triggers `ONE_LONG` haptic (foot clearance cue)

GHS drops to yellow/red range (40–65). This is the **core clinical demo** — it proves the system can detect and differentiate specific gait deviations in real time. Maps directly to the prompt's Phase 3 haptic feedback requirement.

---

## Configuration 3 — COMPWALK-ACL (synthetic fallback)

```
run_pipeline.py --source compwalk --condition acl
```

Uses the `COMPWALKACLAdapter`. Since no real dataset files are on disk, it falls back to `_generate_synthetic_packets()` which mimics the **COMPWALK-ACL dataset** (92 participants, 40 ACL-injured pre-surgery, Xsens Awinda 60Hz sensors). ACL gait characteristics are modelled: slower cadence (~1200ms stride), reduced peak knee flexion (~45° vs 60°), increased push-off plantarflexion compensation. GHS lands in the red zone (~40–44), `TWO_SHORT` dominant. This is the **dataset adaptation module** — the part of the project specifically designed to ingest a real public dataset and show the pipeline generalises beyond synthetic data.

---

## Configuration 4 — Train LSTM Only (via run_pipeline.py)

```
run_pipeline.py --train-only
```

Skips the pipeline entirely. Calls `ml/train.py` directly: generates 3000 synthetic healthy strides, trains the 2-layer stacked LSTM (hidden=64) for 60 epochs with Adam + MSE loss, saves the best validation model to `models/lstm_twin.pt`. This is **Phase 2 in isolation** — normally it runs automatically on first pipeline launch if no model file exists, but this config lets you explicitly retrain (e.g. after changing architecture or hyperparameters).

---

## Configuration 5 — LSTM Train Standalone

```
python -m ml.train --n 3000 --epochs 60
```

Same training as config 4 but invoked as a **module** with CLI flags, bypassing `run_pipeline.py` entirely. Useful for tuning: you can pass `--data /path/to/csv` to train on real recorded strides instead of synthetic ones, or change `--epochs` without touching `run_pipeline.py`. This reflects the original design principle of keeping the ML component independently testable.

---
Commands: 

```
# 1. Go to project directory    
cd {path_to_project}/gaitguard

# 2. Activate the Python environment (ALWAYS do this first)
source .venv/bin/activate

# 3. Generate 10,000 matched training strides → training_data/healthy_strides.npy
python generate_training_data.py --n 10000

# 4. Delete old model and retrain on the larger matched dataset
rm -f models/lstm_twin.pt
python -m ml.train --data training_data/healthy_strides.npy --epochs 100

# 5. Run the pipeline (healthy — should score high)
python run_pipeline.py --source synthetic --pathology healthy --n-strides 80

# 6. Run the pipeline (pathological — should score lower + fire haptics)
python run_pipeline.py --source synthetic --pathology mixed --n-strides 80

# 7. Run with ACL adapter
python run_pipeline.py --source compwalk --condition acl
```

## Summary table

| Config | Phases Run | Data Source | Purpose |
|--------|-----------|-------------|---------|
| 1 | 0→1→2→3 | Synthetic (healthy) | False-positive validation |
| 2 | 0→1→2→3 | Synthetic (pathological) | Haptic trigger demo |
| 3 | 0→1→2→3 | COMPWALK-ACL adapter | Real-dataset generalisation |
| 4 | Phase 2 only | Synthetic (training) | Model retraining (via CLI) |
| 5 | Phase 2 only | Synthetic (training) | Model retraining (standalone) |
