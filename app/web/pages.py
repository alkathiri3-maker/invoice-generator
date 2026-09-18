# -*- coding: utf-8 -*-
"""مسارات الصفحات (واجهة المستخدم)."""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, g, render_template, request, abort, send_from_directory, redirect, session, url_for

from app import db as dbm
from app.export import render as rnd
from app.generator.engine import GenParams
from app import qr_service as qr_svc

bp = Blueprint("pages", __name__)


@bp.context_processor
def _nav():
    from flask import g as _g
    return {
        # الشريط الجانبي منظم في مجموعات لتسهيل التنقل في لوحة المشرف
        "nav_groups": [
            {"title": "الرئيسية", "links": [
                ("pages.admin_dashboard", "لوحة المشرف", "🛡️"),
                ("pages.dashboard", "لوحة المعلومات", "🏠"),
            ]},
            {"title": "الفواتير", "links": [
                ("pages.generate", "توليد الفواتير", "⚙️"),
                ("pages.manual_invoice_page", "فاتورة يدوية", "✍️"),
                ("pages.invoices", "الفواتير الناتجة", "📊"),
                ("pages.manual_invoices_list", "اعتماد الفواتير اليدوية", "✅"),
                ("pages.receipts", "السندات", "🧾"),
            ]},
            {"title": "البيانات", "links": [
                ("pages.companies", "الشركات", "🏢"),
                ("pages.customers", "العملاء", "👥"),
                ("pages.items", "إدارة الأصناف والمجموعات", "📦"),
                ("pages.templates_screen", "القوالب", "🧾"),
            ]},
            {"title": "التقارير", "links": [
                ("pages.reports", "التقارير", "📈"),
            ]},
            {"title": "الأدوات", "links": [
                ("pages.verify_page", "فحص الباركود", "🔎"),
                ("pages.settings_screen", "الإعدادات والأمان", "🛡️"),
            ]},
        ],
        "nav": [
            ("pages.dashboard", "الرئيسية", "🏠"),
            ("pages.companies", "الشركات", "🏢"),
            ("pages.customers", "العملاء", "👥"),
            ("pages.items", "إدارة الأصناف والمجموعات", "📦"),
            ("pages.templates_screen", "القوالب", "🧾"),
            ("pages.generate", "توليد الفواتير", "⚙️"),
            ("pages.invoices", "الفواتير الناتجة", "📊"),
            ("pages.receipts", "السندات", "🧾"),
            ("pages.reports", "التقارير", "📈"),
            ("pages.verify_page", "فحص الباركود", "🔎"),
            ("pages.settings_screen", "الإعدادات والأمان", "🛡️"),
        ],
        # متغيرات عامة لكل الشاشات (مظهر الواجهة + حالة الأمان)
        "ui": dbm.get_ui(_g.conn),
        "security": dbm.get_security(_g.conn),
        "admin_gate": dbm.get_admin_gate(_g.conn),
    }


@bp.route("/")
def index():
    # الصفحة الرئيسية - عرض لوحة المعلومات مباشرة
    return dashboard()

@bp.route("/dashboard")
def dashboard():
    conn = g.conn
    from app import backup as bk
    stats = {
        "companies": conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"],
        "customers": conn.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"],
        "items": conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"],
        "invoices": conn.execute("SELECT COUNT(*) c FROM invoices").fetchone()["c"],
        "receipts": conn.execute("SELECT COUNT(*) c FROM receipts").fetchone()["c"],
        "gross": conn.execute("SELECT COALESCE(SUM(total_amount),0) s FROM invoices").fetchone()["s"],
        "tax": conn.execute("SELECT COALESCE(SUM(tax_amount),0) s FROM invoices").fetchone()["s"],
    }
    batches = conn.execute(
        "SELECT * FROM batches ORDER BY id DESC LIMIT 8"
    ).fetchall()
    # تذكير النسخة الاحتياطية: لا نسخة أبدًا أو مرّ عليها أكثر من 7 أيام
    age = bk.backup_age_days()
    backup_warning = age is None or age >= 7
    backup_age = age if age is not None else -1
    return render_template("dashboard.html", stats=stats, batches=batches,
                           backup_warning=backup_warning, backup_age=backup_age)


