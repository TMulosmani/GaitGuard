"""
Gait Health Score computation and haptic pattern determination.

Formulas (from prompt spec):
    knee_dev[i]   = |knee_observed[i] - twin_knee[i]|   for i = 21…100
    ankle_dev[i]  = |ankle_observed[i] - twin_ankle[i]| for i = 21…100
    z_knee        = mean(knee_dev)  / std_knee
    z_ankle       = mean(ankle_dev) / std_ankle
    dev_score     = z_knee × 0.6 + z_ankle × 0.4
    GHS           = clamp(100 − dev_score × 25, 0, 100)

Haptic trigger (if dev_score ≥ threshold):
    knee deviation dominant in tp 21-35  → TWO_SHORT
    ankle deviation dominant in tp 60-85 → ONE_LONG
    otherwise                            → THREE_SHORT
"""
from __future__ import annotations

import numpy as np

from core.config import SystemConfig
from core.types import DigitalTwin, GaitProfile, HapticPattern, StrideResult


def score_stride(
    observed_knee: np.ndarray,    # (100,) time-normalised
    observed_ankle: np.ndarray,   # (100,)
    twin: DigitalTwin,
    profile: GaitProfile,
    config: SystemConfig,
    stride_number: int = 0,
) -> StrideResult:
    """
    Compute the Gait Health Score and decide the haptic pattern for one stride.
    """
    ap = config.anchor_points  # 20 — anchor region is excluded from scoring

    # --- Per-timepoint absolute deviations (indices 20-99 → 80 points) ---
    knee_dev  = np.abs(observed_knee[ap:]  - twin.twin_knee[ap:])   # (80,)
    ankle_dev = np.abs(observed_ankle[ap:] - twin.twin_ankle[ap:])  # (80,)

    mean_knee_dev  = float(knee_dev.mean())
    mean_ankle_dev = float(ankle_dev.mean())

    z_knee  = mean_knee_dev  / profile.std_knee
    z_ankle = mean_ankle_dev / profile.std_ankle

    dev_score = z_knee * config.ghs_weight_knee + z_ankle * config.ghs_weight_ankle
    ghs = float(np.clip(100.0 - dev_score * config.ghs_scale, 0.0, 100.0))

    haptic = _determine_haptic(knee_dev, ankle_dev, dev_score, config)

    return StrideResult(
        gait_health_score = ghs,
        deviation_score   = dev_score,
        z_knee            = z_knee,
        z_ankle           = z_ankle,
        haptic            = haptic,
        knee_dev          = knee_dev,
        ankle_dev         = ankle_dev,
        observed_knee     = observed_knee,
        observed_ankle    = observed_ankle,
        stride_number     = stride_number,
    )


def _determine_haptic(
    knee_dev: np.ndarray,
    ankle_dev: np.ndarray,
    dev_score: float,
    config: SystemConfig,
) -> HapticPattern:
    if dev_score < config.haptic_threshold_sd:
        return HapticPattern.NONE

    # Map zone bounds (0-99 full cycle) to indices in the 80-point deviation array
    ap = config.anchor_points  # 20
    hs_lo, hs_hi = config.heel_strike_zone[0] - ap, config.heel_strike_zone[1] - ap
    sw_lo, sw_hi = config.swing_zone[0]        - ap, config.swing_zone[1]        - ap

    hs_lo = max(hs_lo, 0)
    sw_lo = max(sw_lo, 0)

    knee_hs  = float(knee_dev[hs_lo:hs_hi].mean())
    ankle_sw = float(ankle_dev[sw_lo:sw_hi].mean())

    if knee_hs >= ankle_sw and knee_hs > 5.0:
        return HapticPattern.TWO_SHORT
    if ankle_sw > knee_hs and ankle_sw > 5.0:
        return HapticPattern.ONE_LONG
    return HapticPattern.THREE_SHORT
