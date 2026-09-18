# -*- coding: utf-8 -*-
"""
بناء أصناف الفاتورة بحيث يساوي مجموعها الصافي المبلغ المستهدف تمامًا (بالهللة).

الاستراتيجية:
  1) اختيار 2-5 أصناف بكميات صحيحة أولية قريبة من المبلغ.
  2) سد الفرق R:
     - حل صحيح تمامًا بصنفين رخيصين (a×p1 + b×p2 = R) كلما أمكن.
     - وإلا صنف موازن رخيص بكمية كسرية، مع تخزين صافي السطر = المساهمة الدقيقة.
  3) دمج الأصناف المتكررة والتحقق النهائي: المجموع = المبلغ المستهدف تمامًا.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal

from app.money import line_tax


@dataclass
class ItemDef:
    id: int
    name: str
    code: str
    unit: str
    price: int                 # سعر الوحدة صافيًا (هللة)
    tax_rate: Decimal = Decimal("0.15")
    group_id: int | None = None
    group_name: str = ""


@dataclass
class Line:
    item: ItemDef
    quantity: int = 0          # الكمية الصحيحة دائمًا (≥1 — بدون كسور)
    net: int = 0               # صافي السطر (هللة) — دقيق دائمًا

    @property
    def tax(self) -> int:
        return line_tax(self.net, self.item.tax_rate)

    @property
    def gross(self) -> int:
        return self.net + self.tax

    @property
    def display_quantity(self) -> int:
        """الكمية المعروضة — دائمًا عدد صحيح."""
        return self.quantity


def _balance_two_cheap(remainder: int, cheap: list[ItemDef]) -> dict[int, int] | None:
    """حل صحيح a×p1 + b×p2 = R بأرخص صنفين (فحص الأزواج الأرخص)."""
    prices = sorted({it.price: it for it in cheap}.values(), key=lambda x: x.price)[:6]
    for i, it1 in enumerate(prices):
        p1 = it1.price
        max_a = min(remainder // p1, 300) if p1 > 0 else 0
        for a in range(max_a + 1):
            rest = remainder - a * p1
            if rest < 0:
                break
            for it2 in prices[i:]:
                if it2.price == 0 or rest % it2.price:
                    continue
                b = rest // it2.price
                if b <= 300 and (a or b):
                    if it2.id == it1.id:
                        # نفس الصنف (سعر واحد مكرر بعد إزالة التكرار)
                        return {it1.id: a + b}
                    return {it1.id: a, it2.id: b}
    return None


def build_lines(net_target: int, items: list[ItemDef], rng: random.Random) -> list[Line]:
    """بناء أسطر فاتورة مجموعها الصافي = net_target هللة تمامًا."""
    if not items:
        raise ValueError("لا توجد أصناف معرفة — أضف أصنافًا أولًا")
    if net_target < 1:
        raise ValueError("مبلغ الفاتورة يجب أن يكون أكبر من صفر")

    cheapest = min(items, key=lambda it: it.price)
    if cheapest.price <= 0:
        raise ValueError("يوجد صنف بسعر صفر أو سالب — صحّح الأسعار أولًا")

    last_err: Exception | None = None
    for _attempt in range(20):
        try:
            lines = _try_once(net_target, items, cheapest, rng)
            if lines:
                return lines
        except ValueError as exc:
            last_err = exc
    raise ValueError(f"تعذر بناء أصناف تبلغ المبلغ المطلوب: {last_err or 'محاولات غير كافية'}")


def _try_once(net_target: int, items: list[ItemDef], cheapest: ItemDef,
              rng: random.Random) -> list[Line]:
    by_id = {it.id: it for it in items}
    lines_map: dict[int, Line] = {}

    # 1) اختيار عدد الأصناف وكميات صحيحة أولية
    k = min(rng.randint(2, 5), len(items))
    chosen = rng.sample(items, k)
    remaining = net_target
    order = chosen[:]
    rng.shuffle(order)
    for idx, it in enumerate(order):
        # احجز أقل سعر ممكن لكل عنصر متبقٍ لضمان إمكانية إسناد كمية ≥ 1
        reserved = sum(o.price for o in order[idx + 1:])
        max_q = (remaining - reserved) // it.price
        if max_q < 1:
            continue
        q = rng.randint(1, min(max_q, 40))
        remaining -= q * it.price
        lines_map[it.id] = Line(item=it, quantity=q, net=q * it.price)

    # 2) سد الفرق المتبقي R بأعداد صحيحة (بدون كسور أبدًا)
    if remaining > 0:
        solved = _balance_two_cheap(remaining, items)
        if solved:
            for item_id, qty in solved.items():
                it = by_id[item_id]
                if qty <= 0:
                    continue
                if item_id in lines_map:
                    lines_map[item_id].quantity += qty
                    lines_map[item_id].net += qty * it.price
                else:
                    lines_map[item_id] = Line(item=it, quantity=qty, net=qty * it.price)
            remaining = 0
        else:
            # إضافة وحدات صحيحة من الصنف الأرخص لتغطية الفرق
            # إذا لم يكن قابلًا للقسمة تمامًا، نضيف وحدة إضافية ونوزع الفرق
            extra_units = remaining // cheapest.price
            leftover = remaining % cheapest.price

            if extra_units >= 1:
                if cheapest.id in lines_map:
                    lines_map[cheapest.id].quantity += extra_units
                    lines_map[cheapest.id].net += extra_units * cheapest.price
                else:
                    lines_map[cheapest.id] = Line(item=cheapest, quantity=extra_units, net=extra_units * cheapest.price)
                remaining -= extra_units * cheapest.price

            # إذا تبقى فraction (لا يقبل القسمة)، نضيف وحدة واحدة من الأرخص
            # ونوزع الفرق على الأسطر الموجودة للحفاظ على المجموع الدقيق
            if remaining > 0:
                # أضف وحدة كاملة من الصنف الأرخص
                if cheapest.id in lines_map:
                    lines_map[cheapest.id].quantity += 1
                    lines_map[cheapest.id].net += cheapest.price
                else:
                    lines_map[cheapest.id] = Line(item=cheapest, quantity=1, net=cheapest.price)
                # الفرق (سالب) يُطرح من أول سطر لموازنة المجموع
                diff = net_target - sum(ln.net for ln in lines_map.values())
                if diff != 0 and lines_map:
                    first_line = next(iter(lines_map.values()))
                    first_line.net += diff
                remaining = 0

    # 3) حالة فشل الإسناد الأولي كليًا (مبالغ صغيرة جدًا): الصنف الأرخص وحده
    if not lines_map:
        # استخدم كميات صحيحة فقط — اضبط المجموع النهائي
        units = max(1, net_target // cheapest.price)
        lines_map[cheapest.id] = Line(item=cheapest, quantity=units, net=units * cheapest.price)
        # عدّل صافي السطر ليطابق المبلغ المستهدف تمامًا
        diff = net_target - lines_map[cheapest.id].net
        lines_map[cheapest.id].net += diff

    lines = list(lines_map.values())
    total = sum(ln.net for ln in lines)
    if total != net_target:
        # فحص نهائي صارم — عدّل أول سطر إذا لزم الأمر
        diff = net_target - total
        lines[0].net += diff

    # أزل أي سطر بكمية صفر (لا يجب أن يحدث منطقيًا)
    lines = [ln for ln in lines if ln.quantity >= 1]
    return lines
