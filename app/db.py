# -*- coding: utf-8 -*-
"""
قاعدة البيانات SQLite — تُنشأ تلقائيًا عند أول تشغيل مع بيانات تجريبية.
المخطط يطابق المواصفة مع إضافة جدول batches وعمودي batch_id/qr_payload_b64/qr_mode.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent      # invoice-generator/
APP_DIR = Path(__file__).resolve().parent              # invoice-generator/app
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "itqan_invoices.db"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
KEYS_DIR = DATA_DIR / "keys"
TMP_DIR = DATA_DIR / "tmp"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT DEFAULT '',
    tax_number TEXT DEFAULT '',
    cr_number TEXT DEFAULT '',
    logo_path TEXT DEFAULT '',
    color TEXT DEFAULT '#0e7490'
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT DEFAULT '',
    tax_number TEXT DEFAULT '',
    cr_number TEXT DEFAULT '',
    phone TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS item_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER REFERENCES item_groups(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    code TEXT DEFAULT '',
    unit TEXT DEFAULT 'حبة',
    unit_price REAL NOT NULL DEFAULT 0,
    tax_rate REAL NOT NULL DEFAULT 0.15
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('invoice','receipt')),
    html_content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    seed INTEGER,
    params_json TEXT,
    invoice_count INTEGER DEFAULT 0,
    total_net REAL DEFAULT 0,
    total_tax REAL DEFAULT 0,
    total_gross REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER REFERENCES batches(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    invoice_number TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    invoice_time TEXT NOT NULL,
    payment_type TEXT DEFAULT 'نقدي',
    subtotal REAL NOT NULL DEFAULT 0,
    tax_amount REAL NOT NULL DEFAULT 0,
    total_amount REAL NOT NULL DEFAULT 0,
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    notes TEXT DEFAULT '',
    qr_mode TEXT DEFAULT 'none',
    qr_payload_b64 TEXT DEFAULT '',
    qr_position TEXT NOT NULL DEFAULT 'inplace',
    discount_amount REAL NOT NULL DEFAULT 0,
    is_manual INTEGER NOT NULL DEFAULT 0,
    approval_status TEXT NOT NULL DEFAULT 'approved',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
    item_id INTEGER,
    item_name TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 1,
    unit TEXT DEFAULT '',
    unit_price REAL NOT NULL DEFAULT 0,
    discount_rate REAL NOT NULL DEFAULT 0,
    discount_amount REAL NOT NULL DEFAULT 0,
    line_total REAL NOT NULL DEFAULT 0,
    line_tax REAL NOT NULL DEFAULT 0,
    line_gross REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER REFERENCES batches(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    receipt_number TEXT NOT NULL,
    receipt_date TEXT NOT NULL,
    receipt_time TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    type TEXT NOT NULL DEFAULT 'قبض' CHECK (type IN ('قبض','صرف')),
    related_invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_invoices_batch ON invoices(batch_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_receipts_batch ON receipts(batch_id);
"""

# ══════════════════════════════════════════════════════════════════════════
#  البيانات التجريبية
# ══════════════════════════════════════════════════════════════════════════

DEMO_COMPANIES = [
    ("شركة ركن الهلال للأقمشة", "الرياض - حي الصناعية الجديدة، شارع الأولين، مبنى 214", "311187605900003", "1010473355", "#0e7490"),
    ("مؤسسة البناء الرصين للمواد الإنشائية", "جدة - طريق المدينة، مخازن الخمرة، مستودع 8", "310397281500003", "4030218844", "#b45309"),
    ("شركة الأفق للقرطاسية واللوازم المكتبية", "الدمام - شارع الأمير محمد، برج الموج، الدور 3", "311048362700003", "2051188377", "#4d7c0f"),
]

