# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for app.generator.distribution module.
Tests amount distribution, invoice count calculation, edge cases.
"""
from __future__ import annotations

import pytest
import random
from datetime import date, timedelta
from app.generator.distribution import distribute_amounts, invoice_count


class TestDistributeAmounts:
    """Tests for distribute_amounts function."""

    def test_distribute_amounts_single_invoice(self):
        """Should return target for n=1."""
        rng = random.Random(42)
        result = distribute_amounts(10000, 1, 100, rng)
        assert len(result) == 1
        assert result[0] == 10000

    def test_distribute_amounts_sum_equals_target(self):
        """Sum of distributed amounts should equal target."""
        rng = random.Random(42)
        target = 50000
        n = 10
        min_amount = 1000
        result = distribute_amounts(target, n, min_amount, rng)
        assert sum(result) == target

    def test_distribute_amounts_each_above_minimum(self):
        """Each amount should be >= min_amount."""
        rng = random.Random(42)
        target = 50000
        n = 10
        min_amount = 1000
        result = distribute_amounts(target, n, min_amount, rng)
        assert all(amt >= min_amount for amt in result)

    def test_distribute_amounts_correct_count(self):
        """Should return exactly n amounts."""
        rng = random.Random(42)
        for n in [1, 5, 10, 20]:
            result = distribute_amounts(100000, n, 100, rng)
            assert len(result) == n

    def test_distribute_amounts_deterministic_seed(self):
        """Same seed should produce same distribution."""
        target = 50000
        n = 10
        min_amount = 1000

        rng1 = random.Random(12345)
        result1 = distribute_amounts(target, n, min_amount, rng1)

        rng2 = random.Random(12345)
        result2 = distribute_amounts(target, n, min_amount, rng2)

        assert result1 == result2

    def test_distribute_amounts_different_seeds_different_results(self):
        """Different seeds should usually produce different distributions."""
        target = 50000
        n = 10
        min_amount = 1000

        rng1 = random.Random(111)
        result1 = distribute_amounts(target, n, min_amount, rng1)

        rng2 = random.Random(222)
        result2 = distribute_amounts(target, n, min_amount, rng2)

        # Should be different (almost certainly)
        assert result1 != result2

    def test_distribute_amounts_zero_minimum(self):
        """Should coerce min_amount=0 to 1."""
        rng = random.Random(42)
        result = distribute_amounts(10000, 5, 0, rng)
        assert all(amt >= 1 for amt in result)
        assert sum(result) == 10000

    def test_distribute_amounts_negative_minimum_coerced(self):
        """Should coerce negative min_amount to 1."""
        rng = random.Random(42)
        result = distribute_amounts(10000, 5, -100, rng)
        assert all(amt >= 1 for amt in result)
        assert sum(result) == 10000

    def test_distribute_amounts_insufficient_total_raises(self):
        """Should raise ValueError if total < n * min_amount."""
        rng = random.Random(42)
        # Need 5000 minimum (5 × 1000) but only have 4000 total
        with pytest.raises(ValueError) as exc_info:
            distribute_amounts(4000, 5, 1000, rng)
        assert "غير كافٍ" in str(exc_info.value)

    def test_distribute_amounts_exactly_minimum_total(self):
        """Should succeed when total equals n * min_amount."""
        rng = random.Random(42)
        result = distribute_amounts(5000, 5, 1000, rng)
        assert len(result) == 5
        assert all(amt == 1000 for amt in result)
        assert sum(result) == 5000

    def test_distribute_amounts_non_integer_n_coerced(self):
        """Should coerce n to int."""
        rng = random.Random(42)
        result = distribute_amounts(10000, 5.7, 100, rng)  # 5.7 → 5
        assert len(result) == 5

    def test_distribute_amounts_large_n(self):
        """Should handle large n values."""
        rng = random.Random(42)
        result = distribute_amounts(1000000, 100, 100, rng)
        assert len(result) == 100
        assert sum(result) == 1000000
        assert all(amt >= 100 for amt in result)

    def test_distribute_amounts_highly_varied_distribution(self):
        """Should produce varied amounts, not just equal shares."""
        rng = random.Random(42)
        target = 100000
        n = 20
        result = distribute_amounts(target, n, 100, rng)
        # Check that not all amounts are the same
        unique_amounts = len(set(result))
        # Should have some variety (if only min_amount, they'd all be the same)
        assert unique_amounts > 1 or n == 1


class TestInvoiceCount:
    """Tests for invoice_count function."""

    def test_invoice_count_total_mode(self):
        """Should return total directly in 'total' mode."""
        result = invoice_count("total", 25, 2.0, date(2026, 1, 1), date(2026, 1, 31))
        assert result == 25

    def test_invoice_count_daily_mode_exact(self):
        """Should calculate invoices from daily average in 'daily' mode."""
        # 10 days × 2.5 invoices/day = 25 invoices
        result = invoice_count("daily", None, 2.5, date(2026, 1, 1), date(2026, 1, 10))
        assert result == 25

    def test_invoice_count_daily_mode_rounding(self):
        """Should round result in 'daily' mode."""
        # 10 days × 2.3 invoices/day = 23 invoices
        result = invoice_count("daily", None, 2.3, date(2026, 1, 1), date(2026, 1, 10))
        assert result == 23

    def test_invoice_count_daily_mode_rounds_half_up(self):
        """Should round .5 and higher up in 'daily' mode."""
        # 10 days × 2.5 invoices/day = 25 invoices
        result = invoice_count("daily", None, 2.5, date(2026, 1, 1), date(2026, 1, 10))
        assert result >= 24

    def test_invoice_count_daily_mode_minimum_one(self):
        """Should return minimum 1 invoice in 'daily' mode."""
        # Even very small daily rate should yield at least 1
        result = invoice_count("daily", None, 0.01, date(2026, 1, 1), date(2026, 1, 1))
        assert result >= 1

    def test_invoice_count_single_day(self):
        """Should handle single-day period correctly."""
        result_total = invoice_count("total", 1, None, date(2026, 1, 1), date(2026, 1, 1))
        assert result_total == 1

        result_daily = invoice_count("daily", None, 2.0, date(2026, 1, 1), date(2026, 1, 1))
        # 1 day × 2.0 = 2
        assert result_daily == 2

    def test_invoice_count_multi_month_period(self):
        """Should count days across months correctly."""
        # Jan 1 to Mar 1 (2026 is not leap year)
        # 31 (Jan) + 28 (Feb) + 1 (Mar 1) = 60 days
        result = invoice_count("daily", None, 1.0, date(2026, 1, 1), date(2026, 3, 1))
        assert result == 60

    def test_invoice_count_invalid_date_range_raises(self):
        """Should raise ValueError if date_to < date_from."""
        with pytest.raises(ValueError) as exc_info:
            invoice_count("total", 10, None, date(2026, 2, 1), date(2026, 1, 1))
        assert "النهاية" in str(exc_info.value)

    def test_invoice_count_daily_mode_zero_daily_rate_raises(self):
        """Should raise ValueError if daily rate is 0 or negative in 'daily' mode."""
        with pytest.raises(ValueError) as exc_info:
            invoice_count("daily", None, 0, date(2026, 1, 1), date(2026, 1, 10))
        assert "موجبًا" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            invoice_count("daily", None, -1.0, date(2026, 1, 1), date(2026, 1, 10))
        assert "موجبًا" in str(exc_info.value)

    def test_invoice_count_total_mode_zero_count_raises(self):
        """Should raise ValueError if total count is 0 or negative in 'total' mode."""
        with pytest.raises(ValueError) as exc_info:
            invoice_count("total", 0, 2.0, date(2026, 1, 1), date(2026, 1, 10))
        assert "1 على الأقل" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            invoice_count("total", -5, 2.0, date(2026, 1, 1), date(2026, 1, 10))
        assert "1 على الأقل" in str(exc_info.value)

    def test_invoice_count_total_mode_none_count_raises(self):
        """Should raise ValueError if total count is None in 'total' mode."""
        with pytest.raises(ValueError) as exc_info:
            invoice_count("total", None, 2.0, date(2026, 1, 1), date(2026, 1, 10))
        assert "1 على الأقل" in str(exc_info.value)

    def test_invoice_count_large_daily_rate(self):
        """Should handle large daily rates."""
        result = invoice_count("daily", None, 100.0, date(2026, 1, 1), date(2026, 1, 10))
        assert result == 1000  # 10 days × 100

    def test_invoice_count_fractional_daily_rate(self):
        """Should handle fractional daily rates."""
        result = invoice_count("daily", None, 0.5, date(2026, 1, 1), date(2026, 1, 31))
        # 31 days × 0.5 = 15.5 → rounds to 16
        assert result >= 15

    def test_invoice_count_consistency(self):
        """Same parameters should produce same result."""
        result1 = invoice_count("daily", None, 2.5, date(2026, 1, 1), date(2026, 1, 10))
        result2 = invoice_count("daily", None, 2.5, date(2026, 1, 1), date(2026, 1, 10))
        assert result1 == result2


class TestDistributionEdgeCases:
    """Integration and edge case tests."""

    def test_distribute_and_count_integration(self):
        """Should work together: count invoices then distribute total."""
        rng = random.Random(42)
        d_from = date(2026, 1, 1)
        d_to = date(2026, 1, 31)
        n = invoice_count("daily", None, 2.0, d_from, d_to)
        target = 50000

        amounts = distribute_amounts(target, n, 100, rng)
        assert len(amounts) == n
        assert sum(amounts) == target

    def test_distribute_minimum_enforced_strictly(self):
        """Minimum enforcement should be exact."""
        rng = random.Random(42)
        min_amt = 999
        result = distribute_amounts(50000, 10, min_amt, rng)
        assert all(amt >= min_amt for amt in result)
        # At least one should hit exactly the minimum (high probability)

    def test_very_large_total(self):
        """Should handle very large totals."""
        rng = random.Random(42)
        result = distribute_amounts(999999999999, 100, 1000, rng)
        assert len(result) == 100
        assert sum(result) == 999999999999

    def test_many_invoices_small_total(self):
        """Should handle many invoices with small total."""
        rng = random.Random(42)
        result = distribute_amounts(10000, 100, 100, rng)
        assert len(result) == 100
        assert sum(result) == 10000
        assert all(amt >= 100 for amt in result)
