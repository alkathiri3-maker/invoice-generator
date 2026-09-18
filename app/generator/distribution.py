# -*- coding: utf-8 -*-
"""
خوارزمية توزيع المبالغ على الفواتير.
تُشتغل بوحدة الهللة (أعداد صحيحة) فيتطابق المجموع الكلي مع المطلوب
تمامًا دون الحاجة لضبط تقريب لاحق (الفروق بالهللة هي أصل العمل).
"""
from __future__ import annotations

import random


def distribute_amounts(net_target: int, n: int, min_amount: int, rng: random.Random) -> list[int]:
    """
    توزيع المبلغ الصافي net_target (هللة) على n فاتورة، بحيث:
      - كل فاتورة ≥ min_amount هللة
      - المجموع = net_target تمامًا
    الطريقة: توليد n-1 قيمة عشوائية مرتبة بين 0 و free ثم حساب الفروق.
    """
    n = int(n)
    if n < 1:
        raise ValueError("عدد الفواتير يجب أن يكون 1 على الأقل")
    net_target = int(net_target)
    min_amount = int(min_amount)
    if min_amount < 1:
        min_amount = 1
    free = net_target - n * min_amount
    if free < 0:
        raise ValueError(
            f"المبلغ الإجمالي غير كافٍ: الحد الأدنى لكل فاتورة ({min_amount / 100:,.2f} ريال) "
            f"× عدد الفواتير ({n}) = {(n * min_amount) / 100:,.2f} ريال يتجاوز الصافي المطلوب "
            f"({net_target / 100:,.2f} ريال). قلّل الحد الأدنى أو عدد الفواتير أو كبّر المبلغ."
        )
    if n == 1:
        return [net_target]

    cuts = sorted(rng.randint(0, free) for _ in range(n - 1))
    amounts: list[int] = []
    prev = 0
    for c in cuts:
        amounts.append(c - prev)
        prev = c
    amounts.append(free - prev)
    return [min_amount + a for a in amounts]


def invoice_count(count_mode: str, count_total, count_daily: float, date_from, date_to) -> int:
    """حساب عدد الفواتير: عدد إجمالي محدد أو متوسط لكل يوم × عدد الأيام."""
    days = (date_to - date_from).days + 1
    if days < 1:
        raise ValueError("تاريخ النهاية يجب أن يكون في نفس تاريخ البداية أو بعده")
    if count_mode == "daily":
        if not count_daily or count_daily <= 0:
            raise ValueError("متوسط الفواتير اليومي يجب أن يكون رقمًا موجبًا")
        return max(1, round(float(count_daily) * days))
    total = int(count_total or 0)
    if total < 1:
        raise ValueError("عدد الفواتير الإجمالي يجب أن يكون 1 على الأقل")
    return total