# ══════════════════════════════════════════════════════════════════════════
#  بوابة حماية المشرف + لوحة المشرف + الفواتير اليدوية
# ══════════════════════════════════════════════════════════════════════════

def _safe_next(target) -> str:
    """التحقق من هدف إعادة التوجيه — يمنع الفتح لمواقع خارجية."""
    if target and str(target).startswith("/") and not str(target).startswith("//"):
        return str(target)
    return url_for("pages.admin_dashboard")


@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """بوابة الحماية: تسجل دخول المشرف بكلمة المرور (الافتراضية admin123)."""
    next_url = request.args.get("next") or ""
    if session.get("admin_ok"):
        return redirect(_safe_next(next_url))
    error = None
    if request.method == "POST":
        password = (request.form.get("password") or "").strip()
        if dbm.verify_admin_password(g.conn, password):
            session.clear()
            session.permanent = True
            session["admin_ok"] = True
            return redirect(_safe_next(request.form.get("next") or next_url))
        error = "كلمة المرور غير صحيحة — حاول مجددًا"
    return render_template("login.html", error=error,
                           gate=dbm.get_admin_gate(g.conn), next_url=next_url)


@bp.route("/admin/logout")
def admin_logout():
    session.pop("admin_ok", None)
    return redirect(url_for("pages.admin_login"))


@bp.route("/admin")
def admin_dashboard():
    """لوحة المشرف — تنظيم الأقسام الرئيسية للتّنقل السريع."""
    conn = g.conn
    stats = {
        "companies": conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"],
        "customers": conn.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"],
        "items": conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"],
        "groups": conn.execute("SELECT COUNT(*) c FROM item_groups").fetchone()["c"],
        "invoices": conn.execute("SELECT COUNT(*) c FROM invoices").fetchone()["c"],
        "manual_drafts": conn.execute(
            "SELECT COUNT(*) c FROM invoices WHERE is_manual=1 AND approval_status='draft'").fetchone()["c"],
        "manual_approved": conn.execute(
            "SELECT COUNT(*) c FROM invoices WHERE is_manual=1 AND approval_status='approved'").fetchone()["c"],
        "receipts": conn.execute("SELECT COUNT(*) c FROM receipts").fetchone()["c"],
        "batches": conn.execute("SELECT COUNT(*) c FROM batches").fetchone()["c"],
        "gross": conn.execute("SELECT COALESCE(SUM(total_amount),0) s FROM invoices").fetchone()["s"],
        "tax": conn.execute("SELECT COALESCE(SUM(tax_amount),0) s FROM invoices").fetchone()["s"],
    }
    pending = conn.execute(
        """SELECT i.id, i.invoice_number, i.invoice_date, i.total_amount, i.payment_type,
                  c.name AS customer_name, co.name AS company_name
           FROM invoices i
           JOIN customers c ON c.id = i.customer_id
           JOIN companies co ON co.id = i.company_id
           WHERE i.is_manual=1 AND i.approval_status='draft'
           ORDER BY i.id DESC LIMIT 8"""
    ).fetchall()
    return render_template("admin.html", stats=stats, pending=pending,
                           gate=dbm.get_admin_gate(conn))


@bp.route("/admin/manual-invoice")
def manual_invoice_page():
    """شاشة إنشاء فاتورة يدوية بحرية كاملة (أصناف، أسعار، كميات، خصومات)."""
    from datetime import date, datetime
    conn = g.conn
    companies = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
    customers = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
    item_rows = conn.execute(
        """SELECT i.id, i.name, i.code, i.unit, i.unit_price, i.tax_rate, g.name AS group_name
           FROM items i LEFT JOIN item_groups g ON g.id = i.group_id
           ORDER BY g.name, i.name"""
    ).fetchall()
    # كتالوج متسلسل للواجهة: المجموعة أولًا ثم أصنافها فقط (منطق الاختيار المتسلسل)
    catalog = {}
    for it in item_rows:
        catalog.setdefault(it["group_name"] or "أصناف بلا مجموعة", []).append({
            "id": it["id"], "name": it["name"], "code": it["code"] or "",
            "unit": it["unit"] or "", "price": float(it["unit_price"] or 0),
            "tax": round(float(it["tax_rate"] or 0) * 100, 2),
        })
    invoice_templates = conn.execute(
        "SELECT id, name FROM templates WHERE type='invoice' ORDER BY name").fetchall()
    # خيارات نوع الباركود (المرحلة الأولى / المرحلة الثانية / بدون) — من خدمة الباركود
    qr_modes = [(m, qr_svc.QR_MODE_LABELS[m]) for m in qr_svc.QR_MODES]
    return render_template(
        "manual_invoice.html", companies=companies, customers=customers,
        item_rows=item_rows, catalog=catalog, invoice_templates=invoice_templates,
        qr_modes=qr_modes,
        today=date.today().isoformat(), now_time=datetime.now().strftime("%H:%M"),
    )


