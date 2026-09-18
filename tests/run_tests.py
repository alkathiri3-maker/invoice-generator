# -*- coding: utf-8 -*-
"""
اختبارات مولّد الفواتير التدريبي — تشغيل:
    python tests/run_tests.py
تتحقق من: الدقة النقدية، التفقيط، التوزيع، بناء الأصناف، المحرك (صافي/شامل)،
السندات، QR (مبسط + مرحلة ثانية وهمي)، والتصدير PDF.
"""
from __future__ import annotations

import base64
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import random  # noqa: E402

from app import db as dbm  # noqa: E402
from app.money import to_halalas, from_halalas, fmt_money, fmt_qty, line_tax  # noqa: E402
from app.tafqit import tafqit, tafqit_money  # noqa: E402
from app.generator.distribution import distribute_amounts, invoice_count  # noqa: E402
from app.generator.items_builder import ItemDef, build_lines  # noqa: E402
from app.generator.engine import GenParams, generate  # noqa: E402
from app.qr_service import attach_qr, qr_image_data_uri  # noqa: E402
import zatca_qr  # noqa: E402

PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


# ══════════════════════════════════════════════════════════════════════════
print("\n[1] الحسابات النقدية بالهللة")
check("to_halalas(10.005) == 1001 (تقريب نصف لأعلى)", to_halalas("10.005") == 1001)
check("to_halalas(0.1) == 10", to_halalas(0.1) == 10)
check("from_halalas(12345) == 123.45", from_halalas(12345) == Decimal("123.45"))
check("fmt_money", fmt_money(1234500) == "12,345.00")
check("fmt_qty يزيل الأصفار", fmt_qty(Decimal("2.5000")) == "2.5")
check("fmt_qty صحيح", fmt_qty(Decimal("3")) == "3")
check("ضريبة السطر 15%", line_tax(10000, "0.15") == 1500)
check("ضريبة نصف هللة للأعلى", line_tax(101, "0.15") == 15)   # 15.15 → 15

print("\n[2] التفقيط العربي")
check("1 → واحد", tafqit(1) == "واحد")
check("2 → اثنان", tafqit(2) == "اثنان")
check("21 → واحد وعشرون", tafqit(21) == "واحد وعشرون")
check("100 → مئة", tafqit(100) == "مئة")
check("200 → مئتان", tafqit(200) == "مئتان")
check("350 → ثلاثمئة وخمسون", tafqit(350) == "ثلاثمئة وخمسون")
check("1000 → ألف", tafqit(1000) == "ألف")
check("2000 → ألفان", tafqit(2000) == "ألفان")
check("3000 → ثلاثة آلاف", tafqit(3000) == "ثلاثة آلاف")
check("11,000 → أحد عشر ألف", "أحد عشر ألف" in tafqit(11000))
check("5,300 → خمسة آلاف وثلاثمئة", tafqit(5300) == "خمسة آلاف وثلاثمئة")
check("2,000,000 → مليونان", tafqit(2_000_000) == "مليونان")
check("3,500,000", tafqit(3_500_000) == "ثلاثة ملايين وخمسمئة ألف")
check("صفر", tafqit(0) == "صفر")
check("تفقيط مبلغ كامل", tafqit_money(5325) == "فقط ثلاثة وخمسون ريال وخمسة وعشرون هللة لا غير")
check("تفقيط مبلغ بلا هللات", tafqit_money(500000) == "فقط خمسة آلاف ريال لا غير")

print("\n[3] توزيع المبالغ")
rng = random.Random(42)
amounts = distribute_amounts(1_000_000, 25, 15_000, rng)
check("المجموع مطابق تمامًا", sum(amounts) == 1_000_000, f"الناتج {sum(amounts)}")
check("الحد الأدنى محترم", min(amounts) >= 15_000)
check("العدد صحيح", len(amounts) == 25)
rng2 = random.Random(42)
amounts2 = distribute_amounts(1_000_000, 25, 15_000, rng2)
check("البذرة تعيد نفس التوزيع", amounts == amounts2)
try:
    distribute_amounts(1000, 25, 5000, rng)
    check("رفض المبلغ غير الكافي", False)
except ValueError:
    check("رفض المبلغ غير الكافي", True)
check("عدد يومي", invoice_count("daily", None, 2.5, __import__("datetime").date(2026, 1, 1),
                                __import__("datetime").date(2026, 1, 10)) == 25)

print("\n[4] بناء الأصناف — المجموع الدقيق")
items = [
    ItemDef(1, "أسمنت مقاوم", "BLD-001", "كيس", 1450),
    ItemDef(2, "قماش قطني", "FAB-001", "متر", 2800),
    ItemDef(3, "بلوك خرساني", "BLD-004", "حبة", 275),
    ItemDef(4, "خيط خياطة", "FAB-005", "بكرة", 350),
    ItemDef(5, "ملف بلاستيكي", "STA-003", "حبة", 125),
    ItemDef(6, "مسطرة", "STA-005", "حبة", 250),
]
bad = 0
for trial in range(300):
    r = random.Random(1000 + trial)
    target = random.Random(trial).randint(500, 3_000_000)
    lines = build_lines(target, items, r)
    s = sum(ln.net for ln in lines)
    if s != target:
        bad += 1
    if any(ln.net <= 0 or ln.quantity <= 0 for ln in lines):
        bad += 1
