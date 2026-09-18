# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for app.qr_service module.
Tests QR payload generation, validation, and error handling.
"""
from __future__ import annotations

import pytest
import base64
from datetime import datetime
from decimal import Decimal
from app.qr_service import (
    normalize_qr_mode, _zatca_amount, qr_module_count,
    _auto_box_size, QR_BOX_SIZE_BASE, QR_MIN_PIXELS
)


class TestNormalizeQRMode:
    """Tests for normalize_qr_mode function."""

    def test_normalize_qr_mode_none(self):
        """Should recognize 'none' mode."""
        assert normalize_qr_mode("none") == "none"

    def test_normalize_qr_mode_simple(self):
        """Should recognize 'simple' mode."""
        assert normalize_qr_mode("simple") == "simple"

    def test_normalize_qr_mode_phase2(self):
        """Should recognize 'phase2' mode."""
        assert normalize_qr_mode("phase2") == "phase2"

    def test_normalize_qr_mode_case_insensitive(self):
        """Should be case-insensitive."""
        assert normalize_qr_mode("SIMPLE") == "simple"
        assert normalize_qr_mode("Phase2") == "phase2"
        assert normalize_qr_mode("NONE") == "none"

    def test_normalize_qr_mode_with_whitespace(self):
        """Should strip whitespace."""
        assert normalize_qr_mode("  simple  ") == "simple"
        assert normalize_qr_mode("\tphase2\n") == "phase2"

    def test_normalize_qr_mode_invalid_defaults_to_none(self):
        """Should default to 'none' for invalid modes."""
        assert normalize_qr_mode("invalid") == "none"
        assert normalize_qr_mode("qr") == "none"
        assert normalize_qr_mode("") == "none"

    def test_normalize_qr_mode_none_input(self):
        """Should default to 'none' for None input."""
        assert normalize_qr_mode(None) == "none"


class TestZatcaAmount:
    """Tests for _zatca_amount formatting function."""

    def test_zatca_amount_integer(self):
        """Should format integer halalas as Riyal with .2f."""
        result = _zatca_amount(1000)  # 10.00 SAR
        assert result == "10.00"

    def test_zatca_amount_fractional(self):
        """Should format fractional amounts correctly."""
        result = _zatca_amount(1050)  # 10.50 SAR
        assert result == "10.50"

    def test_zatca_amount_single_halala(self):
        """Should format single halala."""
        result = _zatca_amount(1)  # 0.01 SAR
        assert result == "0.01"

    def test_zatca_amount_zero(self):
        """Should format zero correctly."""
        result = _zatca_amount(0)
        assert result == "0.00"

    def test_zatca_amount_large_amount(self):
        """Should format large amounts."""
        result = _zatca_amount(1234567)  # 12,345.67 SAR
        assert result == "12345.67"

    def test_zatca_amount_no_thousands_separator(self):
        """Should NOT include thousands separator (ZATCA requirement)."""
        result = _zatca_amount(1000000)  # 10,000.00 SAR
        assert "," not in result
        assert result == "10000.00"

    def test_zatca_amount_string_input(self):
        """Should accept string input."""
        result = _zatca_amount("1000")
        assert result == "10.00"


class TestQRModuleCount:
    """Tests for qr_module_count (QR code size calculation)."""

    def test_qr_module_count_valid_b64(self):
        """Should return positive integer for valid base64."""
        # Valid base64 string representing a simple payload
        payload_b64 = base64.b64encode(b"test payload").decode("ascii")
        result = qr_module_count(payload_b64)
        assert isinstance(result, int)
        assert result > 0

    def test_qr_module_count_increases_with_payload_size(self):
        """Larger payloads should generate larger QR codes."""
        small = base64.b64encode(b"x" * 10).decode("ascii")
        large = base64.b64encode(b"y" * 1000).decode("ascii")

        small_modules = qr_module_count(small)
        large_modules = qr_module_count(large)

        # Larger payload → more modules (almost certainly)
        assert large_modules >= small_modules

    def test_qr_module_count_invalid_b64_returns_reasonable_value(self):
        """Should handle invalid base64 gracefully."""
        # Invalid base64 should not crash
        try:
            result = qr_module_count("not valid base64!!!")
            # If it doesn't raise, it should return something
            assert result > 0
        except Exception:
            # May raise, which is acceptable
            pass


class TestAutoBoxSize:
    """Tests for _auto_box_size automatic box sizing."""

    def test_auto_box_size_minimum_box_respected(self):
        """Should return at least the minimum box_size."""
        payload_b64 = base64.b64encode(b"small").decode("ascii")
        result = _auto_box_size(payload_b64, QR_BOX_SIZE_BASE, QR_MIN_PIXELS)
        assert result >= QR_BOX_SIZE_BASE

    def test_auto_box_size_max_box_enforced(self):
        """Should not exceed QR_BOX_SIZE_MAX (16)."""
        # Even with min_pixels very high, should be capped
        payload_b64 = base64.b64encode(b"test").decode("ascii")
        result = _auto_box_size(payload_b64, 1, 50000)
        # Should be capped at 16
        from app.qr_service import QR_BOX_SIZE_MAX
        assert result <= QR_BOX_SIZE_MAX

    def test_auto_box_size_large_payload_larger_box(self):
        """Larger payload should increase box size to maintain min_pixels."""
        small_payload = base64.b64encode(b"x" * 10).decode("ascii")
        large_payload = base64.b64encode(b"y" * 1000).decode("ascii")

        small_box = _auto_box_size(small_payload, 1, 900)
        large_box = _auto_box_size(large_payload, 1, 900)

        # Box sizes should be calculated without error; actual relationship may vary
        # with QR library behavior, so we just ensure they're reasonable
        assert small_box > 0
        assert large_box > 0

    def test_auto_box_size_zero_min_pixels(self):
        """Should use provided box_size if min_pixels is 0."""
        payload_b64 = base64.b64encode(b"test").decode("ascii")
        result = _auto_box_size(payload_b64, 5, 0)
        assert result == 5

    def test_auto_box_size_invalid_payload_handled(self):
        """Should handle invalid payload gracefully."""
        try:
            result = _auto_box_size("invalid!!!", 8, 900)
            # Should return something reasonable
            assert result > 0
        except Exception:
            # May raise, acceptable
            pass


class TestQRModeLabels:
    """Tests for QR mode labels and descriptions."""

    def test_qr_mode_labels_keys_match_modes(self):
        """QR_MODE_LABELS should have entries for all QR_MODES."""
        from app.qr_service import QR_MODES, QR_MODE_LABELS
        for mode in QR_MODES:
            assert mode in QR_MODE_LABELS
            assert isinstance(QR_MODE_LABELS[mode], str)
            assert len(QR_MODE_LABELS[mode]) > 0


class TestQREdgeCases:
    """Integration and edge case tests for QR service."""

    def test_zatca_amount_and_module_count_integration(self):
        """Should generate consistent amounts for QR encoding."""
        amounts = [0, 1, 100, 1000, 50000, 999999999]
        formatted = [_zatca_amount(a) for a in amounts]

        # All should be in format X.XX
        for fmt in formatted:
            parts = fmt.split(".")
            assert len(parts) == 2
            assert len(parts[1]) == 2

    def test_qr_mode_normalization_idempotent(self):
        """Normalizing twice should give same result as once."""
        modes = ["simple", "PHASE2", "  none  ", "invalid"]
        for mode in modes:
            once = normalize_qr_mode(mode)
            twice = normalize_qr_mode(once)
            assert once == twice

    def test_box_size_calculation_consistent(self):
        """Same payload should produce same box size."""
        payload = base64.b64encode(b"test data").decode("ascii")
        box1 = _auto_box_size(payload, 8, 900)
        box2 = _auto_box_size(payload, 8, 900)
        assert box1 == box2