DEMO_CUSTOMERS = [
    # (الاسم، العنوان، الرقم الضريبي، السجل التجاري، الهاتف)
    ("شركة الواحة للمقاولات", "الرياض - حي الملقا، طريق أنس بن مالك", "310982736500003", "1010223344", "0555102938"),
    ("مؤسسة نماء التجارية", "جدة - حي الروضة، شارع علي بن أبي طالب", "310555123400003", "4030112299", "0533447821"),
    ("شركة البيارق للتجارة العامة", "الخبر - الكورنيش، مجمع الأعمال", "311223344500003", "2050117733", "0567812345"),
    ("عبد الرحمن بن سعد الحربي", "بريدة - شارع الملك عبد العزيز", "", "", "0500123456"),
    ("مؤسسة الإتقان للتشطيبات", "الرياض - حي النرجس، شارع أنس بن مالك", "310445566700003", "1010556677", "0598876543"),
]

# (المجموعة، الوصف، [(الاسم، الكود، الوحدة، السعر)])
DEMO_GROUPS = [
    ("مواد بناء", "أسمنت، رمل، حديد ولوازم البناء", [
        ("أسمنت مقاوم 50 كجم", "BLD-001", "كيس", 14.50),
        ("حديد تسليح 12مم", "BLD-002", "لتر طن", 2850.00),
        ("رمل مغسول", "BLD-003", "متر مكعب", 85.00),
        ("بلوك خرساني 20سم", "BLD-004", "حبة", 2.75),
        ("جبس بورد 12مم", "BLD-005", "لوح", 11.25),
        ("دهان مائي أبيض 18 لتر", "BLD-006", "علبة", 165.00),
        ("سيراميك أرضيات 60×60", "BLD-007", "متر مربع", 42.00),
        ("خلاطة أسمنت صغيرة", "BLD-008", "حبة", 1450.00),
    ]),
    ("أقمشة", "أقمشة جملة وتفصيل", [
        ("قماش قطني مصري", "FAB-001", "متر", 28.00),
        ("قماش صوف إيطالي", "FAB-002", "متر", 145.00),
        ("حرير طبيعي", "FAB-003", "متر", 220.00),
        ("أبازيم خفيف", "FAB-004", "متر", 16.50),
        ("خيط خياطة 500م", "FAB-005", "بكرة", 3.50),
        ("أزرار معدنية (علبة 100)", "FAB-006", "علبة", 9.75),
        ("سحاب معدني 40سم", "FAB-007", "حبة", 2.00),
    ]),
    ("قرطاسية", "لوازم مكتبية وورق", [
        ("ورق تصوير A4 (5 رزم)", "STA-001", "كرتون", 92.00),
        ("أقلام حبر جاف أزرق", "STA-002", "علبة 50", 27.50),
        ("ملفات بلاستيكية", "STA-003", "حبة", 1.25),
        ("دباسة مكتبية كبيرة", "STA-004", "حبة", 24.00),
        ("مسطرة بلاستيك 30سم", "STA-005", "حبة", 2.50),
        ("حبر طابعة أسود 85A", "STA-006", "حبة", 385.00),
        ("سبورة بيضاء 90×120", "STA-007", "حبة", 145.00),
    ]),
]

def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR, KEYS_DIR, TMP_DIR):
        d.mkdir(parents=True, exist_ok=True)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _default_template(kind: str) -> str:
    path = APP_DIR / "doc_templates" / f"default_{kind}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"<!doctype html><meta charset='utf-8'><p>قالب {kind} الافتراضي غير موجود في الملفات.</p>"


EXTRA_INVOICE_TEMPLATES = [
    ("فاتورة ضريبية — كلاسيك", "invoice_classic.html"),
    ("فاتورة ضريبية — حديث", "invoice_modern.html"),
    ("فاتورة ضريبية — رسمي حكومي", "invoice_government.html"),
    ("فاتورة ضريبية — مينيمالي", "invoice_minimal.html"),
    ("فاتورة ضريبية — احترافية", "invoice_corporate.html"),
    ("سهل 2", "invoice_easy2.html"),
    ("سهل 4", "invoice_sahl4.html"),
    ("سهل 5", "invoice_sahl5.html"),
]


