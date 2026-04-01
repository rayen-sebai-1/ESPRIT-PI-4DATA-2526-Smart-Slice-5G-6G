"""Unit tests for src/models/train_congestion_6g.py."""

import torch
import pytest


class TestCongestionLSTM:
    """Tests for the CongestionLSTM model."""

    def test_forward_output_shape(self):
        """The model should accept (batch, 24, 2) and return (batch, 1)."""
        from src.models.train_congestion_6g import CongestionLSTM

        model = CongestionLSTM(input_size=2, hidden_size=64)
        model.eval()

        batch_size = 8
        x = torch.randn(batch_size, 24, 2)
        with torch.no_grad():
            out = model(x)

        assert out.shape == (batch_size, 1), f"Expected ({batch_size}, 1), got {out.shape}"

    def test_forward_output_dtype_is_float(self):
        """Output tensor dtype must be float32."""
        from src.models.train_congestion_6g import CongestionLSTM

        model = CongestionLSTM(input_size=2, hidden_size=64)
        model.eval()

        x = torch.randn(4, 24, 2)
        with torch.no_grad():
            out = model(x)

        assert out.dtype == torch.float32, f"Expected float32, got {out.dtype}"
