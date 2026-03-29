"""
train.py — Offline training of the LSTMTwin on healthy gait waveforms.

Usage:
    python -m ml.train                        # trains on synthetic data
    python -m ml.train --data path/to/data    # trains on real dataset strides

The training data is a numpy array of shape (N, 100, 2) where
  axis 0 = strides, axis 1 = 100 gait-cycle points, axis 2 = [knee, ankle].

The model is saved to the path specified in SystemConfig.model_path.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split
from tqdm import tqdm

# Make the package importable when run from the gaitguard/ root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.config import SystemConfig
from ml.model import build_model


# ---------------------------------------------------------------------------
# Synthetic healthy gait data generator (used when no real data is supplied)
# ---------------------------------------------------------------------------

def _normative_knee(t: np.ndarray) -> np.ndarray:
    """
    Knee flexion curve aligned to Phase 1 segmented stride timing.

    Phase 1's heel-strike detector fires ~12 timepoints into the true gait
    cycle (after the flat-foot dwell), so every segmented stride starts at
    ~tp 12 of the underlying waveform.  Shifting swing onset to tp 28 here
    makes the LSTM training distribution match what Phase 1 actually produces.
    """
    k = (
          2.0 * np.ones_like(t)                                          # baseline
        + 10.0 * np.sin(np.pi * t / 15.0) * (t < 15)                   # loading-response bump
        + 55.0 * np.sin(np.pi * (t - 28) / 42.0) * ((t >= 28) & (t < 70))  # swing flex: onset 28, peak ~49
    )
    return np.clip(k, 0, 70)


def _normative_ankle(t: np.ndarray) -> np.ndarray:
    """
    Ankle curve aligned to Phase 1 segmented stride timing (same ~12 tp offset).
    """
    a = (
        -4.0 * np.sin(np.pi * t / 12.0) * (t < 12)                     # initial PF
        + 12.0 * np.sin(np.pi * (t - 12) / 35.0) * ((t >= 12) & (t < 47))  # DF stance: peak ~29
        - 20.0 * np.sin(np.pi * (t - 43) / 15.0) * ((t >= 43) & (t < 58))  # push-off PF: peak ~50
    )
    return a


def generate_healthy_strides(n_strides: int, rng: np.random.Generator) -> np.ndarray:
    """
    Return synthetic healthy strides of shape (n_strides, 100, 2).
    Adds realistic inter-subject + inter-stride variation.
    """
    t = np.arange(100, dtype=float)
    base_k = _normative_knee(t)
    base_a = _normative_ankle(t)

    strides = []
    for _ in range(n_strides):
        # Subject-level scale + offset variation
        scale_k = rng.normal(1.0, 0.08)
        scale_a = rng.normal(1.0, 0.10)
        shift_k = rng.normal(0.0, 2.0)
        shift_a = rng.normal(0.0, 2.0)

        # Stride-level Gaussian noise
        noise_k = rng.normal(0, 1.5, 100)
        noise_a = rng.normal(0, 1.0, 100)

        k = base_k * scale_k + shift_k + noise_k
        a = base_a * scale_a + shift_a + noise_a
        strides.append(np.stack([k, a], axis=-1))  # (100, 2)

    return np.stack(strides, axis=0).astype(np.float32)  # (N, 100, 2)


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def compute_norm_stats(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute per-channel (knee, ankle) mean and std across all strides and timepoints.

    data: (N, 100, 2)
    Returns: mean (2,), std (2,)
    """
    mean = data.mean(axis=(0, 1))   # (2,)
    std  = data.std(axis=(0, 1))    # (2,)
    std  = np.where(std < 1e-6, 1.0, std)  # guard against zero std
    return mean.astype(np.float32), std.astype(np.float32)


def normalize(data: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Apply z-score normalization. data: (..., 2), mean/std: (2,)."""
    return (data - mean) / std


def denormalize(data: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Invert z-score normalization."""
    return data * std + mean


def train(
    data: np.ndarray,
    config: SystemConfig,
    epochs: int = 50,
    batch_size: int = 64,
    lr: float = 1e-3,
    val_split: float = 0.15,
) -> None:
    """
    Train LSTMTwin and save the model to config.model_path.

    data: (N, 100, 2) float32 array of healthy strides.
    Normalisation stats are saved alongside the model at config.norm_stats_path.
    """
    # --- Normalise (per-channel z-score) before any splitting ---
    mean, std = compute_norm_stats(data)
    data_norm = normalize(data, mean, std)

    os.makedirs(os.path.dirname(config.norm_stats_path) or ".", exist_ok=True)
    np.savez(config.norm_stats_path, mean=mean, std=std)
    print(f"Norm stats saved → {config.norm_stats_path}  "
          f"(knee μ={mean[0]:.2f} σ={std[0]:.2f} | ankle μ={mean[1]:.2f} σ={std[1]:.2f})")

    ap = config.lstm_anchor_len
    X = torch.from_numpy(data_norm[:, :ap, :])    # (N, 20, 2) — normalised anchor
    Y = torch.from_numpy(data_norm[:, ap:, :])    # (N, 80, 2) — normalised target

    dataset = TensorDataset(X, Y)
    n_val = max(1, int(len(dataset) * val_split))
    n_train = len(dataset) - n_val
    train_ds, val_ds = random_split(dataset, [n_train, n_val])
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_dl   = DataLoader(val_ds,   batch_size=batch_size)

    model = build_model(config)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    best_val = float("inf")
    os.makedirs(os.path.dirname(config.model_path) or ".", exist_ok=True)

    for epoch in tqdm(range(1, epochs + 1), desc="Training LSTMTwin"):
        model.train()
        train_loss = 0.0
        for xb, yb in train_dl:
            pred = model(xb)
            loss = criterion(pred, yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(xb)
        train_loss /= n_train

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for xb, yb in val_dl:
                val_loss += criterion(model(xb), yb).item() * len(xb)
        val_loss /= n_val

        if epoch % 10 == 0:
            tqdm.write(f"Epoch {epoch:3d}  train={train_loss:.4f}  val={val_loss:.4f}")

        if val_loss < best_val:
            best_val = val_loss
            torch.save(model.state_dict(), config.model_path)

    print(f"Model saved → {config.model_path}  (best val MSE = {best_val:.4f})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Train the GaitGuard LSTM twin")
    parser.add_argument("--data",    default=None,  help="Path to .npy file of shape (N,100,2)")
    parser.add_argument("--n",       type=int, default=3000, help="Synthetic strides (ignored if --data supplied)")
    parser.add_argument("--epochs",  type=int, default=60)
    parser.add_argument("--batch",   type=int, default=64)
    parser.add_argument("--lr",      type=float, default=1e-3)
    args = parser.parse_args()

    config = SystemConfig()

    if args.data:
        data = np.load(args.data).astype(np.float32)
        print(f"Loaded real data: {data.shape}")
    else:
        rng = np.random.default_rng(42)
        data = generate_healthy_strides(args.n, rng)
        print(f"Generated {len(data)} synthetic healthy strides.")

    train(data, config, epochs=args.epochs, batch_size=args.batch, lr=args.lr)


if __name__ == "__main__":
    main()
