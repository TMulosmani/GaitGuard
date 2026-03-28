"""
visualise.py — Post-session plot generation.

Produces:
  1. Overlay chart: observed vs. twin knee + ankle curves
  2. Per-stride Gait Health Score trend
  3. Deviation heatmap (knee and ankle)

Usage:
    from visualise import plot_session
    plot_session(results, twin, profile, save_dir="sessions/20250101/")
"""
from __future__ import annotations

import os
from typing import List, Optional

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from core.types import DigitalTwin, GaitProfile, StrideResult


def plot_session(
    results: List[StrideResult],
    twin: DigitalTwin,
    profile: GaitProfile,
    save_dir: str = ".",
    show: bool = False,
) -> None:
    """Generate and save three figures for the session."""
    os.makedirs(save_dir, exist_ok=True)
    _plot_overlay(results, twin, profile, save_dir, show)
    _plot_ghs_trend(results, save_dir, show)
    _plot_deviation_heatmap(results, save_dir, show)


# ---------------------------------------------------------------------------

def _plot_overlay(
    results: List[StrideResult],
    twin: DigitalTwin,
    profile: GaitProfile,
    save_dir: str,
    show: bool,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    t = np.arange(100)

    for result in results[-10:]:   # last 10 strides
        axes[0].plot(t, result.observed_knee,  color="#90caf9", alpha=0.4, lw=0.8)
        axes[1].plot(t, result.observed_ankle, color="#a5d6a7", alpha=0.4, lw=0.8)

    axes[0].plot(t, twin.twin_knee,  color="#1565c0", lw=2.5, label="Digital Twin (healthy)")
    axes[0].plot(t, profile.mean_knee, color="#ef9a9a", lw=1.5, ls="--", label="Patient mean (Phase 1)")
    axes[0].fill_between(
        t,
        profile.mean_knee - profile.std_knee,
        profile.mean_knee + profile.std_knee,
        alpha=0.15, color="#ef9a9a",
    )
    axes[0].axvline(x=20, color="grey", ls=":", lw=1, label="Anchor boundary")
    axes[0].set_ylabel("Knee angle (°)\nflexion positive")
    axes[0].legend(fontsize=8)
    axes[0].set_title("Knee Flexion/Extension — Observed vs. Healthy Digital Twin")

    axes[1].plot(t, twin.twin_ankle,  color="#2e7d32", lw=2.5, label="Digital Twin (healthy)")
    axes[1].plot(t, profile.mean_ankle, color="#ef9a9a", lw=1.5, ls="--", label="Patient mean")
    axes[1].axvline(x=20, color="grey", ls=":", lw=1)
    axes[1].set_ylabel("Ankle angle (°)\ndorsiflexion positive")
    axes[1].set_xlabel("Gait cycle (%)")
    axes[1].legend(fontsize=8)
    axes[1].set_title("Ankle Dorsiflexion/Plantarflexion — Observed vs. Healthy Digital Twin")

    plt.tight_layout()
    path = os.path.join(save_dir, "overlay.png")
    plt.savefig(path, dpi=150)
    if show:
        plt.show()
    plt.close(fig)
    print(f"[Visualise] Overlay → {path}")


def _plot_ghs_trend(results: List[StrideResult], save_dir: str, show: bool) -> None:
    scores = [r.gait_health_score for r in results]
    ns     = [r.stride_number for r in results]

    fig, ax = plt.subplots(figsize=(12, 4))
    colors = [
        "#4caf50" if s >= 80 else ("#ff9800" if s >= 50 else "#f44336")
        for s in scores
    ]
    ax.bar(ns, scores, color=colors, width=0.8, edgecolor="none")
    ax.axhline(80, color="#4caf50", ls="--", lw=1, label="Green threshold (80)")
    ax.axhline(50, color="#ff9800", ls="--", lw=1, label="Yellow threshold (50)")
    ax.set_ylim(0, 105)
    ax.set_xlabel("Stride number")
    ax.set_ylabel("Gait Health Score")
    ax.set_title("Gait Health Score — Per Stride")
    ax.legend(fontsize=8)

    green_p  = mpatches.Patch(color="#4caf50", label="Good (≥80)")
    yellow_p = mpatches.Patch(color="#ff9800", label="Fair (50–79)")
    red_p    = mpatches.Patch(color="#f44336", label="Poor (<50)")
    ax.legend(handles=[green_p, yellow_p, red_p], fontsize=8)

    plt.tight_layout()
    path = os.path.join(save_dir, "ghs_trend.png")
    plt.savefig(path, dpi=150)
    if show:
        plt.show()
    plt.close(fig)
    print(f"[Visualise] GHS trend → {path}")


def _plot_deviation_heatmap(results: List[StrideResult], save_dir: str, show: bool) -> None:
    if not results:
        return

    knee_matrix  = np.stack([r.knee_dev  for r in results])   # (S, 80)
    ankle_matrix = np.stack([r.ankle_dev for r in results])   # (S, 80)
    t80 = np.arange(21, 101)

    fig, axes = plt.subplots(2, 1, figsize=(13, 6), sharex=True)

    im0 = axes[0].imshow(knee_matrix,  aspect="auto", cmap="YlOrRd",
                          extent=[21, 100, len(results), 0])
    axes[0].set_title("Knee deviation from Digital Twin (°)")
    axes[0].set_ylabel("Stride #")
    plt.colorbar(im0, ax=axes[0])

    im1 = axes[1].imshow(ankle_matrix, aspect="auto", cmap="YlOrRd",
                          extent=[21, 100, len(results), 0])
    axes[1].set_title("Ankle deviation from Digital Twin (°)")
    axes[1].set_ylabel("Stride #")
    axes[1].set_xlabel("Gait cycle (%)")
    plt.colorbar(im1, ax=axes[1])

    plt.tight_layout()
    path = os.path.join(save_dir, "deviation_heatmap.png")
    plt.savefig(path, dpi=150)
    if show:
        plt.show()
    plt.close(fig)
    print(f"[Visualise] Heatmap → {path}")
