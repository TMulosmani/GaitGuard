"""
LSTMTwin — PyTorch model for healthy digital twin generation.

Architecture (per the prompt spec):
    Input : (batch, anchor_len=20, n_channels=2)  — knee + ankle anchor
    LSTM 1: hidden_size=64
    LSTM 2: hidden_size=64
    Dense : 80 × 2 = 160 outputs  (predicted continuation for knee + ankle)

The model predicts gait-cycle timepoints 21–100 given points 1–20.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class LSTMTwin(nn.Module):
    """
    Two-layer stacked LSTM with a linear readout head.

    Input shape:  (B, anchor_len, n_channels)
    Output shape: (B, prediction_len, n_channels)
    """

    def __init__(
        self,
        n_channels: int = 2,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        anchor_len: int = 20,
        prediction_len: int = 80,
    ):
        super().__init__()
        self.anchor_len = anchor_len
        self.prediction_len = prediction_len
        self.n_channels = n_channels

        self.lstm = nn.LSTM(
            input_size=n_channels,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Linear(hidden_size, prediction_len * n_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, anchor_len, n_channels)
        Returns: (B, prediction_len, n_channels)
        """
        _, (h_n, _) = self.lstm(x)          # h_n: (num_layers, B, hidden)
        last_hidden = h_n[-1]               # (B, hidden)
        out = self.head(last_hidden)        # (B, prediction_len * n_channels)
        return out.view(-1, self.prediction_len, self.n_channels)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def build_model(config) -> LSTMTwin:
    """Instantiate LSTMTwin from a SystemConfig."""
    return LSTMTwin(
        n_channels     = config.lstm_n_channels,
        hidden_size    = config.lstm_hidden_size,
        num_layers     = config.lstm_num_layers,
        dropout        = config.lstm_dropout,
        anchor_len     = config.lstm_anchor_len,
        prediction_len = config.lstm_prediction_len,
    )


def load_model(path: str, config) -> LSTMTwin:
    """Load a saved model from disk."""
    model = build_model(config)
    state = torch.load(path, map_location="cpu")
    model.load_state_dict(state)
    model.eval()
    return model