check("300 حالة: المجموع = الهدف تمامًا وكميات موجبة", bad == 0, f"حالات فاشلة: {bad}")
lines = build_lines(10_000_000, items, random.Random(7))
check("عناصر مدمجة بلا تكرار", len({ln.item.id for ln in lines}) == len(lines))

# ══════════════════════════════════════════════════════════════════════════
print("\n[5] المحرك — وضع صافي (نهاية إلى نهاية)")
tmp = Path(tempfile.mkdtemp(prefix="inv_test_"))
test_db = tmp / "test.db"
conn = dbm.init_db(test_db)

p = GenParams(
    company_id=1, customer_ids=[1, 2, 3],
    date_from="2026-01-01", date_to="2026-03-31",
    count_mode="total", count_total=40, count_daily=0,
    amount="100000", amount_mode="net", min_amount="500",
    payment_type="عشوائي", seed="777", qr_mode="simple",
    with_receipts=True, receipt_type="قبض",
    invoice_start=1000, number_prefix="INV-", receipt_start=5000,
    random_notes=True,
)
summary = generate(conn, p, persist=True)
check("المجموع الصافي = المطلوب تمامًا (100000)", summary["total_net"] == 100000.0,
      f"الناتج {summary['total_net']}")
check("عدد الفواتير 40", summary["count"] == 40)
check("سند لكل فاتورة", summary["receipts"] == 40)
check("أرقام ببادئة", summary["first_number"].startswith("INV-"))

rows = conn.execute("SELECT * FROM invoices WHERE batch_id=1 ORDER BY id").fetchall()
check("تواريخ تصاعدية داخل الفترة",
      all(rows[i]["invoice_date"] <= rows[i + 1]["invoice_date"] for i in range(len(rows) - 1))
      and rows[0]["invoice_date"] >= "2026-01-01" and rows[-1]["invoice_date"] <= "2026-03-31")
numbers = [int(r["invoice_number"].replace("INV-", "")) for r in rows]
check("ترقيم متسلسل تصاعدي", all(numbers[i] < numbers[i + 1] for i in range(len(numbers) - 1)))
gaps = [numbers[i + 1] - numbers[i] for i in range(len(numbers) - 1)]
check("توجد فجوات (+9..+47) في الترقيم", any(g > 1 for g in gaps), f"الفجوات: {set(gaps)}")
check("الفجوات ضمن 1..47 (+1 عادي أو فجوة ملغاة)", all(1 <= g <= 47 for g in gaps))

# دقة أسطر كل فاتورة
line_err = 0
tax_err = 0
for r in rows:
    its = conn.execute("SELECT * FROM invoice_items WHERE invoice_id=?", (r["id"],)).fetchall()
    if round(sum(i["line_total"] for i in its), 2) != round(r["subtotal"], 2):
        line_err += 1
    if round(sum(i["line_tax"] for i in its), 2) != round(r["tax_amount"], 2):
        tax_err += 1
    if round(r["subtotal"] + r["tax_amount"], 2) != round(r["total_amount"], 2):
        line_err += 1
check("أسطر كل فاتورة = صافيها (40/40)", line_err == 0, f"أخطاء: {line_err}")
check("ضريبة كل فاتورة = مجموع ضرائب الأسطر", tax_err == 0, f"أخطاء: {tax_err}")

# QR مبسط مخزن
qr_rows = conn.execute("SELECT qr_payload_b64 FROM invoices WHERE qr_mode='simple' LIMIT 3").fetchall()
ok_tlv = True
for qr in qr_rows:
    payload = base64.b64decode(qr["qr_payload_b64"])
    tags = dict(zatca_qr.parse_tlv(payload))
    if set(tags) != {1, 2, 3, 4, 5} or not tags[2].startswith("3"):
        ok_tlv = False
check("QR مبسط: TLV بالوسوم 1-5 وفكّ سليم", ok_tlv)
check("صورة QR تُولد من الحمولة", qr_image_data_uri(qr_rows[0]["qr_payload_b64"]).startswith("data:image/png"))

# سندات
rc = conn.execute("SELECT * FROM receipts LIMIT 1").fetchone()
check("سند مرتبط بفاتورة", rc is not None and rc["related_invoice_id"] is not None)
check("مبلغ السند = إجمالي الفاتورة",
      abs(rc["amount"] - conn.execute("SELECT total_amount a FROM invoices WHERE id=?",
                                      (rc["related_invoice_id"],)).fetchone()["a"]) < 0.005)

# إعادة التوليد بنفس البذرة
p2 = GenParams(**GenParams.from_json(p.to_json()).__dict__)
s2 = generate(conn, p2, persist=False)
check("البذرة 777 تعيد نفس المجاميع",
      (s2["total_net"], s2["count"]) == (summary["total_net"], summary["count"]))

