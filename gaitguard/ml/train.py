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
    Approximate normative knee flexion curve (degrees) over 0-100% gait cycle.
    Based on Winter (2009) normative data.
    """
    # Piece-wise sinusoidal approximation
    k = (
          5.0 * np.ones_like(t)                            # baseline extension
        + 10.0 * np.sin(np.pi * t / 20.0) * (t < 20)      # loading-response flex
        + 55.0 * np.sin(np.pi * (t - 40) / 40.0) * ((t >= 40) & (t < 80))  # swing flex
    )
    return np.clip(k, 0, 70)


def _normative_ankle(t: np.ndarray) -> np.ndarray:
    """
    Approximate normative ankle dorsiflexion/plantarflexion curve (degrees).
    Positive = dorsiflexion, negative = plantarflexion.
    """
    a = (
        -5.0 * np.sin(np.pi * t / 15.0) * (t < 15)           # initial PF
        + 12.0 * np.sin(np.pi * (t - 15) / 45.0) * ((t >= 15) & (t < 60))  # DF stance
        - 20.0 * np.sin(np.pi * (t - 55) / 15.0) * ((t >= 55) & (t < 70))  # push-off PF
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
    """
    ap = config.lstm_anchor_len
    X = torch.from_numpy(data[:, :ap, :])         # (N, 20, 2) — anchor
    Y = torch.from_numpy(data[:, ap:, :])         # (N, 80, 2) — target

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
