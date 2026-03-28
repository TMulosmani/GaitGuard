"""
Abstract IMUSource — the Strategy interface for all data origins.

Concrete implementations:
  - simulation/synthetic.py  → SyntheticIMUSource
  - adapters/compwalk_acl.py → COMPWALKACLSource
  - (hardware)               → LiveIMUSource (not implemented here)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from core.types import SensorPacket


class IMUSource(ABC):
    """
    Produce an iterable stream of SensorPackets.

    The pipeline calls `packets()` and consumes packets one at a time.
    Implementations may read from hardware, files, or memory.
    """

    @abstractmethod
    def packets(self) -> Iterator[SensorPacket]:
        """Yield SensorPackets in chronological order."""
        ...

    def close(self) -> None:
        """Optional cleanup (close file handles, disconnect BLE, etc.)."""