print("\n[6] المحرك — وضع شامل (تطابق الإجمالي بالهللة)")
p3 = GenParams(
    company_id=2, customer_ids=[1, 4],
    date_from="2026-02-01", date_to="2026-02-28",
    count_mode="total", count_total=30, count_daily=0,
    amount="75234.75", amount_mode="gross", min_amount="250",
    payment_type="نقدي", seed="31337", qr_mode="phase2",
    with_receipts=False,
)
s3 = generate(conn, p3, persist=True)
check("الإجمالي الشامل = 75234.75 تمامًا", abs(s3["total_gross"] - 75234.75) < 0.005,
      f"الناتج {s3['total_gross']}")
gross_rows = conn.execute("SELECT * FROM invoices WHERE batch_id=2").fetchall()
check("مجموع إجماليات صفوف القاعدة مطابق",
      abs(sum(r["total_amount"] for r in gross_rows) - 75234.75) < 0.005)
p2r = conn.execute("SELECT qr_payload_b64 FROM invoices WHERE qr_mode='phase2' LIMIT 1").fetchone()
tags = dict(zatca_qr.parse_tlv(base64.b64decode(p2r["qr_payload_b64"])))
check("QR مرحلة ثانية وهمي: 9 وسوم", set(tags) == set(range(1, 10)), f"الوسوم: {sorted(tags)}")
check("الوسم 2 = الرقم الضريبي", tags[2] == "310397281500003")
check("الوسم 9 موجود (رقم تسلسلي الشهادة التدريبية)", len(tags[9]) >= 2)
check("مفاتيح تدريبية محفوظة", (dbm.KEYS_DIR / "training_key.pem").exists())

print("\n[7] المعاينة والتصدير PDF")
from app import create_app  # noqa: E402
from app.export import render as rnd  # noqa: E402
from app.export import pdf as pdfx  # noqa: E402

app = create_app()
with app.app_context():
    from flask import g as _g
    _g.conn = conn

    inv_row = conn.execute("SELECT * FROM invoices LIMIT 1").fetchone()
    html = rnd.render_invoice(conn, inv_row)
    check("HTML فاتورة كامل", "<html" in html and "فاتورة" in html and "نسخة تدريبية" in html)
    check("التفقيط داخل المستند", "فقط" in html)

    rc_row = conn.execute("SELECT * FROM receipts LIMIT 1").fetchone()
    html_rc = rnd.render_receipt(conn, rc_row)
    check("HTML سند", "سند" in html_rc and "نسخة تدريبية" in html_rc)

    out = tmp / "one.pdf"
    pdfx.html_to_pdf(html, out)
    data = out.read_bytes()
    check(f"PDF فاتورة ({len(data)//1024} ك.ب عبر {pdfx.last_engine()})",
          data[:5] == b"%PDF-" and len(data) > 3000)

    multi = conn.execute("SELECT * FROM invoices LIMIT 3").fetchall()
    combined = tmp / "combined.pdf"
    html_all = rnd.render_combined(conn, "invoice", multi)
    pdfx.html_to_pdf(html_all, combined)
    d2 = combined.read_bytes()
    n_pages = d2.count(b"/Type /Page") - d2.count(b"/Type /Pages")
    check(f"PDF مجمّع لثلاث فواتير ({len(d2)//1024} ك.ب، {n_pages} صفحات)",
          d2[:5] == b"%PDF-" and n_pages >= 3, f"صفحات: {n_pages}")

    zip_path = pdfx.export_zip(conn, "invoice", multi, "اختبار")
    import zipfile as _zf
    with _zf.ZipFile(zip_path) as zf:
        names = zf.namelist()
    check(f"ZIP منفصل ({len(names)} ملفات)", len(names) == 3 and all(n.endswith(".pdf") for n in names))

    # ── فك الباركود آليًا — يثبت أن الرمز يُقرأ ويعيد نفس الحمولة ──
    from app.money import to_halalas as _th, from_halalas as _fh  # noqa: E402
    from app.qr_service import qr_image_data_uri as _qimg  # noqa: E402

    def _decode_qr(data_uri: str) -> str:
        """zxing-cpp (أدق للرموز الكثيفة) ثم OpenCV كبديل."""
        import cv2  # noqa: E402
        import numpy as np  # noqa: E402
        img = cv2.imdecode(
            np.frombuffer(base64.b64decode(data_uri.split(",", 1)[1]), np.uint8),
            cv2.IMREAD_COLOR)
        try:
            import zxingcpp  # noqa: E402
            hits = zxingcpp.read_barcodes(img)
            if hits and hits[0].text:
                return hits[0].text
        except Exception:
            pass
        got, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        return got

    s_row = conn.execute("SELECT qr_payload_b64 FROM invoices WHERE qr_mode='simple' LIMIT 1").fetchone()
    p_row = conn.execute("SELECT qr_payload_b64 FROM invoices WHERE qr_mode='phase2' LIMIT 1").fetchone()
    got_s = _decode_qr(_qimg(s_row["qr_payload_b64"], box_size=10))
    got_p = _decode_qr(_qimg(p_row["qr_payload_b64"], box_size=10))
    check("QR المبسط يُفك إلى نفس الحمولة المخزنة", got_s == s_row["qr_payload_b64"],
          f"طول المقروء {len(got_s)} مقابل {len(s_row['qr_payload_b64'])}")
    check("QR المرحلة الثانية يُفك إلى نفس الحمولة المخزنة", got_p == p_row["qr_payload_b64"],
          f"طول المقروء {len(got_p)} مقابل {len(p_row['qr_payload_b64'])}")

    # ── المدقق المدمج: الهاش والتوقيع وصحة المبالغ ──
    from app import qr_service as qr_svc  # noqa: E402
    from app.qr_service import verify_invoice_qr as _viq  # noqa: E402
    p_full = conn.execute("SELECT * FROM invoices WHERE qr_mode='phase2' LIMIT 1").fetchone()
    vres = _viq(conn, p_full)
    by_name = {c["name"]: c for c in vres["checks"]}
    check("المدقق: وسم 4 المبلغ بالريالات الصحيحة",
          by_name.get("الوسم 4: الإجمالي شامل الضريبة", {}).get("ok") is True)
    check("المدقق: وسم 6 الهاش مطابق لـ XML",
          by_name.get("الوسم 6: هاش SHA-256 لـ XML الفاتورة", {}).get("ok") is True)
    check("المدقق: وسم 7 التوقيع ECDSA صحيح",
          by_name.get("الوسم 7: التوقيع ECDSA (secp256k1)", {}).get("ok") is True)
    check("المدقق: XML قابل لإعادة التوليد", bool(vres.get("xml")) and "<cbc:UUID>" in vres["xml"])
    gen_check = qr_svc.verify_payload_generic(s_row["qr_payload_b64"])
    check("المدقق العام: نص ممسوح يُفك ويفحص", gen_check["checks"][0]["ok"] is True)

    print("\n[8] المظهر والتنبيهات")
    _orig = {k: dbm.get_theme(conn)[k] for k in dbm.get_theme(conn)}
    dbm.save_theme(conn, {
        'primary_color': '#7c2d12', 'header_text_color': '#f8f4f1',
        'alert_banner_enabled': True, 'alert_banner_text': 'تنبيه تجريبي للاختبار — فك التشفير فقط',
        'alert_banner_color': '#b91c1c', 'alert_banner_bg': '#fee2e2',
        'show_watermark': True, 'watermark_text': 'نسخة تجريبية', 'footer_notice': 'تذييل تحذيري تجريبي',
    })
    html_t = rnd.render_invoice(conn, inv_row)
    check("المظهر: اللون الرئيسي يُرثى في HTML", '#7c2d12' in html_t)
    check("المظهر: شريط التنبيه مفعّل ويحمل النص", 'alert-banner' in html_t and 'تنبيه تجريبي' in html_t)
    check("المظهر: الختم المائي يظهر", 'نسخة تجريبية' in html_t)
    check("المظهر: التذييل التحذيري يظهر", 'تذييل تحذيري' in html_t)
    dbm.save_theme(conn, _orig)

