"""
SessionLogger — Observer that writes every StrideResult to disk.

Output: sessions/<timestamp>/strides.csv  +  session_meta.json
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from typing import List

import numpy as np

from core.types import StrideResult


class SessionLogger:
    """
    Receives StrideResult events and appends a row to a CSV file.
    Call `close()` at session end to flush and write the summary.
    """

    def __init__(self, log_dir: str = "sessions/"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_dir = os.path.join(log_dir, ts)
        os.makedirs(self._session_dir, exist_ok=True)

        csv_path = os.path.join(self._session_dir, "strides.csv")
        self._csv_file   = open(csv_path, "w", newline="")
        self._writer     = csv.writer(self._csv_file)
        self._writer.writerow([
            "stride_number", "gait_health_score", "deviation_score",
            "z_knee", "z_ankle", "haptic", "color",
        ])
        self._results: List[StrideResult] = []
        print(f"[Logger] Session → {self._session_dir}")

    # ------------------------------------------------------------------

    def __call__(self, result: StrideResult) -> None:
        """Handler compatible with MonitoringPhase.add_handler()."""
        self._results.append(result)
        self._writer.writerow([
            result.stride_number,
            f"{result.gait_health_score:.1f}",
            f"{result.deviation_score:.3f}",
            f"{result.z_knee:.3f}",
            f"{result.z_ankle:.3f}",
            result.haptic.value,
            result.color_indicator,
        ])
        self._csv_file.flush()

    def close(self) -> None:
        if not self._results:
            self._csv_file.close()
            return

        scores = [r.gait_health_score for r in self._results]
        meta = {
            "n_strides"        : len(self._results),
            "mean_ghs"         : float(np.mean(scores)),
            "min_ghs"          : float(np.min(scores)),
            "max_ghs"          : float(np.max(scores)),
            "haptic_breakdown" : self._haptic_summary(),
        }
        meta_path = os.path.join(self._session_dir, "session_meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        self._csv_file.close()
        print(f"[Logger] Session closed. Mean GHS = {meta['mean_ghs']:.1f}")

    def _haptic_summary(self) -> dict:
        from collections import Counter
        counts = Counter(r.haptic.value for r in self._results)
        return dict(counts)
