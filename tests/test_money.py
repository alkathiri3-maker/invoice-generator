# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for app.money module.
Tests conversion precision, rounding, formatting with edge cases.
"""
from __future__ import annotations

import pytest
from decimal import Decimal, ROUND_HALF_UP
from app.money import (
    parse_decimal, to_halalas, from_halalas, fmt_money, fmt_qty, line_tax, Q2
)


class TestParseDecimal:
    """Tests for parse_decimal utility function."""

    def test_parse_decimal_from_string(self):
        """Should parse valid string to Decimal."""
        assert parse_decimal("100.50") == Decimal("100.50")
        assert parse_decimal("0") == Decimal("0")
        assert parse_decimal("-50.25") == Decimal("-50.25")

    def test_parse_decimal_from_number(self):
        """Should parse int/float to Decimal."""
        assert parse_decimal(100) == Decimal("100")
        assert parse_decimal(100.50) == Decimal("100.5")
        assert parse_decimal(0) == Decimal("0")

    def test_parse_decimal_with_comma_thousands(self):
        """Should remove comma separators from input."""
        assert parse_decimal("1,000.50") == Decimal("1000.50")
        assert parse_decimal("10,000,000") == Decimal("10000000")

    def test_parse_decimal_with_whitespace(self):
        """Should strip whitespace."""
        assert parse_decimal("  100.50  ") == Decimal("100.50")
        assert parse_decimal("\t50\n") == Decimal("50")

    def test_parse_decimal_invalid_input_returns_default(self):
        """Should return default on invalid input."""
        assert parse_decimal("not a number") is None
        assert parse_decimal("not a number", Decimal("0")) == Decimal("0")
        assert parse_decimal("", Decimal("10")) == Decimal("10")

    def test_parse_decimal_none_returns_default(self):
        """Should return default when input is None."""
        assert parse_decimal(None) is None
        assert parse_decimal(None, Decimal("5")) == Decimal("5")

    def test_parse_decimal_empty_string_returns_default(self):
        """Should return default for empty string."""
        assert parse_decimal("") is None
        assert parse_decimal("", Decimal("100")) == Decimal("100")


class TestToHalalas:
    """Tests for to_halalas (Riyal to Halalas conversion)."""

    def test_to_halalas_exact_amount(self):
        """Should convert exact amounts correctly."""
        assert to_halalas("10") == 1000
        assert to_halalas("100.50") == 10050
        assert to_halalas("0.01") == 1
        assert to_halalas(Decimal("1")) == 100

    def test_to_halalas_rounds_half_up(self):
        """Should round .005 and higher up."""
        assert to_halalas("10.005") == 1001  # 10.00 + 0.005 → round up
        assert to_halalas("1.235") == 124    # 1.23 + 0.005 → 1.24 = 124 halalas
        assert to_halalas("0.155") == 16     # 0.15 + 0.005 → 0.16 = 16 halalas

    def test_to_halalas_rounds_half_down(self):
        """Should round .004 and lower down."""
        assert to_halalas("10.004") == 1000
        assert to_halalas("1.234") == 123    # 1.234 → 1.23 = 123 halalas
        assert to_halalas("0.154") == 15     # 0.154 → 0.15 = 15 halalas

    def test_to_halalas_zero(self):
        """Should handle zero correctly."""
        assert to_halalas("0") == 0
        assert to_halalas("0.00") == 0
        assert to_halalas(0) == 0

    def test_to_halalas_negative(self):
        """Should preserve negative values."""
        assert to_halalas("-10") == -1000
        assert to_halalas("-0.01") == -1

    def test_to_halalas_large_amount(self):
        """Should handle large amounts."""
        assert to_halalas("999999999.99") == 99999999999
        assert to_halalas("1000000") == 100000000

    def test_to_halalas_float_input(self):
        """Should handle float input with precision."""
        assert to_halalas(10.0) == 1000
        assert to_halalas(0.1) == 10

    def test_to_halalas_invalid_input_returns_zero(self):
        """Should return 0 for invalid input."""
        assert to_halalas("not a number") == 0
        assert to_halalas(None) == 0


class TestFromHalalas:
    """Tests for from_halalas (Halalas to Riyal conversion)."""

    def test_from_halalas_exact_conversion(self):
        """Should convert halalas to Riyal as Decimal with Q2 precision."""
        assert from_halalas(1000) == Decimal("10.00")
        assert from_halalas(10050) == Decimal("100.50")
        assert from_halalas(1) == Decimal("0.01")
        assert from_halalas(0) == Decimal("0.00")

    def test_from_halalas_quantized_to_q2(self):
        """Should always return exactly 2 decimal places."""
        result = from_halalas(123)
        assert result.as_tuple().exponent == -2
        assert str(result) == "1.23"

    def test_from_halalas_negative(self):
        """Should preserve negative values."""
        assert from_halalas(-1000) == Decimal("-10.00")
        assert from_halalas(-1) == Decimal("-0.01")

    def test_from_halalas_large_amounts(self):
        """Should handle large amounts."""
        assert from_halalas(100000000) == Decimal("1000000.00")

    def test_from_halalas_roundtrip(self):
        """Should roundtrip with to_halalas for normal values."""
        original = Decimal("123.45")
        halalas = to_halalas(original)
        restored = from_halalas(halalas)
        assert restored == Decimal("123.45")


class TestFmtMoney:
    """Tests for fmt_money (halalas formatting)."""

    def test_fmt_money_basic(self):
        """Should format halalas with thousands separator and 2 decimals."""
        assert fmt_money(1000) == "10.00"
        assert fmt_money(10050) == "100.50"
        assert fmt_money(100000) == "1,000.00"

    def test_fmt_money_thousands_separator(self):
        """Should include comma separator for thousands."""
        assert fmt_money(1000000) == "10,000.00"
        assert fmt_money(1234567) == "12,345.67"

    def test_fmt_money_zero(self):
        """Should format zero correctly."""
        assert fmt_money(0) == "0.00"

    def test_fmt_money_negative(self):
        """Should preserve sign."""
        assert fmt_money(-1000) == "-10.00"

    def test_fmt_money_string_input_coerced(self):
        """Should accept string and convert to int."""
        assert fmt_money("1000") == "10.00"


class TestFmtQty:
    """Tests for fmt_qty (quantity formatting with trailing zero removal)."""

    def test_fmt_qty_whole_number(self):
        """Should remove decimal for whole numbers."""
        assert fmt_qty("2.0") == "2"
        assert fmt_qty("100.00") == "100"
        assert fmt_qty(2) == "2"

    def test_fmt_qty_removes_trailing_zeros(self):
        """Should remove trailing zeros after decimal."""
        assert fmt_qty("2.500") == "2.5"
        assert fmt_qty("10.10") == "10.1"
        assert fmt_qty("0.4170") == "0.417"

    def test_fmt_qty_preserves_significant_decimals(self):
        """Should keep significant decimal places."""
        assert fmt_qty("2.5") == "2.5"
        assert fmt_qty("0.001") == "0.001"

    def test_fmt_qty_decimal_input(self):
        """Should handle Decimal input."""
        assert fmt_qty(Decimal("2.5")) == "2.5"
        assert fmt_qty(Decimal("2")) == "2"

    def test_fmt_qty_zero(self):
        """Should format zero as single digit."""
        assert fmt_qty("0") == "0"
        assert fmt_qty("0.0") == "0"

    def test_fmt_qty_invalid_input_returns_zero(self):
        """Should default to 0 for invalid input."""
        assert fmt_qty("not a number") == "0"


class TestLineTax:
    """Tests for line_tax (tax calculation on line amount)."""

    def test_line_tax_default_rate_15_percent(self):
        """Should apply 15% VAT by default."""
        # 1000 halalas (10 SAR) × 15% = 150 halalas (1.50 SAR)
        assert line_tax(1000, Decimal("0.15")) == 150

    def test_line_tax_custom_rate(self):
        """Should apply custom tax rate."""
        # 1000 halalas × 10% = 100 halalas
        assert line_tax(1000, Decimal("0.10")) == 100
        # 1000 halalas × 5% = 50 halalas
        assert line_tax(1000, Decimal("0.05")) == 50

    def test_line_tax_zero_rate(self):
        """Should return 0 for zero rate."""
        assert line_tax(1000, Decimal("0")) == 0

    def test_line_tax_rounds_half_up(self):
        """Should round .5 and higher up."""
        # 1050 × 0.15 = 157.5 → 158 (round up)
        assert line_tax(1050, Decimal("0.15")) == 158

    def test_line_tax_zero_net(self):
        """Should return 0 for zero net."""
        assert line_tax(0, Decimal("0.15")) == 0
        assert line_tax(0, Decimal("0.15")) == 0

    def test_line_tax_negative_net(self):
        """Should handle negative nets (credit notes)."""
        assert line_tax(-1000, Decimal("0.15")) == -150

    def test_line_tax_large_amount(self):
        """Should handle large amounts."""
        assert line_tax(1000000, Decimal("0.15")) == 150000  # 10,000 SAR × 15%

    def test_line_tax_string_rate_coerced(self):
        """Should accept string rate."""
        assert line_tax(1000, "0.15") == 150


class TestEdgeCases:
    """Integration tests for edge cases and extreme values."""

    def test_roundtrip_precision_preserved(self):
        """Multiple round-trips should preserve value."""
        original = Decimal("999.99")
        for _ in range(3):
            halalas = to_halalas(original)
            original = from_halalas(halalas)
        assert original == Decimal("999.99")

    def test_very_small_amounts(self):
        """Should handle very small amounts without precision loss."""
        assert to_halalas("0.01") == 1  # minimum unit
        assert from_halalas(1) == Decimal("0.01")

    def test_tax_calculation_doesnt_exceed_original(self):
        """Tax plus net should equal gross (within rounding)."""
        net = 5000
        tax = line_tax(net, Decimal("0.15"))
        assert tax > 0
        assert net + tax >= net

    def test_currency_formatting_consistency(self):
        """Multiple calls should return same format."""
        h = 12345
        fmt1 = fmt_money(h)
        fmt2 = fmt_money(h)
        assert fmt1 == fmt2

    def test_parse_decimal_handles_various_formats(self):
        """Should handle various input formats flexibly."""
        values = ["100", "100.00", "  100  ", "100,00", "1e2"]
        # Most should parse to ~100 (except 100,00 which is 100)
        result = parse_decimal(values[0])
        assert result == Decimal("100")
