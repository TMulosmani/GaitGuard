"""
Phase 1 — Gait Cycle Segmentation and Personal Anchor Collection

The patient walks for 30–60 s.  The system:
  1. Detects stride boundaries using the triple-condition heel-strike rule.
  2. Rejects artefact strides (too short / too long).
  3. Applies Butterworth filtering to each stride.
  4. Time-normalises every valid stride to 100 points.
  5. After ≥ 20 valid strides, computes:
       - patient mean curves  (mean_knee, mean_ankle)  — (100,)
       - stride-to-stride SDs (std_knee, std_ankle)    — scalars
       - anchor segments      (anchor_knee, anchor_ankle) — (20,)
"""
from __future__ import annotations

from collections import deque
from typing import List, Optional, Tuple

import numpy as np

from core.config import SystemConfig
from core.types import GaitProfile, SensorPacket, StrideData
from dsp.angles import JointAngleComputer
from dsp.filters import apply_butterworth


class SegmentationPhase:
    """
    Call `feed(packet, knee, ankle)` for every incoming sample.
    `is_ready` becomes True once ≥ min_strides_for_profile valid strides
    have been collected.  Then call `build_profile()` to get the GaitProfile.
    """

    def __init__(self, config: SystemConfig):
        self._cfg = config
        self._dt_ms = 1000.0 / config.sample_rate_hz

        # Running buffers for the current (incomplete) stride
        self._stride_knee:  List[float] = []
        self._stride_ankle: List[float] = []
        self._stride_start_ms: Optional[float] = None

        # Condition-hold state (all 3 must be True for condition_hold_ms)
        self._cond_hold_start: Optional[float] = None

        # Lockout after a confirmed boundary
        self._last_boundary_ms: float = -1e9

        # Last completed stride (set in _confirm_boundary, read by Phase 3)
        self.last_completed_stride: Optional[StrideData] = None

        # Completed valid strides
        self._valid_strides: List[StrideData] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def n_valid_strides(self) -> int:
        return len(self._valid_strides)

    @property
    def is_ready(self) -> bool:
        return len(self._valid_strides) >= self._cfg.min_strides_for_profile

    def feed(
        self,
        packet: SensorPacket,
        knee_deg: float,
        ankle_deg: float,
    ) -> bool:
        """
        Process one sample. Returns True if a new stride was just confirmed.
        """
        t = packet.timestamp_ms

        # Accumulate current stride
        self._stride_knee.append(knee_deg)
        self._stride_ankle.append(ankle_deg)
        if self._stride_start_ms is None:
            self._stride_start_ms = t

        # ---- Condition evaluation ------------------------------------
        cond_met = self._conditions_met(packet, knee_deg)

        in_lockout = (t - self._last_boundary_ms) < self._cfg.lockout_ms

        if cond_met and not in_lockout:
            if self._cond_hold_start is None:
                self._cond_hold_start = t
            elif (t - self._cond_hold_start) >= self._cfg.condition_hold_ms:
                # Stride boundary confirmed
                self._confirm_boundary(t)
                self._cond_hold_start = None
                return True
        else:
            self._cond_hold_start = None

        return False

    def build_profile(self) -> GaitProfile:
        """
        Call once `is_ready` is True.  Computes the patient GaitProfile.
        """
        if not self.is_ready:
            raise RuntimeError("Not enough valid strides to build profile.")

        normalised_knee  = []
        normalised_ankle = []

        for stride in self._valid_strides:
            n = self._cfg.gait_cycle_points
            fk = apply_butterworth(
                stride.knee_angles,
                self._cfg.butterworth_cutoff_hz,
                self._cfg.sample_rate_hz,
                self._cfg.butterworth_order,
            )
            fa = apply_butterworth(
                stride.ankle_angles,
                self._cfg.butterworth_cutoff_hz,
                self._cfg.sample_rate_hz,
                self._cfg.butterworth_order,
            )
            nk = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(fk)), fk)
            na = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(fa)), fa)
            normalised_knee.append(nk)
            normalised_ankle.append(na)

        arr_k = np.stack(normalised_knee)   # (S, 100)
        arr_a = np.stack(normalised_ankle)  # (S, 100)

        mean_k = arr_k.mean(axis=0)
        mean_a = arr_a.mean(axis=0)

        # Stride-to-stride SD: mean of per-stride SDs across the cycle
        std_k = float(arr_k.std(axis=0).mean())
        std_a = float(arr_a.std(axis=0).mean())

        ap = self._cfg.anchor_points
        return GaitProfile(
            mean_knee   = mean_k,
            mean_ankle  = mean_a,
            std_knee    = max(std_k, 1e-3),   # avoid division by zero in scorer
            std_ankle   = max(std_a, 1e-3),
            anchor_knee  = mean_k[:ap].copy(),
            anchor_ankle = mean_a[:ap].copy(),
            n_strides   = len(self._valid_strides),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _conditions_met(self, packet: SensorPacket, knee_deg: float) -> bool:
        foot = packet.foot
        gyro_mag = np.sqrt(foot.gyro_x**2 + foot.gyro_y**2 + foot.gyro_z**2)
        accel_z_ok = abs(abs(foot.accel_z) - 1.0) < self._cfg.accel_z_tolerance_g
        return (
            gyro_mag < self._cfg.omega_thresh_dps
            and accel_z_ok
            and abs(knee_deg) < self._cfg.knee_near_zero_deg
        )

    def _confirm_boundary(self, t_ms: float) -> None:
        """Finalise the completed stride and start a new buffer."""
        duration = t_ms - (self._stride_start_ms or t_ms)
        stride = StrideData(
            knee_angles  = np.array(self._stride_knee,  dtype=float),
            ankle_angles = np.array(self._stride_ankle, dtype=float),
            duration_ms  = duration,
        )
        # Store the last completed stride (valid or not) for Phase 3 to read
        self.last_completed_stride = stride

        if stride.is_valid(self._cfg.min_stride_ms, self._cfg.max_stride_ms):
            self._valid_strides.append(stride)

        # Reset buffers for the next stride
        self._stride_knee  = []
        self._stride_ankle = []
        self._stride_start_ms = t_ms
        self._last_boundary_ms = t_ms