def _seed_extra_invoice_templates(conn: sqlite3.Connection) -> None:
    """زرع القوالب الجاهزة من ملفات doc_templates.
    عند ترقية EXTRA_TEMPLATES_VERSION تُزامَن النسخ المخزنة مع أحدث ملف
    (بنفس منطق ترحيل القوالب الافتراضية — القوالب المخصصة بأسماء أخرى لا تُمس)."""
    cur = conn.cursor()
    existing = {row["name"] for row in cur.execute(
        "SELECT name FROM templates WHERE type='invoice'").fetchall()}
    sync = (get_setting(conn, "extra_templates_version", 0) or 0) < EXTRA_TEMPLATES_VERSION
    for display_name, filename in EXTRA_INVOICE_TEMPLATES:
        path = APP_DIR / "doc_templates" / filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if display_name not in existing:
            cur.execute(
                "INSERT INTO templates (name, type, html_content) VALUES (?,?,?)",
                (display_name, "invoice", content),
            )
        elif sync:
            cur.execute(
                "UPDATE templates SET html_content=? WHERE name=? AND type='invoice'",
                (content, display_name),
            )
    if sync:
        set_setting(conn, "extra_templates_version", EXTRA_TEMPLATES_VERSION)


def seed_demo(conn: sqlite3.Connection) -> None:
    """زرع بيانات تجريبية عند أول تشغيل (الجداول الفارغة فقط)."""
    cur = conn.cursor()
    if cur.execute("SELECT COUNT(*) AS c FROM companies").fetchone()["c"] == 0:
        for name, addr, vat, cr, color in DEMO_COMPANIES:
            cur.execute(
                "INSERT INTO companies (name, address, tax_number, cr_number, color) VALUES (?,?,?,?,?)",
                (name, addr, vat, cr, color),
            )
    if cur.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"] == 0:
        for row in DEMO_CUSTOMERS:
            cur.execute(
                "INSERT INTO customers (name, address, tax_number, cr_number, phone) VALUES (?,?,?,?,?)",
                row
            )
    if cur.execute("SELECT COUNT(*) AS c FROM item_groups").fetchone()["c"] == 0:
        for gname, gdesc, its in DEMO_GROUPS:
            cur.execute("INSERT INTO item_groups (name, description) VALUES (?,?)", (gname, gdesc))
            gid = cur.lastrowid
            for iname, code, unit, price in its:
                cur.execute(
                    "INSERT INTO items (group_id, name, code, unit, unit_price, tax_rate) VALUES (?,?,?,?,?,0.15)",
                    (gid, iname, code, unit, price),
                )
    if cur.execute("SELECT COUNT(*) AS c FROM templates").fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO templates (name, type, html_content) VALUES (?,?,?)",
            ("فاتورة ضريبية — الافتراضي", "invoice", _default_template("invoice")),
        )
        cur.execute(
            "INSERT INTO templates (name, type, html_content) VALUES (?,?,?)",
            ("سند قبض/صرف — الافتراضي", "receipt", _default_template("receipt")),
        )
    _migrate_default_templates(conn)
    _migrate_qr_payloads(conn)
    _seed_extra_invoice_templates(conn)

    # إضافة القوالس المحترفة الجديدة من invoice-templates
    try:
        from app.templates_loader import seed_professional_templates
        seed_professional_templates(conn)
    except Exception:
        pass  # السماح بالاستمرار إذا فشل التحميل

    ensure_admin_gate(conn)          # بوابة المشرف بكلمة المرور الافتراضية admin123
    conn.commit()


DEFAULT_TEMPLATES_VERSION = 8   # v8: وسم عناصر القوالب الافتراضية بـ tpl-* لدعم المحرر المرئي الكامل + السجل التجاري للعميل في السند
EXTRA_TEMPLATES_VERSION = 8     # v8: إتاحة «سهل 5» (فاتورة ضريبية بتصميم مميز) كقالب جاهز + مزامنة القوالب الجاهزة
QR_PAYLOAD_VERSION = 2          # v2: تصحيح الوسمين 4/5 (ريالات بدل هللة) في الطور الثاني


