"""
Phase 3 — Real-Time Gait Monitoring with Haptic Feedback

Re-uses the same stride-boundary detection logic from Phase 1.
On each confirmed stride, scores the stride against the digital twin and
emits a StrideResult to all registered output handlers.

Target latency from split detection → haptic output: < 200 ms.
"""
from __future__ import annotations

from typing import Callable, List, Optional

import numpy as np

from core.config import SystemConfig
from core.types import DigitalTwin, GaitProfile, SensorPacket, StrideResult
from phases.phase1_segmentation import SegmentationPhase
from scoring.scorer import score_stride
from dsp.filters import apply_butterworth

# Type alias for output callbacks
StrideHandler = Callable[[StrideResult], None]


class MonitoringPhase:
    """
    Wraps SegmentationPhase logic for real-time use.
    Register output handlers (logger, haptic, BLE display, …) via add_handler().
    """

    def __init__(
        self,
        config: SystemConfig,
        profile: GaitProfile,
        twin: DigitalTwin,
    ):
        self._config  = config
        self._profile = profile
        self._twin    = twin
        self._handlers: List[StrideHandler] = []
        self._stride_num = 0

        # Reuse Phase-1 segmentation logic
        self._segmenter = SegmentationPhase(config)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_handler(self, handler: StrideHandler) -> None:
        """Register a callback that receives StrideResult after each stride."""
        self._handlers.append(handler)

    # ------------------------------------------------------------------
    # Main loop entry point
    # ------------------------------------------------------------------

    def feed(self, packet: SensorPacket, knee_deg: float, ankle_deg: float) -> Optional[StrideResult]:
        """
        Feed one sample from the live sensor stream.

        Returns a StrideResult if a stride was just completed (and dispatched
        to all handlers), otherwise returns None.
        """
        boundary_hit = self._segmenter.feed(packet, knee_deg, ankle_deg)

        if not boundary_hit:
            return None

        # Read the stride that was just completed (saved before buffer reset)
        completed = self._segmenter.last_completed_stride
        if completed is None or len(completed.knee_angles) < 5:
            return None

        knee_raw  = completed.knee_angles
        ankle_raw = completed.ankle_angles

        result = self._process_stride(knee_raw, ankle_raw)
        self._stride_num += 1
        for handler in self._handlers:
            handler(result)
        return result

    # ------------------------------------------------------------------

    def _process_stride(
        self, knee_raw: np.ndarray, ankle_raw: np.ndarray
    ) -> StrideResult:
        """Filter, time-normalise, and score one stride."""
        n = self._config.gait_cycle_points

        fk = apply_butterworth(
            knee_raw,
            self._config.butterworth_cutoff_hz,
            self._config.sample_rate_hz,
            self._config.butterworth_order,
        )
        fa = apply_butterworth(
            ankle_raw,
            self._config.butterworth_cutoff_hz,
            self._config.sample_rate_hz,
            self._config.butterworth_order,
        )

        obs_knee  = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(fk)), fk)
        obs_ankle = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(fa)), fa)

        return score_stride(
            observed_knee  = obs_knee,
            observed_ankle = obs_ankle,
            twin           = self._twin,
            profile        = self._profile,
            config         = self._config,
            stride_number  = self._stride_num,
        )
