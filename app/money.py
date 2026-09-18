# -*- coding: utf-8 -*-
"""
عمليات نقدية دقيقة.
كل الحسابات الداخلية للمولّد تتم بوحدة "الهللة" (أعداد صحيحة) لضمان
تطابق المجاميع تمامًا مع المبلغ المطلوب دون أخطاء الفاصلة العائمة.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

Q2 = Decimal("0.01")


def parse_decimal(value, default=None):
    """تحويل أي مدخل إلى Decimal بأمان؛ يعيد default عند الفشل."""
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, AttributeError):
        return default


def to_halalas(value) -> int:
    """تحويل مبلغ إلى هللة (عدد صحيح) بتقريب نصف لأعلى."""
    d = parse_decimal(value, Decimal(0))
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_halalas(halalas: int) -> Decimal:
    """تحويل هللة إلى Decimal بمقدار ريال."""
    return (Decimal(int(halalas)) / 100).quantize(Q2)


def fmt_money(halalas: int) -> str:
    """تنسيق مبلغ (من هللة) بصيغة 1,234.56."""
    return f"{from_halalas(int(halalas)):,.2f}"


def fmt_qty(q) -> str:
    """تنسيق كمية: إزالة الأصفار الزائدة (2 → 2، 2.500 → 2.5، 0.4170 → 0.417)."""
    d = parse_decimal(q, Decimal(0))
    d = d.normalize()
    if d == d.to_integral_value():
        return str(d.quantize(Decimal("1")))
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def line_tax(net_halalas: int, rate) -> int:
    """ضريبة سطر بالهللة: net × rate بتقريب نصف لأعلى."""
    r = parse_decimal(rate, Decimal("0.15"))
    return int((Decimal(int(net_halalas)) * r).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