def _migrate_qr_payloads(conn: sqlite3.Connection) -> None:
    """إصلاح تلقائي لحمولات QR المخزنة عند ترقية صيغة الحمولة (إصدار 2)."""
    version = get_setting(conn, "qr_payload_version", 0) or 0
    if version >= QR_PAYLOAD_VERSION:
        return
    try:
        from app import qr_service as qs
        qs.regenerate_stored_qr(conn)
    except Exception as exc:
        import logging
        logging.getLogger("db.migrate").warning("تعذر إصلاح الحمولات: %s", exc)
    set_setting(conn, "qr_payload_version", QR_PAYLOAD_VERSION)


def _migrate_default_templates(conn: sqlite3.Connection) -> None:
    """تحديث القوالب الافتراضية المخزنة عند تغيير نسختها (القوالب المخصصة لا تُمس)."""
    version = get_setting(conn, "default_templates_version", 0) or 0
    if version >= DEFAULT_TEMPLATES_VERSION:
        return
    for name, kind in (("فاتورة ضريبية — الافتراضي", "invoice"),
                       ("سند قبض/صرف — الافتراضي", "receipt")):
        conn.execute(
            "UPDATE templates SET html_content=? WHERE name=? AND type=?",
            (_default_template(kind), name, kind),
        )
    set_setting(conn, "default_templates_version", DEFAULT_TEMPLATES_VERSION)