@bp.route("/admin/manual-invoices")
def manual_invoices_list():
    """قائمة الفواتير اليدوية — مع شاشة الاعتماد لكل مسودة."""
    conn = g.conn
    status = (request.args.get("status") or "").strip()
    if status not in ("draft", "approved"):
        status = ""
    where, args = "WHERE i.is_manual=1", []
    if status:
        where += " AND i.approval_status=?"
        args.append(status)
    rows = conn.execute(
        f"""SELECT i.*, c.name AS customer_name, co.name AS company_name
            FROM invoices i
            JOIN customers c ON c.id = i.customer_id
            JOIN companies co ON co.id = i.company_id
            {where} ORDER BY i.id DESC""",
        args).fetchall()
    draft_total = conn.execute(
        "SELECT COUNT(*) c FROM invoices WHERE is_manual=1 AND approval_status='draft'").fetchone()["c"]
    approved_total = conn.execute(
        "SELECT COUNT(*) c FROM invoices WHERE is_manual=1 AND approval_status='approved'").fetchone()["c"]
    return render_template("manual_invoices.html", rows=rows,
                           f_status=status, draft_total=draft_total,
                           approved_total=approved_total)


# ══════════════════════════════════════════════════════════════════════════
#  شاشات إدارة البيانات
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/companies")
def companies():
    rows = g.conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
    return render_template("companies.html", rows=rows)


@bp.route("/customers")
def customers():
    rows = g.conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
    return render_template("customers.html", rows=rows)


@bp.route("/groups")
def groups():
    """مسار قديم — يُحوَّل تلقائيًا إلى القسم الموحد (حفاظًا على الروابط)."""
    return redirect(url_for("pages.items"))


@bp.route("/items")
def items():
    """القسم الموحد: إدارة الأصناف والمجموعات — تبويبات/قائمة جانبية للمجموعات
    مع عرض الأصناف التابعة لكل مجموعة، وكامل أدوات التحكم للطرفين."""
    conn = g.conn
    groups = conn.execute(
        """SELECT g.*, (SELECT COUNT(*) FROM items i WHERE i.group_id = g.id) AS items_count
           FROM item_groups g ORDER BY g.name"""
    ).fetchall()
    rows = conn.execute(
        """SELECT i.*, g.name AS group_name FROM items i
           LEFT JOIN item_groups g ON g.id = i.group_id
           ORDER BY g.name, i.name"""
    ).fetchall()
    ungrouped_count = conn.execute(
        "SELECT COUNT(*) c FROM items WHERE group_id IS NULL").fetchone()["c"]
    catalog = []
    for gr in groups:
        its = conn.execute(
            """SELECT id, name, code, unit, unit_price, tax_rate FROM items
               WHERE group_id=? ORDER BY name""", (gr["id"],)).fetchall()
        catalog.append({
            "id": gr["id"],
            "name": gr["name"],
            "items": [{k: it[k] for k in it.keys()} for it in its],
        })
    return render_template("items.html", rows=rows, groups=groups,
                           catalog=catalog, ungrouped_count=ungrouped_count)


@bp.route("/templates")
def templates_screen():
    rows = g.conn.execute("SELECT * FROM templates ORDER BY type, name").fetchall()
    theme = dbm.get_theme(g.conn)
    return render_template("templates_screen.html", rows=rows, theme=theme,
                           font_choices=dbm.FONT_CHOICES, font_sizes=dbm.FONT_SIZES)


