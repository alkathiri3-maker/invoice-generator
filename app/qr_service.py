# -*- coding: utf-8 -*-
"""
خدمة رمز QR:
  - مبسط   : TLV بالوسوم 1-5 (اسم البائع، الرقم الضريبي، الطابع، الإجمالي، الضريبة) ثم Base64.
  - مرحلة ثانية وهمي: 9 وسوم مع هاش XML وتوقيع ECDSA (secp256k1) بمفاتيح تدريبية
    موقعة ذاتيًا تُنشأ مرة واحدة وتُخزن في data/keys — مع وسوم تعريفية واضحة
    بأنها ليست شهادة ZATCA حقيقية.

يعتمد على وحدة zatca_qr.py الموجودة في جذر المجلد (مولّد QR ضريبي كامل).
"""
from __future__ import annotations

import base64
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import db as dbm
from app.money import from_halalas, fmt_money, fmt_qty

import zatca_qr
from zatca_qr import tlv, build_qr_png

VALID_VAT = zatca_qr._VAT_RE       # ^3\d{14}$ — نفس قاعدة التحقق الضريبي
_NS_UUID = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

# أنواع الباركود الثلاثة المتاحة للمستخدم (المرحلة الأولى / المرحلة الثانية / بدون)
QR_MODES = ("none", "simple", "phase2")
QR_MODE_LABELS = {
    "none": "بدون باركود",
    "simple": "باركود المرحلة الأولى (TLV 1-5)",
    "phase2": "باركود المرحلة الثانية (TLV 1-9 — ZATCA)",
}


def normalize_qr_mode(mode) -> str:
    """تطبيع نوع الباركود القادم من الواجهة — أي قيمة غير معروفة تُعامل كـ«بدون»."""
    m = str(mode or "none").strip().lower()
    return m if m in QR_MODES else "none"


# ضبط جودة صورة الباركود (تُطبع 48-54مم): حجم الوحدة الأساسي/الأقصى وأدنى دقة للصورة
QR_BOX_SIZE_BASE = 8
QR_BOX_SIZE_MAX = 16
QR_MIN_PIXELS = 900


def _zatca_amount(halalas: int) -> str:
    """تنسيق مبلغ بصيغة ZATCA: منزلتان عشريتان بدون فواصل آلاف (مثل '9224.45')."""
    return f"{from_halalas(int(halalas)):.2f}"

def _training_credentials() -> tuple[str, str]:
    """
    مفاتيح تدريبية (secp256k1 + شهادة موقعة ذاتيًا صلاحية 10 سنوات).
    تُنشأ أول مرة وتُخزن في data/keys — ليست شهادة ZATCA بأي حال.
    """
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key_path = dbm.KEYS_DIR / "training_key.pem"
    cert_path = dbm.KEYS_DIR / "training_cert.pem"
    if key_path.exists() and cert_path.exists():
        return key_path.read_text(encoding="ascii"), cert_path.read_text(encoding="ascii")

    key = ec.generate_private_key(ec.SECP256K1())
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "TRAINING — NOT FOR PRODUCTION"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Itqan Invoice Trainer (Fake CSID)"),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    key_path.write_text(key_pem, encoding="ascii")
    cert_path.write_text(cert_pem, encoding="ascii")
    return key_pem, cert_pem


