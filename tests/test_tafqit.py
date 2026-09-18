# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for app.tafqit module.
Tests Arabic numeral text conversion with edge cases and currency formatting.
"""
from __future__ import annotations

import pytest
from app.tafqit import tafqit, tafqit_money


class TestTafqit:
    """Tests for tafqit (Arabic number-to-text conversion)."""

    def test_tafqit_single_digits(self):
        """Should convert single digits correctly."""
        assert tafqit(0) == "صفر"
        assert tafqit(1) == "واحد"
        assert tafqit(2) == "اثنان"
        assert tafqit(5) == "خمسة"
        assert tafqit(9) == "تسعة"

    def test_tafqit_teens(self):
        """Should handle 10-19 correctly."""
        assert tafqit(10) == "عشرة"
        assert tafqit(11) == "أحد عشر"
        assert tafqit(12) == "اثنا عشر"
        assert tafqit(15) == "خمسة عشر"
        assert tafqit(19) == "تسعة عشر"

    def test_tafqit_tens(self):
        """Should handle multiples of 10."""
        assert tafqit(20) == "عشرون"
        assert tafqit(30) == "ثلاثون"
        assert tafqit(50) == "خمسون"
        assert tafqit(90) == "تسعون"

    def test_tafqit_compound_tens(self):
        """Should handle 21-99 with conjunction."""
        result = tafqit(25)
        assert "خمسة" in result
        assert "عشرون" in result
        assert "و" in result

    def test_tafqit_hundreds(self):
        """Should handle hundreds."""
        assert tafqit(100) == "مئة"
        assert tafqit(200) == "مئتان"
        assert tafqit(300) == "ثلاثمئة"
        assert tafqit(500) == "خمسمئة"
        assert tafqit(900) == "تسعمئة"

    def test_tafqit_hundreds_with_units(self):
        """Should combine hundreds with units."""
        result = tafqit(123)
        assert "مئة" in result
        assert "عشرون" in result or "عشرة" in result or "ثلاثة" in result

    def test_tafqit_thousands(self):
        """Should handle thousands with proper pluralization."""
        assert tafqit(1000) == "ألف"
        assert tafqit(2000) == "ألفان"
        result = tafqit(5000)
        assert "آلاف" in result

    def test_tafqit_thousands_with_units(self):
        """Should combine thousands with units."""
        result = tafqit(5234)
        assert "آلاف" in result
        # 5234 = 5 thousands + 234 = 5 thousands + 2 hundreds + 34
        assert any(x in result for x in ["مئة", "مئتان", "ثلاثمئة"])

    def test_tafqit_millions(self):
        """Should handle millions."""
        assert tafqit(1000000) == "مليون"
        assert tafqit(2000000) == "مليونان"
        result = tafqit(5000000)
        assert "ملايين" in result

    def test_tafqit_billions(self):
        """Should handle billions."""
        assert tafqit(1000000000) == "مليار"
        assert tafqit(2000000000) == "ملياران"
        result = tafqit(5000000000)
        assert "مليارات" in result

    def test_tafqit_trillions(self):
        """Should handle trillions."""
        assert tafqit(1000000000000) == "تريليون"
        result = tafqit(5000000000000)
        assert "تريليونات" in result

    def test_tafqit_large_number(self):
        """Should handle large numbers up to hundreds of trillions."""
        result = tafqit(999999999999)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain multiple scale words
        assert "تريليون" in result or "مليار" in result

    def test_tafqit_negative_number(self):
        """Should prefix negative numbers with 'سالب'."""
        assert tafqit(-1) == "سالب واحد"
        assert tafqit(-100) == "سالب مئة"
        result = tafqit(-5000)
        assert result.startswith("سالب")

    def test_tafqit_scales_pluralization(self):
        """Should apply correct pluralization rules for scales."""
        # 1 thousand
        result1 = tafqit(1000)
        # 2 thousands
        result2 = tafqit(2000)
        # 3-10 thousands
        result3 = tafqit(5000)
        # >10 thousands
        result10 = tafqit(11000)

        assert "ألف" in result1
        assert "ألفان" in result2
        assert "آلاف" in result3
        assert "ألف" in result10

    def test_tafqit_zero(self):
        """Zero should always return صفر."""
        assert tafqit(0) == "صفر"

    def test_tafqit_consistency(self):
        """Multiple calls with same input should return same result."""
        assert tafqit(12345) == tafqit(12345)
        assert tafqit(999) == tafqit(999)


class TestTafqitMoney:
    """Tests for tafqit_money (money amount to Arabic text with currency)."""

    def test_tafqit_money_riyals_only(self):
        """Should format riyal-only amounts."""
        result = tafqit_money(1000)  # 10 SAR
        assert "فقط" in result
        assert "ريال" in result
        assert "لا غير" in result

    def test_tafqit_money_halalas_only(self):
        """Should format halala-only amounts."""
        result = tafqit_money(50)  # 0.50 SAR
        assert "هللة" in result
        assert "ريال" not in result or "صفر" in result or "0" in str(result)

    def test_tafqit_money_riyals_and_halalas(self):
        """Should combine riyals and halalas with 'و'."""
        result = tafqit_money(1050)  # 10.50 SAR = 10 riyals + 50 halalas
        assert "ريال" in result
        assert "هللة" in result
        assert "و" in result

    def test_tafqit_money_zero(self):
        """Should handle zero amount."""
        result = tafqit_money(0)
        assert "صفر" in result
        assert "ريال" in result

    def test_tafqit_money_custom_currency(self):
        """Should support custom currency names."""
        result = tafqit_money(1000, currency="دولار", subunit="سنت")
        assert "دولار" in result
        assert "سنت" not in result or "صفر" in result  # No cents if whole dollars

    def test_tafqit_money_custom_subunit(self):
        """Should support custom subunit name."""
        result = tafqit_money(50, currency="ريال", subunit="فلس")
        assert "فلس" in result

    def test_tafqit_money_large_amount(self):
        """Should format large amounts correctly."""
        result = tafqit_money(1234567)  # 12,345.67 SAR
        assert "فقط" in result
        assert "ريال" in result
        assert "لا غير" in result

    def test_tafqit_money_negative(self):
        """Should prefix negative amounts with 'سالب'."""
        result = tafqit_money(-1000)
        assert "سالب" in result
        assert "ريال" in result

    def test_tafqit_money_exact_format(self):
        """Should follow exact format: فقط [prefix] [amount] [currency/subunit] لا غير."""
        result = tafqit_money(1050)
        assert result.startswith("فقط")
        assert result.endswith("لا غير")

    def test_tafqit_money_consistency(self):
        """Multiple calls with same input should return same result."""
        assert tafqit_money(5500) == tafqit_money(5500)
        assert tafqit_money(100) == tafqit_money(100)

    def test_tafqit_money_large_values(self):
        """Should handle very large amounts."""
        result = tafqit_money(999999999999)  # ~9.99 trillion halalas
        assert "فقط" in result
        assert len(result) > 10

    def test_tafqit_money_boundary_100(self):
        """Should correctly split at 100-halala boundary (1 riyal)."""
        result = tafqit_money(100)  # Exactly 1 riyal
        assert "ريال" in result
        # Should not have halalas since it's exact
        assert "هللة" not in result or "صفر" in result

    def test_tafqit_money_boundary_99(self):
        """Should show only halalas when < 1 riyal."""
        result = tafqit_money(99)
        # With default names, 99 halalas is less than 1 riyal
        # May show both or just halalas depending on implementation
        assert "هللة" in result or ("ريال" in result and "صفر" in result)


class TestTafqitEdgeCases:
    """Integration and edge case tests."""

    def test_tafqit_boundary_values(self):
        """Should handle boundary values correctly."""
        # Around scale boundaries
        assert tafqit(999) != tafqit(1000)
        assert tafqit(999999) != tafqit(1000000)

    def test_tafqit_output_always_string(self):
        """Should always return string."""
        for val in [0, 1, 100, 1000, -50, 999999999]:
            result = tafqit(val)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_tafqit_money_output_always_string(self):
        """Should always return string."""
        for val in [0, 1, 100, 1000, 50000]:
            result = tafqit_money(val)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_tafqit_no_english_numerals(self):
        """Should not contain English numerals in output."""
        result = tafqit(12345)
        # Check that it doesn't contain English digits
        assert not any(c.isdigit() for c in result)

    def test_tafqit_money_format_invariant(self):
        """Should always have فقط at start and لا غير at end."""
        for amount in [0, 1, 100, 5000, 999999]:
            result = tafqit_money(amount)
            assert result.startswith("فقط")
            assert result.endswith("لا غير")
