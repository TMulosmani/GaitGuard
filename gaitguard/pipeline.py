"""
GaitPipeline — the central state machine that wires all phases together.

Flow:
    Phase 0 (CALIBRATION)     → waits for standing still
    Phase 1 (SEGMENTATION)    → collects ≥ 20 valid strides, builds GaitProfile
    Phase 2 (TWIN_GENERATION) → runs LSTM to produce DigitalTwin
    Phase 3 (MONITORING)      → scores every stride, fires handlers

Handlers (observers) are registered via `add_handler()` and receive
StrideResult objects from Phase 3.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from core.config import SystemConfig
from core.types import (
    DigitalTwin,
    GaitProfile,
    PipelineState,
    SensorPacket,
    StrideResult,
)
from data_io.source import IMUSource
from phases.phase0_calibration import CalibrationPhase
from phases.phase1_segmentation import SegmentationPhase
from phases.phase2_twin import DigitalTwinPhase
from phases.phase3_monitoring import MonitoringPhase
from dsp.angles import JointAngleComputer

StrideHandler = Callable[[StrideResult], None]


class GaitPipeline:
    """
    Feed packets from an IMUSource through all four phases.

    Usage:
        pipeline = GaitPipeline(config, source)
        pipeline.add_handler(logger)
        pipeline.add_handler(haptic_output)
        pipeline.run()
    """

    def __init__(self, config: SystemConfig, source: IMUSource):
        self._config  = config
        self._source  = source
        self._state   = PipelineState.CALIBRATION
        self._handlers: List[StrideHandler] = []

        self._angle_computer = JointAngleComputer(config)
        self._phase0 = CalibrationPhase(config, self._angle_computer)
        self._phase1 = SegmentationPhase(config)
        self._phase2 = DigitalTwinPhase(config)
        self._phase3: Optional[MonitoringPhase] = None

        # Populated as phases complete
        self._profile: Optional[GaitProfile] = None
        self._twin:    Optional[DigitalTwin]  = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_handler(self, handler: StrideHandler) -> None:
        self._handlers.append(handler)

    def run(self) -> None:
        """Consume the entire source packet stream."""
        for packet in self._source.packets():
            self._step(packet)

    def step(self, packet: SensorPacket) -> Optional[StrideResult]:
        """Process a single packet externally (e.g. from a live read loop)."""
        return self._step(packet)

    @property
    def state(self) -> PipelineState:
        return self._state

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _step(self, packet: SensorPacket) -> Optional[StrideResult]:
        if self._state == PipelineState.CALIBRATION:
            return self._handle_calibration(packet)
        elif self._state == PipelineState.SEGMENTATION:
            return self._handle_segmentation(packet)
        elif self._state == PipelineState.MONITORING:
            return self._handle_monitoring(packet)
        return None

    def _handle_calibration(self, packet: SensorPacket) -> None:
        if self._phase0.feed(packet):
            print(f"[Pipeline] Calibration complete. → SEGMENTATION")
            self._state = PipelineState.SEGMENTATION

    def _handle_segmentation(self, packet: SensorPacket) -> None:
        knee, ankle = self._angle_computer.update(packet.thigh, packet.shin, packet.foot)
        self._phase1.feed(packet, knee, ankle)

        if self._phase1.is_ready:
            n = self._phase1.n_valid_strides
            print(f"[Pipeline] {n} valid strides collected. → TWIN_GENERATION")
            self._state = PipelineState.TWIN_GENERATION
            self._profile = self._phase1.build_profile()
            self._twin    = self._phase2.generate(self._profile)
            print(f"[Pipeline] Digital twin generated. → MONITORING")
            self._state = PipelineState.MONITORING
            self._phase3 = MonitoringPhase(self._config, self._profile, self._twin)
            for h in self._handlers:
                self._phase3.add_handler(h)

    def _handle_monitoring(self, packet: SensorPacket) -> Optional[StrideResult]:
        knee, ankle = self._angle_computer.update(packet.thigh, packet.shin, packet.foot)
        return self._phase3.feed(packet, knee, ankle)
