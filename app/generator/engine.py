# -*- coding: utf-8 -*-
"""
محرك التوليد الرئيسي: تواريخ، ترقيم بفجوات، توزيع مبالغ، بناء أصناف،
ضريبة 15% على مستوى السطر والفاتورة، QR (مبسط/مرحلة ثانية وهمي)، سندات مرافقة.

ضمانات:
  - الوضع الصافي: مجموع صافي الفواتير = المبلغ المطلوب تمامًا.
  - الوضع الشامل: مجموع إجمالي الفواتير (بعد الضريبة) = المبلغ المطلوب تمامًا
    عبر إزاحة دقيقة لأكبر فاتورة (البحث عن إزاحة تصنع التطابق بالهللة).
  - البذرة العشوائية تعيد إنتاج نفس النتائج بالضبط.
"""
from __future__ import annotations

import json
import random
import uuid
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.money import to_halalas, from_halalas, line_tax
from app.generator.distribution import distribute_amounts, invoice_count
from app.generator.items_builder import ItemDef, build_lines, Line

VAT_RATE = Decimal("0.15")

NOTES_POOL = [
    "", "", "", "", "",   # الأغلب بلا ملاحظات
    "دفعة تحت الحساب", "فاتورة شهرية مجمعة", "تسليم فوري من المستودع",
    "عرض خاص لفترة محدودة", "الدفع خلال 30 يومًا من تاريخ الفاتورة",
    "شاملة التوصيل داخل المدينة", "بعد الفحص والاستلام",
]

PAYMENT_WEIGHTS = [("نقدي", 0.40), ("آجل", 0.40), ("تحويل", 0.20)]


@dataclass
class GenParams:
    company_id: int
    customer_ids: list[int]
    item_group_ids: list[int] = field(default_factory=list)   # فارغ = كل الأصناف
    item_ids: list[int] = field(default_factory=list)         # أصناف محددة (items_mode=individual)
    items_mode: str = "groups"                                # groups | individual
    date_from: str = ""               # YYYY-MM-DD
    date_to: str = ""                 # YYYY-MM-DD
    count_mode: str = "total"         # total | daily
    count_total: int = 20
    count_daily: float = 2.0
    amount: str = "10000"             # نص لتفادي مشاكل العشرية
    amount_mode: str = "net"          # net | gross
    min_amount: str = "100"
    payment_type: str = "نقدي"        # نقدي | آجل | تحويل | عشوائي
    seed: str = ""                    # فارغ = بذرة عشوائية
    qr_mode: str = "none"             # none | simple | phase2
    with_receipts: bool = False
    receipt_type: str = "قبض"         # قبض | صرف | عشوائي
    invoice_start: int = 1001
    number_prefix: str = ""
    receipt_start: int = 5001
    template_invoice_id: int | None = None
    template_receipt_id: int | None = None
    random_notes: bool = True

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(raw: str) -> "GenParams":
        return GenParams(**json.loads(raw))


# ══════════════════════════════════════════════════════════════════════════
#  مولدات مساعدة
# ══════════════════════════════════════════════════════════════════════════