def _compose_invoice_xml(seller_vat: str, raw_number, dt, uuid_str: str,
                         lines, tax_halalas: int, total_halalas: int) -> str:
    """XML فاتورة UBL 2.1 مبسط لأغراض الهاش والتوقيع التدريبي فقط.
    lines: متكرر من (الكمية float، الصافي هللة) — نفس صيغة التوليد الأول حرفيًا
    حتى يبقى الوسم 6 (الهاش) قابلاً لإعادة التوليد من القاعدة."""
    rows = "".join(
        f"<cac:InvoiceLine><cbc:ID>{i + 1}</cbc:ID>"
        f"<cbc:InvoicedQuantity>{float(qty):.4f}</cbc:InvoicedQuantity>"
        f"<cbc:LineExtensionAmount currencyID='SAR'>{_zatca_amount(net)}</cbc:LineExtensionAmount>"
        f"</cac:InvoiceLine>"
        for i, (qty, net) in enumerate(lines)
    )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<Invoice xmlns=\"urn:oasis:names:specification:ubl:schema:xsd:Invoice-2\" "
        "xmlns:cac=\"urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2\" "
        "xmlns:cbc=\"urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2\">"
        "<cbc:ProfileID>reporting:1.0</cbc:ProfileID>"
        f"<cbc:ID>{raw_number}</cbc:ID>"
        f"<cbc:UUID>{uuid_str}</cbc:UUID>"
        f"<cbc:IssueDate>{dt.strftime('%Y-%m-%d')}</cbc:IssueDate>"
        f"<cbc:IssueTime>{dt.strftime('%H:%M:%S')}</cbc:IssueTime>"
        "<cbc:InvoiceTypeCode name=\"0100000\">388</cbc:InvoiceTypeCode>"
        "<cbc:DocumentCurrencyCode>SAR</cbc:DocumentCurrencyCode>"
        f"<cac:AccountingSupplierParty><cac:Party>"
        f"<cac:PartyTaxScheme><cbc:CompanyID>{seller_vat}</cbc:CompanyID></cac:PartyTaxScheme>"
        "</cac:Party></cac:AccountingSupplierParty>"
        f"{rows}"
        "<cac:TaxTotal><cbc:TaxAmount currencyID='SAR'>"
        f"{_zatca_amount(tax_halalas)}</cbc:TaxAmount></cac:TaxTotal>"
        "<cac:LegalMonetaryTotal>"
        f"<cbc:TaxInclusiveAmount currencyID='SAR'>{_zatca_amount(total_halalas)}</cbc:TaxInclusiveAmount>"
        "</cac:LegalMonetaryTotal>"
        "</Invoice>"
    )


def _fake_invoice_xml(seller_vat: str, inv, uuid_str: str) -> str:
    """النسخة المكتملة أثناء التوليد (من كائن BuiltInvoice)."""
    lines = [(float(ln.display_quantity), ln.net) for ln in inv.lines]
    return _compose_invoice_xml(seller_vat, inv.number, inv.dt, uuid_str,
                                lines, inv.tax, inv.total)

def _parse_manual_dt(invoice_date, invoice_time):
    """تحليل مرن لتاريخ/وقت الفاتورة — يقبل 'HH:MM' و 'HH:MM:SS' و fromisoformat.
    لا يرفع استثناءً أبدًا (يعود للآن عند الفشل) حتى لا تُحجب الفاتورة اليدوية."""
    from datetime import datetime as _dt
    try:
        ds = str(invoice_date or "").strip()
        ts = str(invoice_time or "").strip()
        for _fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return _dt.strptime(f"{ds} {ts}", _fmt)
            except ValueError:
                continue
        return _dt.fromisoformat(f"{ds} {ts}".replace("T", " "))
    except (ValueError, TypeError):
        return _dt.now()


def _vat_of(company) -> str:
    vat = (company["tax_number"] or "").strip()
    if not VALID_VAT.match(vat):
        raise ValueError(
            f"الرقم الضريبي للشركة '{company['name']}' غير صالح لرمز QR: '{vat}' — "
            "يجب أن يكون 15 رقمًا يبدأ بالرقم 3 (صيغة ZATCA)"
        )
    return vat


def attach_qr(built, company, mode: str, seed: int) -> None:
    """توليد حمولة QR لكل فاتورة وتخزينها (Base64 TLV)."""
    vat = _vat_of(company)
    seller = (company["name"] or "").strip()
    key_pem = cert_pem = None
    if mode == "phase2":
        key_pem, cert_pem = _training_credentials()

    for inv in built:
        ts = inv.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        gross = _zatca_amount(inv.total)
        tax = _zatca_amount(inv.tax)
        if mode == "simple":
            payload = (
                tlv(1, seller) + tlv(2, vat) + tlv(3, ts)
                + tlv(4, gross) + tlv(5, tax)
            )
            inv.qr_mode = "simple"
            inv.qr_payload_b64 = base64.b64encode(payload).decode("ascii")
        else:
            gross_dec = from_halalas(inv.total)
            tax_dec = from_halalas(inv.tax)
            uid = str(uuid.uuid5(_NS_UUID, f"{seed}|{inv.number}|{gross}"))
            xml = _fake_invoice_xml(vat, inv, uid)
            result = zatca_qr.build_phase2_qr(
                seller_name=seller, seller_vat=vat, timestamp=ts,
                gross_total=gross_dec, vat_total=tax_dec,
                invoice_xml=xml, private_key_pem=key_pem,
                zatca_cert_pem=cert_pem, invoice_type="simplified",
            )
            inv.qr_mode = "phase2"
            inv.qr_payload_b64 = result["tlv_b64"]