@bp.route("/templates/<int:tpl_id>/editor")
def template_editor_page(tpl_id: int):
    """محرر القالب في صفحة مستقلة — المحرر المرئي المتقدم + تحرير HTML.

    الصفحة تُفتح من شاشة القوالب (نفس التبويب) وتعمل على نفس نقاط الـ API
    (/api/templates/<id>/style و live-preview)، فلا يوجد أي تكرار للمنطق.
    """
    row = g.conn.execute("SELECT * FROM templates WHERE id=?", (tpl_id,)).fetchone()
    if not row:
        abort(404)
    # الوضع الافتراضي: المحرر المرئي — ويمكن فتح تبويب HTML مباشرة عبر ?tab=html
    mode = "html" if (request.args.get("tab") or "").strip().lower() == "html" else "visual"
    return render_template("template_editor.html", tpl=row, mode=mode)


# ══════════════════════════════════════════════════════════════════════════
#  الإعدادات والأمان (النسخ الاحتياطي، الصلاحيات، المظهر، التنبيهات)
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/settings")
def settings_screen():
    from app import backup as bk
    conn = g.conn
    ctx = {
        "theme": dbm.get_theme(conn),
        "font_choices": dbm.FONT_CHOICES,
        "font_sizes": dbm.FONT_SIZES,
        "security": dbm.get_security(conn),
        "ui": dbm.get_ui(conn),
        "companies": conn.execute(
            "SELECT id, name, color, logo_path FROM companies ORDER BY name").fetchall(),
        "backups": bk.list_backups(),
        "backup_auto": bool(dbm.get_setting(conn, "backup_auto", False)),
        "preview_url": (
            ("/invoices/%d/preview" % conn.execute(
                "SELECT id FROM invoices ORDER BY id DESC LIMIT 1").fetchone()["id"])
            if conn.execute("SELECT COUNT(*) c FROM invoices").fetchone()["c"] else None),
        "stats": {
            "invoices": conn.execute("SELECT COUNT(*) c FROM invoices").fetchone()["c"],
            "receipts": conn.execute("SELECT COUNT(*) c FROM receipts").fetchone()["c"],
            "companies": conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"],
            "customers": conn.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"],
        },
    }
    return render_template("settings.html", **ctx)


@bp.route("/backups/<path:name>")
def backup_download(name: str):
    from app import backup as bk
    return send_from_directory(bk.BACKUP_DIR, Path(name).name, as_attachment=True)

# ══════════════════════════════════════════════════════════════════════════
#  التوليد والنتائج والمعاينة
# ══════════════════════════════════════════════════════════════════════════

def _default_dates():
    from datetime import date, timedelta
    today = date.today()
    return (today - timedelta(days=30)).isoformat(), today.isoformat()


@bp.route("/generate")
def generate():
    conn = g.conn
    companies = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
    customers = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
    groups_raw = conn.execute("""SELECT g.*, (SELECT COUNT(*) FROM items i WHERE i.group_id = g.id) AS items_count
           FROM item_groups g ORDER BY g.name""").fetchall()
    # تحميل كل الأصناف وحسب المجموعات للقالب (الوضع الفردي)
    items_all = conn.execute(
        "SELECT i.*, g.name AS group_name FROM items i LEFT JOIN item_groups g ON g.id=i.group_id ORDER BY g.name, i.name"
    ).fetchall()
    from app.money import fmt_money
    groups = []
    for grp in groups_raw:
        grp_items = [{
            "id": it["id"], "name": it["name"], "code": it["code"],
            "unit": it["unit"], "unit_price": it["unit_price"],
            "unit_price_display": fmt_money(it["unit_price"]),
        } for it in items_all if it["group_id"] == grp["id"]]
        groups.append({
            "id": grp["id"], "name": grp["name"], "description": grp["description"],
            "items_count": grp["items_count"],
            "items_list": grp_items,
        })
    invoice_templates = conn.execute(
        "SELECT id, name FROM templates WHERE type='invoice' ORDER BY name").fetchall()
    receipt_templates = conn.execute(
        "SELECT id, name FROM templates WHERE type='receipt' ORDER BY name").fetchall()
    last = dbm.get_setting(conn, "gen_last", None)
    last_params = GenParams.from_json(last) if last else GenParams(
        company_id=companies[0]["id"] if companies else 0,
        customer_ids=[customers[0]["id"]] if customers else [],
    )
    date_from, date_to = _default_dates()
    return render_template(
        "generate.html", companies=companies, customers=customers, groups=groups,
        invoice_templates=invoice_templates, receipt_templates=receipt_templates,
        last=last_params, def_date_from=date_from, def_date_to=date_to,
    )


