"""
collect_knee_data.py — Calibrate, collect, and splice knee-only strides.

Runs Phase 0 (calibration) + Phase 1 (segmentation) from the pipeline,
discards ankle data entirely, and saves the time-normalised knee strides
as a .npy file of shape (N, 100).

Usage:
    # Synthetic healthy gait (default):
    python collect_knee_data.py --n-strides 200

    # Large collection:
    python collect_knee_data.py --n-strides 1000 --out training_data/knee_strides.npy

    # With pathology injection:
    python collect_knee_data.py --n-strides 500 --pathology mixed

    # COMPWALK-ACL dataset:
    python collect_knee_data.py --source compwalk --condition acl
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from core.config import SystemConfig
from core.types import SensorPacket
from data_io.source import IMUSource
from dsp.angles import JointAngleComputer
from dsp.filters import apply_butterworth
from phases.phase0_calibration import CalibrationPhase


def collect_knee_strides(
    source: IMUSource,
    config: SystemConfig,
    max_strides: int = 0,
) -> np.ndarray:
    """
    Run calibration → stride collection, return knee-only strides.

    Returns: (N, 100) float32 array of time-normalised knee angle curves.
    """
    angle_computer = JointAngleComputer(config)
    phase0 = CalibrationPhase(config, angle_computer)

    # --- Stride detection state (mirrors Phase 1 logic, knee-only output) ---
    dt_ms = 1000.0 / config.sample_rate_hz
    stride_buf: list[float] = []
    stride_start_ms: float | None = None
    cond_hold_start: float | None = None
    last_boundary_ms: float = -1e9

    raw_knee_strides: list[np.ndarray] = []
    calibrated = False

    n_total_boundaries = 0

    for packet in source.packets():
        t = packet.timestamp_ms

        # --- Phase 0: calibration ---
        if not calibrated:
            if phase0.feed(packet):
                calibrated = True
                print(f"[Collect] Calibration complete.")
            continue

        # --- Compute knee angle (ignore ankle) ---
        knee_deg, _ = angle_computer.update(packet.thigh, packet.shin, packet.foot)

        # Accumulate
        stride_buf.append(knee_deg)
        if stride_start_ms is None:
            stride_start_ms = t

        # --- Heel-strike detection (same triple-condition rule) ---
        foot = packet.foot
        gyro_mag = np.sqrt(foot.gyro_x**2 + foot.gyro_y**2 + foot.gyro_z**2)
        accel_z_ok = abs(abs(foot.accel_z) - 1.0) < config.accel_z_tolerance_g
        cond_met = (
            gyro_mag < config.omega_thresh_dps
            and accel_z_ok
            and abs(knee_deg) < config.knee_near_zero_deg
        )
        in_lockout = (t - last_boundary_ms) < config.lockout_ms

        if cond_met and not in_lockout:
            if cond_hold_start is None:
                cond_hold_start = t
            elif (t - cond_hold_start) >= config.condition_hold_ms:
                # Stride boundary confirmed
                duration = t - (stride_start_ms or t)
                n_total_boundaries += 1

                if config.min_stride_ms <= duration <= config.max_stride_ms and len(stride_buf) >= 10:
                    raw_knee = np.array(stride_buf, dtype=float)

                    # Butterworth low-pass filter
                    filtered = apply_butterworth(
                        raw_knee,
                        config.butterworth_cutoff_hz,
                        config.sample_rate_hz,
                        config.butterworth_order,
                    )

                    # Time-normalise to 100 points
                    normalised = np.interp(
                        np.linspace(0, 1, config.gait_cycle_points),
                        np.linspace(0, 1, len(filtered)),
                        filtered,
                    )
                    raw_knee_strides.append(normalised)

                    n = len(raw_knee_strides)
                    if n % 50 == 0 or n <= 5:
                        print(f"  [Collect] {n} valid knee strides (duration={duration:.0f} ms)")

                # Reset for next stride
                stride_buf = []
                stride_start_ms = t
                last_boundary_ms = t
                cond_hold_start = None

                if max_strides > 0 and len(raw_knee_strides) >= max_strides:
                    break
        else:
            cond_hold_start = None

    if not raw_knee_strides:
        print("[Collect] WARNING: No valid strides detected!")
        return np.empty((0, config.gait_cycle_points), dtype=np.float32)

    result = np.stack(raw_knee_strides).astype(np.float32)  # (N, 100)
    return result


def main():
    p = argparse.ArgumentParser(description="Collect knee-only stride data")
    p.add_argument("--source", choices=["synthetic", "compwalk"], default="synthetic")
    p.add_argument("--pathology", choices=["healthy", "reduced_extension", "reduced_clearance", "mixed"],
                   default="healthy")
    p.add_argument("--condition", choices=["acl", "healthy"], default="acl")
    p.add_argument("--data-root", default="")
    p.add_argument("--subject", default="synthetic_acl")
    p.add_argument("--n-strides", type=int, default=200,
                   help="Number of strides to generate from source (synthetic only)")
    p.add_argument("--max-collect", type=int, default=0,
                   help="Stop after collecting this many valid strides (0 = collect all)")
    p.add_argument("--out", default="training_data/knee_strides.npy",
                   help="Output path for the .npy file")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    config = SystemConfig()

    # --- Build source ---
    if args.source == "synthetic":
        from simulation.synthetic import SyntheticIMUSource
        source = SyntheticIMUSource(
            config=config,
            n_strides=args.n_strides,
            pathology=args.pathology,
            rng_seed=args.seed,
        )
        print(f"[Main] Synthetic source: pathology={args.pathology}, n_strides={args.n_strides}")
    else:
        from adapters.compwalk_acl import COMPWALKACLAdapter
        source = COMPWALKACLAdapter(
            data_root=args.data_root,
            subject_id=args.subject,
            condition=args.condition,
        )
        print(f"[Main] COMPWALK-ACL source: condition={args.condition}, subject={args.subject}")

    # --- Collect ---
    print(f"\n=== Knee-Only Stride Collection ===")
    print(f"Stand still for calibration ({config.calibration_duration_s}s) ...\n")

    data = collect_knee_strides(source, config, max_strides=args.max_collect)

    if data.shape[0] == 0:
        print("No strides collected. Exiting.")
        return

    # --- Save ---
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    np.save(args.out, data)

    print(f"\n=== Collection Complete ===")
    print(f"  Strides : {data.shape[0]}")
    print(f"  Shape   : {data.shape}  (strides x gait_cycle_points)")
    print(f"  Knee    : min={data.min():.1f}°  max={data.max():.1f}°  mean={data.mean():.1f}°")
    print(f"  Saved   : {args.out}")


if __name__ == "__main__":
    main()
