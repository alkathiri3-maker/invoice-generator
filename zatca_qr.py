# -*- coding: utf-8 -*-
"""
================================================================================
  ZATCA Phase 2 — QR Code Generator (9-Tag TLV) — نسخة إنتاجية كاملة
  مطابقة معايير هيئة الزكاة والضريبة والجمارك — المرحلة الثانية (الربط والتكامل)
================================================================================
  الوسوم (Tags) حسب مواصفات ZATCA:
    1 = اسم البائع
    2 = الرقم الضريبي للبائع (15 رقماً يبدأ بالرقم 3)
    3 = الطابع الزمني ISO-8601 UTC    مثال: 2026-08-12T10:30:00Z
    4 = إجمالي الفاتورة شاملاً ضريبة القيمة المضافة
    5 = إجمالي ضريبة القيمة المضافة
    6 = Base64( SHA-256( XML الفاتورة UBL 2.1 بعد التوحيد C14N ) )
    7 = التوقيع الرقمي ECDSA (secp256k1) على قيمة الوسم 6  — Base64
    8 = المفتاح العام ECDSA (Base64 — Uncompressed Point)
    9 = الرقم التسلسلي لشهادة الختم التشفيري الصادرة من ZATCA (Hex)

  قواعد المطابقة:
    * الفاتورة المبسطة (Simplified)  → الوسوم 1..9 كاملة (ختم تشفيري إجباري).
    * الفاتورة القياسية (Standard)   → الوسوم 1..5 فقط (بلا ختم تشفيري).

  ⚠ هذه النسخة الإنتاجية لا تحتوي أي مفاتيح أو قيم وهمية:
    - المفتاح الخاص (PEM)   : مفتاح secp256k1 المُرسل ضمن CSR الخاص بـ ZATCA.
    - الشهادة      (PEM)    : شهادة الختم التشفيري (CSID) الصادرة من ZATCA.
    - XML الفاتورة (UBL 2.1): لإنتاج الهاش الحقيقي (الوسم 6).
================================================================================
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.x509.oid import NameOID

import qrcode

try:
    # lxml اختيارية لكنها موصى بها بشدة: توحيد XML (C14N) قبل حساب الهاش
    from lxml import etree as _etree
    _HAVE_LXML = True
except ImportError:  # pragma: no cover
    _HAVE_LXML = False

__all__ = [
    "ZATCAError",
    "build_phase2_qr",
    "compute_invoice_hash",
    "parse_tlv",
    "tlv",
]

# ZATCA تتطلب منحنى secp256k1 حصراً لمفتاح الختم التشفيري
_REQUIRED_CURVE_NAME = "secp256k1"

_VAT_RE = re.compile(r"^3\d{14}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$")
_UUID_RE = re.compile(r"<cbc:UUID[^>]*>([^<]+)</cbc:UUID>", re.IGNORECASE)


class ZATCAError(Exception):
    """خطأ في متطلبات مطابقة ZATCA (بيانات ناقصة/غير صالحة) — رسالته جاهزة للعرض."""


# ════════════════════════════════════════════════════════════════════════════
#  ترميز TLV وفكّه
# ════════════════════════════════════════════════════════════════════════════

def tlv(tag: int, value: str) -> bytes:
    """ترميز وسم واحد بصيغة Tag-Length-Value (UTF-8) مع فحص حدود TLV."""
    if not 0 <= tag <= 255:
        raise ZATCAError(f"رقم وسم غير صالح: {tag}")
    v = (value or "").encode("utf-8")
    if len(v) > 255:
        raise ZATCAError(f"قيمة الوسم {tag} تتجاوز 255 بايت (الحد الأقصى لطول TLV)")
    return bytes([tag, len(v)]) + v


def parse_tlv(payload: bytes) -> list[tuple[int, str]]:
    """فكّ حمولة TLV كاملة بأمان (فحص الحدود) — تعيد قائمة (tag, value)."""
    tags: list[tuple[int, str]] = []
    i, n = 0, len(payload)
    while i < n:
        if i + 2 > n:
            raise ZATCAError(f"حمولة TLV غير مكتملة عند الإزاحة {i}")
        tag = payload[i]
        length = payload[i + 1]
        end = i + 2 + length
        if end > n:
            raise ZATCAError(f"طول الوسم {tag} يتجاوز حدود الحمولة")
        try:
            value = payload[i + 2:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ZATCAError(f"قيمة الوسم {tag} ليست UTF-8 صالحة: {exc}") from exc
        tags.append((tag, value))
        i = end
    return tags


# ════════════════════════════════════════════════════════════════════════════
#  التحقق من صحة المدخلات
# ════════════════════════════════════════════════════════════════════════════

def _validate_vat_number(vat: str) -> str:
    """الرقم الضريبي السعودي: 15 رقماً يبدأ بالرقم 3."""
    vat = (vat or "").strip()
    if not _VAT_RE.match(vat):
        raise ZATCAError(
            f"الرقم الضريبي غير صالح: '{vat}' — يجب أن يكون 15 رقماً يبدأ بالرقم 3"
        )
    return vat


def _validate_timestamp(timestamp: str) -> str:
    """الطابع الزمني ISO-8601 UTC: 2026-08-12T10:30:00Z أو مع أجزاء الثانية."""
    ts = (timestamp or "").strip()
    if not _TIMESTAMP_RE.match(ts):
        raise ZATCAError(
            "الطابع الزمني يجب أن يكون ISO-8601 UTC مثل 2026-08-12T10:30:00Z "
            "أو 2026-08-12T10:30:00.000Z"
        )
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            datetime.strptime(ts, fmt)
            return ts
        except ValueError:
            continue
    raise ZATCAError(f"التاريخ/الوقت داخل الطابع الزمني غير صحيح: '{ts}'")


def _format_amount(value, label: str) -> str:
    """تنسيق المبالغ: منزلتان عشريتان ROUND_HALF_UP بدون فواصل آلاف."""
    if value is None:
        raise ZATCAError(f"{label} مطلوب ولا يمكن أن يكون فارغاً")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ZATCAError(f"{label}: قيمة رقمية غير صالحة ({value!r})") from exc
    if not amount.is_finite():
        raise ZATCAError(f"{label}: يجب أن يكون رقماً محدوداً")
    if amount < 0:
        raise ZATCAError(f"{label}: لا يمكن أن يكون سالباً")
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

# ════════════════════════════════════════════════════════════════════════════
#  الهاش والتوقيع الإنتاجي (ZATCA)
# ════════════════════════════════════════════════════════════════════════════

def canonicalize_invoice_xml(invoice_xml: str) -> bytes:
    """
    توحيد XML الفاتورة (C14N) قبل حساب الهاش.
    مع lxml: توحيد Inclusive C14N القياسي (الأقرب لسلوك ZATCA SDK).
    بدون lxml: تُستخدم البايتات كما هي (يُنصح بتوليد XML موحداً من المصدر).
    """
    raw = (invoice_xml or "").encode("utf-8")
    if not raw.strip():
        raise ZATCAError("XML الفاتورة مطلوب لحساب الهاش الحقيقي (الوسم 6)")
    if not _HAVE_LXML:
        print(
            "تحذير: lxml غير مثبتة — سيُحسب الهاش على XML الخام بدون توحيد C14N. "
            "ثبّت lxml لضمان مطابقة حساب الهاش مع ZATCA SDK.",
            file=sys.stderr,
        )
        return raw
    try:
        root = _etree.fromstring(raw)
        return _etree.tostring(root, method="c14n", exclusive=False, with_comments=False)
    except _etree.XMLSyntaxError as exc:
        raise ZATCAError(f"XML الفاتورة غير صالح: {exc}") from exc


def compute_invoice_hash(invoice_xml: str) -> bytes:
    """الوسم 6: خلاصة SHA-256 (32 بايت) لـ XML الفاتورة بعد التوحيد."""
    return hashlib.sha256(canonicalize_invoice_xml(invoice_xml)).digest()


def load_private_key(private_key_pem: str) -> ec.EllipticCurvePrivateKey:
    """
    تحميل المفتاح الخاص من PEM والتحقق أنه مفتاح EC بمنحنى secp256k1
    كما تتطلب ZATCA. لا يوجد أي توليد مفاتيح بديلة في هذه النسخة.
    """
    if not private_key_pem or not private_key_pem.strip():
        raise ZATCAError(
            "المفتاح الخاص مطلوب بصيغة PEM (مفتاح secp256k1 المُستخدم في CSR الخاص بـ ZATCA)"
        )
    try:
        key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"), password=None
        )
    except (ValueError, TypeError) as exc:
        raise ZATCAError(f"تعذر قراءة المفتاح الخاص (PEM غير صالح): {exc}") from exc
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ZATCAError(
            "المفتاح الخاص يجب أن يكون مفتاح Elliptic Curve (EC) وليس RSA أو نوعاً آخر"
        )
    if key.curve.name != _REQUIRED_CURVE_NAME:
        raise ZATCAError(
            f"ZATCA تتطلب منحنى secp256k1، بينما المفتاح المُحمّل يستخدم '{key.curve.name}'. "
            "أعد توليد المفتاح بمنحنى secp256k1 وفق دليل Onboarding الخاص بـ ZATCA."
        )
    return key


def load_zatca_certificate(cert_pem: str) -> x509.Certificate:
    """تحميل شهادة الختم التشفيري (CSID) الصادرة من ZATCA بصيغة PEM."""
    if not cert_pem or not cert_pem.strip():
        raise ZATCAError(
            "شهادة ZATCA مطلوبة بصيغة PEM لاستخراج الرقم التسلسلي (الوسم 9)"
        )
    try:
        return x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
    except ValueError as exc:
        raise ZATCAError(f"تعذر قراءة شهادة ZATCA (PEM غير صالح): {exc}") from exc


def _public_point_b64(key) -> str:
    """المفتاح العام بترميز Base64 (Uncompressed Point) — الوسم 8."""
    public_key = key.public_key() if isinstance(key, ec.EllipticCurvePrivateKey) else key
    point = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return base64.b64encode(point).decode("ascii")


def _sign_invoice_hash(
    private_key: ec.EllipticCurvePrivateKey, invoice_hash: bytes
) -> str:
    """الوسم 7: توقيع ECDSA (secp256k1) على خلاصة الهاش (32 بايت) — Base64."""
    signature = private_key.sign(invoice_hash, ec.ECDSA(Prehashed(hashes.SHA256())))
    return base64.b64encode(signature).decode("ascii")


def _verify_signature(
    private_key: ec.EllipticCurvePrivateKey, invoice_hash: bytes, signature_b64: str
) -> None:
    """تحقق ذاتي من التوقيع قبل إخراج النتيجة (يفشل فوراً إن كان التوقيع غير مطابق)."""
    try:
        private_key.public_key().verify(
            base64.b64decode(signature_b64),
            invoice_hash,
            ec.ECDSA(Prehashed(hashes.SHA256())),
        )
    except (InvalidSignature, ValueError) as exc:
        raise ZATCAError(f"فشل التحقق الذاتي من التوقيع الرقمي: {exc}") from exc


# ════════════════════════════════════════════════════════════════════════════
#  توليد صورة QR
# ════════════════════════════════════════════════════════════════════════════

def build_qr_png(tlv_b64: str, box_size: int = 5, fill_color: str = "#000000",
                 border: int = 4) -> str:
    """
    توليد صورة QR من حمولة TLV/Base64.
    ملاحظة: استخدم ألواناً عالية التباين (أسود/أبيض افتراضياً) لضمان المسح الضوئي.
    border: المنطقة الهادئة (Quiet Zone) — 4 وحدات هو التوصية القياسية لسهولة المسح.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(tlv_b64)
    qr.make(fit=True)
    image = qr.make_image(fill_color=fill_color, back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
# ════════════════════════════════════════════════════════════════════════════
#  الدالة الرئيسية — توليد QR مطابق ZATCA Phase 2
# ════════════════════════════════════════════════════════════════════════════

def build_phase2_qr(
    seller_name: str,
    seller_vat: str,
    timestamp: str,
    gross_total,
    vat_total,
    invoice_xml: str | None = None,
    private_key_pem: str | None = None,
    zatca_cert_pem: str | None = None,
    invoice_type: str = "simplified",
    qr_box_size: int = 5,
    qr_fill_color: str = "#000000",
) -> dict:
    """
    توليد QR Code مطابق ZATCA Phase 2 (إنتاجي — بلا قيم وهمية).

    المعاملات:
      seller_name    : اسم البائع (الوسم 1)
      seller_vat     : الرقم الضريبي 15 رقماً يبدأ بـ 3 (الوسم 2)
      timestamp      : ISO-8601 UTC مثل "2026-08-12T10:30:00Z" (الوسم 3)
      gross_total    : إجمالي الفاتورة شاملاً الضريبة (الوسم 4)
      vat_total      : إجمالي ضريبة القيمة المضافة (الوسم 5)
      invoice_xml    : XML الفاتورة UBL 2.1 — إجباري للفواتير المبسطة (الوسم 6)
      private_key_pem: المفتاح الخاص secp256k1 — إجباري للفواتير المبسطة (الوسم 7)
      zatca_cert_pem : شهادة ZATCA (CSID) — إجبارية للفواتير المبسطة (الوسمان 8 و 9)
      invoice_type   : "simplified" (افتراضي) أو "standard"

    العائد: dict يحتوي tlv_b64 و qr_png_b64 (Data URI) و hash_hex وتفكيك الوسوم.
    """
    invoice_type = (invoice_type or "").strip().lower()
    if invoice_type not in ("simplified", "standard"):
        raise ZATCAError("invoice_type يجب أن يكون 'simplified' أو 'standard'")
    is_simplified = invoice_type == "simplified"

    seller_name = (seller_name or "").strip()
    if not seller_name:
        raise ZATCAError("اسم البائع مطلوب (الوسم 1)")
    seller_vat = _validate_vat_number(seller_vat)
    timestamp = _validate_timestamp(timestamp)

    gross_str = _format_amount(gross_total, "إجمالي الفاتورة (الوسم 4)")
    vat_str = _format_amount(vat_total, "إجمالي الضريبة (الوسم 5)")
    if Decimal(vat_str) > Decimal(gross_str):
        raise ZATCAError(
            "إجمالي الضريبة (الوسم 5) لا يمكن أن يتجاوز إجمالي الفاتورة (الوسم 4)"
        )

    result: dict = {
        "invoice_type": invoice_type,
        "seller_name": seller_name,
        "seller_vat": seller_vat,
        "timestamp": timestamp,
        "gross_total": gross_str,
        "vat_total": vat_str,
        "invoice_uuid": None,
        "invoice_hash_b64": None,
        "hash_hex": None,
        "signature_b64": None,
        "public_key_b64": None,
        "cert_serial_hex": None,
        "verified": None,
        "tlv_b64": None,
        "qr_png_b64": None,
        "tags": [],
    }

    # ── الوسوم 1..5 (مشتركة بين النوعين) ─────────────────────
    payload = b"".join(
        (
            tlv(1, seller_name),
            tlv(2, seller_vat),
            tlv(3, timestamp),
            tlv(4, gross_str),
            tlv(5, vat_str),
        )
    )

    # ── الوسوم 6..9 (الفواتير المبسطة فقط — ختم تشفيري حقيقي) ─
    if is_simplified:
        missing = [
            name
            for name, value in (
                ("invoice_xml", invoice_xml),
                ("private_key_pem", private_key_pem),
                ("zatca_cert_pem", zatca_cert_pem),
            )
            if not value or not str(value).strip()
        ]
        if missing:
            raise ZATCAError(
                "الفاتورة المبسطة تتطلب الختم التشفيري الكامل وهي ناقصة: "
                + "، ".join(missing)
                + " — مرّر بيانات ZATCA الحقيقية (لا توجد قيم بديلة وهمية في هذه النسخة)."
            )

        private_key = load_private_key(private_key_pem)
        certificate = load_zatca_certificate(zatca_cert_pem)

        public_key_b64 = _public_point_b64(private_key)
        certificate_key_b64 = _public_point_b64(certificate.public_key())
        if public_key_b64 != certificate_key_b64:
            raise ZATCAError(
                "المفتاح الخاص المُمرر لا يطابق المفتاح العام داخل شهادة ZATCA — "
                "تحقق من تطابق زوج المفاتيح مع الشهادة الصادرة"
            )

        invoice_hash = compute_invoice_hash(invoice_xml)
        signature_b64 = _sign_invoice_hash(private_key, invoice_hash)
        _verify_signature(private_key, invoice_hash, signature_b64)

        uuid_match = _UUID_RE.search(invoice_xml)
        result["invoice_uuid"] = uuid_match.group(1).strip() if uuid_match else None
        result["invoice_hash_b64"] = base64.b64encode(invoice_hash).decode("ascii")
        result["hash_hex"] = invoice_hash.hex()
        result["signature_b64"] = signature_b64
        result["public_key_b64"] = public_key_b64
        result["cert_serial_hex"] = format(certificate.serial_number, "X")
        result["verified"] = True

        payload += tlv(6, result["invoice_hash_b64"])
        payload += tlv(7, signature_b64)
        payload += tlv(8, public_key_b64)
        payload += tlv(9, result["cert_serial_hex"])

    # ── الترميز وصورة QR وتفكيك الوسوم للتحقق ─────────────────
    tlv_b64 = base64.b64encode(payload).decode("ascii")
    result["tlv_b64"] = tlv_b64
    result["tags"] = parse_tlv(payload)
    result["qr_png_b64"] = build_qr_png(
        tlv_b64, box_size=qr_box_size, fill_color=qr_fill_color
    )
    return result
# ════════════════════════════════════════════════════════════════════════════
#  وضع الفحص الذاتي — للاختبار المحلي فقط (ليست شهادة ZATCA)
# ════════════════════════════════════════════════════════════════════════════

_SELF_TEST_INVOICE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ProfileID>reporting:1.0</cbc:ProfileID>
  <cbc:ID>SELF-TEST-0001</cbc:ID>
  <cbc:UUID>7ac1a878-e3fe-4b53-a077-c4f2e0b1e6c0</cbc:UUID>
  <cbc:IssueDate>2026-08-12</cbc:IssueDate>
  <cbc:IssueTime>10:30:00</cbc:IssueTime>
  <cbc:InvoiceTypeCode name="0100000">388</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>SAR</cbc:DocumentCurrencyCode>
</Invoice>
"""  # XML مبسّط لفحص سلامة خطوات الهاش/التوقيع فقط — ليس فاتورة مكتملة المطابقة


def _generate_self_test_credentials() -> tuple[str, str]:
    """
    ⚠ اختبار فقط: توليد زوج مفاتيح secp256k1 وشهادة موقعة ذاتياً محلياً
    لفحص سلامة خط الأنابيب. لا يصلح لأي فاتورة حقيقية إطلاقاً.
    """
    key = ec.generate_private_key(ec.SECP256K1())
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "ZATCA SELF-TEST — NOT FOR PRODUCTION")]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    return key_pem, cert_pem


def _expect_zatca_error(action, needle: str, label: str) -> None:
    try:
        action()
    except ZATCAError as exc:
        if needle not in str(exc):
            raise AssertionError(f"{label}: رسالة غير متوقعة: {exc}") from exc
        return
    raise AssertionError(f"{label}: كان متوقعاً رفع ZATCAError ولم يحدث")


def run_self_test() -> int:
    """فحص ذاتي شامل لسلامة الخطوات (توليد ← توقيع ← تحقق ← فكّ TLV ← حالات رفض)."""
    print("=" * 64)
    print("SELF-TEST — فحص ذاتي محلي فقط (مفاتيح مولّدة محلياً، ليست ZATCA)")
    print("=" * 64)

    key_pem, cert_pem = _generate_self_test_credentials()

    common = dict(
        seller_name="شركة ركن الهلال للاقمشة",
        seller_vat="311187605900003",
        timestamp="2026-08-12T10:30:00Z",
        gross_total=3048.19,
        vat_total=397.59,
    )

    # 1) فاتورة مبسطة — خط الأنابيب الكامل
    result = build_phase2_qr(
        **common,
        invoice_xml=_SELF_TEST_INVOICE_XML,
        private_key_pem=key_pem,
        zatca_cert_pem=cert_pem,
        invoice_type="simplified",
    )
    print(f"TLV B64        : {result['tlv_b64'][:48]}...")
    print(f"Invoice Hash   : {result['hash_hex']}")
    print(f"UUID (من XML)  : {result['invoice_uuid']}")
    print(f"Cert Serial    : {result['cert_serial_hex']}")
    print(f"Self-Verified  : {result['verified']}")

    tags = dict(parse_tlv(base64.b64decode(result["tlv_b64"])))
    assert sorted(tags) == list(range(1, 10)), "الوسوم 1..9 غير مكتملة"
    digest = compute_invoice_hash(_SELF_TEST_INVOICE_XML)
    assert tags[6] == base64.b64encode(digest).decode("ascii"), "الوسم 6 لا يطابق الهاش"
    load_private_key(key_pem).public_key().verify(
        base64.b64decode(tags[7]), digest, ec.ECDSA(Prehashed(hashes.SHA256()))
    )
    print("PASS 1: الوسوم 1..9 مكتملة والتوقيع في الوسم 7 يتحقق بعد فكّ TLV")

    # 2) فاتورة قياسية — الوسوم 1..5 فقط
    standard = build_phase2_qr(**common, invoice_type="standard")
    assert [t for t, _ in standard["tags"]] == [1, 2, 3, 4, 5], \
        "الفاتورة القياسية يجب أن تحمل الوسوم 1..5 فقط"
    print("PASS 2: الفاتورة القياسية أخرجت الوسوم 1..5 فقط")
    # 3) حالات رفض (يجب أن تفشل بدل إنتاج مخرجات وهمية)
    _expect_zatca_error(
        lambda: build_phase2_qr(
            "شركة", "123", "2026-08-12T10:30:00Z", 10, 1.5, invoice_type="standard"
        ),
        "15 رقماً",
        "رقم ضريبي غير صالح",
    )
    _expect_zatca_error(
        lambda: build_phase2_qr(
            "شركة", "311187605900003", "12-08-2026 10:30", 10, 1.5,
            invoice_type="standard",
        ),
        "ISO-8601",
        "طابع زمني غير صالح",
    )
    _expect_zatca_error(
        lambda: build_phase2_qr(**common, invoice_type="simplified"),
        "ناقصة",
        "بيانات الختم الناقصة",
    )
    other_key_pem, _ = _generate_self_test_credentials()
    _expect_zatca_error(
        lambda: build_phase2_qr(
            **common,
            invoice_xml=_SELF_TEST_INVOICE_XML,
            private_key_pem=other_key_pem,
            zatca_cert_pem=cert_pem,
            invoice_type="simplified",
        ),
        "لا يطابق",
        "مفتاح لا يطابق الشهادة",
    )
    wrong_curve_pem = (
        ec.generate_private_key(ec.SECP256R1())
        .private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        .decode("ascii")
    )
    _expect_zatca_error(
        lambda: build_phase2_qr(
            **common,
            invoice_xml=_SELF_TEST_INVOICE_XML,
            private_key_pem=wrong_curve_pem,
            zatca_cert_pem=cert_pem,
            invoice_type="simplified",
        ),
        "secp256k1",
        "منحنى غير مدعوم",
    )
    print(
        "PASS 3: حالات الرفض تعمل (رقم ضريبي، طابع زمني، بيانات ناقصة، "
        "مفتاح مغاير، منحنى خطأ)"
    )

    print("-" * 64)
    print("SELF-TEST PASSED — خط الأنابيب سليم (بمفاتيح اختبار محلية مؤقتة)")
    return 0


# ════════════════════════════════════════════════════════════════════════════
#  واجهة سطر الأوامر (CLI)
# ════════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover
            pass

    parser = argparse.ArgumentParser(
        description="مولّد QR مطابق ZATCA Phase 2 (إنتاجي — يتطلب شهادة ZATCA الحقيقية)"
    )
    parser.add_argument(
        "--self-test", action="store_true",
        help="تشغيل الفحص الذاتي بمفاتيح محلية مؤقتة (للاختبار فقط)",
    )
    parser.add_argument("--key", help="مسار ملف المفتاح الخاص PEM (secp256k1)")
    parser.add_argument("--cert", help="مسار شهادة ZATCA (CSID) بصيغة PEM")
    parser.add_argument("--xml", help="مسار ملف XML الفاتورة (UBL 2.1)")
    parser.add_argument("--seller-name", help="اسم البائع (الوسم 1)")
    parser.add_argument("--vat", help="الرقم الضريبي (الوسم 2)")
    parser.add_argument("--timestamp", help="الطابع الزمني ISO-8601 UTC (الوسم 3)")
    parser.add_argument("--total", type=float,
                        help="إجمالي الفاتورة شاملاً الضريبة (الوسم 4)")
    parser.add_argument("--vat-total", type=float, help="إجمالي الضريبة (الوسم 5)")
    parser.add_argument("--type", choices=["simplified", "standard"],
                        default="simplified", help="نوع الفاتورة (افتراضي: simplified)")
    parser.add_argument("--qr-out", help="حفظ صورة QR إلى ملف PNG")
    parser.add_argument("--json", action="store_true", help="طباعة النتيجة بصيغة JSON")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    required = {
        "--key": args.key,
        "--cert": args.cert,
        "--xml": args.xml,
        "--seller-name": args.seller_name,
        "--vat": args.vat,
        "--timestamp": args.timestamp,
        "--total": args.total,
        "--vat-total": args.vat_total,
    }
    missing = [flag for flag, value in required.items() if value is None]
    if missing:
        parser.error(f"وسائط مفقودة: {', '.join(missing)} — أو استخدم --self-test")

    try:
        result = build_phase2_qr(
            seller_name=args.seller_name,
            seller_vat=args.vat,
            timestamp=args.timestamp,
            gross_total=args.total,
            vat_total=args.vat_total,
            invoice_xml=Path(args.xml).read_text(encoding="utf-8-sig"),
            private_key_pem=Path(args.key).read_text(encoding="utf-8-sig"),
            zatca_cert_pem=Path(args.cert).read_text(encoding="utf-8-sig"),
            invoice_type=args.type,
        )
    except ZATCAError as exc:
        print(f"خطأ ZATCA: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=" * 64)
        print("ZATCA Phase 2 QR — إنتاجي (9-Tag TLV)")
        print("=" * 64)
        print(f"نوع الفاتورة    : {result['invoice_type']}")
        print(f"UUID الفاتورة   : {result['invoice_uuid']}")
        print(f"Invoice Hash    : {result['hash_hex']}")
        print(f"Cert Serial     : {result['cert_serial_hex']}")
        print(f"تم التحقق ذاتياً : {result['verified']}")
        print(f"TLV B64         : {result['tlv_b64'][:60]}...")
        print("--- Tags Breakdown ---")
        for tag, value in result["tags"]:
            shown = value if len(value) <= 60 else value[:60] + "…"
            print(f"  Tag {tag}: {shown}")

    if args.qr_out:
        png_bytes = base64.b64decode(result["qr_png_b64"].split(",", 1)[1])
        Path(args.qr_out).write_bytes(png_bytes)
        print(f"تم حفظ صورة QR: {args.qr_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())