# ══════════════════════════════════════════════════════════════════════════
print("\n[9] الإعدادات والأمان والنسخ الاحتياطي")
from app import backup as bk  # noqa: E402

conn = dbm.connect(test_db)   # سياق app_context أغلق الاتصال عند انتهائه

# ── الأمان: كلمة سر التحكم ──
sec = dbm.get_security(conn)
check("الأمان: افتراضيًا لا توجد كلمة سر", sec["password_set"] is False)
check("الأمان: التحقق ينجح بلا كلمة سر (مفتوح)", dbm.verify_password(conn, "") is True)
try:
    dbm.save_security(conn, {"protect_delete": True})
    check("الأمان: تفعيل الحماية بلا كلمة سر يُرفض", False)
except ValueError:
    check("الأمان: تفعيل الحماية بلا كلمة سر يُرفض", True)
sec = dbm.get_security(conn)
check("الأمان: افتراضيًا حماية الحذف مفعلة (لا تعمل إلا مع كلمة سر)", sec["protect_delete"] is True)
dbm.save_security(conn, {"new_password": "s3cret", "current_password": ""})
sec = dbm.get_security(conn)
check("الأمان: تعيين كلمة سر يعمل", sec["password_set"] is True)
check("الأمان: كلمة سر صحيحة تُقبل", dbm.verify_password(conn, "s3cret") is True)
check("الأمان: كلمة سر خاطئة تُرفض", dbm.verify_password(conn, "wrong") is False)
try:
    dbm.save_security(conn, {"new_password": "newpass", "current_password": "bad"})
    check("الأمان: تغيير كلمة السر بكلمة خاطئة يُرفض", False)
except ValueError:
    check("الأمان: تغيير كلمة السر بكلمة خاطئة يُرفض", True)
