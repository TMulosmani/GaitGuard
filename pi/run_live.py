#!/usr/bin/env python3
"""
GaitGuard — Live pipeline entry point for Raspberry Pi.

Receives real-time IMU data from the two ESP32 devices over WiFi UDP
and runs the full 4-phase GaitPipeline. Sends haptic commands and
display updates back to the ESPs.

Usage:
    python run_live.py
    python run_live.py --no-plots
"""
from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys

# Make gaitguard/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gaitguard"))

from core.config import SystemConfig
from core.types import HapticPattern
from data_io.logger import SessionLogger
from pipeline import GaitPipeline

from wifi_receiver import WiFiIMUSource, CommandSender, make_esp_handler


def _console_handler(result):
    bar_len = 20
    filled  = int(result.gait_health_score / 100 * bar_len)
    bar     = "█" * filled + "░" * (bar_len - filled)
    color   = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m"}.get(
        result.color_indicator, ""
    )
    reset   = "\033[0m"
    haptic_str = f"  haptic={result.haptic.value}" if result.haptic.value != "none" else ""
    print(
        f"  Stride {result.stride_number:3d}  GHS={result.gait_health_score:5.1f}  "
        f"{color}[{bar}]{reset}{haptic_str}"
    )


def main():
    parser = argparse.ArgumentParser(description="GaitGuard — Live pipeline")
    parser.add_argument("--no-plots", action="store_true", help="Skip post-session plots")
    args = parser.parse_args()

    config = SystemConfig()

    # --- WiFi source ---
    source = WiFiIMUSource()
    cmd = CommandSender()

    # Graceful shutdown on Ctrl+C
    def shutdown(sig, frame):
        print("\n[Live] Shutting down...")
        source.stop()
    signal.signal(signal.SIGINT, shutdown)

    # --- Pipeline ---
    logger = SessionLogger(log_dir=config.session_log_dir)
    pipeline = GaitPipeline(config, source)

    pipeline.add_handler(_console_handler)
    pipeline.add_handler(logger)
    pipeline.add_handler(make_esp_handler(cmd))

    print("\n=== GaitGuard Live Pipeline ===")
    print(f"Listening for ESP#1 (thigh/shin) on UDP :{5001}")
    print(f"Listening for ESP#2 (foot) on UDP :{5002}")
    print("Waiting for sensor data...\n")

    # --- Calibration display ---
    # We'll update the ESP IPs once we see packets, and send calibration state
    calibration_sent = False

    # Run the pipeline — it blocks here consuming WiFi packets
    for packet in source.packets():
        # Auto-detect ESP IPs on first packets
        if source.esp1_ip and not cmd._esp1_ip:
            cmd.set_esp1_ip(source.esp1_ip)
            print(f"[Live] ESP#1 connected from {source.esp1_ip}")
        if source.esp2_ip and not cmd._esp2_ip:
            cmd.set_esp2_ip(source.esp2_ip)
            print(f"[Live] ESP#2 connected from {source.esp2_ip}")

        # Send calibration state to display
        if not calibration_sent and cmd._esp2_ip:
            cmd.send_display_update(0, "green", 1)  # STATE_CALIBRATING
            calibration_sent = True

        # Write raw IMU data for dashboard
        def _imu_dict(r):
            angle = math.degrees(math.atan2(r.accel_x, math.sqrt(r.accel_y**2 + r.accel_z**2)))
            return {"angle": round(angle, 1), "ax": round(r.accel_x, 3),
                    "ay": round(r.accel_y, 3), "az": round(r.accel_z, 3),
                    "gx": round(r.gyro_x, 2), "gy": round(r.gyro_y, 2), "gz": round(r.gyro_z, 2)}
        try:
            with open("/tmp/gaitguard_imu.json", "w") as _f:
                json.dump({"thigh": _imu_dict(packet.thigh), "shin": _imu_dict(packet.shin),
                           "foot": _imu_dict(packet.foot), "knee": 0, "ankle": 0, "live": True}, _f)
        except Exception:
            pass

        result = pipeline.step(packet)

        # If pipeline just transitioned out of calibration, update display
        if calibration_sent and pipeline.state.name == "SEGMENTATION":
            cmd.send_display_update(0, "green", 2)  # STATE_WALKING
            calibration_sent = False  # prevent re-sending

    # --- Cleanup ---
    logger.close()
    cmd.close()
    source.close()

    print("\n=== Session complete ===")


if __name__ == "__main__":
    main()
