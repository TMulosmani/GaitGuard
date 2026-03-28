"""
JointAngleComputer: maintains three complementary filters (thigh, shin, foot)
and exposes calibration + per-sample angle computation.
"""
from __future__ import annotations

from typing import Tuple

from core.config import SystemConfig
from core.types import IMUReading
from dsp.filters import ComplementaryFilter, accel_to_angle


class JointAngleComputer:
    """
    Computes knee flexion/extension and ankle dorsiflexion/plantarflexion
    from raw IMU readings using complementary filters.

    Usage:
        computer = JointAngleComputer(config)
        computer.set_baseline(thigh_base, shin_base, foot_base)
        knee_deg, ankle_deg = computer.update(thigh_imu, shin_imu, foot_imu)
    """

    def __init__(self, config: SystemConfig):
        self._alpha = config.complementary_alpha
        self._sr = config.sample_rate_hz
        self._cf_thigh = ComplementaryFilter(self._alpha, self._sr)
        self._cf_shin  = ComplementaryFilter(self._alpha, self._sr)
        self._cf_foot  = ComplementaryFilter(self._alpha, self._sr)
        self._baseline_knee: float = 0.0
        self._baseline_ankle: float = 0.0

    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset filter states (call at start of each session)."""
        self._cf_thigh.reset()
        self._cf_shin.reset()
        self._cf_foot.reset()

    def set_baseline(
        self,
        thigh_base_deg: float,
        shin_base_deg: float,
        foot_base_deg: float,
    ) -> None:
        """
        Store Phase-0 calibration baselines so 'standing straight' = 0°.
        """
        self._baseline_knee  = thigh_base_deg - shin_base_deg
        self._baseline_ankle = shin_base_deg  - foot_base_deg
        # Seed the filters at their baseline values
        self._cf_thigh.reset(thigh_base_deg)
        self._cf_shin.reset(shin_base_deg)
        self._cf_foot.reset(foot_base_deg)

    def update(
        self,
        thigh: IMUReading,
        shin: IMUReading,
        foot: IMUReading,
    ) -> Tuple[float, float]:
        """
        Process one synchronized sensor packet.

        Returns:
            (knee_angle_deg, ankle_angle_deg) relative to calibration baseline.
            Positive knee = flexion. Positive ankle = dorsiflexion.
        """
        thigh_angle = self._cf_thigh.update(
            thigh.gyro_x, accel_to_angle(thigh.accel_x, thigh.accel_z)
        )
        shin_angle = self._cf_shin.update(
            shin.gyro_x, accel_to_angle(shin.accel_x, shin.accel_z)
        )
        foot_angle = self._cf_foot.update(
            foot.gyro_x, accel_to_angle(foot.accel_x, foot.accel_z)
        )

        knee  = (thigh_angle - shin_angle)  - self._baseline_knee
        ankle = (shin_angle  - foot_angle)  - self._baseline_ankle
        return knee, ankle