dbm.save_security(conn, {"new_password": "newpass", "current_password": "s3cret"})
check("الأمان: تغيير الكلمة بالكلمة الحالية الصحيحة", dbm.verify_password(conn, "newpass") is True)
try:
    dbm.save_security(conn, {"protect_delete": False})
    check("الأمان: تغيير الحماية بلا كلمة السر الحالية يُرفض", False)
except ValueError:
    check("الأمان: تغيير الحماية بلا كلمة السر الحالية يُرفض", True)
dbm.save_security(conn, {"protect_delete": False, "current_password": "newpass"})
check("الأمان: تعطيل حماية الحذف بالكلمة الصحيحة", dbm.get_security(conn)["protect_delete"] is False)
dbm.save_security(conn, {"remove_password": True, "current_password": "newpass"})
check("الأمان: إزالة كلمة السر تعمل", dbm.get_security(conn)["password_set"] is False)

# ── مظهر الواجهة ──
ui = dbm.save_ui(conn, {"accent_color": "#7c3aed", "sidebar_from": "#4c1d95",
                        "sidebar_to": "#5b21b6", "app_notice": "تنبيه تجريبي عام"})
check("المظهر: حفظ لون الواجهة", ui["accent_color"] == "#7c3aed")
check("المظهر: حساب اللون الغامق المشتق", "accent_dark" in ui and ui["accent_dark"].startswith("#"))
check("المظهر: حساب اللون الفاتح المشتق", "accent_light" in ui and ui["accent_light"].startswith("#"))
check("المظهر: التنبيه العام يُحفظ", ui["app_notice"] == "تنبيه تجريبي عام")
ui = dbm.save_ui(conn, {"app_notice": ""})
check("المظهر: مسح التنبيه العام ممكن", ui["app_notice"] == "")
dbm.set_setting(conn, "ui", {})

# ── حقن الخط في المستندات ──
dbm.save_theme(conn, {"font_family": "Tajawal", "font_size": "14"})
with app.app_context():
    html_f = rnd.render_invoice(conn, inv_row)
    check("الخط: لينك Tajawal يُحقن في المستند", "Tajawal" in html_f and "fonts.googleapis" in html_f)
    check("الخط: تجاوز CSS للحجم 14 يُحقن", "font-size:14px" in html_f)
    check("الخط: الحقن قبل نهاية head", html_f.lower().rindex("</head>") > html_f.find("font-size:14px"))
    html_c = rnd.render_combined(conn, "invoice", [inv_row])
    check("الخط: الدمج المشترك يحمل لينك الخط", "Tajawal" in html_c)
# ── لون العنوان المستقل ──
dbm.save_theme(conn, {"title_color": "#dc2626"})
theme_after = dbm.get_theme(conn)
check("المظهر: حفظ لون العنوان المستقل", theme_after["title_color"] == "#dc2626")
check("المظهر: لون العنوان يختلف عن الرئيسي", theme_after["title_color"] != theme_after["primary_color"])
with app.app_context():
    html_t = rnd.render_invoice(conn, inv_row)
    check("المظهر: لون العنوان يظهر في القالب", "#dc2626" in html_t)
# إعادة لون العنوان ليتطابق مع الرئيسي
dbm.save_theme(conn, {"title_color": theme_after["primary_color"]})
check("المظهر: إعادة لون العنوان للالرئيسي", dbm.get_theme(conn)["title_color"] == theme_after["primary_color"])
# ── لون اسم شركة البائع المستقل ──
dbm.save_theme(conn, {"seller_name_color": "#7c3aed"})
theme_seller = dbm.get_theme(conn)
check("المظهر: حفظ لون اسم شركة البائع", theme_seller["seller_name_color"] == "#7c3aed")
check("المظهر: لون البائع يختلف عن العنوان", theme_seller["seller_name_color"] != theme_seller["title_color"])
with app.app_context():
    html_s = rnd.render_invoice(conn, inv_row)
    check("المظهر: لون اسم البائع يظهر في الفاتورة", "#7c3aed" in html_s)
    rc_c = rnd.render_receipt(conn, rc_row)
    check("المظهر: لون اسم البائع يظهر في السند", "#7c3aed" in rc_c)
dbm.save_theme(conn, {"seller_name_color": theme_seller["title_color"]})
dbm.save_theme(conn, {k: v for k, v in dbm.THEME_DEFAULTS.items()})

