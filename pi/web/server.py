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
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

STATUS_PATH = "/tmp/gaitguard_status.json"
STRIDES_PATH = "/tmp/gaitguard_strides.json"
IMU_PATH = "/tmp/gaitguard_imu.json"
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
    "thigh": {"angle": 0, "ax": 0, "ay": 0, "az": 1, "gx": 0, "gy": 0, "gz": 0},
    "shin":  {"angle": 0, "ax": 0, "ay": 0, "az": 1, "gx": 0, "gy": 0, "gz": 0},
    "foot":  {"angle": 0, "ax": 0, "ay": 0, "az": 1, "gx": 0, "gy": 0, "gz": 0},
    "knee": 0, "ankle": 0
}


def read_json(path, default):
    """Read a JSON file, returning default on any error."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return default


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
            self._json_response(read_json(STATUS_PATH, DEFAULT_STATUS))
        elif self.path == "/api/strides":
            self._json_response(read_json(STRIDES_PATH, DEFAULT_STRIDES))
        elif self.path == "/api/imu":
            self._json_response(read_json(IMU_PATH, DEFAULT_IMU))
        elif self.path == "/":
            # Serve index.html explicitly
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/haptic":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = {}
            pattern = data.get("pattern", 1)  # 1=TWO_SHORT, 2=ONE_LONG, 3=THREE_SHORT

            # Read ESP#1 IP from status file
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
