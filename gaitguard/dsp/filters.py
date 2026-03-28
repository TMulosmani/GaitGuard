"""
Signal processing primitives.
  - ComplementaryFilter: per-axis gyro+accel angle fusion
  - apply_butterworth:   zero-phase low-pass filter for IMU signals
  - accel_to_angle:      tilt estimate from accelerometer
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt


# ---------------------------------------------------------------------------
# Accelerometer tilt helper
# ---------------------------------------------------------------------------

def accel_to_angle(ax: float, az: float) -> float:
    """Estimate tilt angle (degrees) in the sagittal plane from accel X and Z."""
    return float(np.degrees(np.arctan2(ax, az)))


# ---------------------------------------------------------------------------
# Complementary filter
# ---------------------------------------------------------------------------

class ComplementaryFilter:
    """
    Fuses gyroscope and accelerometer to estimate joint angle.

        angle[t] = α × (angle[t-1] + gyro_rate × dt) + (1−α) × accel_angle

    One instance per IMU axis. Call reset() before each session.
    """

    def __init__(self, alpha: float = 0.98, sample_rate_hz: float = 50.0):
        self.alpha = alpha
        self.dt = 1.0 / sample_rate_hz
        self._angle: float = 0.0

    def reset(self, initial_angle: float = 0.0) -> None:
        self._angle = initial_angle

    def update(self, gyro_rate_dps: float, accel_angle_deg: float) -> float:
        gyro_pred = self._angle + gyro_rate_dps * self.dt
        self._angle = self.alpha * gyro_pred + (1.0 - self.alpha) * accel_angle_deg
        return self._angle

    @property
    def angle(self) -> float:
        return self._angle


# ---------------------------------------------------------------------------
# Butterworth low-pass filter
# ---------------------------------------------------------------------------

def apply_butterworth(
    signal: np.ndarray,
    cutoff_hz: float,
    sample_rate_hz: float,
    order: int = 4,
) -> np.ndarray:
    """
    Zero-phase forward-backward Butterworth low-pass filter.
    Falls back to the raw signal if it is too short for filtfilt.
    """
    nyq = sample_rate_hz / 2.0
    normal_cutoff = min(cutoff_hz / nyq, 0.99)
    b, a = butter(order, normal_cutoff, btype="low", analog=False)
    min_len = 3 * (max(len(a), len(b)) - 1)
    if len(signal) < min_len:
        return signal.copy()
    return filtfilt(b, a, signal)