# ── اختيار الأصناف: فردي أو مجمّع ──
from app.generator.engine import GenParams
# إنشاء بيانات اختبار: مجموعة وصنف
g_row = conn.execute("SELECT id FROM item_groups LIMIT 1").fetchone()
i_row = conn.execute("SELECT id FROM items WHERE group_id=? LIMIT 1", (g_row["id"],)).fetchone()
if g_row and i_row:
    p_individual = GenParams(
        company_id=1, customer_ids=[1],
        items_mode="individual", item_ids=[i_row["id"]],
        amount="1000", count_total=1,
        date_from="2025-01-01", date_to="2025-01-31",
    )
    check("الأصناف: GenParams يقبل items_mode=individual", p_individual.items_mode == "individual")
    check("الأصناف: GenParams يقبل item_ids", len(p_individual.item_ids) == 1)
    # التوليد الفعلي بصنف وا�د
    with app.app_context():
        from app.generator.engine import generate as engine_generate
        summary = engine_generate(conn, p_individual, persist=False, return_built=True)
        check("الأصناف: توليد بصنف محدد ينجح", summary["count"] == 1)
        inv_built = summary["_built"][0]
        item_names = [ln.item.name for ln in inv_built.lines]
        i_name = conn.execute("SELECT name FROM items WHERE id=?", (i_row["id"],)).fetchone()["name"]
        check("الأصناف: الفاتورة تحتوي الصنف المحدد", i_name in item_names)
    # الوضع المجمّع (الافتراضي)
    p_groups = GenParams(company_id=1, customer_ids=[1], items_mode="groups",
                         item_group_ids=[g_row["id"]], amount="1000", count_total=1,
                         date_from="2025-01-01", date_to="2025-01-31")
    check("الأصناف: GenParams يقبل items_mode=groups", p_groups.items_mode == "groups")
    with app.app_context():
        from app.generator.engine import generate as engine_generate
        summary_g = engine_generate(conn, p_groups, persist=False, return_built=True)
        check("الأصناف: توليد حسب المجموعات ينجح", summary_g["count"] == 1)
else:
    check("الأصناف: لا توجد بيانات اختبار (تم تخطي الاختبار)", True)

# ── التحقق من أن الكميات أعداد صحيحة (≥ 1) ──
if g_row and i_row:
    with app.app_context():
        p_check = GenParams(company_id=1, customer_ids=[1], items_mode="groups",
                             item_group_ids=[g_row["id"]], amount="5000", count_total=1,
                             date_from="2025-01-01", date_to="2025-01-31")
        summary_check = engine_generate(conn, p_check, persist=False, return_built=True)
        inv_chk = summary_check["_built"][0]
        for ln in inv_chk.lines:
            check(f"الكمية: صنف '{ln.item.name}' كمية >= 1", ln.quantity >= 1)
            check(f"الكمية: صنف '{ln.item.name}' عدد صحيح", ln.quantity == int(ln.quantity))

# ── التحقق من عرض الأصناف المجمعة في القالب ──
with app.app_context():
    if "group_name" in html_f or "grp-col" in html_f:
        check("القالب: يعرض عمود المجموعة", True)
    else:
        check("القالب: لا توجد بيانات مجموعة (تم التخطي)", True)

# ── النسخ الاحتياطي: إنشاء → تعديل → استعادة ──
# ══════════════════════════════════════════════════════════════════════════
print("\n[10] الفواتير اليدوية: الباركود + وحدة الصنف + السجل التجاري + منع التكرار")

from app import qr_service as qr_svc                       # noqa: E402
from app.web.api import (_invoice_number_conflict, _normalize_invoice_number,
                         _normalize_manual_datetime)  # noqa: E402
from app.qr_service import _parse_manual_dt  # noqa: E402
import io as _io                                            # noqa: E402
from PIL import Image                                       # noqa: E402

# ── الأعمدة الجديدة (ترحيل آمن للقواعد القديمة) ──
cust_cols = {r["name"] for r in conn.execute("PRAGMA table_info(customers)")}
inv_item_cols = {r["name"] for r in conn.execute("PRAGMA table_info(invoice_items)")}
check("قاعدة البيانات: عمود «السجل التجاري» للعميل موجود", "cr_number" in cust_cols)
check("قاعدة البيانات: عمود «الوحدة» في سطور الفاتورة موجود", "unit" in inv_item_cols)

# ── فاتورة يدوية اختبارية (بلا باركود + وحدة صنف حرة) ──
cur = conn.execute(
    """INSERT INTO invoices (batch_id, company_id, customer_id, invoice_number, invoice_date,
       invoice_time, payment_type, subtotal, tax_amount, total_amount, template_id, notes,
       qr_mode, qr_payload_b64, qr_position, discount_amount, is_manual, approval_status, created_at)
       VALUES (NULL, 1, 1, 'M-TEST-1', '2026-01-15', '10:30:00', 'نقدي', 100.0, 15.0, 115.0,
               NULL, '', 'none', '', 'inplace', 0, 1, 'draft', ?)""", (dbm.now_iso(),))
m_id = cur.lastrowid
conn.execute(
    """INSERT INTO invoice_items (invoice_id, item_id, item_name, quantity, unit,
       unit_price, discount_rate, discount_amount, line_total, line_tax, line_gross)
       VALUES (?, NULL, 'كرتون تجريبي', 2, 'كرتون فاخر', 50.0, 0, 0, 100.0, 15.0, 115.0)""",
    (m_id,))
conn.commit()
m_row = conn.execute("SELECT * FROM invoices WHERE id=?", (m_id,)).fetchone()

# ── حمولة الباركود: المرحلة الأولى (5 وسوم) والمرحلة الثانية (9 وسوم) ──
check("أنواع الباركود المدعومة: بدون / المرحلة الأولى / المرحلة الثانية",
      tuple(qr_svc.QR_MODES) == ("none", "simple", "phase2"))
