"""
COMPWALK-ACL Dataset Adapter
============================
Dataset: "COMPWALK-ACL" (Nature Scientific Data, 2025)
  92 participants — 25 healthy adults, 27 healthy adolescents,
  40 ACL-injured (pre-surgery) + 27 at 3-month post-reconstruction.
  Sensor system: Xsens Awinda (60 Hz).
  Sensor placements: bilateral thighs, shins, feet (+ pelvis, sternum).

This adapter reads the Xsens Awinda export CSV format and maps the
right-leg sensors (or left if specified) to GaitGuard's three-IMU layout:
    Xsens "Right Upper Leg"  → IMU 1 (thigh)
    Xsens "Right Lower Leg"  → IMU 2 (shin)
    Xsens "Right Foot"       → IMU 3 (foot)

Expected CSV structure (one file per trial):
    Columns (example from Xsens MT Manager export):
        PacketCounter, SampleTimeFine,
        Acc_X_RUL, Acc_Y_RUL, Acc_Z_RUL, Gyr_X_RUL, Gyr_Y_RUL, Gyr_Z_RUL,
        Acc_X_RLL, Acc_Y_RLL, Acc_Z_RLL, Gyr_X_RLL, Gyr_Y_RLL, Gyr_Z_RLL,
        Acc_X_RF,  Acc_Y_RF,  Acc_Z_RF,  Gyr_X_RF,  Gyr_Y_RF,  Gyr_Z_RF,
        ...

If the dataset is not available on disk, the adapter falls back to a
built-in synthetic generator that mimics COMPWALK-ACL's ACL-pathology
characteristics (reduced peak knee extension, altered swing phase timing).

Usage:
    from adapters.compwalk_acl import COMPWALKACLAdapter

    # With real data:
    source = COMPWALKACLAdapter(data_root="/data/compwalk_acl/", subject_id="S01")

    # Without real data (synthetic fallback):
    source = COMPWALKACLAdapter(data_root="", subject_id="synthetic_acl")

    pipeline = GaitPipeline(config, source)
    pipeline.run()
"""
from __future__ import annotations

import os
import glob
from typing import Iterator, List, Optional

import numpy as np
import pandas as pd

from adapters.base import DatasetAdapter
from core.config import SystemConfig
from core.types import IMUReading, SensorPacket


# ---------------------------------------------------------------------------
# Column name mapping for Xsens Awinda CSV export
# ---------------------------------------------------------------------------

_XSENS_COLS = {
    "time_s"   : "SampleTimeFine",     # raw counter; divide by 1e4 for seconds
    "thigh"    : dict(
        ax="Acc_X_RUL", ay="Acc_Y_RUL", az="Acc_Z_RUL",
        gx="Gyr_X_RUL", gy="Gyr_Y_RUL", gz="Gyr_Z_RUL",
    ),
    "shin"     : dict(
        ax="Acc_X_RLL", ay="Acc_Y_RLL", az="Acc_Z_RLL",
        gx="Gyr_X_RLL", gy="Gyr_Y_RLL", gz="Gyr_Z_RLL",
    ),
    "foot"     : dict(
        ax="Acc_X_RF",  ay="Acc_Y_RF",  az="Acc_Z_RF",
        gx="Gyr_X_RF",  gy="Gyr_Y_RF",  gz="Gyr_Z_RF",
    ),
}