def _plan_schedule(n: int, d_from: date, d_to: date, rng: random.Random,
                   cust_ids: list[int]) -> list[tuple[datetime, int]]:
    """جدولة n فاتورة داخل الفترة مع ضمانين:
      1) يوم فريد لكل عميل — لا يتكرر يوم (ولا تاريخ) الفاتورة لنفس العميل أبدًا.
      2) ترتيب زمني تصاعدي (يُقابَل بالترقيم التصاعدي).
    يعيد قائمة (datetime, customer_id) مرتبة تصاعديًا، ويرفع خطأً إذا نفدت أيام
    الفترة لأحد العملاء."""
    days = (d_to - d_from).days + 1
    remaining: dict[int, list[int]] = {}      # لكل عميل: الأيام غير المستخدمة
    pairs: list[tuple[datetime, int]] = []
    for cid in cust_ids:
        rem = remaining.get(cid)
        if rem is None:
            rem = list(range(days))
            remaining[cid] = rem
        if not rem:
            raise ValueError(
                "تعذر الجدولة: أيام الفترة نفدت لأحد العملاء — "
                f"وسّع الفترة الزمنية أو قلل عدد الفواتير (أيام الفترة: {days})"
            )
        idx = rng.randrange(len(rem))
        off = rem[idx]
        rem[idx] = rem[-1]
        rem.pop()
        d = d_from + timedelta(days=off)
        sec = rng.randint(8 * 3600, 20 * 3600 - 60)     # من 08:00:00 إلى 19:59:xx
        pairs.append((datetime(d.year, d.month, d.day,
                               sec // 3600, (sec % 3600) // 60, sec % 60), cid))
    pairs.sort(key=lambda t: t[0])
    return pairs


def _validate_uniqueness(built: list[BuiltInvoice]) -> None:
    """تحقق نهائي دفاعي: يوم الفاتورة ورقمها فريدان لكل عميل."""
    seen_day: set[tuple[int, str]] = set()
    seen_num: set[tuple[int, int]] = set()
    for inv in built:
        kday = (inv.customer_id, inv.dt.strftime("%Y-%m-%d"))
        if kday in seen_day:
            raise ValueError(f"تكرار يوم فاتورة لنفس العميل ({kday[1]})")
        seen_day.add(kday)
        knum = (inv.customer_id, inv.number)
        if knum in seen_num:
            raise ValueError(f"تكرار رقم فاتورة لنفس العميل ({inv.number})")
        seen_num.add(knum)


def _invoice_numbers(n: int, start: int, rng: random.Random,
                     gap_prob: float = 0.22) -> list[int]:
    """ترقيم متسلسل مع فجوات عشوائية (+9 إلى +47) لمحاكاة فواتير ملغاة."""
    numbers, num = [], start
    for i in range(n):
        numbers.append(num)
        if i < n - 1 and rng.random() < gap_prob:
            num += rng.randint(9, 47)      # فجوة: أرقام متخطاة (فواتير ملغاة/مسودة)
        else:
            num += 1
    return numbers


def _pick_payment(payment_type: str, rng: random.Random) -> str:
    if payment_type != "عشوائي":
        return payment_type
    x = rng.random()
    acc = 0.0
    for name, w in PAYMENT_WEIGHTS:
        acc += w
        if x <= acc:
            return name
    return "نقدي"


def _deterministic_uuid(*parts) -> str:
    """UUID ثابت يعاد إنتاجه بنفس المدخلات (لتوافق إعادة التوليد بالبذرة)."""
    ns = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")   # uuid.NAMESPACE_DNS
    return str(uuid.uuid5(ns, "|".join(str(p) for p in parts)))


# ══════════════════════════════════════════════════════════════════════════
#  هياكل النتائج في الذاكرة
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class BuiltInvoice:
    number: int
    dt: datetime
    customer_id: int
    payment: str
    notes: str
    lines: list[Line] = field(default_factory=list)

    @property
    def subtotal(self) -> int:
        return sum(ln.net for ln in self.lines)

    @property
    def tax(self) -> int:
        return sum(ln.tax for ln in self.lines)

    @property
    def total(self) -> int:
        return self.subtotal + self.tax

    def copy_lines(self) -> list[Line]:
        return [
            Line(item=ln.item, quantity=ln.quantity, net=ln.net)
            for ln in self.lines
        ]


@dataclass
class BuiltReceipt:
    number: int
    dt: datetime
    customer_id: int
    amount: int
    type: str
    related_invoice_number: int
    notes: str = ""


def _parse_date(s: str, label: str) -> date:
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{label} غير صالح: '{s}' — استخدم صيغة YYYY-MM-DD") from exc


# ══════════════════════════════════════════════════════════════════════════
#  الإزاحة الدقيقة للوضع الشامل (تطابق الإجمالي بالهللة)
# ══════════════════════════════════════════════════════════════════════════

def _shift_invoice_lines(inv: BuiltInvoice, delta: int, cheapest: ItemDef) -> BuiltInvoice | None:
    """إزاحة إجمالي فاتورة بمقدار ≈ delta هللة بتعديل/إضافة سطر الصنف الأرخص."""
    if delta == 0:
        return inv
    lines = inv.copy_lines()
    target = None
    for ln in lines:
        if ln.item.id == cheapest.id and (delta > 0 or ln.net + delta > 0):
            target = ln
            break
    if target is None:
        if delta < 0:
            # أنقص أكبر سطر (إزاحة سالبة صغيرة)
            big = max(lines, key=lambda ln: ln.net)
            if big.net + delta <= 0:
                return None
            big.net += delta
            big.quantity += Decimal(delta) / Decimal(big.item.price)
        else:
            lines.append(Line(item=cheapest, quantity=Decimal(delta) / Decimal(cheapest.price),
                              net=delta))
    else:
        target.net += delta
        target.quantity += Decimal(delta) / Decimal(target.item.price)
        if target.net <= 0 or target.quantity <= 0:
            return None
    out = BuiltInvoice(number=inv.number, dt=inv.dt, customer_id=inv.customer_id,
                       payment=inv.payment, notes=inv.notes, lines=lines)
    return out


def _adjust_for_exact_gross(built: list[BuiltInvoice], target_gross: int,
                            items: list[ItemDef]) -> None:
    """في الوضع الشامل: اجعل مجموع الإجماليات = المطلوب تمامًا (إزاحة أكبر فاتورة)."""
    diff = target_gross - sum(b.total for b in built)
    if diff == 0:
        return
    target_inv = max(built, key=lambda b: b.subtotal)
    cheapest = min(items, key=lambda it: it.price)
    base = int(round(Decimal(diff) / Decimal("1.15")))
    candidates = [base]
    for k in range(1, 900):
        candidates.extend([base + k, base - k, k, -k])
    rest_total = sum(b.total for b in built if b is not target_inv)
    for delta in candidates:
        trial = _shift_invoice_lines(target_inv, delta, cheapest)
        if trial is None:
            continue
        if rest_total + trial.total == target_gross:
            target_inv.lines = trial.lines
            return
    raise ValueError(
        f"تعذر مطابقة الإجمالي الشامل تمامًا (الفرق {diff} هللة) — "
        "جرّب تعطيل الحد الأدنى المرتفع أو تعديل المبلغ."
    )


# ══════════════════════════════════════════════════════════════════════════
#  الدالة الرئيسية
# ══════════════════════════════════════════════════════════════════════════

def generate(conn, p: GenParams, persist: bool = True, return_built: bool = False) -> dict:
    """توليد دفعة فواتير كاملة. يعيد ملخصًا، ويخزن في القاعدة عند persist=True.
    return_built=True يعيد أيضًا الكائنات المبنية (_built/_receipts) للمعاينة الجافة."""
    from app.money import from_halalas
    from app.qr_service import attach_qr
    from app.generator.distribution import invoice_count as _ic  # noqa: F401 (توثيق الاعتماد)

    # ── التحقق من المدخلات ──
    company = conn.execute("SELECT * FROM companies WHERE id=?", (p.company_id,)).fetchone()
    if not company:
        raise ValueError("اختر شركة بائعة صحيحة")
    if not p.customer_ids:
        raise ValueError("اختر عميلًا واحدًا على الأقل")
    placeholders = ",".join("?" * len(p.customer_ids))
    found = conn.execute(
        f"SELECT id FROM customers WHERE id IN ({placeholders})", p.customer_ids
    ).fetchall()
    if len(found) != len(set(p.customer_ids)):
        raise ValueError("أحد العملاء المحددين غير موجود")
    if p.items_mode == "individual" and p.item_ids:
        # اختيار أصناف محددة يدويًا
        iph = ",".join("?" * len(p.item_ids))
        rows = conn.execute(
            f"""SELECT i.*, g.id AS group_id, g.name AS group_name
                FROM items i LEFT JOIN item_groups g ON g.id=i.group_id
                WHERE i.id IN ({iph}) ORDER BY unit_price ASC""",
            [int(i) for i in p.item_ids],
        ).fetchall()
        if not rows:
            raise ValueError("لا توجد أصناف محددة صحيحة — اختر أصنافًا أولًا")
    elif p.item_group_ids:
        gph = ",".join("?" * len(p.item_group_ids))
        rows = conn.execute(
            f"""SELECT i.*, g.id AS group_id, g.name AS group_name
                FROM items i LEFT JOIN item_groups g ON g.id=i.group_id
                WHERE i.group_id IN ({gph}) ORDER BY unit_price ASC""",
            [int(g) for g in p.item_group_ids],
        ).fetchall()
        if not rows:
            raise ValueError("المجموعات المحددة لا تحتوي أصنافًا — اختر مجموعة أخرى أو أضف أصنافًا لها")
    else:
        rows = conn.execute(
            """SELECT i.*, g.id AS group_id, g.name AS group_name
               FROM items i LEFT JOIN item_groups g ON g.id=i.group_id
               ORDER BY unit_price ASC"""
        ).fetchall()
        if not rows:
            raise ValueError("لا توجد أصناف — أضف أصنافًا أولاً")
    items = [
        ItemDef(id=r["id"], name=r["name"], code=r["code"], unit=r["unit"],
                price=to_halalas(r["unit_price"]), tax_rate=Decimal(str(r["tax_rate"])),
                group_id=r["group_id"], group_name=r["group_name"] or "")
        for r in rows
    ]
    if any(it.price <= 0 for it in items):
        raise ValueError("يوجد صنف بسعر صفر أو سالب — صحّح الأسعار أولًا")

    d_from = _parse_date(p.date_from, "تاريخ البداية")
    d_to = _parse_date(p.date_to, "تاريخ النهاية")
    n = invoice_count(p.count_mode, p.count_total, p.count_daily, d_from, d_to)

    # ── البذرة العشوائية ──
    if str(p.seed or "").strip().isdigit():
        seed_used = int(p.seed)
    else:
        seed_used = random.randrange(2**31)
    rng = random.Random(seed_used)

    # ── المبالغ المستهدفة ──
    target_halalas = to_halalas(p.amount)
    if target_halalas < n:
        raise ValueError("المبلغ الإجمالي صغير جدًا مقارنة بعدد الفواتير")
    if p.amount_mode == "gross":
        # صافٍ مبدئي = الشامل ÷ 1.15 (يُضبط لاحقًا لتطابق الشامل تمامًا)
        net_total = int((Decimal(target_halalas) / Decimal("1.15")).quantize(
            Decimal("1"), rounding="ROUND_HALF_UP"))
    else:
        net_total = target_halalas
    min_h = max(1, to_halalas(p.min_amount))
    amounts = distribute_amounts(net_total, n, min_h, rng)

    # ── العملاء والمدفوعات والملاحظات ──
    cust_ids = [rng.choice(list(p.customer_ids)) for _ in range(n)]
    payments = [_pick_payment(p.payment_type, rng) for _ in range(n)]
    notes = [rng.choice(NOTES_POOL) if p.random_notes else "" for _ in range(n)]

    # ── الجدولة: يوم فريد لكل عميل + ترتيب زمني تصاعدي ──
    schedule = _plan_schedule(n, d_from, d_to, rng, cust_ids)
    numbers = _invoice_numbers(n, int(p.invoice_start), rng)

    # ── بناء الفواتير ──
    built: list[BuiltInvoice] = []
    for i, (dt, cid) in enumerate(schedule):
        inv = BuiltInvoice(number=numbers[i], dt=dt, customer_id=cid,
                           payment=payments[i], notes=notes[i])
        inv.lines = build_lines(amounts[i], items, rng)
        built.append(inv)

    _validate_uniqueness(built)

    if p.amount_mode == "gross":
        _adjust_for_exact_gross(built, target_halalas, items)

    # ── رمز QR ──
    if p.qr_mode in ("simple", "phase2"):
        attach_qr(built, company, p.qr_mode, seed_used)

    # ── السندات المرافقة ──
    receipts: list[BuiltReceipt] = []
    if p.with_receipts:
        for inv in built:
            rtype = _pick_receipt_type(p.receipt_type, rng)
            dt = inv.dt + timedelta(minutes=5 + rng.randint(0, 90))
            receipts.append(BuiltReceipt(
                number=int(p.receipt_start) + len(receipts),
                dt=dt, customer_id=inv.customer_id, amount=inv.total,
                type=rtype, related_invoice_number=inv.number,
            ))

    summary = {
        "seed": seed_used,
        "count": n,
        "receipts": len(receipts),
        "total_net": float(from_halalas(sum(b.subtotal for b in built))),
        "total_tax": float(from_halalas(sum(b.tax for b in built))),
        "total_gross": float(from_halalas(sum(b.total for b in built))),
        "target": float(from_halalas(target_halalas)),
        "amount_mode": p.amount_mode,
        "first_number": f"{p.number_prefix}{built[0].number}" if built else "",
        "last_number": f"{p.number_prefix}{built[-1].number}" if built else "",
    }

    if persist:
        summary["batch_id"] = _persist(conn, p, built, receipts, seed_used)

    if return_built:
        summary["_built"] = built
        summary["_receipts"] = receipts
        summary["_company_id"] = p.company_id

    return summary


def _pick_receipt_type(rtype: str, rng: random.Random) -> str:
    if rtype in ("قبض", "صرف"):
        return rtype
    return "قبض" if rng.random() < 0.75 else "صرف"

def _persist(conn, p: GenParams, built: list[BuiltInvoice],
             receipts: list[BuiltReceipt], seed_used: int) -> int:
    """تخزين الدفعة (فواتير + أسطر + سندات) في القاعدة داخل معاملة واحدة."""
    from app import db as dbm
    from app.money import from_halalas as fh

    created = dbm.now_iso()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO batches (created_at, seed, params_json, invoice_count, "
        "total_net, total_tax, total_gross) VALUES (?,?,?,?,?,?,?)",
        (created, seed_used, p.to_json(), len(built),
         float(fh(sum(b.subtotal for b in built))),
         float(fh(sum(b.tax for b in built))),
         float(fh(sum(b.total for b in built)))),
    )
    batch_id = cur.lastrowid

    number_to_id: dict[int, int] = {}
    for inv in built:
        cur.execute(
            "INSERT INTO invoices (batch_id, company_id, customer_id, invoice_number, "
            "invoice_date, invoice_time, payment_type, subtotal, tax_amount, total_amount, "
            "template_id, notes, qr_mode, qr_payload_b64, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (batch_id, p.company_id, inv.customer_id, f"{p.number_prefix}{inv.number}",
             inv.dt.strftime("%Y-%m-%d"), inv.dt.strftime("%H:%M:%S"), inv.payment,
             float(fh(inv.subtotal)), float(fh(inv.tax)), float(fh(inv.total)),
             p.template_invoice_id, inv.notes,
             getattr(inv, "qr_mode", "none") or "none",
             getattr(inv, "qr_payload_b64", "") or "", created),
        )
        inv_id = cur.lastrowid
        number_to_id[inv.number] = inv_id
        for ln in inv.lines:
            cur.execute(
                "INSERT INTO invoice_items (invoice_id, item_id, item_name, quantity, "
                "unit_price, line_total, line_tax, line_gross) VALUES (?,?,?,?,?,?,?,?)",
                (inv_id, ln.item.id, ln.item.name, float(ln.display_quantity),
                 float(fh(ln.item.price)), float(fh(ln.net)), float(fh(ln.tax)),
                 float(fh(ln.gross))),
            )

    for rc in receipts:
        cur.execute(
            "INSERT INTO receipts (batch_id, company_id, customer_id, receipt_number, "
            "receipt_date, receipt_time, amount, type, related_invoice_id, template_id, "
            "notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (batch_id, p.company_id, rc.customer_id, str(rc.number),
             rc.dt.strftime("%Y-%m-%d"), rc.dt.strftime("%H:%M:%S"),
             float(fh(rc.amount)), rc.type, number_to_id.get(rc.related_invoice_number),
             p.template_receipt_id,
             f"سند مرافق للفاتورة رقم {p.number_prefix}{rc.related_invoice_number}",
             created),
        )
    conn.commit()
    return batch_id



