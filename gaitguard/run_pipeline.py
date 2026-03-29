"""
run_pipeline.py — GaitGuard entry point.

Examples
--------
# Demo with synthetic healthy gait:
    python run_pipeline.py --source synthetic --pathology healthy

# Demo with synthetic ACL-pathology gait (triggers haptics):
    python run_pipeline.py --source synthetic --pathology mixed

# Replay COMPWALK-ACL dataset (synthetic fallback if files absent):
    python run_pipeline.py --source compwalk --condition acl

# Replay real COMPWALK-ACL CSV files:
    python run_pipeline.py --source compwalk --data-root /data/compwalk_acl --subject S01

# Only train the LSTM (no pipeline run):
    python run_pipeline.py --train-only
"""
from __future__ import annotations

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Make gaitguard/ importable from the project root
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))

from core.config import SystemConfig
from data_io.logger import SessionLogger
from pipeline import GaitPipeline
from report import generate_report
from visualise import plot_session


# ---------------------------------------------------------------------------
# Console output handler (prints a line per stride — useful for demos)
# ---------------------------------------------------------------------------

def _console_handler(result):
    bar_len = 20
    filled  = int(result.gait_health_score / 100 * bar_len)
    bar     = "█" * filled + "░" * (bar_len - filled)
    color   = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m"}.get(
        result.color_indicator, ""
    )
    reset   = "\033[0m"
    haptic_str = f"  haptic={result.haptic.value}" if result.haptic.value != "none" else ""
    print(
        f"  Stride {result.stride_number:3d}  GHS={result.gait_health_score:5.1f}  "
        f"{color}[{bar}]{reset}{haptic_str}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="GaitGuard — Real-time gait analysis pipeline")
    p.add_argument("--source",     choices=["synthetic", "compwalk"], default="synthetic")
    p.add_argument("--pathology",  choices=["healthy", "reduced_extension", "reduced_clearance", "mixed"],
                   default="healthy", help="Synthetic data pathology (--source synthetic only)")
    p.add_argument("--condition",  choices=["acl", "healthy"], default="acl",
                   help="COMPWALK-ACL condition (--source compwalk only)")
    p.add_argument("--data-root",  default="", help="Path to COMPWALK-ACL dataset root")
    p.add_argument("--subject",    default="synthetic_acl", help="Subject ID for COMPWALK-ACL")
    p.add_argument("--n-strides",  type=int, default=80, help="Strides to generate (synthetic)")
    p.add_argument("--no-plots",   action="store_true", help="Skip visualisation")
    p.add_argument("--train-only", action="store_true", help="Train LSTM and exit")
    return p.parse_args()


def main():
    args   = parse_args()
    config = SystemConfig()

    # ---- Optional: train only ----------------------------------------
    if args.train_only:
        from ml.train import generate_healthy_strides, train
        import numpy as np
        rng  = np.random.default_rng(42)
        data = generate_healthy_strides(3000, rng)
        train(data, config, epochs=60)
        return

    # ---- Source selection (Strategy) ---------------------------------
    if args.source == "synthetic":
        from simulation.synthetic import SyntheticIMUSource
        source = SyntheticIMUSource(
            config    = config,
            n_strides = args.n_strides,
            pathology = args.pathology,
        )
        print(f"[Main] Source: synthetic  pathology={args.pathology}  n_strides={args.n_strides}")

    elif args.source == "compwalk":
        from adapters.compwalk_acl import COMPWALKACLAdapter
        source = COMPWALKACLAdapter(
            data_root  = args.data_root,
            subject_id = args.subject,
            condition  = args.condition,
        )
        print(f"[Main] Source: COMPWALK-ACL  condition={args.condition}  subject={args.subject}")

    # ---- Handlers (Observers) ----------------------------------------
    logger = SessionLogger(log_dir=config.session_log_dir)

    # ---- Pipeline ----------------------------------------------------
    pipeline = GaitPipeline(config, source)
    pipeline.add_handler(_console_handler)
    pipeline.add_handler(logger)

    print("\n=== GaitGuard Pipeline ===")
    print("Phase 0: Stand still for calibration …\n")

    pipeline.run()

    logger.close()

    # ---- Post-session visualisation ----------------------------------
    if not args.no_plots and pipeline._profile and pipeline._twin:
        results = logger._results
        if results:
            plot_session(
                results  = results,
                twin     = pipeline._twin,
                profile  = pipeline._profile,
                save_dir = logger._session_dir,
                show     = False,
            )
            generate_report(
                results     = results,
                twin        = pipeline._twin,
                profile     = pipeline._profile,
                session_dir = logger._session_dir,
                source      = args.source,
                condition   = args.pathology if args.source == "synthetic" else args.condition,
            )

    print("\n=== Session complete ===")


if __name__ == "__main__":
    main()