@bp.route("/invoices")
def invoices():
    conn = g.conn
    batch_id = request.args.get("batch_id", type=int)
    q = (request.args.get("q") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    # ── ترقيم الصفحات: رقم الصفحة + عدد الصفوف في الصفحة ──
    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or 50
    if per_page not in (25, 50, 100, 200):
        per_page = 50

    where, args = [], []
    if batch_id:
        where.append("i.batch_id = ?")
        args.append(batch_id)
    if q:
        where.append("(i.invoice_number LIKE ? OR c.name LIKE ?)")
        args.extend([f"%{q}%", f"%{q}%"])
    if date_from:
        where.append("i.invoice_date >= ?")
        args.append(date_from)
    if date_to:
        where.append("i.invoice_date <= ?")
        args.append(date_to)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    # ── إجمالي النتائج المطابقة (للترقيم) ثم صفحة واحدة فقط ──
    total_count = conn.execute(
        f"""SELECT COUNT(*) c FROM invoices i
            JOIN customers c ON c.id = i.customer_id {clause}""", args
    ).fetchone()["c"]
    pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(page, pages)
    offset = (page - 1) * per_page

    rows = conn.execute(
        f"""SELECT i.*, c.name AS customer_name, co.name AS company_name,
                   (SELECT COUNT(*) FROM receipts r WHERE r.related_invoice_id = i.id) AS receipts_count
            FROM invoices i
            JOIN customers c ON c.id = i.customer_id
            JOIN companies co ON co.id = i.company_id
            {clause} ORDER BY i.invoice_date, i.invoice_time
            LIMIT {per_page} OFFSET {offset}""",
        args,
    ).fetchall()
    # ── قائمة الدفعات لفلتر «الدفعة» (كل الدفعات دون ترقيم) ──
    batches = conn.execute(
        "SELECT * FROM batches ORDER BY id DESC LIMIT 200").fetchall()
    # ── ترقيم صفحات قسم الدفعات (مستقل عن ترقيم صفحات الفواتير) ──
    b_page = max(1, request.args.get("b_page", type=int) or 1)
    b_per_page = request.args.get("b_per_page", type=int) or 10
    if b_per_page not in (10, 25, 50):
        b_per_page = 10
    b_total = conn.execute("SELECT COUNT(*) c FROM batches").fetchone()["c"]
    b_pages = max(1, (b_total + b_per_page - 1) // b_per_page)
    b_page = min(b_page, b_pages)
    # اسم البائع: كل دفعة تُولَّد لشركة واحدة — يُستخرج من فواتير الدفعة
    # اسم المشتري/العميل: أسماء العملاء المميزة في فواتير الدفعة (عمود واضح في الجدول)
    batch_rows = conn.execute(
        f"""SELECT b.*,
               (SELECT co.name FROM invoices i
                JOIN companies co ON co.id = i.company_id
                WHERE i.batch_id = b.id ORDER BY i.id LIMIT 1) AS company_name,
               (SELECT GROUP_CONCAT(name, '، ') FROM (
                   SELECT DISTINCT c.name AS name FROM invoices i
                   JOIN customers c ON c.id = i.customer_id
                   WHERE i.batch_id = b.id)) AS buyer_names
            FROM batches b
            ORDER BY b.id DESC
            LIMIT {b_per_page} OFFSET {(b_page - 1) * b_per_page}"""
    ).fetchall()
    total_gross = conn.execute(
        f"""SELECT COALESCE(SUM(i.total_amount),0) s FROM invoices i
            JOIN customers c ON c.id = i.customer_id {clause}""", args
    ).fetchone()["s"]
    invoice_templates = conn.execute(
        "SELECT id, name FROM templates WHERE type='invoice' ORDER BY name").fetchall()
    return render_template(
        "invoices.html", rows=rows, batches=batches, batch_rows=batch_rows,
        total_gross=total_gross, invoice_templates=invoice_templates,
        f_batch=batch_id or "", f_q=q, f_from=date_from, f_to=date_to,
        page=page, pages=pages, per_page=per_page, total_count=total_count,
        b_page=b_page, b_pages=b_pages, b_per_page=b_per_page, b_total=b_total,
    )


@bp.route("/receipts")
def receipts():
    conn = g.conn
    batch_id = request.args.get("batch_id", type=int)
    q = (request.args.get("q") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()

    where, args = [], []
    if batch_id:
        where.append("r.batch_id = ?")
        args.append(batch_id)
    if q:
        where.append("(r.receipt_number LIKE ? OR c.name LIKE ?)")
        args.extend([f"%{q}%", f"%{q}%"])
    if date_from:
        where.append("r.receipt_date >= ?")
        args.append(date_from)
    if date_to:
        where.append("r.receipt_date <= ?")
        args.append(date_to)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    rows = conn.execute(
        f"""SELECT r.*, c.name AS customer_name, co.name AS company_name
           FROM receipts r
           JOIN customers c ON c.id = r.customer_id
           JOIN companies co ON co.id = r.company_id
           {clause} ORDER BY r.receipt_date, r.receipt_time LIMIT 2000""",
        args,
    ).fetchall()
    batches = conn.execute("SELECT * FROM batches ORDER BY id DESC LIMIT 50").fetchall()
    total_amount = conn.execute(
        f"""SELECT COALESCE(SUM(r.amount),0) s FROM receipts r
            JOIN customers c ON c.id = r.customer_id {clause}""", args
    ).fetchone()["s"]
    return render_template(
        "receipts.html", rows=rows, batches=batches, total_amount=total_amount,
        f_batch=batch_id or "", f_q=q, f_from=date_from, f_to=date_to,
    )


@bp.route("/invoices/<int:inv_id>/preview")
def invoice_preview(inv_id: int):
    row = g.conn.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
    if not row:
        abort(404)
    return rnd.render_invoice(g.conn, row)


@bp.route("/receipts/<int:rc_id>/preview")
def receipt_preview(rc_id: int):
    row = g.conn.execute("SELECT * FROM receipts WHERE id=?", (rc_id,)).fetchone()
    if not row:
        abort(404)
    return rnd.render_receipt(g.conn, row)


@bp.route("/templates/<int:tpl_id>/preview")
def template_preview(tpl_id: int):
    row = g.conn.execute("SELECT * FROM templates WHERE id=?", (tpl_id,)).fetchone()
    if not row:
        abort(404)
    return rnd.render_sample(row["html_content"], row["type"])


# ══════════════════════════════════════════════════════════════════════════
#  فحص وتحقق الباركود
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/verify", methods=["GET", "POST"])
def verify_page():
    conn = g.conn
    pasted = None
    if request.method == "POST":
        b64 = (request.form.get("b64") or "").strip()
        if b64:
            pasted = qr_svc.verify_payload_generic(b64)
    return render_template("verify.html", rows=_recent_qr_invoices(conn),
                           pasted=pasted, result=None, inv_row=None,
                           big_qr=None, no_qr=False)


@bp.route("/verify/<int:inv_id>")
def verify_invoice_page(inv_id: int):
    conn = g.conn
    row = conn.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
    if not row:
        abort(404)
    if not (row["qr_payload_b64"] or "").strip():
        return render_template("verify.html", rows=_recent_qr_invoices(conn),
                               pasted=None, result=None, inv_row=row,
                               big_qr=None, no_qr=True)
    result = qr_svc.verify_invoice_qr(conn, row)
    big_qr = qr_svc.qr_image_data_uri(row["qr_payload_b64"], box_size=8)
    return render_template("verify.html", rows=_recent_qr_invoices(conn),
                           pasted=None, result=result, inv_row=row,
                           big_qr=big_qr, no_qr=False)


@bp.route("/verify/<int:inv_id>/xml")
def verify_invoice_xml(inv_id: int):
    row = g.conn.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
    if not row:
        abort(404)
    xml = qr_svc.build_invoice_xml_for_row(g.conn, row)
    return Response(
        xml, mimetype="application/xml",
        headers={"Content-Disposition": f"attachment; filename=invoice_{row['invoice_number']}.xml"},
    )


@bp.route("/verify/<int:inv_id>/demo")
def verify_demo_html(inv_id: int):
    row = g.conn.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
    if not row:
        abort(404)
    return Response(qr_svc.build_demo_html(g.conn, row), mimetype="text/html")


def _recent_qr_invoices(conn):
    return conn.execute(
        """SELECT i.id, i.invoice_number, i.invoice_date, i.qr_mode, i.total_amount,
                  c.name AS customer_name
           FROM invoices i JOIN customers c ON c.id = i.customer_id
           WHERE i.qr_payload_b64 != '' ORDER BY i.id DESC LIMIT 100"""
    ).fetchall()


# ══════════════════════════════════════════════════════════════════════════
#  الملفات (شعارات / تصديرات)
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/uploads/<path:name>")
def uploads(name: str):
    return send_from_directory(dbm.UPLOAD_DIR, name)


@bp.route("/exports/<path:name>")
def exports(name: str):
    return send_from_directory(dbm.EXPORT_DIR, name, as_attachment=True)


# ══════════════════════════════════════════════════════════════════════════
#  التقارير (Reports Module) — وحدة مستقلة: تقرير فواتير تفصيلي قابل للتصفية
#  (الشركة، البائع، العميل، طريقة الدفع، نطاق التاريخ، رقم الفاتورة) مع طباعة
#  مخصصة A4/PDF واختيار الأعمدة المطلوب طباعتها.
# ══════════════════════════════════════════════════════════════════════════

_REPORT_PER_PAGE = (25, 50, 100, 200, 500)
_REPORT_MAX_PRINT_ROWS = 5000   # سقف أمان لطباعة «كل النتائج المطابقة»


def _report_filters() -> tuple[str, list]:
    """بناء شرط التصفية لتقارير الفواتير من معاملات الرابط.

    الفلاتر المدعومة: الشركة (البائع)، اسم البائع (بحث نصي)، اسم العميل،
    طريقة الدفع، نطاق التاريخ (من/إلى)، ورقم الفاتورة.
    """
    company_id = request.args.get("company_id", type=int)
    seller = (request.args.get("seller") or "").strip()
    customer = (request.args.get("customer") or "").strip()
    payment = (request.args.get("payment") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    inv_number = (request.args.get("invoice_number") or "").strip()

    where, args = [], []
    if company_id:
        where.append("i.company_id = ?")
        args.append(company_id)
    if seller:
        where.append("co.name LIKE ?")
        args.append(f"%{seller}%")
    if customer:
        where.append("c.name LIKE ?")
        args.append(f"%{customer}%")
    if payment:
        where.append("i.payment_type = ?")
        args.append(payment)
    if date_from:
        where.append("i.invoice_date >= ?")
        args.append(date_from)
    if date_to:
        where.append("i.invoice_date <= ?")
        args.append(date_to)
    if inv_number:
        where.append("i.invoice_number LIKE ?")
        args.append(f"%{inv_number}%")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return clause, args


def _report_totals(conn, clause: str, args: list):
    """إجماليات كل النتائج المطابقة (العدد، الصافي، الخصومات، الضريبة، الشامل)."""
    return conn.execute(
        f"""SELECT COUNT(*) cnt,
                   COALESCE(SUM(i.subtotal), 0) net,
                   COALESCE(SUM(i.discount_amount), 0) disc,
                   COALESCE(SUM(i.tax_amount), 0) tax,
                   COALESCE(SUM(i.total_amount), 0) gross
            FROM invoices i
            JOIN customers c ON c.id = i.customer_id
            JOIN companies co ON co.id = i.company_id {clause}""",
        args,
    ).fetchone()


def _report_rows(conn, clause: str, args: list, limit: str) -> list[dict]:
    """صفوف التقرير: بيانات الفاتورة الأساسية + اسم البائع (الشركة) واسم العميل.

    limit نص جاهز مثل '50 OFFSET 0' أو '5000' (قيم مُتحقَّق منها برمجيًا فقط).
    """
    return [dict(r) for r in conn.execute(
        f"""SELECT i.id, i.invoice_number, i.invoice_date, i.invoice_time,
                   i.payment_type, i.subtotal, i.discount_amount, i.tax_amount,
                   i.total_amount, i.is_manual, i.approval_status,
                   co.name AS company_name, c.name AS customer_name
            FROM invoices i
            JOIN customers c ON c.id = i.customer_id
            JOIN companies co ON co.id = i.company_id
            {clause}
            ORDER BY i.invoice_date, i.invoice_time, i.id
            LIMIT {limit}""",
        args,
    ).fetchall()]


def _report_filter_desc() -> list[tuple[str, str]]:
    """وصف الفلاتر المطبقة حاليًا (للترويسة المعروضة والمطبوعة)."""
    company_id = request.args.get("company_id", type=int)
    seller = (request.args.get("seller") or "").strip()
    customer = (request.args.get("customer") or "").strip()
    payment = (request.args.get("payment") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    inv_number = (request.args.get("invoice_number") or "").strip()

    desc: list[tuple[str, str]] = []
    if company_id:
        row = g.conn.execute("SELECT name FROM companies WHERE id=?",
                             (company_id,)).fetchone()
        desc.append(("الشركة (البائع)", row["name"] if row else str(company_id)))
    if seller:
        desc.append(("اسم البائع", seller))
    if customer:
        desc.append(("اسم العميل", customer))
    if payment:
        desc.append(("طريقة الدفع", payment))
    if date_from:
        desc.append(("من تاريخ", date_from))
    if date_to:
        desc.append(("إلى تاريخ", date_to))
    if inv_number:
        desc.append(("رقم الفاتورة", inv_number))
    return desc


@bp.route("/reports")
def reports():
    """قسم التقارير — تقرير تفصيلي قابل للتصفية والطباعة المخصصة (A4/PDF)."""
    conn = g.conn
    clause, args = _report_filters()
    totals = _report_totals(conn, clause, args)
    total_count = totals["cnt"]

    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or 50
    if per_page not in _REPORT_PER_PAGE:
        per_page = 50
    pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(page, pages)

    rows = _report_rows(conn, clause, args,
                        f"{per_page} OFFSET {(page - 1) * per_page}")
    companies = conn.execute(
        "SELECT id, name FROM companies ORDER BY name").fetchall()
    payments = [r["payment_type"] for r in conn.execute(
        "SELECT DISTINCT payment_type FROM invoices "
        "WHERE payment_type != '' ORDER BY payment_type").fetchall()]
    return render_template(
        "reports.html", rows=rows, totals=totals, total_count=total_count,
        page=page, pages=pages, per_page=per_page,
        companies=companies, payments=payments,
        filter_desc=_report_filter_desc(),
        f_company=request.args.get("company_id", type=int) or "",
        f_seller=(request.args.get("seller") or "").strip(),
        f_customer=(request.args.get("customer") or "").strip(),
        f_payment=(request.args.get("payment") or "").strip(),
        f_from=(request.args.get("date_from") or "").strip(),
        f_to=(request.args.get("date_to") or "").strip(),
        f_number=(request.args.get("invoice_number") or "").strip(),
    )


@bp.route("/reports/data")
def reports_data():
    """بيانات التقرير بصيغة JSON — تُستخدم لطباعة «كل النتائج المطابقة» دون
    الترقيم (بسقف أمان 5000 صف)."""
    clause, args = _report_filters()
    totals = _report_totals(g.conn, clause, args)
    rows = _report_rows(g.conn, clause, args, str(_REPORT_MAX_PRINT_ROWS))
    return {
        "ok": True,
        "count": totals["cnt"],
        "truncated": totals["cnt"] > len(rows),
        "totals": {"net": totals["net"], "disc": totals["disc"],
                   "tax": totals["tax"], "gross": totals["gross"]},
        "rows": rows,
    }

