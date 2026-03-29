#!/usr/bin/env python3
"""GaitGuard Web Dashboard Server

Serves the dashboard UI and JSON APIs for live gait monitoring.
Uses only Python standard library — no external dependencies.
Designed for Raspberry Pi / QNX deployment.

Usage:
    python3 server.py [--port 8080]
"""

import json
import os
import sys
import socket
import struct
import signal
import subprocess
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

STATUS_PATH = "/tmp/gaitguard_status.json"
STRIDES_PATH = "/tmp/gaitguard_strides.json"
IMU_PATH = "/tmp/gaitguard_imu.json"
AXIS_CONFIG_PATH = "/tmp/gaitguard_axis_config.json"
WEB_DIR = Path(__file__).resolve().parent

DEFAULT_STATUS = {
    "state": "CALIBRATION",
    "mode": "record",
    "esp1_connected": False,
    "esp2_connected": False,
    "esp1_ip": "—",
    "esp2_ip": "—",
    "stride_count": 0,
    "calibration_progress": 0.0,
    "current_ghs": 0.0,
    "current_color": "green",
    "last_haptic": "none",
    "profile_strides": 20,
}

DEFAULT_STRIDES = {"strides": []}
DEFAULT_IMU = {
    "thigh": {"angle": 0, "ax": 0, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0},
    "shin":  {"angle": 0, "ax": 0, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0},
    "foot":  {"angle": 0, "ax": 0, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0},
    "knee": 0, "ankle": 0, "live": False
}

DEFAULT_AXIS_CONFIG = {
    "thigh": {"accel_fwd": "ax", "accel_down": "az", "gyro_bend": "gx"},
    "shin":  {"accel_fwd": "ax", "accel_down": "az", "gyro_bend": "gx"},
    "foot":  {"accel_fwd": "ax", "accel_down": "az", "gyro_bend": "gx"},
}


GAITGUARD_BIN = Path(__file__).resolve().parent.parent / "gaitguard"

# Track the running pipeline process
_pipeline_proc = None


def read_json(path, default):
    """Read a JSON file, returning default on any error."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return default


def pipeline_start(mode, activity="walking"):
    """Start the gaitguard binary in record or test mode with activity type."""
    global _pipeline_proc
    pipeline_stop()
    # Clear stale status
    for p in [STATUS_PATH, STRIDES_PATH, IMU_PATH]:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
    _pipeline_proc = subprocess.Popen(
        [str(GAITGUARD_BIN), mode, activity],
        cwd=str(GAITGUARD_BIN.parent),
        stdout=open("/tmp/gaitguard.log", "w"),
        stderr=subprocess.STDOUT,
    )
    return _pipeline_proc.pid


def pipeline_stop():
    """Stop the running pipeline."""
    global _pipeline_proc
    # QNX uses slay instead of pkill
    subprocess.run(["slay", "-f", "gaitguard"], capture_output=True)
    if _pipeline_proc:
        try:
            _pipeline_proc.terminate()
            _pipeline_proc.wait(timeout=3)
        except Exception:
            try:
                _pipeline_proc.kill()
            except Exception:
                pass
        _pipeline_proc = None


def pipeline_running():
    """Check if the pipeline is running."""
    global _pipeline_proc
    if _pipeline_proc and _pipeline_proc.poll() is None:
        return True
    # QNX doesn't have pgrep — just rely on _pipeline_proc tracking
    return False


class GaitGuardHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the GaitGuard dashboard."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    # --- CORS ---
    _udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    # --- API routing ---
    def do_GET(self):
        if self.path == "/api/status":
            status = read_json(STATUS_PATH, DEFAULT_STATUS)
            status["pipeline_running"] = pipeline_running()
            self._json_response(status)
        elif self.path == "/api/strides":
            self._json_response(read_json(STRIDES_PATH, DEFAULT_STRIDES))
        elif self.path == "/api/imu":
            self._json_response(read_json(IMU_PATH, DEFAULT_IMU))
        elif self.path == "/api/axis-config":
            self._json_response(read_json(AXIS_CONFIG_PATH, DEFAULT_AXIS_CONFIG))
        elif self.path == "/":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}

    def do_POST(self):
        if self.path == "/api/haptic":
            data = self._read_body()
            pattern = data.get("pattern", 1)
            status = read_json(STATUS_PATH, DEFAULT_STATUS)
            esp1_ip = status.get("esp1_ip", "")
            if esp1_ip and status.get("esp1_connected"):
                try:
                    self._udp_sock.sendto(
                        struct.pack("BB", int(pattern), 0xFF),
                        (esp1_ip, 5003)
                    )
                    self._json_response({"ok": True, "sent_to": esp1_ip, "pattern": pattern})
                except Exception as e:
                    self._json_response({"ok": False, "error": str(e)})
            else:
                self._json_response({"ok": False, "error": "ESP#1 not connected"})

        elif self.path == "/api/pipeline/start":
            data = self._read_body()
            mode = data.get("mode", "record")
            if mode not in ("record", "test"):
                self._json_response({"ok": False, "error": "mode must be 'record' or 'test'"})
                return
            activity = data.get("activity", "walking")
            pid = pipeline_start(mode, activity)
            self._json_response({"ok": True, "mode": mode, "activity": activity, "pid": pid})

        elif self.path == "/api/pipeline/stop":
            pipeline_stop()
            self._json_response({"ok": True})

        elif self.path == "/api/axis-config":
            data = self._read_body()
            try:
                with open(AXIS_CONFIG_PATH, "w") as f:
                    json.dump(data, f)
                self._json_response({"ok": True})
            except Exception as e:
                self._json_response({"ok": False, "error": str(e)})

        else:
            self.send_response(404)
            self.end_headers()

    def _json_response(self, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    # Suppress per-request log spam in production; comment out to debug.
    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="GaitGuard Dashboard Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), GaitGuardHandler)
    print(f"[GaitGuard] Dashboard running at http://0.0.0.0:{args.port}")
    print(f"[GaitGuard] Serving files from {WEB_DIR}")
    print(f"[GaitGuard] Status JSON: {STATUS_PATH}")
    print(f"[GaitGuard] Strides JSON: {STRIDES_PATH}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[GaitGuard] Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
