"""
GaitGuard — WiFi UDP receiver for Raspberry Pi.

Listens on two UDP ports for IMU data from the two ESP32 devices,
parses binary packets into SensorPacket objects, and feeds them
into the GaitPipeline. Sends haptic commands and display updates
back to the ESPs.

Ports (must match esp/config.h):
    5001  ← ESP#1 thigh/shin IMU data (27 bytes)
    5002  ← ESP#2 foot IMU data (15 bytes)
    5003  → ESP#1 haptic commands (2 bytes)
    5004  → ESP#2 display updates (6 bytes)
"""
from __future__ import annotations

import socket
import struct
import time
import threading
from typing import Iterator, Optional, Tuple

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gaitguard"))

from core.types import IMUReading, SensorPacket, StrideResult, HapticPattern
from data_io.source import IMUSource

# ---------------------------------------------------------------------------
# Config — mirrors esp/config.h
# ---------------------------------------------------------------------------

PORT_IMU_THIGH_SHIN = 5001
PORT_IMU_FOOT       = 5002
PORT_HAPTIC_CMD     = 5003
PORT_DISPLAY_CMD    = 5004

DEVICE_ID_THIGH_SHIN = 0x01
DEVICE_ID_FOOT       = 0x02

# IMU scale factors
# ESP#1 (MPU-6050): ±4g = 8192 LSB/g,  ±500°/s = 65.5 LSB/(°/s)
# ESP#2 (QMI8658):  ±4g = 8192 LSB/g,  ±512°/s = 64.0 LSB/(°/s)
ACCEL_SCALE_MPU = 8192.0
GYRO_SCALE_MPU  = 65.5
ACCEL_SCALE_QMI = 8192.0
GYRO_SCALE_QMI  = 64.0

# Timeout: if no packet arrives in this many seconds, yield what we have
RECV_TIMEOUT_S = 0.1


# ---------------------------------------------------------------------------
# Packet parsing
# ---------------------------------------------------------------------------

def _parse_imu_block(data: bytes, offset: int, timestamp_ms: float,
                     accel_scale: float, gyro_scale: float) -> IMUReading:
    """Parse 12 bytes (6 × int16 BE) into an IMUReading."""
    ax, ay, az, gx, gy, gz = struct.unpack_from(">hhhhhh", data, offset)
    return IMUReading(
        accel_x=ax / accel_scale,
        accel_y=ay / accel_scale,
        accel_z=az / accel_scale,
        gyro_x=gx / gyro_scale,
        gyro_y=gy / gyro_scale,
        gyro_z=gz / gyro_scale,
        timestamp_ms=timestamp_ms,
    )


def parse_thigh_shin_packet(data: bytes, timestamp_ms: float) -> Tuple[IMUReading, IMUReading]:
    """Parse a 27-byte ESP#1 packet into (thigh, shin) IMUReadings.
    ESP#1 uses MPU-6050 (±4g / ±500°/s)."""
    thigh = _parse_imu_block(data, 3, timestamp_ms, ACCEL_SCALE_MPU, GYRO_SCALE_MPU)
    shin  = _parse_imu_block(data, 15, timestamp_ms, ACCEL_SCALE_MPU, GYRO_SCALE_MPU)
    return thigh, shin


def parse_foot_packet(data: bytes, timestamp_ms: float) -> IMUReading:
    """Parse a 15-byte ESP#2 packet into a foot IMUReading.
    ESP#2 uses QMI8658C (±4g / ±512°/s)."""
    return _parse_imu_block(data, 3, timestamp_ms, ACCEL_SCALE_QMI, GYRO_SCALE_QMI)


# ---------------------------------------------------------------------------
# Command senders
# ---------------------------------------------------------------------------

class CommandSender:
    """Sends haptic and display commands back to the ESPs."""

    def __init__(self, esp1_ip: Optional[str] = None, esp2_ip: Optional[str] = None):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._esp1_ip = esp1_ip
        self._esp2_ip = esp2_ip

    def set_esp1_ip(self, ip: str) -> None:
        self._esp1_ip = ip

    def set_esp2_ip(self, ip: str) -> None:
        self._esp2_ip = ip

    def send_haptic(self, pattern: HapticPattern) -> None:
        """Send a haptic command to ESP#1."""
        if not self._esp1_ip:
            return
        pattern_map = {
            HapticPattern.NONE: 0,
            HapticPattern.TWO_SHORT: 1,
            HapticPattern.ONE_LONG: 2,
            HapticPattern.THREE_SHORT: 3,
        }
        code = pattern_map.get(pattern, 0)
        if code == 0:
            return
        self._sock.sendto(struct.pack("BB", code, 255), (self._esp1_ip, PORT_HAPTIC_CMD))

    def send_display_update(self, score: float, color: str, state: int) -> None:
        """Send a display update to ESP#2."""
        if not self._esp2_ip:
            return
        color_map = {"green": 0, "yellow": 1, "red": 2}
        color_byte = color_map.get(color, 0)
        score_int = int(score * 10)  # 1 decimal place
        pkt = struct.pack(">BHBBx", 1, score_int, color_byte, state)
        self._sock.sendto(pkt, (self._esp2_ip, PORT_DISPLAY_CMD))

    def close(self) -> None:
        self._sock.close()


