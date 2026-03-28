"""
Immutable value objects for the GaitGuard pipeline.
All dataclasses are frozen so they're safe to pass between components.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Raw sensor types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IMUReading:
    """Raw reading from a single IMU at one timestep."""
    accel_x: float   # g
    accel_y: float   # g
    accel_z: float   # g
    gyro_x: float    # deg/s  (sagittal-plane rotation — primary for gait)
    gyro_y: float    # deg/s
    gyro_z: float    # deg/s
    timestamp_ms: float


@dataclass(frozen=True)
class SensorPacket:
    """Synchronized readings from all three IMUs at one timestep."""
    thigh: IMUReading
    shin: IMUReading
    foot: IMUReading
    timestamp_ms: float


# ---------------------------------------------------------------------------
# Processed gait data
# ---------------------------------------------------------------------------

@dataclass
class StrideData:
    """One complete, raw-sampled stride (before time-normalisation)."""
    knee_angles: np.ndarray    # shape (N,) degrees
    ankle_angles: np.ndarray   # shape (N,) degrees
    duration_ms: float

    def is_valid(self, min_ms: float = 400.0, max_ms: float = 2500.0) -> bool:
        return min_ms <= self.duration_ms <= max_ms


@dataclass
class GaitProfile:
    """Patient's personal gait profile computed from Phase 1 strides."""
    mean_knee: np.ndarray     # (100,) time-normalised mean
    mean_ankle: np.ndarray    # (100,)
    std_knee: float           # stride-to-stride scalar SD (degrees)
    std_ankle: float
    anchor_knee: np.ndarray   # (20,)  first 20 % of gait cycle
    anchor_ankle: np.ndarray  # (20,)
    n_strides: int


@dataclass
class DigitalTwin:
    """LSTM-generated healthy twin waveform for this patient."""
    twin_knee: np.ndarray    # (100,) = anchor[20] + predicted[80]
    twin_ankle: np.ndarray   # (100,)


# ---------------------------------------------------------------------------
# Output / result types
# ---------------------------------------------------------------------------

class HapticPattern(Enum):
    NONE         = "none"
    TWO_SHORT    = "two_short"    # insufficient knee extension at heel strike
    ONE_LONG     = "one_long"     # inadequate foot clearance during swing
    THREE_SHORT  = "three_short"  # general high-deviation stride


@dataclass
class StrideResult:
    """Complete scored output from Phase 3 for one stride."""
    gait_health_score: float    # 0–100
    deviation_score: float      # SD units
    z_knee: float
    z_ankle: float
    haptic: HapticPattern
    knee_dev: np.ndarray        # (80,) absolute deviations at tp 21-100
    ankle_dev: np.ndarray       # (80,)
    observed_knee: np.ndarray   # (100,) time-normalised observed
    observed_ankle: np.ndarray  # (100,)
    stride_number: int = 0

    @property
    def color_indicator(self) -> str:
        if self.gait_health_score >= 80:
            return "green"
        if self.gait_health_score >= 50:
            return "yellow"
        return "red"


# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------

class PipelineState(Enum):
    CALIBRATION     = auto()
    SEGMENTATION    = auto()
    TWIN_GENERATION = auto()
    MONITORING      = auto()
    ERROR           = auto()