# Xsens accelerometer unit is m/s² — convert to g (1 g = 9.81 m/s²)
_ACCEL_TO_G = 1.0 / 9.81


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class COMPWALKACLAdapter(DatasetAdapter):
    """
    Replays a COMPWALK-ACL trial as a SensorPacket stream.

    Parameters
    ----------
    data_root   : Root directory of the COMPWALK-ACL dataset.
                  If empty or the trial file is not found, synthetic data
                  is generated automatically.
    subject_id  : Subject folder name (e.g. "S01") or "synthetic_*".
    side        : "right" (default) or "left".
    condition   : "acl" (default) or "healthy". Affects synthetic generation.
    sample_rate_hz: Target output sample rate (resamples if needed).
    """

    def __init__(
        self,
        data_root: str = "",
        subject_id: str = "synthetic_acl",
        side: str = "right",
        condition: str = "acl",
        sample_rate_hz: float = 50.0,
    ):
        self._side = side.lower()
        self._condition = condition.lower()
        self._sr = sample_rate_hz
        self._packets: List[SensorPacket] = []
        super().__init__(data_root, subject_id)

    # ------------------------------------------------------------------
    # DatasetAdapter interface
    # ------------------------------------------------------------------

    def _load(self) -> None:
        csv_path = self._find_csv()
        if csv_path:
            self._packets = self._parse_csv(csv_path)
            print(f"[COMPWALK-ACL] Loaded {len(self._packets)} packets from {csv_path}")
        else:
            print(f"[COMPWALK-ACL] Trial CSV not found — generating synthetic {self._condition} data.")
            self._packets = _generate_synthetic_packets(
                condition=self._condition,
                n_strides=40,
                sample_rate_hz=self._sr,
            )

    def packets(self) -> Iterator[SensorPacket]:
        yield from self._packets

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------

    def _find_csv(self) -> Optional[str]:
        if not self.data_root or not os.path.isdir(self.data_root):
            return None
        pattern = os.path.join(self.data_root, self.subject_id, "**", "*.csv")
        matches = glob.glob(pattern, recursive=True)
        return matches[0] if matches else None

    def _parse_csv(self, path: str) -> List[SensorPacket]:
        df = pd.read_csv(path, comment="#")

        # Adapt column names for the chosen side
        cols = _XSENS_COLS if self._side == "right" else _left_side_cols()

        time_col = cols["time_s"]
        if time_col not in df.columns:
            raise ValueError(f"Expected time column '{time_col}' not found. "
                             f"Available: {list(df.columns[:10])}")

        # Convert time to milliseconds
        raw_time = df[time_col].to_numpy(dtype=float)
        t_ms = (raw_time / raw_time[0] - 1.0) * 1000.0   # relative ms from 0

        packets = []
        for i in range(len(df)):
            thigh = self._row_to_imu(df, i, cols["thigh"], t_ms[i])
            shin  = self._row_to_imu(df, i, cols["shin"],  t_ms[i])
            foot  = self._row_to_imu(df, i, cols["foot"],  t_ms[i])
            packets.append(SensorPacket(thigh=thigh, shin=shin, foot=foot, timestamp_ms=t_ms[i]))

        return packets

    @staticmethod
    def _row_to_imu(df: pd.DataFrame, i: int, col_map: dict, t_ms: float) -> IMUReading:
        return IMUReading(
            accel_x    = float(df[col_map["ax"]].iloc[i]) * _ACCEL_TO_G,
            accel_y    = float(df[col_map["ay"]].iloc[i]) * _ACCEL_TO_G,
            accel_z    = float(df[col_map["az"]].iloc[i]) * _ACCEL_TO_G,
            gyro_x     = float(df[col_map["gx"]].iloc[i]),
            gyro_y     = float(df[col_map["gy"]].iloc[i]),
            gyro_z     = float(df[col_map["gz"]].iloc[i]),
            timestamp_ms = t_ms,
        )


def _left_side_cols() -> dict:
    """Return column mapping for the left leg."""
    c = {k: dict(v) if isinstance(v, dict) else v for k, v in _XSENS_COLS.items()}
    for seg in ("thigh", "shin", "foot"):
        for key, val in c[seg].items():
            c[seg][key] = val.replace("R", "L", 1)
    return c


# ---------------------------------------------------------------------------
# Synthetic COMPWALK-ACL–style packet generator
# ---------------------------------------------------------------------------