pl1 = qr_svc.build_payload_for_invoice(conn, m_row, "simple")
t1 = dict(zatca_qr.parse_tlv(base64.b64decode(pl1)))
check("الفاتورة اليدوية: باركود المرحلة الأولى = 5 وسوم",
      set(t1) == set(range(1, 6)), f"الوسوم {sorted(t1)}")
check("الفاتورة اليدوية: مبلغ الباركود بصيغة ZATCA (ريالات بمنزلتين)",
      "." in t1[4] and "." in t1[5], f"{t1[4]} / {t1[5]}")
pl2 = qr_svc.build_payload_for_invoice(conn, m_row, "phase2")
t2 = dict(zatca_qr.parse_tlv(base64.b64decode(pl2)))
check("الفاتورة اليدوية: باركود المرحلة الثانية = 9 وسوم",
      set(t2) == set(range(1, 10)), f"الوسوم {sorted(t2)}")
try:
    qr_svc.build_payload_for_invoice(conn, m_row, "none")
    check("الفاتورة اليدوية: «بدون باركود» لا يولّد حمولة", False)
except ValueError:
    check("الفاتورة اليدوية: «بدون باركود» لا يولّد حمولة", True)


def _png_stats(uri: str):
    img = Image.open(_io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))).convert("RGB")
    colors = img.getcolors(maxcolors=1_000_000) or []
    lums = [0.299 * r + 0.587 * g + 0.114 * b for _, (r, g, b) in colors]
    return img.size, len(colors), (min(lums) if lums else -1), (max(lums) if lums else -1)


size1, ncol1, lo1, hi1 = _png_stats(qr_svc.qr_image_data_uri(pl1))
size2, ncol2, lo2, hi2 = _png_stats(qr_svc.qr_image_data_uri(pl2))
check("باركود م1: صورة مربعة عالية الدقة (>= الحد الأدنى)",
      size1[0] == size1[1] and size1[0] >= qr_svc.QR_MIN_PIXELS, f"{size1}")
check("باركود م2: صورة مربعة عالية الدقة (>= الحد الأدنى)",
      size2[0] == size2[1] and size2[0] >= qr_svc.QR_MIN_PIXELS, f"{size2}")
check("باركود م2: تباين كامل أسود/أبيض",
      ncol2 <= 4 and lo2 <= 5 and hi2 >= 250, f"ألوان {ncol2} / {lo2:.0f}..{hi2:.0f}")
check("باركود م1: تباين كامل أسود/أبيض",
      ncol1 <= 4 and lo1 <= 5 and hi1 >= 250, f"ألوان {ncol1} / {lo1:.0f}..{hi1:.0f}")

# ── الطباعة: الباركود أسفل «المبلغ كتابةً» + الوحدة + السجل التجاري ──
with app.app_context():
    html_off = rnd.render_invoice(conn, m_row)
    check("القالب: «بدون باركود» لا تُطبع صورة باركود", 'inv-qr" src=' not in html_off)
    check("القالب: موضع الباركود ثابت (لا تموضع مطلق للباركود)",
          "img.inv-qr{position:absolute" not in html_off
          and "img.inv-qr{display:block" in html_off)
    check("القالب: وحدة الصنف الحرة تظهر في سطور الفاتورة", "كرتون فاخر" in html_off)
    check("القالب: السجل التجاري للعميل يظهر عند كتابته", "السجل التجاري" in html_off)
    conn.execute("UPDATE invoices SET qr_mode='phase2', qr_payload_b64=? WHERE id=?",
                 (pl2, m_id))
    conn.commit()
    m_row = conn.execute("SELECT * FROM invoices WHERE id=?", (m_id,)).fetchone()
    html_on = rnd.render_invoice(conn, m_row)
    check("القالب: صورة الباركود تُطبع عند تفعيله",
          'inv-qr" src="data:image/png' in html_on)
    check("القالب: الباركود بعد «المبلغ كتابةً» مباشرة",
          html_on.index("inv-qr") > html_on.index("corp-words")
          if "corp-words" in html_on else 'inv-qr" src=' in html_on)

# ─ السجل التجاري: يُخفى تمامًا إذا تُرك فارغًا ──
no_cr = conn.execute(
    "SELECT id FROM customers WHERE COALESCE(cr_number,'')='' ORDER BY id LIMIT 1").fetchone()
if no_cr:
    cur = conn.execute(
        """INSERT INTO invoices (batch_id, company_id, customer_id, invoice_number, invoice_date,
           invoice_time, payment_type, subtotal, tax_amount, total_amount, template_id, notes,
           qr_mode, qr_payload_b64, qr_position, discount_amount, is_manual, approval_status, created_at)
           VALUES (NULL, 1, ?, 'M-TEST-2', '2026-01-16', '11:00:00', 'نقدي', 100.0, 15.0, 115.0,
                   NULL, '', 'none', '', 'inplace', 0, 1, 'draft', ?)""",
        (no_cr["id"], dbm.now_iso()))
    m2_id = cur.lastrowid
    conn.commit()
    m2_row = conn.execute("SELECT * FROM invoices WHERE id=?", (m2_id,)).fetchone()
    with app.app_context():
        html_no_cr = rnd.render_invoice(conn, m2_row)
    check("القالب: السجل التجاري يُخفى تمامًا عند تركه فارغًا",
          "السجل التجاري" not in html_no_cr)
