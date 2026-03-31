#!/usr/bin/env python3
"""
collect_knee_live.py — Live knee-angle collection from hardware.
Pure Python — no numpy/scipy required (runs on QNX Pi).

Listens for ESP#1 (thigh/shin) over WiFi UDP, computes knee angle,
detects stride boundaries, and saves time-normalised knee strides as JSON.

Usage:
    python3 collect_knee_live.py
    python3 collect_knee_live.py --duration 60 --out knee_strides.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import signal
import socket
import struct
import sys
import threading
import time

# ---------------------------------------------------------------------------
# UDP config (must match esp/config.h)
# ---------------------------------------------------------------------------
PORT_IMU_THIGH_SHIN = 5001
PORT_IMU_FOOT       = 5002
DEVICE_ID_THIGH_SHIN = 0x01
DEVICE_ID_FOOT       = 0x02

ACCEL_SCALE_MPU = 8192.0
GYRO_SCALE_MPU  = 65.5
ACCEL_SCALE_QMI = 8192.0
GYRO_SCALE_QMI  = 64.0

# Pipeline config (mirrors core/config.py)
SAMPLE_RATE_HZ       = 50.0
CALIBRATION_DURATION  = 2.0   # seconds
COMPLEMENTARY_ALPHA   = 0.98
GAIT_CYCLE_POINTS     = 100
OMEGA_THRESH_DPS      = 15.0
ACCEL_Z_TOL_G         = 0.15
KNEE_NEAR_ZERO_DEG    = 15.0
CONDITION_HOLD_MS     = 80.0
LOCKOUT_MS            = 300.0
MIN_STRIDE_MS         = 400.0
MAX_STRIDE_MS         = 2500.0


# ---------------------------------------------------------------------------
# Complementary filter
# ---------------------------------------------------------------------------
class ComplementaryFilter:
    def __init__(self, alpha: float, sample_rate: float):
        self._alpha = alpha
        self._dt = 1.0 / sample_rate
        self._angle = 0.0
        self._initialized = False

    def reset(self, initial: float = 0.0):
        self._angle = initial
        self._initialized = True

    def update(self, gyro_rate_dps: float, accel_angle_deg: float) -> float:
        if not self._initialized:
            self._angle = accel_angle_deg
            self._initialized = True
            return self._angle
        gyro_pred = self._angle + gyro_rate_dps * self._dt
        self._angle = self._alpha * gyro_pred + (1 - self._alpha) * accel_angle_deg
        return self._angle


def accel_to_angle(ax: float, az: float) -> float:
    return math.degrees(math.atan2(ax, az))


def smooth(data: list[float], window: int = 8) -> list[float]:
    """Dual-pass moving average (poor-man's low-pass)."""
    if len(data) < window:
        return data[:]
    out = []
    half = window // 2
    for i in range(len(data)):
        lo = max(0, i - half)
        hi = min(len(data), i + half + 1)
        out.append(sum(data[lo:hi]) / (hi - lo))
    # second pass
    out2 = []
    for i in range(len(out)):
        lo = max(0, i - half)
        hi = min(len(out), i + half + 1)
        out2.append(sum(out[lo:hi]) / (hi - lo))
    return out2


def time_normalise(data: list[float], n_points: int) -> list[float]:
    """Linear interpolation to fixed-length curve."""
    if len(data) < 2:
        return [0.0] * n_points
    result = []
    for i in range(n_points):
        t = i / (n_points - 1) * (len(data) - 1)
        idx = int(t)
        frac = t - idx
        if idx >= len(data) - 1:
            result.append(data[-1])
        else:
            result.append(data[idx] * (1 - frac) + data[idx + 1] * frac)
    return result


# ---------------------------------------------------------------------------
# Main collector
# ---------------------------------------------------------------------------
class KneeCollector:
    def __init__(self, duration_s: float = 0, use_foot: bool = True):
        self.duration_s = duration_s
        self.use_foot = use_foot
        self.running = True

        # Filters
        self.cf_thigh = ComplementaryFilter(COMPLEMENTARY_ALPHA, SAMPLE_RATE_HZ)
        self.cf_shin  = ComplementaryFilter(COMPLEMENTARY_ALPHA, SAMPLE_RATE_HZ)

        # Calibration
        self.calibrated = False
        self.cal_thigh: list[float] = []
        self.cal_shin: list[float] = []
        self.cal_needed = int(CALIBRATION_DURATION * SAMPLE_RATE_HZ)
        self.baseline_knee = 0.0

        # Stride detection
        self.stride_buf: list[float] = []
        self.stride_start_t: float | None = None
        self.cond_hold_start: float | None = None
        self.last_boundary_t: float = -1e9

        # Results
        self.strides: list[list[float]] = []
        self.all_knee: list[float] = []
        self.all_ts: list[float] = []

        # Foot data (optional)
        self.latest_foot: tuple | None = None
        self.foot_lock = threading.Lock()
        self.foot_connected = False

        # Sockets
        self.sock1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock1.bind(("0.0.0.0", PORT_IMU_THIGH_SHIN))
        self.sock1.settimeout(0.1)

        self.sock2 = None
        if use_foot:
            self.sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock2.bind(("0.0.0.0", PORT_IMU_FOOT))
            self.sock2.settimeout(0.1)

    def _foot_recv_loop(self):
        while self.running and self.sock2:
            try:
                data, addr = self.sock2.recvfrom(64)
            except socket.timeout:
                continue
            if len(data) < 15 or data[0] != DEVICE_ID_FOOT:
                continue
            if not self.foot_connected:
                self.foot_connected = True
                print(f"  [Foot ESP#2 connected from {addr[0]}]")
            vals = struct.unpack_from(">hhhhhh", data, 3)
            with self.foot_lock:
                self.latest_foot = tuple(v / s for v, s in zip(
                    vals, [ACCEL_SCALE_QMI]*3 + [GYRO_SCALE_QMI]*3))

    def _detect_boundary(self, knee_deg: float, t_ms: float) -> bool:
        in_lockout = (t_ms - self.last_boundary_t) < LOCKOUT_MS
        knee_ok = abs(knee_deg) < KNEE_NEAR_ZERO_DEG

        foot_ok = True
        with self.foot_lock:
            if self.latest_foot is not None:
                ax, ay, az, gx, gy, gz = self.latest_foot
                gyro_mag = math.sqrt(gx**2 + gy**2 + gz**2)
                foot_ok = (gyro_mag < OMEGA_THRESH_DPS and
                           abs(abs(az) - 1.0) < ACCEL_Z_TOL_G)

        cond_met = knee_ok and foot_ok and not in_lockout

        if cond_met:
            if self.cond_hold_start is None:
                self.cond_hold_start = t_ms
            elif (t_ms - self.cond_hold_start) >= CONDITION_HOLD_MS:
                self.cond_hold_start = None
                return True
        else:
            self.cond_hold_start = None
        return False

    def _finalise_stride(self, t_ms: float):
        if not self.stride_buf or self.stride_start_t is None:
            return
        duration = t_ms - self.stride_start_t

        if MIN_STRIDE_MS <= duration <= MAX_STRIDE_MS and len(self.stride_buf) >= 10:
            filtered = smooth(self.stride_buf)
            normalised = time_normalise(filtered, GAIT_CYCLE_POINTS)
            self.strides.append(normalised)
            n = len(self.strides)
            print(f"  Stride {n:3d} spliced  ({duration:.0f} ms, {len(self.stride_buf)} samples)")

        self.stride_buf = []
        self.stride_start_t = t_ms
        self.last_boundary_t = t_ms

    def run(self):
        start_time = time.time()

        if self.use_foot and self.sock2:
            threading.Thread(target=self._foot_recv_loop, daemon=True).start()

        print(f"\n{'='*50}")
        print(f"  KNEE DATA COLLECTION")
        print(f"{'='*50}")
        print(f"  Listening on UDP :{PORT_IMU_THIGH_SHIN} for thigh/shin...")
        if self.use_foot:
            print(f"  Listening on UDP :{PORT_IMU_FOOT} for foot (optional)...")
        print(f"  Waiting for ESP#1...\n")

        esp_connected = False

        while self.running:
            if self.duration_s > 0 and (time.time() - start_time) > self.duration_s + CALIBRATION_DURATION + 5:
                break

            try:
                data, addr = self.sock1.recvfrom(64)
            except socket.timeout:
                continue

            if len(data) < 27 or data[0] != DEVICE_ID_THIGH_SHIN:
                continue

            if not esp_connected:
                esp_connected = True
                print(f"  [ESP#1 connected from {addr[0]}]")
                print(f"\n  >>> STAND STILL for {CALIBRATION_DURATION:.0f} seconds <<<\n")

            t_ms = (time.time() - start_time) * 1000.0

            # Parse thigh + shin
            vals = struct.unpack_from(">hhhhhhhhhhhh", data, 3)
            thigh_ax, thigh_ay, thigh_az = vals[0]/ACCEL_SCALE_MPU, vals[1]/ACCEL_SCALE_MPU, vals[2]/ACCEL_SCALE_MPU
            thigh_gx = vals[3]/GYRO_SCALE_MPU
            shin_ax, shin_ay, shin_az = vals[6]/ACCEL_SCALE_MPU, vals[7]/ACCEL_SCALE_MPU, vals[8]/ACCEL_SCALE_MPU
            shin_gx = vals[9]/GYRO_SCALE_MPU

            thigh_accel_ang = accel_to_angle(thigh_ax, thigh_az)
            shin_accel_ang = accel_to_angle(shin_ax, shin_az)

            # --- CALIBRATION ---
            if not self.calibrated:
                self.cal_thigh.append(thigh_accel_ang)
                self.cal_shin.append(shin_accel_ang)
                remaining = self.cal_needed - len(self.cal_thigh)
                if remaining > 0 and remaining % 25 == 0:
                    print(f"  Calibrating... {remaining / SAMPLE_RATE_HZ:.1f}s left")
                if len(self.cal_thigh) >= self.cal_needed:
                    base_thigh = sum(self.cal_thigh) / len(self.cal_thigh)
                    base_shin = sum(self.cal_shin) / len(self.cal_shin)
                    self.baseline_knee = base_thigh - base_shin
                    self.cf_thigh.reset(base_thigh)
                    self.cf_shin.reset(base_shin)
                    self.calibrated = True
                    print(f"  Calibration done! (baseline = {self.baseline_knee:.1f}°)")
                    if self.duration_s > 0:
                        print(f"\n  >>> WALK NOW for {self.duration_s:.0f} seconds <<<\n")
                    else:
                        print(f"\n  >>> WALK NOW — press Ctrl+C when done <<<\n")
                continue

            # --- KNEE ANGLE ---
            thigh_ang = self.cf_thigh.update(thigh_gx, thigh_accel_ang)
            shin_ang = self.cf_shin.update(shin_gx, shin_accel_ang)
            knee_deg = (thigh_ang - shin_ang) - self.baseline_knee

            self.all_knee.append(knee_deg)
            self.all_ts.append(t_ms)

            # Accumulate
            self.stride_buf.append(knee_deg)
            if self.stride_start_t is None:
                self.stride_start_t = t_ms

            # --- STRIDE DETECTION ---
            if self._detect_boundary(knee_deg, t_ms):
                self._finalise_stride(t_ms)

            # Duration check
            if self.duration_s > 0:
                walk_elapsed = time.time() - start_time - CALIBRATION_DURATION
                if walk_elapsed >= self.duration_s:
                    print(f"\n  Duration reached ({self.duration_s:.0f}s).")
                    break

        self.running = False
        self.sock1.close()
        if self.sock2:
            self.sock2.close()

    def save(self, out_path: str):
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        result = {
            "strides": self.strides,
            "n_strides": len(self.strides),
            "gait_cycle_points": GAIT_CYCLE_POINTS,
            "raw_knee_angles": self.all_knee,
            "raw_timestamps_ms": self.all_ts,
            "n_raw_samples": len(self.all_knee),
            "baseline_knee_deg": self.baseline_knee,
        }

        with open(out_path, "w") as f:
            json.dump(result, f)

        if self.strides:
            all_vals = [v for s in self.strides for v in s]
            mn = min(all_vals)
            mx = max(all_vals)
            avg = sum(all_vals) / len(all_vals)
            print(f"\n  Spliced strides saved → {out_path}")
            print(f"    Strides : {len(self.strides)}")
            print(f"    Points  : {GAIT_CYCLE_POINTS} per stride")
            print(f"    Knee    : min={mn:.1f}°  max={mx:.1f}°  mean={avg:.1f}°")
        else:
            print("\n  WARNING: No valid strides detected.")

        if self.all_knee:
            print(f"    Raw samples: {len(self.all_knee)}")


def main():
    p = argparse.ArgumentParser(description="Collect knee angle data from live hardware")
    p.add_argument("--duration", type=float, default=0,
                   help="Walking duration in seconds (0 = until Ctrl+C)")
    p.add_argument("--out", default="knee_strides.json",
                   help="Output JSON file path")
    p.add_argument("--no-foot", action="store_true",
                   help="Don't listen for foot ESP#2")
    args = p.parse_args()

    collector = KneeCollector(duration_s=args.duration, use_foot=not args.no_foot)

    def shutdown(sig, frame):
        print("\n\n  Stopping collection...")
        collector.running = False
    signal.signal(signal.SIGINT, shutdown)

    collector.run()
    collector.save(args.out)

    print(f"\n{'='*50}")
    print(f"  DONE — {len(collector.strides)} strides collected")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