# ---------------------------------------------------------------------------
# WiFiIMUSource — implements IMUSource for the live pipeline
# ---------------------------------------------------------------------------

class WiFiIMUSource(IMUSource):
    """
    Receives UDP packets from both ESPs and yields SensorPackets.

    Pairs up thigh/shin data from ESP#1 with foot data from ESP#2.
    Uses the most recent foot reading if a new one hasn't arrived
    by the time a thigh/shin packet comes in (and vice versa).
    """

    def __init__(self):
        self._sock1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock1.bind(("0.0.0.0", PORT_IMU_THIGH_SHIN))
        self._sock1.settimeout(RECV_TIMEOUT_S)

        self._sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock2.bind(("0.0.0.0", PORT_IMU_FOOT))
        self._sock2.settimeout(RECV_TIMEOUT_S)

        self._running = True
        self._start_ms = time.time() * 1000

        # Track ESP IPs from received packets
        self.esp1_ip: Optional[str] = None
        self.esp2_ip: Optional[str] = None

        # Latest readings (for pairing)
        self._latest_thigh: Optional[IMUReading] = None
        self._latest_shin:  Optional[IMUReading] = None
        self._latest_foot:  Optional[IMUReading] = None

        # Background thread for foot packets
        self._foot_lock = threading.Lock()
        self._foot_thread = threading.Thread(target=self._foot_recv_loop, daemon=True)
        self._foot_thread.start()

    def _now_ms(self) -> float:
        return time.time() * 1000 - self._start_ms

    def _foot_recv_loop(self) -> None:
        """Background thread: continuously receive foot packets."""
        while self._running:
            try:
                data, addr = self._sock2.recvfrom(64)
            except socket.timeout:
                continue
            if len(data) < 15:
                continue
            if data[0] != DEVICE_ID_FOOT:
                continue

            self.esp2_ip = addr[0]
            foot = parse_foot_packet(data, self._now_ms())
            with self._foot_lock:
                self._latest_foot = foot

    def packets(self) -> Iterator[SensorPacket]:
        """
        Yield SensorPackets driven by ESP#1's 50 Hz cadence.

        Each time a thigh/shin packet arrives, pair it with the
        latest foot reading and yield a complete SensorPacket.
        """
        # Create a zero foot reading as fallback until ESP#2 connects
        zero_foot = IMUReading(0, 0, 1.0, 0, 0, 0, 0)

        print(f"[WiFiIMUSource] Listening on :{PORT_IMU_THIGH_SHIN} and :{PORT_IMU_FOOT}")
        print(f"[WiFiIMUSource] Waiting for ESP packets...")

        while self._running:
            try:
                data, addr = self._sock1.recvfrom(64)
            except socket.timeout:
                continue

            if len(data) < 27:
                continue
            if data[0] != DEVICE_ID_THIGH_SHIN:
                continue

            self.esp1_ip = addr[0]
            ts = self._now_ms()
            thigh, shin = parse_thigh_shin_packet(data, ts)

            with self._foot_lock:
                foot = self._latest_foot if self._latest_foot else zero_foot

            yield SensorPacket(
                thigh=thigh,
                shin=shin,
                foot=foot,
                timestamp_ms=ts,
            )

    def close(self) -> None:
        self._running = False
        self._sock1.close()
        self._sock2.close()

    def stop(self) -> None:
        """Signal the source to stop yielding."""
        self._running = False


# ---------------------------------------------------------------------------
# Stride result handler — sends commands back to ESPs
# ---------------------------------------------------------------------------

def make_esp_handler(cmd: CommandSender):
    """Create a stride handler that sends haptic + display commands."""
    def handler(result: StrideResult) -> None:
        # Send haptic feedback to ESP#1
        if result.haptic != HapticPattern.NONE:
            cmd.send_haptic(result.haptic)

        # Send display update to ESP#2
        state = 2  # STATE_WALKING
        cmd.send_display_update(
            score=result.gait_health_score,
            color=result.color_indicator,
            state=state,
        )
    return handler
