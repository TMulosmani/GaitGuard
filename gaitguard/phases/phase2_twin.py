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
        self._model = self._load_model()

    # ------------------------------------------------------------------

    def generate(self, profile: GaitProfile) -> DigitalTwin:
        """
        Run LSTM inference on the patient's anchor to produce a DigitalTwin.
        """
        # Build (1, 20, 2) input tensor
        anchor = np.stack(
            [profile.anchor_knee, profile.anchor_ankle], axis=-1
        ).astype(np.float32)                        # (20, 2)
        x = torch.from_numpy(anchor).unsqueeze(0)   # (1, 20, 2)

        with torch.no_grad():
            pred = self._model(x)                   # (1, 80, 2)

        pred_np = pred.squeeze(0).numpy()           # (80, 2)
        pred_knee  = pred_np[:, 0]
        pred_ankle = pred_np[:, 1]

        twin_knee  = np.concatenate([profile.anchor_knee,  pred_knee])   # (100,)
        twin_ankle = np.concatenate([profile.anchor_ankle, pred_ankle])  # (100,)

        return DigitalTwin(twin_knee=twin_knee, twin_ankle=twin_ankle)

    # ------------------------------------------------------------------

    def _load_model(self):
        from ml.model import build_model, load_model

        path = self._config.model_path
        if os.path.exists(path):
            model = load_model(path, self._config)
            print(f"[Phase 2] Loaded LSTM model from {path}")
        else:
            print(f"[Phase 2] Model not found at {path}. Training from synthetic data …")
            self._train_and_save()
            model = load_model(path, self._config)

        model.eval()
        return model

    def _train_and_save(self) -> None:
        from ml.train import generate_healthy_strides, train
        rng = np.random.default_rng(42)
        data = generate_healthy_strides(3000, rng)
        train(data, self._config, epochs=60)