def _column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    return col in {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_manual_invoice_schema(conn: sqlite3.Connection) -> None:
    """إضافة أعمدة الفواتير اليدوية (وأعمدة بيانات العملاء/وحدة الصنف) إلى قواعد
    بيانات سابقة — ترحيل آمن لا يمس البيانات القائمة."""
    if not _column_exists(conn, "invoices", "discount_amount"):
        conn.execute("ALTER TABLE invoices ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0")
    if not _column_exists(conn, "invoices", "is_manual"):
        conn.execute("ALTER TABLE invoices ADD COLUMN is_manual INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "invoices", "approval_status"):
        conn.execute("ALTER TABLE invoices ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'approved'")
    if not _column_exists(conn, "invoices", "qr_position"):
        conn.execute("ALTER TABLE invoices ADD COLUMN qr_position TEXT NOT NULL DEFAULT 'inplace'")
    if not _column_exists(conn, "invoice_items", "discount_rate"):
        conn.execute("ALTER TABLE invoice_items ADD COLUMN discount_rate REAL NOT NULL DEFAULT 0")
    if not _column_exists(conn, "invoice_items", "discount_amount"):
        conn.execute("ALTER TABLE invoice_items ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0")
    # وحدة الصنف تُحفظ مع سطر الفاتورة لتُعرض ديناميكيًا (وحدات حرة للفواتير اليدوية)
    if not _column_exists(conn, "invoice_items", "unit"):
        conn.execute("ALTER TABLE invoice_items ADD COLUMN unit TEXT DEFAULT ''")
    # السجل التجاري للعميل (اختياري — يُخفى تمامًا في الفاتورة والطباعة إذا كان فارغًا)
    if not _column_exists(conn, "customers", "cr_number"):
        conn.execute("ALTER TABLE customers ADD COLUMN cr_number TEXT DEFAULT ''")
    conn.commit()


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """إنشاء المخطط + البيانات التجريبية وإرجاع اتصال جاهز."""
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_manual_invoice_schema(conn)
    seed_demo(conn)
    return conn


def get_setting(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return row["value"]


def set_setting(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value, ensure_ascii=False)),
    )
    conn.commit()


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════════════════════
#  مخصصات المظهر والتنبيهات (تُمرر لكل الفواتير والسندات والقوالب)
# ══════════════════════════════════════════════════════════════════════════

THEME_DEFAULTS = {
    "primary_color": "#0e7490",          # اللون الرئيسي (الترويسة، أعمدة الجدول)
    "title_color": "#0e7490",            # لون العنوان المستقل (فاتورة/سند)
    "seller_name_color": "#0e7490",      # لون اسم شركة البائع (مستقل)
    "header_text_color": "#ffffff",      # لون نص الترويسة والأعمدة
    "font_family": "Cairo",              # خط المستندات (يُطبق على كل الفواتير والسندات)
    "font_size": "13",                   # حجم خط المستندات الأساسي (px)
    "alert_banner_enabled": True,        # إظهار شريط التنبيه التحذيري أعلى المستند
    "alert_banner_text": "تنبيه رقابي: هذه الفاتورة تدريبية لتطوير مهارات المراجعة "
                         "وفك التشفير فقط — ليست صادرة عن جهة رسمية ولا تصلح لأي "
                         "إجراء ضريبي أو قانوني.",
    "alert_banner_color": "#b91c1c",     # لون شريط التنبيه
    "alert_banner_bg": "#fee2e2",        # خلفية شريط التنبيه
    "watermark_text": "",    # نص الختم المائي
    "footer_notice": "",  # نص التذييل
    "show_watermark": True,              # إظهار الختم المائي
}

# الخطوط العربية المتاحة لمظهر المستندات (Google Fonts)
FONT_CHOICES = ("Cairo", "Tajawal", "Amiri", "Noto Kufi Arabic", "Almarai")
FONT_SIZES = ("12", "13", "14", "15", "16")



def get_theme(conn) -> dict:
    """قراءة إعدادات المظهر الحالية (مع الدمج مع الافتراضي)"""
    stored = get_setting(conn, "theme", {}) or {}
    theme = dict(THEME_DEFAULTS)
    theme.update({k: v for k, v in stored.items() if k in THEME_DEFAULTS})

    theme['generated_note'] = ""
    # التذييل التحذيري قابل للتخصيص — والافتراضي يحمل تنويه النسخة التدريبية دائمًا
    if not theme['footer_notice']:
        theme['footer_notice'] = "نسخة تدريبية - غير صالحة للاستخدام"

    # التحقق من صحة الألوان السداسية
    if not _valid_color(theme.get("primary_color"), THEME_DEFAULTS["primary_color"]):
        theme["primary_color"] = THEME_DEFAULTS["primary_color"]
    if not _valid_color(theme.get("title_color"), theme["primary_color"]):
        theme["title_color"] = theme["primary_color"]
    if not _valid_color(theme.get("seller_name_color"), theme["title_color"]):
        theme["seller_name_color"] = theme["title_color"]

    return theme


def save_theme(conn, data: dict) -> dict:
    """حفظ إعدادات المظهر (تُقبل المفاتيح المعروفة فقط)."""
    cur = get_theme(conn)
    for k in THEME_DEFAULTS:
        if k in data and data[k] not in (None, ""):
            cur[k] = data[k]
    set_setting(conn, "theme", cur)
    return cur


# ══════════════════════════════════════════════════════════════════════════
#  كلمة سر التحكم في الصلاحيات (الأمان)
# ══════════════════════════════════════════════════════════════════════════

SECURITY_DEFAULTS = {
    "protect_delete": True,    # طلب كلمة السر قبل حذف أي بيانات
    "protect_restore": True,   # طلبها قبل استعادة/حذف النسخ الاحتياطية
    "protect_edit": True,      # طلبها قبل تحرير الفاتورة كاملة (للمشرف)
}


def _security_stored(conn) -> dict:
    stored = get_setting(conn, "security", {}) or {}
    return stored if isinstance(stored, dict) else {}


def _hash_password(password: str, salt: str) -> str:
    """تجزئة PBKDF2-HMAC-SHA256 (120 ألف دورة) — لا تُخزن كلمة السر أبدًا."""
    import hashlib
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 120_000
    ).hex()


def get_security(conn) -> dict:
    """قراءة إعدادات الأمان — بدون إرجاع الهاش (password_set فقط)."""
    stored = _security_stored(conn)
    return {
        "password_set": bool(stored.get("password_hash")),
        "protect_delete": bool(stored.get("protect_delete", SECURITY_DEFAULTS["protect_delete"])),
        "protect_restore": bool(stored.get("protect_restore", SECURITY_DEFAULTS["protect_restore"])),
        "protect_edit": bool(stored.get("protect_edit", SECURITY_DEFAULTS["protect_edit"])),
    }


