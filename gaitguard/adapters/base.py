"""
Abstract DatasetAdapter — normalises an external dataset's file format
into a stream of SensorPackets compatible with the GaitGuard pipeline.

Each concrete adapter:
  1. Reads the dataset files from disk.
  2. Maps dataset-specific sensor placements and column names to
     IMUReading fields (accel_x/y/z, gyro_x/y/z, timestamp_ms).
  3. Implements `packets()` to yield SensorPackets in time order.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from core.types import IMUReading, SensorPacket
from data_io.source import IMUSource


class DatasetAdapter(IMUSource, ABC):
    """
    Base class for all dataset replay sources.

    Subclasses must implement `_load()` and `packets()`.
    """

    def __init__(self, data_root: str, subject_id: str = ""):
        self.data_root  = data_root
        self.subject_id = subject_id
        self._load()

    @abstractmethod
    def _load(self) -> None:
        """Parse dataset files from `self.data_root` into memory."""
        ...

    @abstractmethod
    def packets(self) -> Iterator[SensorPacket]:
        """Yield SensorPackets in chronological order."""
        ...

    # ------------------------------------------------------------------
    # Utility: build a zero-reading placeholder (for missing sensors)
    # ------------------------------------------------------------------

    @staticmethod
    def _zero_imu(timestamp_ms: float) -> IMUReading:
        return IMUReading(0, 0, 1, 0, 0, 0, timestamp_ms)