def _generate_synthetic_packets(
    condition: str,
    n_strides: int = 40,
    sample_rate_hz: float = 50.0,
    rng_seed: int = 0,
) -> List[SensorPacket]:
    """
    Generate realistic synthetic SensorPackets that mimic COMPWALK-ACL data.

    ACL condition characteristics (vs healthy):
      - Reduced peak knee flexion during swing (~45° vs ~60°)
      - Slower cadence (~95 vs ~110 steps/min)
      - Increased ankle plantarflexion compensation at push-off
    """
    rng = np.random.default_rng(rng_seed)
    dt_ms = 1000.0 / sample_rate_hz

    # Stride duration parameters (ms)
    if condition == "acl":
        stride_mean_ms, stride_std_ms = 1200.0, 80.0
        peak_knee_flex   = 45.0    # deg (healthy ≈ 60)
        push_off_pf      = -25.0   # deg (increased compensation)
    else:
        stride_mean_ms, stride_std_ms = 1050.0, 60.0
        peak_knee_flex   = 60.0
        push_off_pf      = -20.0

    packets: List[SensorPacket] = []
    t_ms = 0.0

    for _ in range(n_strides):
        stride_ms = max(400.0, rng.normal(stride_mean_ms, stride_std_ms))
        n_samples = int(stride_ms / dt_ms)
        phase = np.linspace(0, 1, n_samples)

        # ---- Knee angle profile (thigh–shin) -------------------------
        knee = (
              5.0 * np.ones(n_samples)
            + 10.0 * np.sin(np.pi * phase / 0.2) * (phase < 0.2)
            + peak_knee_flex * np.sin(np.pi * (phase - 0.4) / 0.4) * ((phase >= 0.4) & (phase < 0.8))
        )
        knee += rng.normal(0, 1.5, n_samples)

        # ---- Ankle angle profile (shin–foot) -------------------------
        ankle = (
            -5.0  * np.sin(np.pi * phase / 0.15) * (phase < 0.15)
            + 12.0 * np.sin(np.pi * (phase - 0.15) / 0.45) * ((phase >= 0.15) & (phase < 0.6))
            + push_off_pf * np.sin(np.pi * (phase - 0.55) / 0.15) * ((phase >= 0.55) & (phase < 0.70))
        )
        ankle += rng.normal(0, 1.0, n_samples)

        # ---- Back-compute IMU readings from angle profiles -----------
        thigh_ang = knee + rng.normal(5, 2, n_samples)
        shin_ang  = thigh_ang - knee
        foot_ang  = shin_ang  - ankle

        # Gyro from gradient; zero foot during flat-foot dwell (first 10%)
        flat_s = max(8, int(0.20 * n_samples))
        gyro_th = np.gradient(thigh_ang, dt_ms / 1000.0)
        gyro_sh = np.gradient(shin_ang,  dt_ms / 1000.0)
        gyro_ft = np.gradient(foot_ang,  dt_ms / 1000.0)
        gyro_ft[:flat_s] = 0.0

        n_a, n_g = 0.01, 0.5
        for j in range(n_samples):
            ts = t_ms + j * dt_ms
            ax_th = float(np.sin(np.radians(thigh_ang[j])))
            az_th = float(np.cos(np.radians(thigh_ang[j])))
            ax_sh = float(np.sin(np.radians(shin_ang[j])))
            az_sh = float(np.cos(np.radians(shin_ang[j])))
            ax_ft = float(np.sin(np.radians(foot_ang[j])))
            az_ft = float(np.cos(np.radians(foot_ang[j])))

            thigh = IMUReading(
                ax_th + rng.normal(0, n_a), 0, az_th + rng.normal(0, n_a),
                float(gyro_th[j]) + rng.normal(0, n_g), 0, 0, ts,
            )
            shin = IMUReading(
                ax_sh + rng.normal(0, n_a), 0, az_sh + rng.normal(0, n_a),
                float(gyro_sh[j]) + rng.normal(0, n_g), 0, 0, ts,
            )
            foot = IMUReading(
                ax_ft + rng.normal(0, n_a), 0, az_ft + rng.normal(0, n_a),
                float(gyro_ft[j]) + rng.normal(0, n_g), 0, 0, ts,
            )
            packets.append(SensorPacket(thigh=thigh, shin=shin, foot=foot, timestamp_ms=ts))

        t_ms += stride_ms

    return packets