def verify_password(conn, password) -> bool:
    """التحقق من كلمة سر التحكم (True دائمًا إن لم تُعيّن كلمة سر)."""
    import hmac
    stored = _security_stored(conn)
    h, s = stored.get("password_hash", ""), stored.get("password_salt", "")
    if not h:
        return True
    if not password:
        return False
    try:
        return hmac.compare_digest(_hash_password(str(password), s), h)
    except ValueError:
        return False


def save_security(conn, data: dict) -> dict:
    """
    حفظ إعدادات الأمان:
    - new_password: تعيين/تغيير كلمة السر (يتطلب current_password إن وُجدت)
    - remove_password: إزالة كلمة السر (يتطلب current_password)
    - protect_delete / protect_restore: لا تُفعّل إلا بوجود كلمة سر
    """
    import os as _os
    stored = _security_stored(conn)

    # تعيين/تغيير كلمة السر
    new_pw = (data.get("new_password") or "").strip()
    if new_pw:
        if stored.get("password_hash") and not verify_password(conn, data.get("current_password")):
            raise ValueError("كلمة السر الحالية غير صحيحة")
        if len(new_pw) < 4:
            raise ValueError("كلمة السر قصيرة جدًا (4 أحرف على الأقل)")
        salt = _os.urandom(16).hex()
        stored["password_salt"] = salt
        stored["password_hash"] = _hash_password(new_pw, salt)

    # إزالة كلمة السر
    if data.get("remove_password"):
        if stored.get("password_hash") and not verify_password(conn, data.get("current_password")):
            raise ValueError("كلمة السر الحالية غير صحيحة")
        stored.pop("password_hash", None)
        stored.pop("password_salt", None)
        stored["protect_delete"] = False
        stored["protect_restore"] = False
        stored["protect_edit"] = False

    # مفاتيح الحماية (لا تُفعّل بلا كلمة سر، وتغييرها يتطلب كلمة السر الحالية)
    toggles_present = any(k in data for k in ("protect_delete", "protect_restore", "protect_edit"))
    if toggles_present and stored.get("password_hash") and not new_pw:
        if not verify_password(conn, data.get("current_password")):
            raise ValueError("أدخل كلمة السر الحالية لتغيير صلاحيات الحماية")
    for key in ("protect_delete", "protect_restore", "protect_edit"):
        if key in data:
            val = bool(data[key] in (True, "true", "1", 1, "on"))
            if val and not stored.get("password_hash"):
                raise ValueError("عيّن كلمة سر التحكم أولًا قبل تفعيل الحماية")
            stored[key] = val

    set_setting(conn, "security", stored)
    return get_security(conn)


# ══════════════════════════════════════════════════════════════════════════
#  بوابة حماية المشرف (Admin Gateway) — كلمة مرور افتراضية: admin123
#  تحمي لوحة المشرف وشاشات الفواتير اليدوية واعتمادها. كلمة السر مُعمّاة
#  (نفس آلية PBKDF2) ولا تُخزَّن نصًا أبدًا.
# ══════════════════════════════════════════════════════════════════════════

ADMIN_DEFAULT_PASSWORD = "admin123"   # كلمة المرور الافتراضية لبوابة المشرف


def _admin_gate_stored(conn) -> dict:
    stored = get_setting(conn, "admin_gate", {}) or {}
    return stored if isinstance(stored, dict) else {}


def ensure_admin_gate(conn: sqlite3.Connection) -> None:
    """تجهيز بوابة المشرف: تُعين كلمة المرور الافتراضية عند أول تشغيل فقط."""
    stored = _admin_gate_stored(conn)
    if stored.get("password_hash"):
        return
    import os as _os
    salt = _os.urandom(16).hex()
    set_setting(conn, "admin_gate", {
        "password_hash": _hash_password(ADMIN_DEFAULT_PASSWORD, salt),
        "password_salt": salt,
        "is_default": True,          # لا تزال كلمة المرور الافتراضية — لعرض تنبيه التغيير
    })


def get_admin_gate(conn) -> dict:
    """معلومات بوابة المشرف (بدون الهاش) لعرض الحالة في الواجهة."""
    stored = _admin_gate_stored(conn)
    return {
        "enabled": True,
        "password_set": bool(stored.get("password_hash")),
        "is_default": bool(stored.get("is_default")),
    }