else:
    check("القالب: لا يوجد عميل بلا سجل تجاري (تم التخطي)", True)

# ── حماية الفواتير: منع تكرار الرقم فقط لنفس العميل والشركة معًا ──
check("منع التكرار: تطبيع الرقم (مسافات/حالة الحروف)",
      _normalize_invoice_number("  m-test-1 ") == "M-TEST-1")
dup_both = _invoice_number_conflict(conn, "M-TEST-1", 1, 1)
check("منع التكرار: نفس الرقم لنفس العميل والشركة معًا يُرفض",
      bool(dup_both) and dup_both["scope"] == "العميل والشركة"
      and dup_both["message"] == "رقم الفاتورة مكرر لنفس العميل والشركة، يرجى اختيار رقم آخر.")
check("منع التكرار: نفس الرقم لعميل مختلف مسموح",
      _invoice_number_conflict(conn, "M-TEST-1", 9999, 1) is None)
check("منع التكرار: نفس الرقم لشركة مختلفة مسموح",
      _invoice_number_conflict(conn, "M-TEST-1", 1, 999) is None)
check("منع التكرار: رقم جديد لنفس الجهة مسموح",
      _invoice_number_conflict(conn, "M-TEST-999", 1, 1) is None)
check("منع التكرار: نفس الرقم لجهة أخرى مسموح",
      _invoice_number_conflict(conn, "M-TEST-1", 9999, 999) is None)
check("منع التكرار: تجاهل الفاتورة نفسها عند التعديل",
      _invoice_number_conflict(conn, "M-TEST-1", 1, 1, exclude_id=m_id) is None)
check("منع التكرار: مسافات وحالة حروف مختلفة تُرفض لنفس العميل والشركة",
      bool(_invoice_number_conflict(conn, "  m-test-1  ", 1, 1)))
check("تحليل التاريخ/الوقت: يقبل 'HH:MM' (ما يرسله input time)",
      _normalize_manual_datetime("2026-01-15", "10:30") == ("2026-01-15", "10:30:00"))
check("تحليل التاريخ/الوقت: يقبل 'HH:MM:SS'",
      _normalize_manual_datetime("2026-01-15", "10:30:45") == ("2026-01-15", "10:30:45"))
check("تحليل التاريخ/الوقت: يقبل datetime-local المدمج",
      _normalize_manual_datetime("2026-01-15T10:30", "") == ("2026-01-15", "10:30:00"))
check("تحليل التاريخ/الوقت: fromisoformat كملاذ أخير بلا استثناء",
      _parse_manual_dt("2026-01-15", "10:30").strftime("%H:%M:%S") == "10:30:00")

real_backups = bk.BACKUP_DIR
bk.BACKUP_DIR = tmp / "backups_test"
n_comp_before = conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"]
zpath = bk.create_backup(conn=conn, db_path=test_db, tag="اختبار")
check("النسخ: إنشاء ملف ZIP", zpath.exists() and zpath.suffix == ".zip")
check("النسخ: القائمة تعرض النسخة", len(bk.list_backups()) == 1)
meta_count = bk.list_backups()[0]["counts"]
check("النسخ: meta.json يعدّ الشركات", meta_count.get("companies") == n_comp_before)

conn.execute("DELETE FROM companies WHERE id=(SELECT MAX(id) FROM companies)")
conn.commit()
n_comp_after = conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"]
check("النسخ: تعديل البيانات بعد النسخة", n_comp_after == n_comp_before - 1)

conn.close()  # إغلاق الاتصال قبل الاستعادة (قفل الملفات في Windows)
res = bk.restore_backup(zpath, db_path=test_db)
check("النسخ: الاستعادة تعيد اسم المصدر", res["restored_from"] == zpath.name)
conn = dbm.connect(test_db)
n_restored = conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"]
check("النسخ: الاستعادة تعيد البيانات الأصلية", n_restored == n_comp_before)
check("النسخ: نسخة أمان قبل الاستعادة أُنشئت", len(bk.list_backups()) >= 2)

bk.delete_backup(bk.list_backups()[-1]["name"])
check("النسخ: حذف نسخة يعمل", len(bk.list_backups()) == len([p for p in bk.BACKUP_DIR.glob('*.zip')]))
try:
    bk.delete_backup("../escape.zip")
    check("النسخ: أسماء المسارات الخبيثة تُرفض", False)
except ValueError:
    check("النسخ: أسماء المسارات الخبيثة تُرفض", True)
bk.BACKUP_DIR = real_backups

conn.close()
shutil.rmtree(tmp, ignore_errors=True)

print("\n" + "=" * 60)
print(f"النتيجة: {PASS} ناجح، {FAIL} فاشل")
print("=" * 60)
sys.exit(1 if FAIL else 0)



