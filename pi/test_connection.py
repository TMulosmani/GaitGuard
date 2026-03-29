#!/usr/bin/env python3
"""
Quick connectivity test — run on the Pi to verify ESP packets arrive.

Prints raw packet data from both ESPs without running the full pipeline.
Press Ctrl+C to stop.

Usage:
    python test_connection.py
"""
import socket
import struct
import time
import threading

PORT_1 = 5001  # thigh/shin
PORT_2 = 5002  # foot

# MPU-6050 scale (ESP#1) — close enough for QMI8658 too
ACCEL_SCALE = 8192.0
GYRO_SCALE  = 65.0


def listen_port(port: int, label: str):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.settimeout(1.0)

    count = 0
    last_print = time.time()

    print(f"[{label}] Listening on :{port}")

    while True:
        try:
            data, addr = sock.recvfrom(64)
        except socket.timeout:
            continue

        count += 1
        now = time.time()

        # Print details every 0.5s (not every packet at 50Hz)
        if now - last_print >= 0.5:
            device_id = data[0]
            seq = struct.unpack_from(">H", data, 1)[0]

            if len(data) >= 15:
                ax, ay, az, gx, gy, gz = struct.unpack_from(">hhhhhh", data, 3)
                print(
                    f"[{label}] from {addr[0]}  seq={seq:5d}  "
                    f"accel=({ax/ACCEL_SCALE:+.2f}, {ay/ACCEL_SCALE:+.2f}, {az/ACCEL_SCALE:+.2f})g  "
                    f"gyro=({gx/GYRO_SCALE:+.1f}, {gy/GYRO_SCALE:+.1f}, {gz/GYRO_SCALE:+.1f})°/s  "
                    f"[{count} pkts total]"
                )
            last_print = now


def main():
    print("=== GaitGuard Connection Test ===")
    print("Waiting for ESP packets... (Ctrl+C to stop)\n")

    t1 = threading.Thread(target=listen_port, args=(PORT_1, "ESP#1 thigh/shin"), daemon=True)
    t2 = threading.Thread(target=listen_port, args=(PORT_2, "ESP#2 foot"), daemon=True)
    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDone.")


if __name__ == "__main__":
    main()