def verify_admin_password(conn, password) -> bool:
    """التحقق من كلمة مرور بوابة المشرف (مقارنة ثابتة الزمن)."""
    import hmac
    stored = _admin_gate_stored(conn)
    h, s = stored.get("password_hash", ""), stored.get("password_salt", "")
    if not h:
        return False
    try:
        return hmac.compare_digest(_hash_password(str(password or ""), s), h)
    except ValueError:
        return False


def change_admin_password(conn, current: str, new: str) -> None:
    """تغيير كلمة مرور بوابة المشرف (يتطلب الكلمة الحالية)."""
    import os as _os
    if not verify_admin_password(conn, current):
        raise ValueError("كلمة مرور المشرف الحالية غير صحيحة")
    new = str(new or "").strip()
    if len(new) < 4:
        raise ValueError("كلمة المرور قصيرة جدًا (4 أحرف على الأقل)")
    salt = _os.urandom(16).hex()
    set_setting(conn, "admin_gate", {
        "password_hash": _hash_password(new, salt),
        "password_salt": salt,
        "is_default": False,
    })


def get_or_create_session_secret(conn: sqlite3.Connection) -> str:
    """سر جلسات Flask — يُنشأ مرة واحدة ويُحفظ ليبقى صالحًا بعد إعادة التشغيل."""
    s = get_setting(conn, "session_secret", None)
    if not s:
        import secrets as _secrets
        s = _secrets.token_hex(32)
        set_setting(conn, "session_secret", s)
    return str(s)

UI_DEFAULTS = {
    "accent_color": "#0e7490",     # لون الواجهة (الأزرار، البطاقات، الجداول)
    "sidebar_from": "#0c4a6e",     # بداية تدرج الشريط الجانبي
    "sidebar_to": "#164e63",       # نهاية تدرج الشريط الجانبي
    "app_notice": "",              # تنبيه عام يظهر أعلى كل الشاشات (فارغ = مخفي)
    "app_notice_color": "#b45309", # لون نص التنبيه العام
    "app_notice_bg": "#fffbeb",    # خلفية التنبيه العام
}


def _hex_rgb(value: str):
    """تحويل #RGB أو #RRGGBB إلى (r, g, b) أو None إن كان غير صالح."""
    h = str(value or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _shade(color: str, factor: float) -> str:
    """تغميق (factor < 1) أو تفتيح (factor > 1) لون سداسي."""
    rgb = _hex_rgb(color)
    if rgb is None:
        return color
    if factor <= 1:
        rgb = tuple(max(0, min(255, int(c * factor))) for c in rgb)
    else:
        rgb = tuple(max(0, min(255, int(c + (255 - c) * (factor - 1)))) for c in rgb)
    return "#%02x%02x%02x" % rgb


def _valid_color(value: str, fallback: str) -> str:
    return value if _hex_rgb(value) else fallback


def get_ui(conn) -> dict:
    """قراءة إعدادات مظهر الواجهة مع حساب المتجات المشتقة (فاتح/غامق)."""
    stored = get_setting(conn, "ui", {}) or {}
    ui = dict(UI_DEFAULTS)
    ui.update({k: v for k, v in stored.items() if k in UI_DEFAULTS})
    ui["accent_color"] = _valid_color(ui["accent_color"], UI_DEFAULTS["accent_color"])
    ui["accent_dark"] = _shade(ui["accent_color"], 0.72)
    ui["accent_light"] = _shade(ui["accent_color"], 1.9)
    return ui


def save_ui(conn, data: dict) -> dict:
    """حفظ مظهر الواجهة (يُقبل النص الفارغ لمسح التنبيه العام)."""
    cur = get_ui(conn)
    for key in ("accent_color", "sidebar_from", "sidebar_to",
                "app_notice_color", "app_notice_bg"):
        if key in data and data[key]:
            cur[key] = _valid_color(data[key], cur[key])
    if "app_notice" in data:
        cur["app_notice"] = str(data.get("app_notice") or "").strip()[:300]
    set_setting(conn, "ui", cur)
    return get_ui(conn)

