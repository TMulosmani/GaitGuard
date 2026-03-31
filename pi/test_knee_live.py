#!/usr/bin/env python3
"""
test_knee_live.py — Live knee gait test with haptic feedback.

Loads the average knee stride profile, then monitors your walking in
real-time. Each detected stride is compared to the average — if the
deviation is too large, the haptic motor shakes.

Pure Python, no numpy/scipy needed.

Usage:
    python3 test_knee_live.py
    python3 test_knee_live.py --profile knee_profile.json
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
# Config
# ---------------------------------------------------------------------------
PORT_IMU_THIGH_SHIN = 5001
PORT_IMU_FOOT       = 5002
PORT_HAPTIC_CMD     = 5003
DEVICE_ID_THIGH_SHIN = 0x01
DEVICE_ID_FOOT       = 0x02

ACCEL_SCALE_MPU = 8192.0
GYRO_SCALE_MPU  = 65.5
ACCEL_SCALE_QMI = 8192.0
GYRO_SCALE_QMI  = 64.0

SAMPLE_RATE_HZ      = 50.0
CALIBRATION_DURATION = 2.0
COMPLEMENTARY_ALPHA  = 0.98
GAIT_CYCLE_POINTS    = 100
KNEE_NEAR_ZERO_DEG   = 15.0
OMEGA_THRESH_DPS     = 15.0
ACCEL_Z_TOL_G        = 0.15
CONDITION_HOLD_MS    = 80.0
LOCKOUT_MS           = 300.0
MIN_STRIDE_MS        = 400.0
MAX_STRIDE_MS        = 2500.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class ComplementaryFilter:
    def __init__(self, alpha, sr):
        self._alpha = alpha
        self._dt = 1.0 / sr
        self._angle = 0.0
        self._init = False

    def reset(self, val=0.0):
        self._angle = val
        self._init = True

    def update(self, gyro, accel_ang):
        if not self._init:
            self._angle = accel_ang
            self._init = True
            return self._angle
        gp = self._angle + gyro * self._dt
        self._angle = self._alpha * gp + (1 - self._alpha) * accel_ang
        return self._angle


def accel_to_angle(ax, az):
    return math.degrees(math.atan2(ax, az))


def smooth(data, window=8):
    if len(data) < window:
        return data[:]
    half = window // 2
    out = []
    for i in range(len(data)):
        lo, hi = max(0, i - half), min(len(data), i + half + 1)
        out.append(sum(data[lo:hi]) / (hi - lo))
    out2 = []
    for i in range(len(out)):
        lo, hi = max(0, i - half), min(len(out), i + half + 1)
        out2.append(sum(out[lo:hi]) / (hi - lo))
    return out2


def time_normalise(data, n):
    if len(data) < 2:
        return [0.0] * n
    result = []
    for i in range(n):
        t = i / (n - 1) * (len(data) - 1)
        idx = int(t)
        frac = t - idx
        if idx >= len(data) - 1:
            result.append(data[-1])
        else:
            result.append(data[idx] * (1 - frac) + data[idx + 1] * frac)
    return result


def mean_abs_dev(stride, reference):
    total = 0.0
    for a, b in zip(stride, reference):
        total += abs(a - b)
    return total / len(stride)


# ---------------------------------------------------------------------------
# Haptic sender
# ---------------------------------------------------------------------------
class HapticSender:
    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._esp1_ip = None

    def set_ip(self, ip):
        self._esp1_ip = ip

    def shake(self):
        if not self._esp1_ip:
            return
        # TWO_SHORT = 1, ONE_LONG = 2, THREE_SHORT = 3
        self._sock.sendto(struct.pack("BB", 3, 255), (self._esp1_ip, PORT_HAPTIC_CMD))

    def close(self):
        self._sock.close()


# ---------------------------------------------------------------------------
# Live test
# ---------------------------------------------------------------------------
class KneeTest:
    def __init__(self, profile: dict):
        self.mean_knee = profile["mean_knee"]
        self.threshold = profile["threshold_deg"]
        self.running = True

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

        # Foot data
        self.latest_foot: tuple | None = None
        self.foot_lock = threading.Lock()

        # Stats
        self.n_good = 0
        self.n_bad = 0

        # Haptic
        self.haptic = HapticSender()

        # Sockets
        self.sock1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        self.sock1.bind(("0.0.0.0", PORT_IMU_THIGH_SHIN))
        self.sock1.settimeout(0.1)

        self.sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        self.sock2.bind(("0.0.0.0", PORT_IMU_FOOT))
        self.sock2.settimeout(0.1)

    def _foot_recv_loop(self):
        while self.running:
            try:
                data, addr = self.sock2.recvfrom(64)
            except socket.timeout:
                continue
            if len(data) < 15 or data[0] != DEVICE_ID_FOOT:
                continue
            vals = struct.unpack_from(">hhhhhh", data, 3)
            with self.foot_lock:
                self.latest_foot = tuple(v / s for v, s in zip(
                    vals, [ACCEL_SCALE_QMI]*3 + [GYRO_SCALE_QMI]*3))

    def _detect_boundary(self, knee_deg, t_ms):
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

    def _score_stride(self, t_ms):
        if not self.stride_buf or self.stride_start_t is None:
            return
        duration = t_ms - self.stride_start_t

        if MIN_STRIDE_MS <= duration <= MAX_STRIDE_MS and len(self.stride_buf) >= 10:
            filtered = smooth(self.stride_buf)
            normalised = time_normalise(filtered, GAIT_CYCLE_POINTS)
            rng = max(normalised) - min(normalised)

            # Skip low-motion strides (not a real step)
            if rng < 5.0:
                self.stride_buf = []
                self.stride_start_t = t_ms
                self.last_boundary_t = t_ms
                return

            mad = mean_abs_dev(normalised, self.mean_knee)
            stride_num = self.n_good + self.n_bad + 1

            if mad > self.threshold:
                self.n_bad += 1
                self.haptic.shake()
                print(f"  Stride {stride_num:3d}  MAD={mad:5.1f}°  threshold={self.threshold:.1f}°"
                      f"  \033[91m██ SHAKE ██\033[0m")
            else:
                self.n_good += 1
                print(f"  Stride {stride_num:3d}  MAD={mad:5.1f}°  threshold={self.threshold:.1f}°"
                      f"  \033[92m✓ OK\033[0m")

        self.stride_buf = []
        self.stride_start_t = t_ms
        self.last_boundary_t = t_ms

    def run(self):
        start_time = time.time()
        threading.Thread(target=self._foot_recv_loop, daemon=True).start()

        print(f"\n{'='*55}")
        print(f"  KNEE GAIT TEST — LIVE")
        print(f"  Profile: {len(self.mean_knee)} pts, threshold={self.threshold:.1f}°")
        print(f"{'='*55}")
        print(f"  Waiting for ESP#1...\n")

        esp_connected = False

        while self.running:
            try:
                data, addr = self.sock1.recvfrom(64)
            except socket.timeout:
                continue
            if len(data) < 27 or data[0] != DEVICE_ID_THIGH_SHIN:
                continue

            if not esp_connected:
                esp_connected = True
                self.haptic.set_ip(addr[0])
                connect_time = time.time()
                print(f"  [ESP#1 connected from {addr[0]}]")
                print(f"  Motor test in 5 seconds...")
                print(f"\n  >>> STAND STILL for {CALIBRATION_DURATION:.0f} seconds <<<\n")
                # Schedule motor test: shake for ~1 second after 5s
                def _motor_test():
                    time.sleep(5.0)
                    if self.running:
                        print("  \033[93m>>> MOTOR TEST — shaking for 1 second <<<\033[0m")
                        end = time.time() + 1.0
                        while time.time() < end and self.running:
                            self.haptic.shake()
                            time.sleep(0.15)
                        print("  Motor test done.\n")
                threading.Thread(target=_motor_test, daemon=True).start()

            t_ms = (time.time() - start_time) * 1000.0
            vals = struct.unpack_from(">hhhhhhhhhhhh", data, 3)
            thigh_ax, thigh_az = vals[0]/ACCEL_SCALE_MPU, vals[2]/ACCEL_SCALE_MPU
            thigh_gx = vals[3]/GYRO_SCALE_MPU
            shin_ax, shin_az = vals[6]/ACCEL_SCALE_MPU, vals[8]/ACCEL_SCALE_MPU
            shin_gx = vals[9]/GYRO_SCALE_MPU

            thigh_ang = accel_to_angle(thigh_ax, thigh_az)
            shin_ang = accel_to_angle(shin_ax, shin_az)

            # Calibration
            if not self.calibrated:
                self.cal_thigh.append(thigh_ang)
                self.cal_shin.append(shin_ang)
                if len(self.cal_thigh) >= self.cal_needed:
                    bt = sum(self.cal_thigh) / len(self.cal_thigh)
                    bs = sum(self.cal_shin) / len(self.cal_shin)
                    self.baseline_knee = bt - bs
                    self.cf_thigh.reset(bt)
                    self.cf_shin.reset(bs)
                    self.calibrated = True
                    print(f"  Calibrated! (baseline={self.baseline_knee:.1f}°)")
                    print(f"\n  >>> WALK NOW — Ctrl+C to stop <<<\n")
                continue

            # Knee angle
            ta = self.cf_thigh.update(thigh_gx, thigh_ang)
            sa = self.cf_shin.update(shin_gx, shin_ang)
            knee = (ta - sa) - self.baseline_knee

            self.stride_buf.append(knee)
            if self.stride_start_t is None:
                self.stride_start_t = t_ms

            if self._detect_boundary(knee, t_ms):
                self._score_stride(t_ms)

        # Cleanup
        self.sock1.close()
        self.sock2.close()
        self.haptic.close()

        total = self.n_good + self.n_bad
        print(f"\n{'='*55}")
        print(f"  TEST COMPLETE")
        print(f"  Total strides: {total}")
        if total > 0:
            print(f"  Good: {self.n_good} ({100*self.n_good/total:.0f}%)")
            print(f"  Bad (shakes): {self.n_bad} ({100*self.n_bad/total:.0f}%)")
        print(f"{'='*55}\n")


def main():
    p = argparse.ArgumentParser(description="Live knee gait test with haptic feedback")
    p.add_argument("--profile", default="knee_profile.json", help="Path to profile JSON")
    args = p.parse_args()

    with open(args.profile) as f:
        profile = json.load(f)

    print(f"Loaded profile: {profile['n_strides']} strides, threshold={profile['threshold_deg']:.1f}°")

    test = KneeTest(profile)

    def shutdown(sig, frame):
        print("\n\n  Stopping...")
        test.running = False
    signal.signal(signal.SIGINT, shutdown)

    test.run()


if __name__ == "__main__":
    main()
