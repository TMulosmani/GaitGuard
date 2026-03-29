#!/usr/bin/env python3
"""
Export trained LSTM weights to a flat binary file for the C pipeline.

Usage:
    cd gaitguard && python ../pi/export_weights.py

Outputs: ../pi/weights.bin

Binary layout (all float32, row-major):
    Wi0:     (4*64, 2)       = 512 floats
    Wh0:     (4*64, 64)      = 16384 floats
    bi0:     (4*64,)         = 256 floats
    bh0:     (4*64,)         = 256 floats
    Wi1:     (4*64, 64)      = 16384 floats
    Wh1:     (4*64, 64)      = 16384 floats
    bi1:     (4*64,)         = 256 floats
    bh1:     (4*64,)         = 256 floats
    Whead:   (160, 64)       = 10240 floats
    bhead:   (160,)          = 160 floats
    norm_mean: (2,)          = 2 floats
    norm_std:  (2,)          = 2 floats
    ------------------------------------------
    Total: 61,072 floats × 4 bytes = 244,288 bytes
"""
import os
import sys
import struct
import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gaitguard"))

from core.config import SystemConfig
from ml.model import load_model, build_model
from ml.train import generate_healthy_strides, train


def export(output_path: str = None):
    config = SystemConfig()
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "weights.bin")

    model_path = config.model_path
    norm_path = config.norm_stats_path

    # Train if needed
    if not os.path.exists(model_path) or not os.path.exists(norm_path):
        print("Model not found, training from synthetic data...")
        rng = np.random.default_rng(42)
        data = generate_healthy_strides(3000, rng)
        train(data, config, epochs=60)

    # Load model
    model = load_model(model_path, config)
    sd = model.state_dict()

    # Load norm stats
    stats = np.load(norm_path)
    norm_mean = stats["mean"].astype(np.float32)
    norm_std = stats["std"].astype(np.float32)

    with open(output_path, "wb") as f:
        # LSTM layer 0
        f.write(sd["lstm.weight_ih_l0"].numpy().astype(np.float32).tobytes())
        f.write(sd["lstm.weight_hh_l0"].numpy().astype(np.float32).tobytes())
        f.write(sd["lstm.bias_ih_l0"].numpy().astype(np.float32).tobytes())
        f.write(sd["lstm.bias_hh_l0"].numpy().astype(np.float32).tobytes())
        # LSTM layer 1
        f.write(sd["lstm.weight_ih_l1"].numpy().astype(np.float32).tobytes())
        f.write(sd["lstm.weight_hh_l1"].numpy().astype(np.float32).tobytes())
        f.write(sd["lstm.bias_ih_l1"].numpy().astype(np.float32).tobytes())
        f.write(sd["lstm.bias_hh_l1"].numpy().astype(np.float32).tobytes())
        # Linear head
        f.write(sd["head.weight"].numpy().astype(np.float32).tobytes())
        f.write(sd["head.bias"].numpy().astype(np.float32).tobytes())
        # Norm stats
        f.write(norm_mean.tobytes())
        f.write(norm_std.tobytes())

    size = os.path.getsize(output_path)
    print(f"Exported {size:,} bytes to {output_path}")
    print(f"  norm_mean: knee={norm_mean[0]:.2f}, ankle={norm_mean[1]:.2f}")
    print(f"  norm_std:  knee={norm_std[0]:.2f}, ankle={norm_std[1]:.2f}")


if __name__ == "__main__":
    export()
