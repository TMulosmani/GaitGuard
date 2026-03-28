"""
SyntheticIMUSource — generates healthy or pathological gait packets for testing.

Used to:
  1. Demo the full pipeline without hardware.
  2. Verify that Phase 3 haptic triggers fire correctly for injected pathologies.
  3. Generate training data for the LSTM (see ml/train.py).

Pathology modes
---------------
  "healthy"           Normal gait
  "reduced_extension" Insufficient knee extension at heel strike (→ TWO_SHORT haptic)
  "reduced_clearance" Reduced foot clearance during swing (→ ONE_LONG haptic)
  "mixed"             Both pathologies present
"""
from __future__ import annotations

from typing import Iterator, List

import numpy as np

from core.config import SystemConfig
from core.types import IMUReading, SensorPacket
from data_io.source import IMUSource


class SyntheticIMUSource(IMUSource):
    """
    Generates a stream of SensorPackets from parametric gait waveforms.

    Parameters
    ----------
    config      : SystemConfig (used for sample rate)
    n_strides   : Number of strides to generate
    pathology   : "healthy" | "reduced_extension" | "reduced_clearance" | "mixed"
    rng_seed    : For reproducibility
    """

    def __init__(
        self,
        config: SystemConfig,
        n_strides: int = 60,
        pathology: str = "healthy",
        rng_seed: int = 42,
    ):
        self._config    = config
        self._n_strides = n_strides
        self._pathology = pathology
        self._rng       = np.random.default_rng(rng_seed)
        self._packets: List[SensorPacket] = self._build()

    # ------------------------------------------------------------------

    def packets(self) -> Iterator[SensorPacket]:
        yield from self._packets

    # ------------------------------------------------------------------

    def _build(self) -> List[SensorPacket]:
        sr   = self._config.sample_rate_hz
        dt   = 1000.0 / sr  # ms per sample
        p    = self._pathology
        rng  = self._rng

        # Cadence: ~110 steps/min → ~545 ms/stride → ~1090 ms/gait cycle
        stride_ms = rng.normal(1090, 60)

        all_packets: List[SensorPacket] = []
        t_ms = 0.0

        # --- Standing-still phase (exactly calibration_duration_s) ---
        stand_samples = int(self._config.calibration_duration_s * sr)
        for j in range(stand_samples):
            ts = t_ms + j * dt
            # Standing: knee≈0, ankle≈0, thigh≈10°, shin≈10°, foot≈10°
            base_ang = 10.0
            imu_stand = IMUReading(
                float(np.sin(np.radians(base_ang))) + rng.normal(0, 0.005),
                0.0,
                float(np.cos(np.radians(base_ang))) + rng.normal(0, 0.005),
                rng.normal(0, 0.1),   # near-zero gyro
                0.0, 0.0,
                ts,
            )
            all_packets.append(SensorPacket(
                thigh=imu_stand, shin=imu_stand, foot=imu_stand, timestamp_ms=ts,
            ))
        t_ms += stand_samples * dt

        for _ in range(self._n_strides):
            smpl = max(20, int(stride_ms / dt))
            phase = np.linspace(0, 1, smpl)

            knee  = self._knee_profile(phase, p, rng)
            ankle = self._ankle_profile(phase, p, rng)

            # Absolute segment angles (arbitrary reference)
            thigh_ang = knee  + rng.normal(10, 1, smpl)
            shin_ang  = thigh_ang - knee
            foot_ang  = shin_ang  - ankle

            # Gyro = finite difference of angle (deg/s)
            # At heel-strike (first ~100 ms = flat-foot dwell), zero the foot gyro
            # so stride-boundary detection can trigger reliably.
            flat_samples = max(8, int(0.20 * smpl))  # first 20 % of stride (flat-foot dwell)

            gyro_th = np.gradient(thigh_ang, dt / 1000.0)
            gyro_sh = np.gradient(shin_ang,  dt / 1000.0)
            gyro_ft = np.gradient(foot_ang,  dt / 1000.0)
            gyro_ft[:flat_samples] = 0.0   # flat-foot dwell

            na, ng = 0.01, 0.3

            def make_imu(ang, gx, ts):
                return IMUReading(
                    float(np.sin(np.radians(ang))) + rng.normal(0, na),
                    0.0,
                    float(np.cos(np.radians(ang))) + rng.normal(0, na),
                    float(gx) + rng.normal(0, ng),
                    0.0, 0.0,
                    ts,
                )

            for j in range(smpl):
                ts = t_ms + j * dt
                all_packets.append(SensorPacket(
                    thigh = make_imu(thigh_ang[j], gyro_th[j], ts),
                    shin  = make_imu(shin_ang[j],  gyro_sh[j], ts),
                    foot  = make_imu(foot_ang[j],  gyro_ft[j], ts),
                    timestamp_ms = ts,
                ))

            t_ms += stride_ms
            stride_ms = rng.normal(1090, 60)  # slight stride-to-stride variation

        return all_packets

    # ------------------------------------------------------------------
    # Waveform templates
    # ------------------------------------------------------------------

    @staticmethod
    def _knee_profile(phase: np.ndarray, pathology: str, rng) -> np.ndarray:
        """Knee flexion angle (degrees) across the gait cycle."""
        heel_strike_flex = 0.0 if pathology in ("reduced_extension", "mixed") else 2.0
        peak_swing_flex  = 55.0 if pathology in ("reduced_extension", "mixed") else 60.0

        k = (
              heel_strike_flex * np.ones_like(phase)
            + 12.0 * np.sin(np.pi * phase / 0.2)  * (phase < 0.2)
            + (peak_swing_flex - heel_strike_flex) * np.sin(np.pi * (phase - 0.4) / 0.4)
              * ((phase >= 0.4) & (phase < 0.8))
        )
        k += rng.normal(0, 1.5, len(phase))
        return np.clip(k, 0, 75)

    @staticmethod
    def _ankle_profile(phase: np.ndarray, pathology: str, rng) -> np.ndarray:
        """Ankle dorsiflexion/plantarflexion angle (degrees)."""
        push_off_pf = -15.0 if pathology in ("reduced_clearance", "mixed") else -20.0
        df_peak     =  10.0 if pathology in ("reduced_clearance", "mixed") else  13.0

        a = (
            -5.0    * np.sin(np.pi * phase / 0.15) * (phase < 0.15)
            + df_peak * np.sin(np.pi * (phase - 0.15) / 0.45) * ((phase >= 0.15) & (phase < 0.6))
            + push_off_pf * np.sin(np.pi * (phase - 0.55) / 0.15) * ((phase >= 0.55) & (phase < 0.70))
        )
        a += rng.normal(0, 1.0, len(phase))
        return a