def qr_module_count(payload_b64: str) -> int:
    """عدد وحدات رمز QR (بلا المنطقة الهادئة) — يُستخدم لضبط حجم الصورة."""
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
    qr.add_data(payload_b64)
    qr.make(fit=True)
    return int(qr.modules_count)


def _auto_box_size(payload_b64: str, box_size: int, min_pixels: int) -> int:
    """ضبط حجم الوحدة تلقائيًا: لا تقل الصورة عن min_pixels بكسل مهما كان الرمز كثيفًا
    (باركود المرحلة الثانية 9 وسوم كثيف — يحتاج صورة كبيرة ليبقى مقروءًا فورًا)."""
    try:
        modules = qr_module_count(payload_b64)
    except Exception:      # لا نُفشل التوليد إذا تعذّر حساب الوحدات
        return int(box_size or 1)
    needed = -(-int(min_pixels) // max(1, modules + 8))     # قسمة لأعلى (وحدات + المنطقة الهادئة)
    return max(int(box_size or 0), min(QR_BOX_SIZE_MAX, needed))


def qr_image_data_uri(payload_b64: str, box_size: int = QR_BOX_SIZE_BASE,
                      min_pixels: int = QR_MIN_PIXELS) -> str:
    """صورة QR عالية الجودة (Data URI) من حمولة TLV/Base64 المخزنة — تُستخدم داخل القوالب.

    معايير الجودة والتباين المُثبتة (لتعمل فورًا مع كاميرا الجوال وتطبيقات الفحص):
      - أسود نقي (#000000) على أبيض نقي — بلا شفافية ولا تدرجات.
      - منطقة هادئة (Quiet Zone) = 4 وحدات كما في ISO/IEC 18004 وتوصية ZATCA.
      - تصحيح الأخطاء مستوى M (نفس ما يستخدمه مولد ZATCA).
      - حجم تلقائي: باركود المرحلة الأولى (~3×3سم) والثانية (كثيف) لا تقل صورته عن
        min_pixels بكسل، فيبقى الحجم المطبوع 48-54مم بحدّة كافية للمسح.
    """
    if not payload_b64:
        return ""
    box = _auto_box_size(payload_b64, box_size, min_pixels) if min_pixels else int(box_size or 1)
    return build_qr_png(payload_b64, box_size=box, fill_color="#000000", border=4)


def qr_note_for(mode: str) -> str:
    if mode == "simple":
        return "رمز QR مبسط (Tag 1-5) — نسخة تدريبية"
    if mode == "phase2":
        return "رمز QR مرحلة ثانية — محاكاة تدريبية بتوقيع ECDSA على مفاتيح غير رسمية (Tag 1-9)"
    return ""


def build_payload_for_invoice(conn, inv_row, mode: str | None = None) -> str:
    """بناء حمولة الباركود (Base64 TLV) لفاتورة مخزنة — للفواتير اليدوية عند الحفظ
    ولإعادة التوليد والتعديل.

    mode: none | simple | phase2 (فارغ = النوع المخزّن في الفاتورة).
    يرفع ValueError برسالة عربية واضحة إذا تعذّر التوليد (مثلًا رقم ضريبي غير صالح).
    """
    from app.money import to_halalas as _to_halalas

    mode = normalize_qr_mode(mode if mode is not None else inv_row["qr_mode"])
    if mode not in ("simple", "phase2"):
        raise ValueError("نوع الباركود يجب أن يكون المرحلة الأولى أو المرحلة الثانية")

    company = conn.execute("SELECT * FROM companies WHERE id=?",
                           (inv_row["company_id"],)).fetchone()
    if not company:
        raise ValueError("الشركة البائعة غير موجودة — تعذّر توليد الباركود")
    vat = _vat_of(company)                     # يتحقق من صحة الرقم الضريبي (15 رقمًا يبدأ بـ 3)
    seller = (company["name"] or "").strip()
    ts = f"{inv_row['invoice_date']}T{inv_row['invoice_time']}Z"
    total_h = _to_halalas(inv_row["total_amount"])
    tax_h = _to_halalas(inv_row["tax_amount"])

    if mode == "simple":
        # المرحلة الأولى: 5 وسوم (اسم البائع، الرقم الضريبي، الطابع الزمني، الإجمالي، الضريبة)
        payload = (tlv(1, seller) + tlv(2, vat) + tlv(3, ts)
                   + tlv(4, _zatca_amount(total_h)) + tlv(5, _zatca_amount(tax_h)))
        return base64.b64encode(payload).decode("ascii")

    # المرحلة الثانية: 9 وسوم (تشمل هاش XML وتوقيع ECDSA ومفتاح الشهادة التدريبية)
    key_pem, cert_pem = _training_credentials()
    xml = build_invoice_xml_for_row(conn, inv_row)
    res = zatca_qr.build_phase2_qr(
        seller_name=seller, seller_vat=vat, timestamp=ts,
        gross_total=from_halalas(total_h), vat_total=from_halalas(tax_h),
        invoice_xml=xml, private_key_pem=key_pem,
        zatca_cert_pem=cert_pem, invoice_type="simplified",
    )
    return res["tlv_b64"]


# ══════════════════════════════════════════════════════════════════════════
#  الفحص والتحقق — نفس منطق تطبيق ZATCA مع قبول شهادة التدريب
# ══════════════════════════════════════════════════════════════════════════

_TAG_LABELS = {
    1: "اسم البائع",
    2: "الرقم الضريبي للبائع",
    3: "الطابع الزمني ISO-8601",
    4: "الإجمالي شامل الضريبة",
    5: "إجمالي ضريبة القيمة المضافة",
    6: "هاش XML الفاتورة (SHA-256)",
    7: "التوقيع الرقمي ECDSA",
    8: "المفتاح العام secp256k1",
    9: "الرقم التسلسلي لشهادة الختم",
}


def _check(out: dict, name: str, ok, detail: str = "") -> None:
    """إضافة فحص — ok: True/False/None (معلوماتية)."""
    out["checks"].append({
        "name": name,
        "ok": ok,
        "icon": "✅" if ok is True else ("❌" if ok is False else "ℹ️"),
        "detail": detail,
    })


def _parse_payload(payload_b64: str):
    raw = base64.b64decode(payload_b64)
    tags = zatca_qr.parse_tlv(raw)
    return tags, dict(tags)


def regenerate_stored_qr(conn, batch_id: int | None = None,
                         invoice_id: int | None = None,
                         company_id: int | None = None) -> int:
    """إعادة توليد حمولات QR للفواتير المخزنة (إصلاح الطور الثاني في القواعد القديمة
    التي حُفظت بأرقام الهللة بدل الريالات في الوسمين 4/5) — أو لفاتورة واحدة بعد
    تحريرها، أو لكل فواتير شركة معيّنة بعد تعديل بياناتها (تحديث متتابع تلقائي
    لاسم البائع ورقمه الضريبي في الوسمين 1-2). يعيد عدد الفواتير المحدثة."""
    from app.money import to_halalas

    if invoice_id:
        rows = conn.execute(
            "SELECT * FROM invoices WHERE id=? AND qr_payload_b64 != ''",
            (invoice_id,)).fetchall()
    elif company_id:
        rows = conn.execute(
            "SELECT * FROM invoices WHERE company_id=? AND qr_payload_b64 != '' ORDER BY id",
            (company_id,)).fetchall()
    elif batch_id:
        rows = conn.execute(
            "SELECT * FROM invoices WHERE batch_id=? AND qr_payload_b64 != '' ORDER BY id",
            (batch_id,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM invoices WHERE qr_payload_b64 != '' ORDER BY id").fetchall()
    updated = 0
    for row in rows:
        mode = row["qr_mode"] or "none"
        if mode not in ("simple", "phase2"):
            continue
        try:
            new_b64 = build_payload_for_invoice(conn, row, mode)
            if new_b64 != row["qr_payload_b64"]:
                conn.execute("UPDATE invoices SET qr_payload_b64=? WHERE id=?",
                             (new_b64, row["id"]))
                updated += 1
        except Exception as exc:   # لا توقف الدورة عند أي فاتورة معطوبة
            import logging
            logging.getLogger("qr.regen").warning("فاتورة %s: %s", row["id"], exc)
            continue
    if updated:
        conn.commit()
    return updated


def build_invoice_xml_for_row(conn, inv_row) -> str:
    """إعادة توليد XML الفاتورة المستخدم في حساب الوسم 6 (الهاش) من صفوف القاعدة."""
    from datetime import datetime as _dt
    from app.money import to_halalas
    from app.generator.engine import GenParams

    batch = conn.execute("SELECT seed, params_json FROM batches WHERE id=?",
                         (inv_row["batch_id"],)).fetchone()
    prefix = ""
    seed = 0
    if batch:
        seed = int(batch["seed"] or 0)
        try:
            prefix = GenParams.from_json(batch["params_json"]).number_prefix or ""
        except Exception:
            prefix = ""
    number = inv_row["invoice_number"] or ""
    raw_num = number[len(prefix):] if prefix and number.startswith(prefix) else number

    dt = _parse_manual_dt(inv_row['invoice_date'], inv_row['invoice_time'])
    total_h = to_halalas(inv_row["total_amount"])
    tax_h = to_halalas(inv_row["tax_amount"])
    uid = str(uuid.uuid5(_NS_UUID, f"{seed}|{raw_num}|{_zatca_amount(total_h)}"))
    lines = [
        (float(r["quantity"]), to_halalas(r["line_total"]))
        for r in conn.execute(
            "SELECT quantity, line_total FROM invoice_items WHERE invoice_id=? ORDER BY id",
            (inv_row["id"],),
        )
    ]
    company = conn.execute("SELECT tax_number FROM companies WHERE id=?",
                           (inv_row["company_id"],)).fetchone()
    return _compose_invoice_xml((company["tax_number"] if company else ""),
                                raw_num, dt, uid, lines, tax_h, total_h)

def verify_invoice_qr(conn, inv_row) -> dict:
    """فحص كامل لباركود فاتورة مخزنة — بيانات الوسوم + فحوصات مطابقة + توقيع."""
    from app.money import to_halalas

    out = {"mode": inv_row["qr_mode"] or "none", "payload_b64": inv_row["qr_payload_b64"] or "",
           "tags": [], "checks": [], "xml": None}
    if not out["payload_b64"]:
        _check(out, "الحمولة", False, "لا يوجد باركود لهذه الفاتورة")
        return out

    try:
        tags, tmap = _parse_payload(out["payload_b64"])
    except Exception as exc:
        _check(out, "فك الترميز TLV", False, str(exc))
        return out

    out["tags"] = [{"tag": t, "label": _TAG_LABELS.get(t, "وسم غير معروف"),
                    "value": v, "bytes": len(v.encode("utf-8"))} for t, v in tags]
    _check(out, "فك الترميز TLV", True, f"{len(tags)} وسوم صحيحة البنية")

    company = conn.execute("SELECT * FROM companies WHERE id=?",
                           (inv_row["company_id"],)).fetchone()
    if company:
        _check(out, "الوسم 1: اسم البائع", tmap.get(1) == (company["name"] or "").strip(),
               tmap.get(1, ""))
        _check(out, "الوسم 2: الرقم الضريبي", tmap.get(2) == (company["tax_number"] or "").strip(),
               tmap.get(2, ""))
    ts_expected = f"{inv_row['invoice_date']}T{inv_row['invoice_time']}Z"
    _check(out, "الوسم 3: الطابع الزمني", tmap.get(3) == ts_expected,
           tmap.get(3, "") + ("" if tmap.get(3) == ts_expected else f" (المتوقع {ts_expected})"))
    _check(out, "الوسم 4: الإجمالي شامل الضريبة",
           tmap.get(4) == _zatca_amount(to_halalas(inv_row["total_amount"])), tmap.get(4, ""))
    _check(out, "الوسم 5: إجمالي الضريبة",
           tmap.get(5) == _zatca_amount(to_halalas(inv_row["tax_amount"])), tmap.get(5, ""))

    if out["mode"] == "phase2":
        xml = build_invoice_xml_for_row(conn, inv_row)
        out["xml"] = xml
        expected_hash = base64.b64encode(zatca_qr.compute_invoice_hash(xml)).decode("ascii")
        _check(out, "الوسم 6: هاش SHA-256 لـ XML الفاتورة",
               tmap.get(6) == expected_hash,
               "مطابق — قابل لإعادة الحساب من XML القابل للتنزيل" if tmap.get(6) == expected_hash
               else "غير مطابق")
        _verify_signature(out, tmap)
        _check_cert(out, tmap)
    else:
        _check(out, "المرحلة المبسطة", None,
               "وسوم 1-5 فقط دون ختم تشفيري — مطابق لمواصفات المرحلة الأولى")
    return out

def _verify_signature(out: dict, tmap: dict) -> None:
    """التحقق من التوقيع ECDSA (وسم 7) ضد المفتاح العام (وسم 8) على الهاش (وسم 6)."""
    if not {6, 7, 8} <= set(tmap):
        _check(out, "الوسم 7: التوقيع الرقمي", False, "وسوم ناقصة (6/7/8)")
        return
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
        from cryptography.exceptions import InvalidSignature

        pub_raw = base64.b64decode(tmap[8])
        pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_raw)
        pub.verify(base64.b64decode(tmap[7]), base64.b64decode(tmap[6]),
                   ec.ECDSA(Prehashed(hashes.SHA256())))
        _check(out, "الوسم 7: التوقيع ECDSA (secp256k1)", True,
               "صحيح — يطابق المفتاح العام في الوسم 8")
    except InvalidSignature:
        _check(out, "الوسم 7: التوقيع ECDSA (secp256k1)", False, "التوقيع لا يطابق المفتاح العام")
    except Exception as exc:
        _check(out, "الوسم 7: التوقيع ECDSA (secp256k1)", False, f"خطأ: {exc}")


def _check_cert(out: dict, tmap: dict) -> None:
    """معلومات شهادة الختم التدريبية (الوسم 9) — توضيح سلوك التطبيق الرسمي."""
    if 9 not in tmap:
        _check(out, "الوسم 9: شهادة الختم", False, "مفقود")
        return
    try:
        from cryptography import x509
        _, cert_pem = _training_credentials()
        cert = x509.load_pem_x509_certificate(cert_pem.encode("ascii"))
        serial_hex = format(cert.serial_number, "X")
        cn = cert.subject.rfc4514_string()
        matches = tmap[9] == serial_hex
        _check(out, "الوسم 9: شهادة الختم التشفيري",
               True if matches else False,
               f"شهادة تدريبية موقعة ذاتيًا ({cn}) — تطبيق ZATCA الرسمي سيرفضها دائمًا "
               "لأنها ليست CSID صادرة من الهيئة (هذا متوقع ومقصود في النسخة التدريبية)")
    except Exception as exc:
        _check(out, "الوسم 9: شهادة الختم", False, f"خطأ: {exc}")

def verify_payload_generic(b64_text: str) -> dict:
    """فحص نص Base64 ممسوح ضوئيًا (من أي ماسح) — بنية + فحوصات + توقيع إن وُجد."""
    out = {"mode": "pasted", "payload_b64": (b64_text or "").strip(),
           "tags": [], "checks": [], "xml": None}
    payload = out["payload_b64"]
    if not payload:
        _check(out, "المدخل", False, "ألصق نص Base64 أولًا")
        return out
    try:
        tags, tmap = _parse_payload(payload)
    except Exception as exc:
        _check(out, "فك Base64/TLV", False, f"النص ليس حمولة TLV صالحة: {exc}")
        return out

    out["tags"] = [{"tag": t, "label": _TAG_LABELS.get(t, "وسم غير معروف"),
                    "value": v, "bytes": len(v.encode("utf-8"))} for t, v in tags]
    _check(out, "فك Base64/TLV", True, f"{len(tags)} وسوم: {sorted(tmap)}")
    if 1 in tmap:
        _check(out, "الوسم 1: اسم البائع", bool(tmap[1].strip()), tmap[1])
    if 2 in tmap:
        _check(out, "الوسم 2: الرقم الضريبي (15 رقمًا يبدأ بـ 3)",
               bool(zatca_qr._VAT_RE.match(tmap[2])), tmap[2])
    if 3 in tmap:
        _check(out, "الوسم 3: الطابع الزمني ISO-8601 UTC",
               bool(zatca_qr._TIMESTAMP_RE.match(tmap[3])), tmap[3])
    for tag, label in ((4, "الوسم 4: الإجمالي"), (5, "الوسم 5: الضريبة")):
        if tag in tmap:
            try:
                from decimal import Decimal
                val = Decimal(tmap[tag])
                _check(out, label, val >= 0 and tmap[tag] == f"{val:.2f}", tmap[tag])
            except Exception:
                _check(out, label, False, f"قيمة غير رقمية: {tmap[tag]}")
    if 5 in tmap and 4 in tmap:
        try:
            from decimal import Decimal
            _check(out, "الضريبة لا تتجاوز الإجمالي", Decimal(tmap[5]) <= Decimal(tmap[4]),
                   f"{tmap[5]} ≤ {tmap[4]}")
        except Exception:
            pass
    if {6, 7, 8} <= set(tmap):
        _verify_signature(out, tmap)
    else:
        _check(out, "الختم التشفيري", None,
               "لا توجد وسوم 6-8 (فاتورة مرحلة أولى) — لا يوجد توقيع للتحقق")
    if 9 in tmap:
        _check(out, "الوسم 9: شهادة الختم", None,
               f"الرقم التسلسلي {tmap[9]} — التحقق الرسمي يتطلب شهادة CSID صادرة من ZATCA")
    return out


def build_demo_html(conn, inv_row) -> str:
    """تصدير صفحة HTML مستقلة للفاتورة مع QR عالي الدقة، حمولة حقيقية،
    ومدقق secp256k1 يعمل في المتصفح (بديل ملف invoice_zatca.html)."""
    import html as _html
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    v = verify_invoice_qr(conn, inv_row)
    png = qr_image_data_uri(v["payload_b64"], box_size=8)
    tags_rows = "".join(
        f"<tr><td><b>Tag {t['tag']}</b></td><td>{_html.escape(t['label'])}</td>"
        f"<td class='v'>{_html.escape(t['value'] if len(t['value']) <= 70 else t['value'][:67] + '…')}</td></tr>"
        for t in v["tags"]
    )
    checks_rows = "".join(
        f"<tr><td class='ic'>{c['icon']}</td><td><b>{_html.escape(c['name'])}</b>"
        f"<div class='d'>{_html.escape(c['detail'])}</div></td></tr>"
        for c in v["checks"]
    )
    compact_hex = pub_hex = hash_hex = ""
    tmap = dict(_parse_payload(v["payload_b64"])[1])
    if {6, 7, 8} <= set(tmap):
        r, s = decode_dss_signature(base64.b64decode(tmap[7]))
        compact_hex = (r.to_bytes(32, "big") + s.to_bytes(32, "big")).hex()
        pub_hex = base64.b64decode(tmap[8]).hex()
        hash_hex = base64.b64decode(tmap[6]).hex()
    xml = v.get("xml") or ""
    mode_label = "مرحلة ثانية وهمي" if v["mode"] == "phase2" else "مبسط"

    page = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<title>صفحة فحص باركود — فاتورة __NUM__ (تدريبية)</title>
<style>
* { box-sizing: border-box; } body { font-family: 'Segoe UI', Tahoma, sans-serif; background:#f5f7fa; margin:0; padding:20px; }
.card { background:#fff; max-width:920px; margin:0 auto 16px; padding:24px 28px; border-radius:12px; box-shadow:0 2px 12px rgba(0,0,0,.08); }
h1 { font-size:22px; color:#0e7490; margin:0 0 4px; } .sub { color:#64748b; font-size:13px; margin-bottom:14px; }
.warn { background:#fef2f2; border:1.5px solid #fecaca; color:#b91c1c; font-weight:700; padding:10px 14px; border-radius:10px; font-size:13px; line-height:1.8; }
.row { display:flex; gap:20px; flex-wrap:wrap; align-items:flex-start; }
.qrside { text-align:center; } .qrside img { width:230px; height:230px; border:1px solid #e2e8f0; border-radius:8px; background:#fff; }
table { width:100%; border-collapse:collapse; font-size:12.5px; } th { background:#0e7490; color:#fff; padding:8px; }
td { padding:7px 9px; border-bottom:1px solid #e2e8f0; text-align:right; } td.ic { width:36px; text-align:center; }
td.v { direction:ltr; text-align:left; font-family:Consolas,monospace; font-size:11px; color:#334155; word-break:break-all; }
.d { color:#64748b; font-size:11.5px; margin-top:2px; font-weight:400; }
textarea { width:100%; min-height:90px; font-family:Consolas,monospace; font-size:10.5px; direction:ltr; text-align:left; border:1px dashed #cbd5e1; border-radius:6px; padding:8px; background:#fafafa; }
.badge { display:inline-block; background:#ecfeff; color:#155e75; font-weight:700; border-radius:99px; padding:3px 12px; font-size:12px; }
#result { margin-top:10px; font-weight:700; }
.ok { color:#047857; } .bad { color:#b91c1c; } .na { color:#64748b; }
.foot { text-align:center; color:#b91c1c; font-weight:700; font-size:12px; padding:10px; }
</style>
</head>
<body>
<div class="card">
  <h1>فاتورة رقم __NUM__ <span class="badge">__MODE__</span></h1>
  <div class="sub">صفحة فحص باركود تدريبية — مطابقة منطق تطبيق ZATCA مع قبول شهادة التدريب</div>
  <div class="warn">⚠ تطبيق ZATCA الرسمي سيرفض هذا الرمز دائمًا لأن شهادة الختم (Tag 9) تدريبية موقعة ذاتيًا وليست CSID صادرة من الهيئة. المدقق أدناه يتحقق من الهاش والتوقيع رياضيًا.</div>
</div>
<div class="card">
  <div class="row">
    <div class="qrside">
      <img src="__QR__" alt="QR">
      <div class="d">امسحه بأي ماسح — سيقرأ نص Base64 أدناه</div>
    </div>
    <div style="flex:1;min-width:300px">
      <table><tr><th colspan="3">الوسوم (TLV)</th></tr>__TAGS__</table>
    </div>
  </div>
</div>
<div class="card">
  <table><tr><th colspan="2">نتيجة الفحص على الخادم</th></tr>__CHECKS__</table>
</div>
<div class="card">
  <h1 style="font-size:16px">الحمولة (Base64)</h1>
  <textarea readonly id="b64">__B64__</textarea>
  <h1 style="font-size:16px;margin-top:14px">XML الفاتورة (مصدر الوسم 6)</h1>
  <textarea readonly style="min-height:130px">__XML__</textarea>
  <div id="result"></div>
</div>
<div class="foot">نسخة تدريبية — غير صالحة للاستخدام الرسمي | مولّد الفواتير التدريبي — إتقان</div>
<script type="text/plain" id="xmlsrc">__XMLRAW__</script>
<script type="module">
try {
  const secp = await import('https://esm.sh/@noble/secp256k1@2.2.3');
  const xmlBytes = new TextEncoder().encode(document.getElementById('xmlsrc').textContent);
  const digest = await crypto.subtle.digest('SHA-256', xmlBytes);
  const hashHex = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
  const okHash = hashHex === '__HASH__';
  const okSig = await secp.verify('__SIG__', hashHex, '__PUB__');
  document.getElementById('result').innerHTML =
    (okHash ? '<span class="ok">✅ الوسم 6: الهاش مطابق لـ XML الفاتورة</span> — '
            : '<span class="bad">❌ الوسم 6: الهاش غير مطابق</span> — ')
    + (okSig ? '<span class="ok">✅ الوسم 7: التوقيع ECDSA صحيح ضد المفتاح العام (وسم 8)</span>'
             : '<span class="bad">❌ الوسم 7: التوقيع غير صحيح</span>');
} catch (e) {
  document.getElementById('result').innerHTML =
    '<span class="na">ℹ️ التحقق داخل المتصفح يحتاج اتصالًا بالإنترنت (مكتبة secp256k1) — نتائج الخادم أعلاه هي المرجع.</span>';
}
</script>
</body>
</html>"""
    # __REPLACE__
    return page.replace("__NUM__", str(inv_row["invoice_number"])) \
               .replace("__MODE__", mode_label) \
               .replace("__QR__", png) \
               .replace("__TAGS__", tags_rows) \
               .replace("__CHECKS__", checks_rows) \
               .replace("__B64__", v["payload_b64"]) \
               .replace("__XMLRAW__", xml) \
               .replace("__XML__", _html.escape(xml)) \
               .replace("__HASH__", hash_hex) \
               .replace("__SIG__", compact_hex) \
               .replace("__PUB__", pub_hex)





