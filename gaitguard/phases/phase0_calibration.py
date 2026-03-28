"""
Phase 0 — Vertical Standing Calibration

Patient stands still for `calibration_duration_s` seconds.
The mean accelerometer tilt angles from all three IMUs are stored as the
zero-reference baseline.  All subsequent joint angles are computed relative
to this baseline so that 'standing straight' always equals 0° knee flexion.
"""
from __future__ import annotations

from typing import List

import numpy as np

from core.config import SystemConfig
from core.types import SensorPacket
from dsp.angles import JointAngleComputer
from dsp.filters import accel_to_angle


class CalibrationPhase:
    """
    Feed SensorPackets one at a time via `feed()`.
    Returns True (and calls `angle_computer.set_baseline()`) when done.
    """

    def __init__(self, config: SystemConfig, angle_computer: JointAngleComputer):
        self._config = config
        self._angle_computer = angle_computer
        self._n_needed = int(config.calibration_duration_s * config.sample_rate_hz)
        self._thigh_angles: List[float] = []
        self._shin_angles:  List[float] = []
        self._foot_angles:  List[float] = []
        self._complete = False

    @property
    def is_complete(self) -> bool:
        return self._complete

    @property
    def progress(self) -> float:
        """0.0 → 1.0 fraction of calibration samples collected."""
        return min(len(self._thigh_angles) / self._n_needed, 1.0)

    # ------------------------------------------------------------------

    def feed(self, packet: SensorPacket) -> bool:
        """
        Accumulate one packet.  Returns True when calibration finishes.
        """
        if self._complete:
            return True

        self._thigh_angles.append(accel_to_angle(packet.thigh.accel_x, packet.thigh.accel_z))
        self._shin_angles.append( accel_to_angle(packet.shin.accel_x,  packet.shin.accel_z))
        self._foot_angles.append( accel_to_angle(packet.foot.accel_x,  packet.foot.accel_z))

        if len(self._thigh_angles) >= self._n_needed:
            thigh_base = float(np.mean(self._thigh_angles))
            shin_base  = float(np.mean(self._shin_angles))
            foot_base  = float(np.mean(self._foot_angles))
            self._angle_computer.set_baseline(thigh_base, shin_base, foot_base)
            self._complete = True

        return self._complete
