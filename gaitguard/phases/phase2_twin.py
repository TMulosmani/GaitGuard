"""
Phase 2 — LSTM-Based Healthy Digital Twin Generation

Feeds the patient's anchor segments (first 20 % of gait cycle) into the
pre-trained LSTMTwin and concatenates the prediction to produce a 100-point
personalised healthy reference waveform.
"""
from __future__ import annotations

import os

import numpy as np
import torch

from core.config import SystemConfig
from core.types import DigitalTwin, GaitProfile


class DigitalTwinPhase:
    """
    Thin wrapper around the LSTM inference call.

    Usage:
        phase2 = DigitalTwinPhase(config)
        twin   = phase2.generate(profile)
    """

    def __init__(self, config: SystemConfig):
        self._config = config
        self._norm_mean: np.ndarray | None = None
        self._norm_std:  np.ndarray | None = None
        self._model = self._load_model()

    # ------------------------------------------------------------------

    def generate(self, profile: GaitProfile) -> DigitalTwin:
        """
        Run LSTM inference on the patient's anchor to produce a DigitalTwin.
        The anchor is normalised before inference; the prediction is denormalised
        back to degrees before being returned.
        """
        anchor = np.stack(
            [profile.anchor_knee, profile.anchor_ankle], axis=-1
        ).astype(np.float32)                                  # (20, 2)

        # Normalise if stats are available
        if self._norm_mean is not None:
            anchor_in = (anchor - self._norm_mean) / self._norm_std
        else:
            anchor_in = anchor

        x = torch.from_numpy(anchor_in).unsqueeze(0)         # (1, 20, 2)

        with torch.no_grad():
            pred_norm = self._model(x)                        # (1, 80, 2)

        pred_np = pred_norm.squeeze(0).numpy()                # (70, 2)

        # Denormalise back to degrees
        if self._norm_mean is not None:
            pred_np = pred_np * self._norm_std + self._norm_mean

        # Boundary blend: smoothly connect the last anchor point to the
        # LSTM's prediction over the first 5 post-anchor timepoints,
        # eliminating the discontinuity at the anchor boundary.
        n_blend = 5
        anchor_end = anchor[-1]                               # (2,) last anchor point
        for i in range(n_blend):
            alpha = (i + 1) / (n_blend + 1)                  # 1/6 … 5/6
            pred_np[i] = (1.0 - alpha) * anchor_end + alpha * pred_np[i]

        pred_knee  = pred_np[:, 0]
        pred_ankle = pred_np[:, 1]

        twin_knee  = np.concatenate([profile.anchor_knee,  pred_knee])   # (100,)
        twin_ankle = np.concatenate([profile.anchor_ankle, pred_ankle])  # (100,)

        return DigitalTwin(twin_knee=twin_knee, twin_ankle=twin_ankle)

    # ------------------------------------------------------------------

    def _load_model(self):
        from ml.model import build_model, load_model

        model_path = self._config.model_path
        norm_path  = self._config.norm_stats_path

        needs_train = not os.path.exists(model_path) or not os.path.exists(norm_path)

        if needs_train:
            print(f"[Phase 2] Model or norm stats not found. Training from synthetic data …")
            self._train_and_save()

        # Load norm stats
        stats = np.load(norm_path)
        self._norm_mean = stats["mean"].astype(np.float32)  # (2,)
        self._norm_std  = stats["std"].astype(np.float32)   # (2,)
        print(f"[Phase 2] Norm stats loaded  "
              f"knee μ={self._norm_mean[0]:.2f} σ={self._norm_std[0]:.2f} | "
              f"ankle μ={self._norm_mean[1]:.2f} σ={self._norm_std[1]:.2f}")

        model = load_model(model_path, self._config)
        print(f"[Phase 2] Loaded LSTM model from {model_path}")
        model.eval()
        return model

    def _train_and_save(self) -> None:
        from ml.train import generate_healthy_strides, train
        rng = np.random.default_rng(42)
        data = generate_healthy_strides(3000, rng)
        train(data, self._config, epochs=60)
