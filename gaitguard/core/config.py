"""
SystemConfig — all tunable parameters in one place.
Override any field at instantiation or load from a JSON file.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Tuple


@dataclass
class SystemConfig:
    # ---- Sensor -------------------------------------------------------
    sample_rate_hz: float = 50.0

    # ---- Phase 0: Calibration ----------------------------------------
    calibration_duration_s: float = 2.0

    # ---- Phase 1: Segmentation ----------------------------------------
    min_strides_for_profile: int = 20

    # Heel-strike / stride-boundary detection
    omega_thresh_dps: float = 15.0      # foot gyro magnitude (deg/s)
    accel_z_tolerance_g: float = 0.15   # foot flat: |accel_z – 1 g| < this
    knee_near_zero_deg: float = 15.0    # knee within ±15° of calibrated zero
    condition_hold_ms: float = 80.0     # all 3 conditions must hold this long
    lockout_ms: float = 300.0           # min time between stride boundaries
    min_stride_ms: float = 400.0
    max_stride_ms: float = 2500.0

    # ---- Signal processing -------------------------------------------
    butterworth_cutoff_hz: float = 6.0
    butterworth_order: int = 4
    complementary_alpha: float = 0.98   # gyro weight

    # ---- Gait cycle --------------------------------------------------
    gait_cycle_points: int = 100
    anchor_points: int = 20

    # ---- Phase 3: Scoring --------------------------------------------
    haptic_threshold_sd: float = 2.0
    ghs_weight_knee: float = 0.6
    ghs_weight_ankle: float = 0.4
    ghs_scale: float = 25.0             # GHS = max(0, 100 – dev * ghs_scale)

    # Haptic trigger zones (indices into 0-99 normalised gait cycle)
    heel_strike_zone: Tuple[int, int] = (21, 35)
    swing_zone: Tuple[int, int] = (60, 85)

    # ---- Display thresholds ------------------------------------------
    score_green: float = 80.0
    score_yellow: float = 50.0

    # ---- LSTM --------------------------------------------------------
    lstm_hidden_size: int = 64
    lstm_num_layers: int = 2
    lstm_dropout: float = 0.2
    lstm_anchor_len: int = 20
    lstm_prediction_len: int = 80
    lstm_n_channels: int = 2            # knee + ankle

    # ---- Connectivity ------------------------------------------------
    ble_timeout_ms: float = 500.0

    # ---- Paths -------------------------------------------------------
    model_path: str = "models/lstm_twin.pt"
    norm_stats_path: str = "models/lstm_norm.npz"
    session_log_dir: str = "sessions/"

    # ------------------------------------------------------------------

    @classmethod
    def from_json(cls, path: str) -> "SystemConfig":
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)
