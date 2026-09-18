# -*- coding: utf-8 -*-
"""
تفقيط المبالغ بالحروف العربية.
يدعم الأعداد حتى مئات التريليونات مع قواعد المثنى والجمع،
وتفقيط العملة (ريال/هللة افتراضيًا).
"""
from __future__ import annotations

_ONES = [
    "", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة",
    "عشرة", "أحد عشر", "اثنا عشر", "ثلاثة عشر", "أربعة عشر", "خمسة عشر",
    "ستة عشر", "سبعة عشر", "ثمانية عشر", "تسعة عشر",
]
_TENS = {2: "عشرون", 3: "ثلاثون", 4: "أربعون", 5: "خمسون", 6: "ستون", 7: "سبعون", 8: "ثمانون", 9: "تسعون"}
_HUNDREDS = {
    1: "مئة", 2: "مئتان", 3: "ثلاثمئة", 4: "أربعمئة", 5: "خمسمئة",
    6: "ستمئة", 7: "سبعمئة", 8: "ثمانمئة", 9: "تسعمئة",
}
# (المفرد، المثنى، الجمع 3-10)
_SCALES = {
    1: ("ألف", "ألفان", "آلاف"),
    2: ("مليون", "مليونان", "ملايين"),
    3: ("مليار", "ملياران", "مليارات"),
    4: ("تريليون", "تريليونان", "تريليونات"),
}


def _under_thousand(n: int) -> str:
    """تفقيط عدد من 1 إلى 999 (دون المئات الصفرية)."""
    parts = []
    hundreds, rest = divmod(n, 100)
    if hundreds:
        parts.append(_HUNDREDS[hundreds])
    if rest:
        if rest < 20:
            parts.append(_ONES[rest])
        else:
            tens = rest // 10
            units = rest % 10
            if units:
                parts.append(f"{_ONES[units]} و{_TENS[tens]}")
            else:
                parts.append(_TENS[tens])
    return " و".join(parts)


def tafqit(number: int) -> str:
    """تفقيط عدد صحيح بالحروف العربية. يعيد نصًا مثل: 'خمسة آلاف وثلاثمئة'."""
    n = int(number)
    if n < 0:
        return "سالب " + tafqit(-n)
    if n == 0:
        return "صفر"

    # تقسيم إلى مجموعات ثلاثية من اليمين
    groups = []
    while n:
        groups.append(n % 1000)
        n //= 1000

    pieces = []
    for idx in range(len(groups) - 1, -1, -1):
        value = groups[idx]
        if value == 0:
            continue
        if idx == 0:
            pieces.append(_under_thousand(value))
        else:
            singular, dual, plural = _SCALES[idx]
            if value == 1:
                pieces.append(singular)
            elif value == 2:
                pieces.append(dual)
            elif 3 <= value <= 10:
                pieces.append(f"{_under_thousand(value)} {plural}")
            else:
                pieces.append(f"{_under_thousand(value)} {singular}")
    return " و".join(pieces)


def tafqit_money(amount_halalas: int, currency: str = "ريال", subunit: str = "هللة") -> str:
    """
    تفقيط مبلغ مالي بالهللة:
    'فقط خمسة آلاف وثلاثمئة ريال وخمسة وعشرون هللة لا غير'
    """
    halalas = int(amount_halalas)
    riyals, hal = divmod(abs(halalas), 100)
    parts = []
    if riyals or hal == 0:
        parts.append(f"{tafqit(riyals)} {currency}")
    if hal:
        parts.append(f"{tafqit(hal)} {subunit}")
    body = parts[0] + (" و" + parts[1] if len(parts) > 1 else "")
    prefix = "سالب " if halalas < 0 else ""
    return f"فقط {prefix}{body} لا غير"
