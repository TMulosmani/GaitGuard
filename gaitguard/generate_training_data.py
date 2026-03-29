"""
generate_training_data.py
--------------------------
Generates a large .npy training dataset using the SAME waveforms as
SyntheticIMUSource — so the LSTM twin is trained on data that matches
what the simulator actually produces.

Saves: training_data/healthy_strides.npy  shape=(N, 100, 2)
         [knee, ankle] at 100 gait-cycle points, healthy only.

Usage:
    python generate_training_data.py --n 10000
    python generate_training_data.py --n 10000 --seed 123
"""
from __future__ import annotations

import argparse
import os
import numpy as np


# ── Waveform templates (copied from simulation/synthetic.py) ────────────────

def _knee_profile(phase: np.ndarray, rng) -> np.ndarray:
    """Healthy knee flexion (degrees). Peak ~60° during swing."""
    heel_strike_flex = 2.0
    peak_swing_flex  = 60.0
    k = (
          heel_strike_flex * np.ones_like(phase)
        + 12.0 * np.sin(np.pi * phase / 0.2)  * (phase < 0.2)
        + (peak_swing_flex - heel_strike_flex) * np.sin(np.pi * (phase - 0.4) / 0.4)
          * ((phase >= 0.4) & (phase < 0.8))
    )
    k += rng.normal(0, 1.5, len(phase))
    return np.clip(k, 0, 75)


def _ankle_profile(phase: np.ndarray, rng) -> np.ndarray:
    """Healthy ankle dorsiflexion/plantarflexion (degrees). Peak DF ~13°, push-off PF ~-20°."""
    push_off_pf = -20.0
    df_peak     =  13.0
    a = (
        -5.0    * np.sin(np.pi * phase / 0.15) * (phase < 0.15)
        + df_peak * np.sin(np.pi * (phase - 0.15) / 0.45) * ((phase >= 0.15) & (phase < 0.6))
        + push_off_pf * np.sin(np.pi * (phase - 0.55) / 0.15) * ((phase >= 0.55) & (phase < 0.70))
    )
    a += rng.normal(0, 1.0, len(phase))
    return a


# ── Per-subject variation ────────────────────────────────────────────────────

def generate_strides(n_strides: int, rng: np.random.Generator) -> np.ndarray:
    """
    Return (n_strides, 100, 2) float32 array of healthy strides.

    Each stride gets:
      - Subject-level amplitude scale  (±8% knee, ±10% ankle)
      - Subject-level timing jitter    (phase shift ±3%)
      - Stride-level Gaussian noise    (already inside _knee/_ankle_profile)
    """
    phase = np.linspace(0, 1, 100)
    strides = []

    for _ in range(n_strides):
        # Subject-level variation: slightly shift the phase and scale amplitude
        scale_k = rng.normal(1.0, 0.08)
        scale_a = rng.normal(1.0, 0.10)
        shift   = rng.normal(0.0, 0.03)           # timing jitter ±3 % cycle
        ph      = np.clip(phase + shift, 0, 1)

        k = _knee_profile(ph, rng) * scale_k
        a = _ankle_profile(ph, rng) * scale_a

        strides.append(np.stack([k, a], axis=-1))  # (100, 2)

    return np.stack(strides).astype(np.float32)    # (N, 100, 2)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n",    type=int, default=10000, help="Number of strides to generate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out",  default="training_data/healthy_strides.npy")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rng  = np.random.default_rng(args.seed)
    data = generate_strides(args.n, rng)
    np.save(args.out, data)

    print(f"Saved {data.shape[0]} strides → {args.out}")
    print(f"  shape : {data.shape}   dtype : {data.dtype}")
    print(f"  knee  : min={data[:,:,0].min():.1f}°  max={data[:,:,0].max():.1f}°  mean={data[:,:,0].mean():.1f}°")
    print(f"  ankle : min={data[:,:,1].min():.1f}°  max={data[:,:,1].max():.1f}°  mean={data[:,:,1].mean():.1f}°")


if __name__ == "__main__":
    main()
