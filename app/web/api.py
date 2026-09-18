# -*- coding: utf-8 -*-
"""واجهة API (JSON) — إدارة البيانات، التوليد، المعاينة، التصدير."""
from __future__ import annotations

import sqlite3
import time
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from flask import Blueprint, g, jsonify, request, send_from_directory

from app import db as dbm
from app.generator.engine import GenParams, generate as engine_generate
from app.export import render as rnd
from app.export import pdf as pdfx
from app import qr_service as qr_svc
from app.money import from_halalas, line_tax, parse_decimal, to_halalas

bp = Blueprint("api", __name__)


def ok(**kw):
    return jsonify({"ok": True, **kw})


def err(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def body() -> dict:
    """قراءة جسم الطلب: JSON أولاً (كما يرسله api())، مع دعم FormData/form-encoded
    (كما يرسله submitModal عبر FormData) — هذا يمنع خطأ «اسم الصنف مطلوب» المنبعث
    من أن النماذج تُرسل كـ multipart بدلاً من JSON."""
    d = request.get_json(silent=True)
    if d:
        return d
    if request.form:
        return request.form.to_dict()
    return {}


def _clean(value, max_len: int = 300) -> str:
    return (str(value or "")).strip()[:max_len]


# ══════════════════════════════════════════════════════════════════════════
#  الشركات (مع رفع الشعار)
# ══════════════════════════════════════════════════════════════════════════

@bp.post("/companies")
def save_company():
    conn = g.conn
    f = request.form
    cid = f.get("id", type=int)
    logo_path = _clean(f.get("logo_path"))
    file = request.files.get("logo")
    if file and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("png", "jpg", "jpeg", "gif", "webp", "svg"):
            return err("صيغة الشعار غير مدعومة (png/jpg/gif/webp/svg)")
        logo_path = f"logo_{int(time.time())}.{ext}"
        file.save(dbm.UPLOAD_DIR / logo_path)
    if cid:
        cur_row = conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
        if not cur_row:
            return err("الشركة غير موجودة", 404)
        # ── حفظ جزئي آمن: أي حقل غائب عن الطلب يُؤخذ من القيمة الحالية بدل مسحه ──
        # (يحمي طلبات تغيير اللون من الإعدادات التي تُرسل id+name+color فقط)
        def _p(k, cur, mx=400):
            return _clean(f.get(k), mx) if k in f else (cur or "")
        name = _p("name", cur_row["name"], 200) or cur_row["name"]
        if "name" in f and not _clean(f.get("name"), 200):
            return err("اسم الشركة مطلوب")
        color = _clean(f.get("color"), 20) if (f.get("color") or "").strip() else (cur_row["color"] or "#0e7490")
        values = (name, _p("address", cur_row["address"], 400),
                  _p("tax_number", cur_row["tax_number"], 30),
                  _p("cr_number", cur_row["cr_number"], 30),
                  logo_path, color)
        if logo_path == "" and f.get("keep_logo") == "1":
            cur = conn.execute("SELECT logo_path FROM companies WHERE id=?", (cid,)).fetchone()
            values = (values[0], values[1], values[2], values[3], cur["logo_path"] if cur else "", values[5])
        conn.execute(
            "UPDATE companies SET name=?, address=?, tax_number=?, cr_number=?, logo_path=?, color=? WHERE id=?",
            values + (cid,))
        conn.commit()
        # ── مزامنة تلقائية (Real-time Cascade): الفواتير والسندات تقرأ بيانات
        # الشركة لحظيًا عبر JOIN، واللقطة الوحيدة المخزنة هي حمولة QR —
        # نعيد توليدها لكل فواتير هذه الشركة لتعكس الاسم/الرقم الضريبي الجديد ──
        inv_count = conn.execute(
            "SELECT COUNT(*) c FROM invoices WHERE company_id=?", (cid,)).fetchone()["c"]
        rc_count = conn.execute(
            "SELECT COUNT(*) c FROM receipts WHERE company_id=?", (cid,)).fetchone()["c"]
        qr_refreshed = 0
        try:
            qr_refreshed = qr_svc.regenerate_stored_qr(conn, company_id=cid)
        except Exception:
            pass
        return ok(id=cid, cascade={"invoices": inv_count,
                                   "receipts": rc_count,
                                   "qr_refreshed": qr_refreshed})
    name = _clean(f.get("name"), 200)
    if not name:
        return err("اسم الشركة مطلوب")
    values = (name, _clean(f.get("address"), 400), _clean(f.get("tax_number"), 30),
              _clean(f.get("cr_number"), 30), logo_path, _clean(f.get("color"), 20) or "#0e7490")
    cur = conn.execute(
        "INSERT INTO companies (name, address, tax_number, cr_number, logo_path, color) VALUES (?,?,?,?,?,?)",
        values)
    conn.commit()
    return ok(id=cur.lastrowid)


@bp.post("/customers")
def save_customer():
    conn = g.conn
    d = body()
    cid = d.get("id")
    if cid:
        cur_row = conn.execute("SELECT * FROM customers WHERE id=?", (int(cid),)).fetchone()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(customers)").fetchall()]
        has_cr = "cr_number" in cols
        def _c(k, cur, mx=400):
            return _clean(d.get(k), mx) if k in d else (cur or "")
        if cur_row:
            name = _c("name", cur_row["name"], 200) or cur_row["name"]
            vals = [name, _c("address", cur_row["address"], 400),
                    _c("tax_number", cur_row["tax_number"], 30),
                    _c("phone", cur_row["phone"], 20)]
            if has_cr:
                cr = _c("cr_number", cur_row["cr_number"], 30)
                conn.execute(
                    "UPDATE customers SET name=?, address=?, tax_number=?, cr_number=?, phone=? WHERE id=?",
                    (vals[0], vals[1], vals[2], cr, vals[3], int(cid)))
            else:
                conn.execute(
                    "UPDATE customers SET name=?, address=?, tax_number=?, phone=? WHERE id=?",
                    (vals[0], vals[1], vals[2], vals[3], int(cid)))
        else:
            name = _clean(d.get("name"), 200)
            if not name:
                return err("اسم العميل مطلوب")
            if has_cr:
                conn.execute(
                    "UPDATE customers SET name=?, address=?, tax_number=?, cr_number=?, phone=? WHERE id=?",
                    (name, _clean(d.get("address"), 400), _clean(d.get("tax_number"), 30),
                     _clean(d.get("cr_number"), 30), _clean(d.get("phone"), 20), int(cid)))
            else:
                conn.execute(
                    "UPDATE customers SET name=?, address=?, tax_number=?, phone=? WHERE id=?",
                    (name, _clean(d.get("address"), 400), _clean(d.get("tax_number"), 30),
                     _clean(d.get("phone"), 20), int(cid)))
        conn.commit()
        # ── مزامنة تلقائية: الفواتير والسندات تعرض بيانات العميل لحظيًا عبر
        # JOIN (لا توجد لقطة مخزنة لبيانات العميل)، فنعيد فقط عدّاد الجهات
        # المرتبطة لتأكيد التحديث الشامل للواجهة ──
        inv_count = conn.execute(
            "SELECT COUNT(*) c FROM invoices WHERE customer_id=?", (int(cid),)).fetchone()["c"]
        rc_count = conn.execute(
            "SELECT COUNT(*) c FROM receipts WHERE customer_id=?", (int(cid),)).fetchone()["c"]
        return ok(id=int(cid), cascade={"invoices": inv_count, "receipts": rc_count})
    name = _clean(d.get("name"), 200)
    if not name:
        return err("اسم العميل مطلوب")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(customers)").fetchall()]
    if "cr_number" in cols:
        cur = conn.execute(
            "INSERT INTO customers (name, address, tax_number, cr_number, phone) VALUES (?,?,?,?,?)",
            (name, _clean(d.get("address"), 400), _clean(d.get("tax_number"), 30),
             _clean(d.get("cr_number"), 30), _clean(d.get("phone"), 20)))
    else:
        cur = conn.execute(
            "INSERT INTO customers (name, address, tax_number, phone) VALUES (?,?,?,?)",
            (name, _clean(d.get("address"), 400), _clean(d.get("tax_number"), 30),
             _clean(d.get("phone"), 20)))
    conn.commit()
    return ok(id=cur.lastrowid)


@bp.post("/groups")
def save_group():
    conn = g.conn
    d = body()
    name = _clean(d.get("name"), 200)
    if not name:
        return err("اسم المجموعة مطلوب")
    desc = _clean(d.get("description"), 400)
    gid = d.get("id")
    if gid:
        conn.execute("UPDATE item_groups SET name=?, description=? WHERE id=?", (name, desc, int(gid)))
        conn.commit()
        return ok(id=int(gid))
    cur = conn.execute("INSERT INTO item_groups (name, description) VALUES (?,?)", (name, desc))
    conn.commit()
    return ok(id=cur.lastrowid)

@bp.post("/items")
def save_item():
    conn = g.conn
    d = body()
    name = _clean(d.get("name"), 200)
    if not name:
        return err("اسم الصنف مطلوب")
    try:
        price = round(float(d.get("unit_price") or 0), 2)
    except (TypeError, ValueError):
        return err("سعر الوحدة غير صالح")
    if price <= 0:
        return err("سعر الوحدة يجب أن يكون أكبر من صفر")
    try:
        tax_rate = float(d.get("tax_rate") if d.get("tax_rate") not in (None, "") else 0.15)
    except (TypeError, ValueError):
        return err("نسبة الضريبة غير صالحة")
    group_id = d.get("group_id")
    values = (int(group_id) if group_id else None, name, _clean(d.get("code"), 40),
              _clean(d.get("unit"), 40) or "حبة", price, tax_rate)
    iid = d.get("id")
    if iid:
        conn.execute(
            "UPDATE items SET group_id=?, name=?, code=?, unit=?, unit_price=?, tax_rate=? WHERE id=?",
            values + (int(iid),))
        conn.commit()
        return ok(id=int(iid))
    cur = conn.execute(
        "INSERT INTO items (group_id, name, code, unit, unit_price, tax_rate) VALUES (?,?,?,?,?,?)",
        values)
    conn.commit()
    return ok(id=cur.lastrowid)

@bp.post("/items/import")
def import_items():
    """استيراد أصناف دفعة واحدة من ملف Excel (.xlsx) أو CSV.
    الأعمدة المقبولة: name (إجباري)، code, unit, unit_price (إجباري >0)،
    tax_rate، group (اسم المجموعة أو group_id). يدعم أعمدة عربية وإنجليزية."""
    import csv as _csv
    import io as _io
    conn = g.conn
    file = request.files.get("file")
    if not file or not file.filename:
        return err("لم يتم رفع أي ملف")
    fn = file.filename.lower()
    try:
        if fn.endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(file.stream, read_only=True, data_only=True)
            rows = list(wb.active.iter_rows(values_only=True))
        elif fn.endswith(".csv"):
            text = file.stream.read().decode("utf-8-sig", "replace")
            sample = text[:4096]
            try:
                dialect = _csv.Sniffer().sniff(sample, delimiters=";,,\t|")
            except _csv.Error:
                dialect = _csv.excel
            rows = list(_csv.reader(_io.StringIO(text), dialect))
        else:
            return err("صيغة غير مدعومة — استخدم .xlsx أو .csv")
    except Exception as exc:  # pragma: no cover
        return err(f"تعذر قراءة الملف: {exc}")
    if not rows or len(rows) < 2:
        return err("الملف لا يحتوي على بيانات — الصف الأول يجب أن يكون رؤوس الأعمدة")
    header = [str(h).strip().lower() for h in rows[0]]
    groups = {r["name"].lower(): r["id"] for r in conn.execute("SELECT id,name FROM item_groups")}
    groups_id = {str(r["id"]): r["id"] for r in conn.execute("SELECT id,name FROM item_groups")}

    def col(*names):
        for n in names:
            if n in header:
                return header.index(n)
        return None

    i_name = col("name", "اسم الصنف", "الصنف")
    i_code = col("code", "الكود")
    i_unit = col("unit", "الوحدة")
    i_price = col("unit_price", "price", "سعر الوحدة", "السعر")
    i_tax = col("tax_rate", "tax", "نسبة الضريبة")
    i_group = col("group", "المجموعة", "group_name", "group_id")
    if i_name is None:
        return err("العمود 'name' إجباري — سمّه 'اسم الصنف' أو 'name'")
    if i_price is None:
        return err("العمود 'unit_price' إجباري — سمّيه 'سعر الوحدة' أو 'unit_price'")

    count, skipped, errors = 0, 0, []
    tx_started = False
    try:
        conn.execute("BEGIN")
        tx_started = True
        for r in rows[1:]:
            cells = list(r) + [None] * (len(header) - len(r))
            if all((c is None or str(c).strip() == "") for c in cells):
                continue  # صف فارغ
            name = _clean(cells[i_name], 200)
            if not name:
                errors.append(f"صف مُتخطّى: اسم الصنف فارغ (الصف {count + skipped + 1})")
                skipped += 1
                continue
            try:
                price = round(float(cells[i_price] or 0), 2)
            except (TypeError, ValueError):
                errors.append(f"صف مُتخطّى: سعر غير صالح للصنف '{name}'")
                skipped += 1
                continue
            if price <= 0:
                errors.append(f"صف مُتخطّى: سعر غير موجب للصنف '{name}'")
                skipped += 1
                continue
            code = _clean(cells[i_code], 40) if i_code is not None else ""
            unit = (_clean(cells[i_unit], 40) if i_unit is not None else "") or "حبة"
            tax_rate = 0.15
            try:
                tr = float(cells[i_tax]) if i_tax is not None and cells[i_tax] not in (None, "") else 0.15
                # قبول 15 أو 0.15
                if tr > 1:
                    tr = tr / 100.0
                tax_rate = tr if 0 <= tr <= 1 else 0.15
            except (TypeError, ValueError):
                pass
            gid = None
            if i_group is not None:
                gv = cells[i_group]
                if gv is not None:
                    gvs = str(gv).strip()
                    if gvs in groups_id:
                        gid = groups_id[gvs]
                    elif gvs:
                        key = gvs.lower()
                        if key in groups:
                            gid = groups[key]
                        else:
                            # إنشاء المجموعة تلقائياً إن لم تكن موجودة
                            cur = conn.execute(
                                "INSERT INTO item_groups (name, description) VALUES (?,?)", (gvs, ""))
                            gid = cur.lastrowid
                            groups[key] = gid
                            groups_id[str(gid)] = gid
            conn.execute(
                "INSERT INTO items (group_id, name, code, unit, unit_price, tax_rate) VALUES (?,?,?,?,?,?)",
                (gid, name, code, unit, price, tax_rate))
            count += 1
        conn.commit()
    except Exception as exc:  # pragma: no cover
        if tx_started:
            conn.rollback()
        return err(f"فشل الاستيراد: {exc}")
    if errors:
        return ok(count=count, skipped=skipped, errors=errors)
    return ok(count=count, skipped=skipped)


@bp.get("/items/catalog")
def items_catalog():
    """المجموعات وأصنافها من قاعدة البيانات — للاختيار المتسلسل في تحرير الفاتورة:
    يُختار «المجموعة الرئيسية» أولًا ثم تظهر «الأصناف التابعة لهذه المجموعة فقط»."""
    conn = g.conn

    def _row(i):
        return {"id": i["id"], "name": i["name"], "code": i["code"] or "",
                "unit": i["unit"] or "", "unit_price": float(i["unit_price"] or 0)}

    groups_out = []
    for gr in conn.execute("SELECT id, name FROM item_groups ORDER BY name").fetchall():
        its = conn.execute(
            """SELECT id, name, code, unit, unit_price FROM items
               WHERE group_id=? ORDER BY name""", (gr["id"],)).fetchall()
        groups_out.append({"id": gr["id"], "name": gr["name"],
                           "items": [_row(i) for i in its]})
    # أصناف غير مرتبطة بأي مجموعة (group_id فارغ) — تُعرض ضمن مجموعة خاصة لتبقى قابلة للاختيار
    orphans = conn.execute(
        """SELECT id, name, code, unit, unit_price FROM items
           WHERE group_id IS NULL ORDER BY name""").fetchall()
    if orphans:
        groups_out.append({"id": 0, "name": "أصناف بلا مجموعة",
                           "items": [_row(i) for i in orphans]})
    return ok(groups=groups_out)


@bp.get("/items/export")
def export_items():
    """تصدير الأصناف إلى Excel (xlsx) أو CSV بناءً على امتداد ?format=."""
    import io as _io
    conn = g.conn
    fmt = (request.args.get("format") or "xlsx").lower()
    rows = conn.execute(
        "SELECT i.id, g.name AS group_name, i.name, i.code, i.unit, "
        "i.unit_price, i.tax_rate FROM items i "
        "LEFT JOIN item_groups g ON g.id = i.group_id "
        "ORDER BY g.name, i.name"
    ).fetchall()
    filename = f"items_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{fmt}"
    if fmt == "csv":
        buf = _io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["id", "group", "name", "code", "unit", "unit_price", "tax_rate"])
        for r in rows:
            w.writerow([r["id"], r["group_name"] or "", r["name"], r["code"],
                        r["unit"], f"{r['unit_price']:.2f}", r["tax_rate"]])
        return send_from_directory(
            dbm.EXPORT_DIR, filename=filename.replace(".csv", ".txt"),
            as_attachment=True,
        ) if False else (buf.getvalue(), 200, {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": f'attachment; filename="{filename}"',
        })
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return err("مكتبة openpyxl غير مثبتة — ثبّتها بـ: pip install openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "الأصناف"
    headers = ["id", "المجموعة", "اسم الصنف", "الكود", "الوحدة", "سعر الوحدة", "نسبة الضريبة"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0E7490")
        cell.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append([r["id"], r["group_name"] or "", r["name"], r["code"],
                   r["unit"], float(r["unit_price"]), float(r["tax_rate"])])
    widths = [6, 18, 50, 14, 10, 14, 12]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    out = _io.BytesIO()
    wb.save(out)
    out.seek(0)
    from flask import Response
    return Response(
        out.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.get("/theme")
def get_theme_api():
    return ok(**dbm.get_theme(g.conn))


@bp.post("/theme")
def save_theme_api():
    d = body()
    cur = dbm.save_theme(g.conn, d)
    return ok(**cur)


# ══════════════════════════════════════════════════════════════════════════
#  قالب التصميم عبر Excel — تصدير للتعديل + استيراد ليُطبق على كل المستندات
# ══════════════════════════════════════════════════════════════════════════

_THEME_XLSX_FIELDS = (
    # (المفتاح، الوصف بالعربية)
    ("primary_color", "اللون الرئيسي (سداسي مثل #0e7490)"),
    ("title_color", "لون العنوان (اتركه فارغًا ليرث اللون الرئيسي)"),
    ("seller_name_color", "لون اسم شركة البائع"),
    ("header_text_color", "لون نص الترويسة وأعمدة الجدول"),
    ("font_family", "الخط: Cairo / Tajawal / Amiri / Noto Kufi Arabic / Almarai"),
    ("font_size", "حجم خط المستندات (12 - 16)"),
    ("alert_banner_enabled", "إظهار شريط التنبيه أعلى المستند (نعم / لا)"),
    ("alert_banner_text", "نص شريط التنبيه التحذيري"),
    ("alert_banner_color", "لون نص شريط التنبيه"),
    ("alert_banner_bg", "خلفية شريط التنبيه"),
    ("watermark_text", "نص الختم المائي"),
    ("footer_notice", "نص التذييل التحذيري"),
    ("show_watermark", "إظهار الختم المائي (نعم / لا)"),
)

_THEME_BOOL_KEYS = {"alert_banner_enabled", "show_watermark"}


@bp.get("/theme/export")
def theme_export_xlsx():
    """تصدير إعدادات قالب التصميم إلى ملف Excel قابل للتعديل."""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    conn = g.conn
    theme = dbm.get_theme(conn)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "قالب التصميم"
    ws.sheet_view.rightToLeft = True
    ws.append(("المفتاح", "الوصف", "القيمة"))
    head_fill = PatternFill("solid", fgColor="0E7490")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="right")
    for key, desc in _THEME_XLSX_FIELDS:
        ws.append((key, desc, theme.get(key, "")))
    # عرض الأعمدة وتلوين عمود القيمة
    val_fill = PatternFill("solid", fgColor="FEF9C3")
    for r in range(2, ws.max_row + 1):
        ws.cell(r, 3).fill = val_fill
        ws.cell(r, 3).alignment = Alignment(horizontal="right")
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 58
    ws.column_dimensions["C"].width = 34
    note = ws.cell(ws.max_row + 2, 1,
                   "عدّل عمود «القيمة» فقط ثم استورد الملف ليُطبق على كل الفواتير والسندات")
    note.font = Font(italic=True, color="B91C1C")
    dbm.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = dbm.EXPORT_DIR / f"قالب_التصميم_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(out)
    return ok(file=out.name)


@bp.post("/theme/import")
def theme_import_xlsx():
    """استيراد ملف Excel المعدل وتطبيقه كقالب تصميم على كل المستندات."""
    import openpyxl
    conn = g.conn
    file = request.files.get("file")
    if not file or not file.filename:
        return err("اختر ملف Excel (.xlsx)")
    if not file.filename.lower().endswith(".xlsx"):
        return err("يجب أن يكون الملف بصيغة Excel (.xlsx)")
    dbm.TMP_DIR.mkdir(parents=True, exist_ok=True)
    path = dbm.TMP_DIR / f"theme_import_{int(time.time())}.xlsx"
    file.save(path)
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except Exception as exc:
        path.unlink(missing_ok=True)
        return err(f"تعذر قراءة ملف Excel: {exc}")
    ws = wb.active
    # عمود القيمة: الثالث إن كان السطر الأول ترويسة (المفتاح/الوصف/القيمة) وإلا الثاني
    value_col = 3 if (str(ws.cell(1, 1).value or "").strip() == "المفتاح") else 2
    known = {k for k, _ in _THEME_XLSX_FIELDS}
    data = {}
    for r in range(1, ws.max_row + 1):
        key = str(ws.cell(r, 1).value or "").strip()
        if key not in known:
            continue
        raw = ws.cell(r, value_col).value
        if key in _THEME_BOOL_KEYS:
            if isinstance(raw, str):
                data[key] = raw.strip().lower() in ("نعم", "true", "1", "yes", "مفعل", "مفعّل")
            else:
                data[key] = bool(raw)
        elif raw is not None:
            val = str(raw).strip()
            if val:
                data[key] = val
    path.unlink(missing_ok=True)
    if not data:
        return err("لم يتم العثور على مفاتيح معروفة في الملف — عدّل عمود «القيمة» فقط")
    saved = dbm.save_theme(conn, data)
    return ok(updated=len(data), keys=sorted(data),
              font=saved.get("font_family"), size=saved.get("font_size"))


# ══════════════════════════════════════════════════════════════════════════
#  الأمان — كلمة سر التحكم في الصلاحيات
# ══════════════════════════════════════════════════════════════════════════

def _require_password(d: dict, scope: str) -> str | None:
    """يتحقق من كلمة السر للإجراءات المحمية — يُرجع رسالة خطأ أو None."""
    sec = dbm.get_security(g.conn)
    if not sec.get(scope):
        return None
    if not sec.get("password_set"):
        return None
    pw = (d.get("password") or d.get("current_password") or "").strip()
    if not pw:
        return "هذا الإجراء محمي — أدخل كلمة سر التحكم"
    if not dbm.verify_password(g.conn, pw):
        return "كلمة سر التحكم غير صحيحة"
    return None


@bp.get("/security")
def security_get():
    return ok(**dbm.get_security(g.conn))


@bp.post("/security")
def security_save():
    d = body()
    try:
        sec = dbm.save_security(g.conn, d)
    except ValueError as exc:
        return err(str(exc))
    return ok(**sec)


@bp.post("/security/verify")
def security_verify():
    d = body()
    sec = dbm.get_security(g.conn)
    if not sec.get("password_set"):
        return ok()
    if dbm.verify_password(g.conn, (d.get("password") or "").strip()):
        return ok()
    return err("كلمة سر التحكم غير صحيحة", 403)


# ══════════════════════════════════════════════════════════════════════════
#  مظهر واجهة البرنامج
# ══════════════════════════════════════════════════════════════════════════

@bp.get("/ui")
def ui_get():
    return ok(**dbm.get_ui(g.conn))


@bp.post("/ui")
def ui_save():
    d = body()
    cur = dbm.save_ui(g.conn, d)
    return ok(**cur)


# ══════════════════════════════════════════════════════════════════════════
#  النسخ الاحتياطية
# ══════════════════════════════════════════════════════════════════════════

@bp.get("/backup/list")
def backup_list():
    from app import backup as bk
    return ok(backups=bk.list_backups(),
              auto=bool(dbm.get_setting(g.conn, "backup_auto", False)))


@bp.post("/backup/create")
def backup_create():
    from app import backup as bk
    d = body()
    try:
        p = bk.create_backup(conn=g.conn, tag="يدوي")
    except (OSError, sqlite3.Error, ValueError) as exc:
        return err(f"تعذر إنشاء النسخة: {exc}", 500)
    return ok(file=p.name, size=p.stat().st_size)


@bp.post("/backup/auto")
def backup_auto_toggle():
    d = body()
    enabled = bool(d.get("enabled") in (True, "true", "1", 1, "on"))
    dbm.set_setting(g.conn, "backup_auto", enabled)
    if not enabled:
        dbm.set_setting(g.conn, "last_auto_backup", "")
    return ok(enabled=enabled)


@bp.post("/backup/restore")
def backup_restore():
    from app import backup as bk
    d = body()
    if e := _require_password(d, "protect_restore"):
        return err(e, 403)
    file = request.files.get("file")
    try:
        if file and file.filename:
            if not file.filename.lower().endswith(".zip"):
                return err("يجب أن يكون ملف الاستعادة بصيغة ZIP")
            dbm.TMP_DIR.mkdir(parents=True, exist_ok=True)
            path = dbm.TMP_DIR / f"restore_{int(time.time())}.zip"
            file.save(path)
        else:
            name = _clean(d.get("name"), 200)
            if not name:
                return err("اختر نسخة احتياطية أو ارفع ملف ZIP")
            path = bk.BACKUP_DIR / Path(name).name
            if not path.exists():
                return err("النسخة الاحتياطية غير موجودة")
        # أغلق اتصال الطلب قبل استبدال ملف القاعدة (قفل الملفات في Windows)
        try:
            g.conn.close()
        except Exception:
            pass
        g.pop("conn", None)
        result = bk.restore_backup(path)
        # إعادة التهيئة ثم اتصال جديد لبقية الطلب
        c = dbm.init_db()
        c.close()
        g.conn = dbm.connect()
        try:
            path.unlink()
        except OSError:
            pass
    except ValueError as exc:
        return err(str(exc))
    except (OSError, sqlite3.Error) as exc:  # pragma: no cover
        return err(f"فشل الاستعادة: {exc}", 500)
    return ok(**result)


@bp.post("/backup/delete")
def backup_delete():
    from app import backup as bk
    d = body()
    if e := _require_password(d, "protect_restore"):
        return err(e, 403)
    name = _clean(d.get("name"), 200)
    try:
        bk.delete_backup(name)
    except ValueError as exc:
        return err(str(exc))
    except OSError:  # pragma: no cover
        return err("تعذر حذف الملف", 500)
    return ok(deleted=name)



@bp.post("/templates")
def save_template():
    conn = g.conn
    d = body()
    name = _clean(d.get("name"), 200)
    ttype = _clean(d.get("type"), 10)
    content = d.get("html_content") or ""
    if not name:
        return err("اسم القالب مطلوب")
    if ttype not in ("invoice", "receipt"):
        return err("نوع القالب يجب أن يكون invoice أو receipt")
    if len(content.strip()) < 20:
        return err("محتوى القالب قصير جدًا")
    tid = d.get("id")
    if tid:
        conn.execute("UPDATE templates SET name=?, type=?, html_content=? WHERE id=?",
                     (name, ttype, content, int(tid)))
        conn.commit()
        return ok(id=int(tid))
    cur = conn.execute("INSERT INTO templates (name, type, html_content) VALUES (?,?,?)",
                       (name, ttype, content))
    conn.commit()
    return ok(id=cur.lastrowid)


@bp.get("/templates/<int:tid>/get")
def get_template(tid: int):
    row = g.conn.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()
    if not row:
        return err("القالب غير موجود")
    return ok(row={
        "id": row["id"], "name": row["name"], "type": row["type"],
        "html_content": row["html_content"],
    })


@bp.post("/templates/<int:tid>/reset")
def reset_template(tid: int):
    conn = g.conn
    row = conn.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()
    if not row:
        return err("القالب غير موجود")
    content = dbm._default_template(row["type"])
    conn.execute("UPDATE templates SET html_content=? WHERE id=?", (content, tid))
    conn.commit()
    return ok(id=tid)


@bp.post("/templates/<int:tid>/style")
def save_template_style(tid: int):
    """حفظ إعدادات المحرر المرئي كتعليق TPL_STYLE في بداية القالب.
    يدمج الإعدادات مع القالب (style_json أو إعدادات مباشرة) ويحافظ على باقي المحتوى."""
    conn = g.conn
    d = body()
    row = conn.execute("SELECT html_content FROM templates WHERE id=?", (tid,)).fetchone()
    if not row:
        return err("القالب غير موجود")
    content = row["html_content"] or ""
    s = d.get("style") or d.get("style_json")
    if s is None:
        # حفظ فردي: دمج المفاتيح المرسلة مع الإعدادات الحالية
        cur = dict(rnd.DEFAULT_TPL_STYLE)
        cur.update({k: str(v).strip() for k, v in d.items()
                    if k in cur and str(v).strip() not in ("", None)})
        s = cur
    try:
        js = json.dumps(s, ensure_ascii=False, separators=(",", ":"))
    except Exception as e:
        return err("إعدادات النمط غير صالحة")
    # استبدام أو إضافة تعليق TPL_STYLE في بداية القالب
    pat = re.compile(r"<!--\s*TPL_STYLE:.*?-->\s*", re.DOTALL)
    marker = "<!--TPL_STYLE:" + js + "-->\n"
    if pat.search(content):
        content = pat.sub(marker, content)
    else:
        content = marker + content
    conn.execute("UPDATE templates SET html_content=? WHERE id=?", (content, tid))
    conn.commit()
    return ok(id=tid)


@bp.get("/templates/<int:tid>/style")
def get_template_style(tid: int):
    """قراءة إعدادات المحرر المرئي الحالية من القالب."""
    row = g.conn.execute("SELECT html_content FROM templates WHERE id=?", (tid,)).fetchone()
    if not row:
        return err("القالب غير موجود")
    ts = rnd.parse_tpl_style(row["html_content"])
    return ok(style=ts)


@bp.post("/templates/<int:tid>/live-preview")
def live_preview(tid: int):
    """معاينة حية للقالب مع إعدادات نمط مؤقتّة (بدون حفظ)."""
    conn = g.conn
    row = conn.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()
    if not row:
        return err("القالب غير موجود")
    d = body()
    ts = rnd.parse_tpl_style(row["html_content"])
    # دمج الإعدادات المؤقتة مع الإعدادات الحالية للقالب
    # (الواجهة ترسل المفاتيح كاملة: القيمة الفارغة = عودة للون/الحجم الأصلي للقالب)
    overrides = d.get("style") or d.get("style_json")
    if isinstance(overrides, dict):
        for k in ts:
            if k in overrides:
                ts[k] = str(overrides[k] or "").strip()
    from flask import render_template_string
    ctx = _sample_ctx(row["type"])
    ctx["theme"] = dbm.get_theme(conn)
    # تطبيق مفاتيح الإظهار/الإخفاء على بيانات المعاينة (البائع/المشتري)
    rnd._apply_tpl_style_ctx(ctx, ts)
    rendered = render_template_string(row["html_content"], **ctx)
    injected = rnd._inject_theme_overrides(rendered, ctx["theme"], ts)
    return ok(html=rnd._move_qr_block(injected, ts.get("qr_position", "below_totals")))


def _sample_ctx(kind: str) -> dict:
    from app.money import fmt_money, to_halalas
    from app.tafqit import tafqit_money
    total = 40009
    lines = [
        {"name": "قماش قطني مصري", "code": "FAB-001", "unit": "متر",
         "quantity": 12, "quantity_display": "12",
         "unit_price_display": "28.00", "line_net_display": "336.00",
         "line_tax_display": "50.40", "line_gross_display": "386.40"},
        {"name": "خيط خياطة 500م", "code": "FAB-005", "unit": "بكرة",
         "quantity": 3.4, "quantity_display": "3.4",
         "unit_price_display": "3.50", "line_net_display": "11.90",
         "line_tax_display": "1.79", "line_gross_display": "13.69"},
    ]
    base = {
        "company": {"name": "شركة ركن الهلال للأقمشة", "address": "الرياض - الصناعية الجديدة",
                     "tax_number": "311187605900003", "cr_number": "1010473355",
                     "color": "#0e7490", "logo_data_uri": ""},
        "customer": {"name": "شركة الواحة للمقاولات", "address": "الرياض - الملقا",
                     "tax_number": "310982736500003", "cr_number": "1010223344",
                     "phone": "0555102938"},
        "doc_title": "فاتورة ضريبية",
        "watermark_text": "",
        "footer_notice": "",
        "generated_note": "مولّد الفواتير التدريبي — إتقان",
        "standalone": True,
    }
    if kind == "receipt":
        base["doc_title"] = "سند قبض"
        base["rc"] = {"id": 0, "number": "5001", "type": "قبض", "doc_title": "سند قبض",
                      "date_display": "12/08/2026", "time_display": "11:05:00",
                      "amount_display": "400.09", "amount_words": tafqit_money(total),
                      "related_invoice": "1023", "notes": "سند مرافق للفاتورة رقم 1023"}
        return base
    base["inv"] = {"id": 0, "number": "1023", "date_display": "12/08/2026",
                   "time_display": "10:30:45", "payment_type": "آجل", "notes": "دفعة تحت الحساب",
                   "lines": lines, "subtotal_display": "347.90", "tax_display": "52.19",
                   "total_display": "400.09", "total_halalas": total,
                   "total_words": tafqit_money(total), "qr_img": "", "qr_note": ""}
    # باركود نموذجي (وسوم 1-5) حتى تظهر صورة QR فعليًا أثناء تجربة المواضع في المحرر
    base["inv"]["qr_img"], base["inv"]["qr_note"] = rnd._sample_qr_ctx()
    return base


# ══════════════════════════════════════════════════════════════════════════
#  الحذف
# ══════════════════════════════════════════════════════════════════════════

@bp.post("/<table>/<int:row_id>/delete")
def delete_row(table: str, row_id: int):
    tables = {
        "companies": "companies", "customers": "customers", "groups": "item_groups",
        "items": "items", "templates": "templates", "invoices": "invoices",
        "receipts": "receipts", "batches": "batches",
    }
    if table not in tables:
        return err("جدول غير معروف")
    if e := _require_password(body(), "protect_delete"):
        return err(e, 403)
    conn = g.conn
    conn.execute(f"DELETE FROM {tables[table]} WHERE id=?", (row_id,))
    conn.commit()
    return ok(id=row_id)


# ══════════════════════════════════════════════════════════════════════════
#  تحرير الفاتورة كاملة (محمي بكلمة سر التحكم — للمشرف)
# ══════════════════════════════════════════════════════════════════════════

@bp.get("/invoices/<int:inv_id>/get")
def invoice_get(inv_id: int):
    """بيانات الفاتورة وأسطرها لتعبئة نموذج التحرير المحمي."""
    conn = g.conn
    row = conn.execute(
        """SELECT i.*, c.name AS customer_name, co.name AS company_name
           FROM invoices i
           JOIN customers c ON c.id = i.customer_id
           JOIN companies co ON co.id = i.company_id
           WHERE i.id=?""", (inv_id,)).fetchone()
    if not row:
        return err("الفاتورة غير موجودة", 404)
    lines_out = []
    incl_flags = []
    for ln in conn.execute(
            """SELECT item_name, quantity, unit, unit_price, line_total, line_tax, line_gross
               FROM invoice_items WHERE invoice_id=? ORDER BY id""", (inv_id,)).fetchall():
        net_hal = to_halalas(ln["line_total"])
        tax_hal = to_halalas(ln["line_tax"])
        # نسبة الضريبة الفعلية للسطر (كنسبة مئوية لتعبئة النموذج)
        rate_pct = (Decimal(tax_hal) * 100 / Decimal(net_hal)) if net_hal else Decimal(0)
        # استنتاج وضع التسعير: إذا كان (سعر الوحدة × الكمية) يطابق الإجمالي الشامل
        # دون الصافي فالأسعار كانت شاملة الضريبة (وإلا فالضريبة تُضاف على السعر)
        pq_hal = int((Decimal(to_halalas(ln["unit_price"]))
                      * parse_decimal(ln["quantity"], Decimal(0))).quantize(Decimal("1")))
        incl_flags.append(bool(to_halalas(ln["line_gross"]) == pq_hal and net_hal != pq_hal))
        lines_out.append({
            "item_name": ln["item_name"],
            "quantity": float(ln["quantity"] or 0),
            "unit": (ln["unit"] if "unit" in ln.keys() else "") or "",
            "unit_price": float(ln["unit_price"] or 0),
            "tax_rate": float(rate_pct.quantize(Decimal("0.001"))),
        })
    customers = conn.execute(
        "SELECT id, name FROM customers ORDER BY name").fetchall()
    return ok(invoice={
        "id": row["id"],
        "batch_id": row["batch_id"],
        "customer_id": row["customer_id"],
        "customer_name": row["customer_name"],
        "company_name": row["company_name"],
        "invoice_number": row["invoice_number"],
        "invoice_date": row["invoice_date"],
        "invoice_time": (row["invoice_time"] or "")[:5],
        "payment_type": row["payment_type"] or "نقدي",
        "notes": row["notes"] or "",
        "prices_include_tax": any(incl_flags),
        "template_id": row["template_id"],
        "qr_position": row["qr_position"] if "qr_position" in row.keys() else "inplace",
    }, lines=lines_out,
       customers=[{"id": c["id"], "name": c["name"]} for c in customers])


@bp.post("/invoices/<int:inv_id>/update")
def invoice_update(inv_id: int):
    """تحرير الفاتورة كاملة (محمي): البيانات + الأصناف، مع إعادة الحساب
    بوحدة الهللة وتحديث مجاميع الدفعة والسند المرافق تلقائيًا."""
    conn = g.conn
    d = body()
    if e := _require_password(d, "protect_edit"):
        return err(e, 403)
    row = conn.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
    if not row:
        return err("الفاتورة غير موجودة", 404)

    customer_id = int(d.get("customer_id") or row["customer_id"])
    if not conn.execute("SELECT 1 FROM customers WHERE id=?", (customer_id,)).fetchone():
        return err("العميل (المشتري) غير موجود")
    invoice_date = _clean(d.get("invoice_date"), 10) or row["invoice_date"]
    try:
        datetime.strptime(invoice_date, "%Y-%m-%d")
    except ValueError:
        return err("التاريخ غير صحيح (يجب أن يكون بصيغة YYYY-MM-DD)")
    invoice_time = _clean(d.get("invoice_time"), 8) or row["invoice_time"]
    # التطبيع إلى HH:MM:SS (صيغة التخزين الأصلية التي تعتمدها خدمة QR)
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            invoice_time = datetime.strptime(invoice_time, fmt).strftime("%H:%M:%S")
            break
        except ValueError:
            continue
    else:
        return err("الوقت غير صحيح")
    payment_type = _clean(d.get("payment_type"), 20) or row["payment_type"] or "نقدي"
    notes = _clean(d.get("notes"), 500)

    # ── رقم الفاتورة: قابل للتعديل ──
    # (يُفحص التكرار لنفس الجهة: نفس العميل أو نفس الشركة البائعة — وبلا اعتبار للفاتورة نفسها)
    new_number = _clean(d.get("invoice_number"), 60)
    invoice_number = new_number or row["invoice_number"]
    if not invoice_number:
        return err("رقم الفاتورة مطلوب")
    if new_number and new_number != row["invoice_number"]:
        conflict = _invoice_number_conflict(conn, invoice_number, customer_id,
                                            row["company_id"], exclude_id=inv_id)
        if conflict:
            return err(conflict["message"])

    # ── القالب وموضع الباركود ─
    # موضع الباركود ثابت في كل القوالب (أسفل «المبلغ كتابةً») — لم يعد خيارًا للمستخدم
    tpl_id = None
    if d.get("template_id"):
        try:
            tpl_id = int(d["template_id"])
        except (TypeError, ValueError):
            return err("قالب الفاتورة غير صحيح")
        if not conn.execute("SELECT 1 FROM templates WHERE id=? AND type='invoice'",
                            (tpl_id,)).fetchone():
            return err("قالب الفاتورة المختار غير موجود")
    qr_pos = "inplace"

    # ── وضع التسعير: هل الأسعار شاملة الضريبة أم تُضاف عليها الضريبة؟ ──
    prices_incl = bool(d.get("prices_include_tax"))

    # ── الأصناف: إعادة الحساب بوحدة الهللة ──
    lines_in = d.get("lines")
    if not isinstance(lines_in, list) or not lines_in:
        return err("يجب إدخال سطر صنف واحد على الأقل")
    parsed = []
    subtotal_hal = tax_total_hal = 0
    for ln in lines_in:
        if not isinstance(ln, dict):
            return err("سطر صنف غير صحيح")
        name = _clean(ln.get("item_name"), 200)
        qty = parse_decimal(ln.get("quantity"), None)
        price = parse_decimal(ln.get("unit_price"), None)
        if not name:
            return err("اسم الصنف مطلوب في كل سطر")
        if qty is None or qty <= 0:
            return err(f"الكمية غير صحيحة للصنف: {name}")
        if price is None or price < 0:
            return err(f"سعر الوحدة غير صحيح للصنف: {name}")
        rate_dec = Decimal("0.15")   # ضريبة القيمة المضافة — قيمة ثابتة 15%
        price_hal = to_halalas(price)
        # المبلغ الإجمالي للصنف = الكمية × سعر الوحدة (بوحدة الهللة)
        line_hal = int((Decimal(price_hal) * qty).quantize(Decimal("1")))
        if prices_incl:
            # الأسعار شاملة الضريبة: الإجمالي الشامل = الكمية × سعر الوحدة،
            # والصافي = الإجمالي ÷ 1.15 والضريبة هي الفرق
            net_hal = int((Decimal(line_hal) * 100 / 115).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            tax_hal = line_hal - net_hal
            gross_hal = line_hal
        else:
            # الضريبة تُضاف على السعر: الصافي = الكمية × سعر الوحدة ثم ضريبة 15%
            net_hal = line_hal
            tax_hal = line_tax(net_hal, rate_dec)
            gross_hal = net_hal + tax_hal
        # ربط السطر بالصنف في قاعدة البيانات (بالاسم) لتظهر وحدته وكوده على الفاتورة —
        # الأولوية للوحدة المرسلة من الواجهة (مختارة من بطاقة الصنف وقابلة للتعديل اليدوي)
        sent_unit = _clean(ln.get("unit"), 40)
        it_row = conn.execute(
            "SELECT id, unit FROM items WHERE name=? LIMIT 1", (name,)).fetchone()
        parsed.append((name, qty, from_halalas(price_hal), from_halalas(net_hal),
                       from_halalas(tax_hal), from_halalas(gross_hal),
                       it_row["id"] if it_row else None,
                       sent_unit or ((it_row["unit"] if it_row else "") or "")))
        subtotal_hal += net_hal
        tax_total_hal += tax_hal
    total_hal = subtotal_hal + tax_total_hal

    # ── الحفظ ─
    conn.execute(
        """UPDATE invoices SET invoice_number=?, customer_id=?, invoice_date=?, invoice_time=?,
           payment_type=?, subtotal=?, tax_amount=?, total_amount=?, notes=?,
           template_id=?, qr_position=? WHERE id=?""",
        (invoice_number, customer_id, invoice_date, invoice_time, payment_type,
         float(from_halalas(subtotal_hal)), float(from_halalas(tax_total_hal)),
         float(from_halalas(total_hal)), notes, tpl_id, qr_pos, inv_id))
    conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (inv_id,))
    for name, qty, price_f, net_f, tax_f, gross_f, item_id, unit in parsed:
        conn.execute(
            """INSERT INTO invoice_items (invoice_id, item_id, item_name, quantity, unit,
               unit_price, line_total, line_tax, line_gross) VALUES (?,?,?,?,?,?,?,?,?)""",
            (inv_id, item_id, name, float(qty), unit, float(price_f), float(net_f),
             float(tax_f), float(gross_f)))
    # السند المرافق: يتبع قيمة الفاتورة تلقائيًا
    conn.execute("UPDATE receipts SET amount=? WHERE related_invoice_id=?",
                 (float(from_halalas(total_hal)), inv_id))
    # مجاميع الدفعة: تُحسب من فواتيرها تلقائيًا
    conn.execute(
        """UPDATE batches SET
           total_net = (SELECT COALESCE(SUM(subtotal),0) FROM invoices WHERE batch_id=?),
           total_tax = (SELECT COALESCE(SUM(tax_amount),0) FROM invoices WHERE batch_id=?),
           total_gross = (SELECT COALESCE(SUM(total_amount),0) FROM invoices WHERE batch_id=?)
           WHERE id=?""",
        (row["batch_id"], row["batch_id"], row["batch_id"], row["batch_id"]))
    # إعادة توليد الباركود إذا كانت الفاتورة تحمله (ليتبع البيانات المعدلة)
    if (row["qr_payload_b64"] or "").strip():
        try:
            qr_svc.regenerate_stored_qr(conn, invoice_id=inv_id)
        except Exception:  # لا يفشل التحرير إذا تعذّر توليد QR
            pass
    conn.commit()
    return ok(id=inv_id, batch_id=row["batch_id"])


# ══════════════════════════════════════════════════════════════════════════
#  تقرير الدفعة (طباعة Excel أو PDF)
# ══════════════════════════════════════════════════════════════════════════

# مواقع باركود الفاتورة: ثُبّت الموضع تلقائيًا أسفل «المبلغ كتابةً» في كل القوالب،
# ولذلك أُلغي خيار الموقع من الواجهة والـAPI (العمود qr_position باقٍ للتوافق بقيمة inplace).

_REPORT_HEADERS = ("البائع", "المشتري", "الحساب", "التاريخ", "الوقت",
                   "رقم الفاتورة", "طريقة السداد", "قيمة الضريبة المضافة",
                   "المبلغ الشامل")


def _batch_report_rows(conn, batch_id: int):
    return conn.execute(
        """SELECT co.name AS seller_name, c.name AS buyer_name,
                  COALESCE(c.tax_number,'') AS account,
                  i.invoice_date, i.invoice_time, i.invoice_number, i.payment_type,
                  i.tax_amount, i.total_amount
           FROM invoices i
           JOIN companies co ON co.id = i.company_id
           JOIN customers c ON c.id = i.customer_id
           WHERE i.batch_id=?
           ORDER BY i.invoice_date, i.invoice_time, i.id""", (batch_id,)).fetchall()


def _fmt_report_date(s) -> str:
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(s or "")


@bp.get("/batches/<int:batch_id>/report")
def batch_report(batch_id: int):
    """تقرير فواتير الدفعة: البائع، المشتري، الحساب، التاريخ، الوقت، رقم
    الفاتورة، طريقة السداد، قيمة الضريبة المضافة، المبلغ الشامل — Excel أو PDF."""
    conn = g.conn
    fmt = (request.args.get("format") or "xlsx").lower()
    batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not batch:
        return err("الدفعة غير موجودة", 404)
    rows = _batch_report_rows(conn, batch_id)
    if not rows:
        return err("لا توجد فواتير في هذه الدفعة")
    dbm.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt == "pdf":
        return _report_pdf(batch, batch_id, rows, stamp)
    return _report_xlsx(batch, batch_id, rows, stamp)


def _report_pdf(batch, batch_id: int, rows, stamp: str):
    """بناء تقرير PDF عبر محرك التحويل (WeasyPrint → Edge headless)."""
    body_tr = []
    total_tax = total_gross = 0.0
    for r in rows:
        tax_v = float(r["tax_amount"] or 0)
        gross_v = float(r["total_amount"] or 0)
        total_tax += tax_v
        total_gross += gross_v
        body_tr.append(
            "<tr>"
            f"<td>{r['seller_name']}</td><td>{r['buyer_name']}</td>"
            f"<td dir='ltr'>{r['account'] or '—'}</td>"
            f"<td>{_fmt_report_date(r['invoice_date'])}</td>"
            f"<td dir='ltr'>{(r['invoice_time'] or '')[:5]}</td>"
            f"<td dir='ltr'><b>{r['invoice_number']}</b></td>"
            f"<td>{r['payment_type']}</td>"
            f"<td class='num'>{tax_v:,.2f}</td>"
            f"<td class='num'><b>{gross_v:,.2f}</b></td>"
            "</tr>")
    head_th = "".join(
        f'<th class="{ "num" if i >= 7 else "" }">{h}</th>'
        for i, h in enumerate(_REPORT_HEADERS))
    html = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<style>
  @page {{ size: A4 landscape; margin: 10mm; }}
  body {{ font-family: 'Cairo','Tajawal','Segoe UI',sans-serif; direction: rtl; font-size: 10.5px; }}
  h2 {{ margin: 0 0 2mm; }}
  .meta {{ color: #475569; margin: 0 0 3mm; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #94a3b8; padding: 2.5px 5px; text-align: right; }}
  th {{ background: #0e7490; color: #fff; }}
  td.num, th.num {{ text-align: left; direction: ltr; }}
  tr.tot {{ background: #e0f2fe; font-weight: 700; }}
  .note {{ margin-top: 5mm; color: #b91c1c; font-size: 9.5px; }}
</style>
</head>
<body>
<h2>تقرير الدفعة #{batch_id}</h2>
<p class="meta">أُنشئت الدفعة: {batch['created_at'][:16]} — عدد الفواتير: {len(rows)}</p>
<table>
  <thead><tr>{head_th}</tr></thead>
  <tbody>
    {''.join(body_tr)}
    <tr class="tot"><td colspan="7">الإجمالي</td>
        <td class="num">{total_tax:,.2f}</td><td class="num">{total_gross:,.2f}</td></tr>
  </tbody>
</table>
<p class="note">نسخة تدريبية — غير صالحة للاستخدام الرسمي</p>
</body>
</html>"""
    out = dbm.EXPORT_DIR / f"تقرير_الدفعة_{batch_id}_{stamp}.pdf"
    pdfx.html_to_pdf(html, out)
    return ok(file=out.name, engine=pdfx.last_engine())


def _report_xlsx(batch, batch_id: int, rows, stamp: str):
    """بناء تقرير Excel (xlsx) عبر openpyxl."""
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        return err("مكتبة openpyxl غير مثبتة — ثبّتها لتصدير Excel", 500)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"الدفعة {batch_id}"
    ws.sheet_view.rightToLeft = True
    ws.append(_REPORT_HEADERS)
    head_fill = PatternFill("solid", fgColor="0E7490")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="right")
    total_tax_x = total_gross_x = 0.0
    for r in rows:
        tax_v = float(r["tax_amount"] or 0)
        gross_v = float(r["total_amount"] or 0)
        total_tax_x += tax_v
        total_gross_x += gross_v
        ws.append([r["seller_name"], r["buyer_name"], r["account"] or "",
                   _fmt_report_date(r["invoice_date"]), (r["invoice_time"] or "")[:5],
                   r["invoice_number"], r["payment_type"], tax_v, gross_v])
    ws.append(["الإجمالي", "", "", "", "", "", "", total_tax_x, total_gross_x])
    tot_row = ws.max_row
    for cell in ws[tot_row]:
        cell.font = Font(bold=True)
    for col in ("I", "J"):
        for row in ws[f"{col}2":f"{col}{tot_row}"]:
            row[0].number_format = "#,##0.00"
    out = dbm.EXPORT_DIR / f"تقرير_الدفعة_{batch_id}_{stamp}.xlsx"
    wb.save(out)
    return ok(file=out.name)


# ══════════════════════════════════════════════════════════════════════════
#  قالب الدفعة (تغيير قالب فواتير المجموعة كاملة)
# ══════════════════════════════════════════════════════════════════════════

@bp.post("/batches/<int:batch_id>/set-template")
def batch_set_template(batch_id: int):
    """تطبيق قالب فواتير واحد على كل فواتير الدفعة (المجموعة كاملة)."""
    conn = g.conn
    d = body()
    if not conn.execute("SELECT 1 FROM batches WHERE id=?", (batch_id,)).fetchone():
        return err("الدفعة غير موجودة", 404)
    tid = d.get("template_id")
    if tid:
        tid = int(tid)
        trow = conn.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()
        if not trow:
            return err("القالب غير موجود")
        if trow["type"] != "invoice":
            return err("القالب المختار ليس قالب فاتورة")
    else:
        tid = None
    cur = conn.execute("UPDATE invoices SET template_id=? WHERE batch_id=?", (tid, batch_id))
    conn.commit()
    return ok(updated=cur.rowcount, template_id=tid)


# ══════════════════════════════════════════════════════════════════════════
#  التطبيق الجماعي للقالب (Bulk Action) — على الفواتير المختارة
# ══════════════════════════════════════════════════════════════════════════

@bp.post("/invoices/set-template")
def invoices_bulk_set_template():
    """تطبيق قالب فواتير واحد على كل الفواتير المختارة (تطبيق جماعي)."""
    conn = g.conn
    d = body()
    raw = d.get("ids") or []
    if isinstance(raw, (int, str)):
        raw = [raw]
    ids = sorted({int(i) for i in raw if str(i).strip().isdigit()})
    if not ids:
        return err("لم يتم تحديد أي فاتورة")
    tid = d.get("template_id")
    if tid:
        tid = int(tid)
        trow = conn.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()
        if not trow:
            return err("القالب غير موجود")
        if trow["type"] != "invoice":
            return err("القالب المختار ليس قالب فاتورة")
    else:
        tid = None
    marks = ",".join("?" * len(ids))
    cur = conn.execute(
        f"UPDATE invoices SET template_id=? WHERE id IN ({marks})", (tid, *ids))
    conn.commit()
    return ok(updated=cur.rowcount, template_id=tid)


# ══════════════════════════════════════════════════════════════════════════
#  التوليد والمعاينة والتصدير
# ══════════════════════════════════════════════════════════════════════════

def _params_from(d: dict) -> GenParams:
    customers = d.get("customer_ids") or []
    if isinstance(customers, (int, str)):
        customers = [customers]
    groups_in = d.get("item_group_ids") or []
    if isinstance(groups_in, (int, str)):
        groups_in = [groups_in]
    items_in = d.get("item_ids") or []
    if isinstance(items_in, (int, str)):
        items_in = [items_in]
    return GenParams(
        company_id=int(d.get("company_id") or 0),
        customer_ids=[int(c) for c in customers],
        item_group_ids=[int(g) for g in groups_in],
        item_ids=[int(i) for i in items_in],
        items_mode=_clean(d.get("items_mode"), 10) or "groups",
        date_from=_clean(d.get("date_from"), 10) or date.today().isoformat(),
        date_to=_clean(d.get("date_to"), 10) or date.today().isoformat(),
        count_mode=_clean(d.get("count_mode"), 10) or "total",
        count_total=int(d.get("count_total") or 0),
        count_daily=float(d.get("count_daily") or 0),
        amount=_clean(d.get("amount"), 20) or "0",
        amount_mode="gross" if d.get("amount_mode") == "gross" else "net",
        min_amount=_clean(d.get("min_amount"), 20) or "0",
        payment_type=_clean(d.get("payment_type"), 10) or "نقدي",
        seed=_clean(d.get("seed"), 12),
        qr_mode=_clean(d.get("qr_mode"), 10) or "none",
        with_receipts=bool(d.get("with_receipts")),
        receipt_type=_clean(d.get("receipt_type"), 10) or "قبض",
        invoice_start=int(d.get("invoice_start") or 1001),
        number_prefix=_clean(d.get("number_prefix"), 10),
        receipt_start=int(d.get("receipt_start") or 5001),
        template_invoice_id=int(d["template_invoice_id"]) if d.get("template_invoice_id") else None,
        template_receipt_id=int(d["template_receipt_id"]) if d.get("template_receipt_id") else None,
        random_notes=bool(d.get("random_notes")),
    )

@bp.post("/generate")
def generate_batch():
    d = body()
    try:
        p = _params_from(d)
        summary = engine_generate(g.conn, p, persist=True)
        dbm.set_setting(g.conn, "gen_last", p.to_json())
    except ValueError as exc:
        return err(str(exc))
    except Exception as exc:  # pragma: no cover
        return err(f"خطأ غير متوقع: {exc}")
    return ok(batch_id=summary.get("batch_id"), summary=summary)


@bp.post("/preview-dry")
def preview_dry():
    """توليد دفعة مؤقتة (بدون تخزين) وإرجاع HTML لفاتورة واحدة منها."""
    d = body()
    try:
        p = _params_from(d)
        summary = engine_generate(g.conn, p, persist=False, return_built=True)
        built = summary["_built"]
        if not built:
            return err("لم يتم توليد أي فاتورة")
        inv = built[len(built) // 2]      # فاتورة من المنتصف (أكثر تمثيلًا)
        row = {
            "id": 0,
            "company_id": p.company_id,
            "customer_id": inv.customer_id,
            "invoice_number": f"{p.number_prefix}{inv.number}",
            "invoice_date": inv.dt.strftime("%Y-%m-%d"),
            "invoice_time": inv.dt.strftime("%H:%M:%S"),
            "payment_type": inv.payment,
            "subtotal": float(inv.subtotal) / 100,
            "tax_amount": float(inv.tax) / 100,
            "total_amount": float(inv.total) / 100,
            "template_id": p.template_invoice_id,
            "notes": inv.notes,
            "qr_mode": getattr(inv, "qr_mode", "none") or "none",
            "qr_payload_b64": getattr(inv, "qr_payload_b64", "") or "",
        }
        tpl = None
        if p.template_invoice_id:
            trow = g.conn.execute("SELECT html_content FROM templates WHERE id=?",
                                  (p.template_invoice_id,)).fetchone()
            tpl = trow["html_content"] if trow else None
        html = rnd.render_invoice(g.conn, row, template_html=tpl, built_inv=inv)
        return ok(html=html, seed=summary["seed"])
    except ValueError as exc:
        return err(str(exc))
    except Exception as exc:  # pragma: no cover
        return err(f"خطأ غير متوقع: {exc}")


@bp.post("/export")
def export_docs():
    """تصدير PDF: mode=combined (ملف واحد) أو zip (ملفات منفصلة مضغوطة)."""
    d = body()
    kind = "receipt" if d.get("kind") == "receipt" else "invoice"
    mode = d.get("mode") or "combined"
    conn = g.conn
    try:
        if d.get("ids"):
            ids = [int(x) for x in d["ids"]]
            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(
                f"SELECT * FROM {('invoices' if kind == 'invoice' else 'receipts')} "
                f"WHERE id IN ({placeholders}) ORDER BY id", ids).fetchall()
            label = "مستندات"
        elif d.get("batch_id"):
            rows = conn.execute(
                f"SELECT * FROM {('invoices' if kind == 'invoice' else 'receipts')} "
                f"WHERE batch_id=? ORDER BY id", (int(d["batch_id"]),)).fetchall()
            batch = conn.execute("SELECT id, created_at FROM batches WHERE id=?",
                                 (int(d["batch_id"]),)).fetchone()
            label = f"الدفعة_{batch['id']}" if batch else "الدفعة"
        else:
            return err("حدد مستندات أو دفعة للتصدير")
        if not rows:
            return err("لا توجد مستندات مطابقة")

        if mode == "zip":
            path = pdfx.export_zip(conn, kind, rows, label)
        elif len(rows) == 1:
            path = pdfx.export_single_pdf(conn, kind, rows[0])
        else:
            path = pdfx.export_combined_pdf(conn, kind, rows, label)
    except ValueError as exc:
        return err(str(exc))
    except RuntimeError as exc:
        return err(str(exc), 500)
    return ok(file=path.name, engine=pdfx.last_engine())


@bp.get("/exports/<path:name>")
def download_export(name: str):
    return send_from_directory(dbm.EXPORT_DIR, name, as_attachment=True)
# ══════════════════════════════════════════════════════════════════════════
#  الفواتير اليدوية + بوابة المشرف (API)
#  كل هذه النقاط محمية ببوابة حماية المشرف (قبل الوصول لأقسام المشرف/الاعتماد).
# ══════════════════════════════════════════════════════════════════════════

def _calc_manual_invoice(d: dict) -> dict:
    """حساب فاتورة يدوية بوحدة الهللة.

    - خصم كل سطر: نسبة % تُخصم من إجمالي السطر قبل الضريبة.
    - خصم على مستوى الفاتورة: يُوزَّع تناسبيًا على السطور حتى يبقى
      مجموع line_total = subtotal ومجموع line_tax = tax_amount تمامًا.
    """
    from decimal import ROUND_HALF_UP as _RHU, Decimal as _Dec
    from app.money import line_tax as _line_tax

    raw_lines = d.get("lines") or []
    if isinstance(raw_lines, str):
        import json as _json
        try:
            raw_lines = _json.loads(raw_lines)
        except Exception:
            raw_lines = []
    if not raw_lines:
        raise ValueError("أضف سطرًا واحدًا على الأقل (صنف بكمية وسعر)")

    # ── وضع التسعير: هل الأسعار شاملة الضريبة أم تُضاف عليها الضريبة؟ ──
    prices_incl = bool(d.get("prices_include_tax"))

    parsed = []
    for i, ln in enumerate(raw_lines or []):
        if not isinstance(ln, dict):
            raise ValueError(f"بيانات السطر {i + 1} غير صحيحة")
        name = _clean(ln.get("item_name"), 200)
        if not name:
            raise ValueError(f"اسم الصنف مطلوب في السطر {i + 1}")
        qty = parse_decimal(ln.get("quantity"), None)
        price = parse_decimal(ln.get("unit_price"), None)
        tax_rate = parse_decimal(ln.get("tax_rate"), _Dec("15"))
        disc_rate = parse_decimal(ln.get("discount_rate"), _Dec(0))
        if qty is None or qty <= 0:
            raise ValueError(f"الكمية غير صحيحة في السطر: {name}")
        if price is None or price < 0:
            raise ValueError(f"سعر الوحدة غير صحيح في السطر: {name}")
        tax_rate = min(max(tax_rate or _Dec(0), _Dec(0)), _Dec(100)) / 100
        disc_rate = min(max(disc_rate or _Dec(0), _Dec(0)), _Dec(100)) / 100
        # المبلغ الإجمالي للصنف = الكمية × سعر الوحدة (بوحدة الهللة)
        line_hal = int((price * 100 * qty).quantize(_Dec("1"), rounding=_RHU))
        if prices_incl:
            # الأسعار شاملة الضريبة: الصافي = الإجمالي ÷ (1 + نسبة الضريبة)
            net_hal = int((_Dec(line_hal) / (_Dec("1") + _Dec(tax_rate)))
                          .quantize(_Dec("1"), rounding=_RHU))
        else:
            # الضريبة تُضاف على السعر: الصافي = الكمية × سعر الوحدة
            net_hal = line_hal
        line_disc_hal = int((_Dec(net_hal) * disc_rate).quantize(_Dec("1"), rounding=_RHU))
        taxable_hal = max(0, net_hal - line_disc_hal)
        it_id = ln.get("item_id")
        try:
            it_id = int(it_id) if it_id else None
        except (TypeError, ValueError):
            it_id = None
        parsed.append({
            "item_id": it_id,
            "name": name,
            "unit": _clean(ln.get("unit"), 40),   # وحدة الصنف (ديناميكية: من قاعدة البيانات أو حرة)
            "qty": qty,
            "price_hal": int((price * 100).quantize(_Dec("1"), rounding=_RHU)),
            "net_hal": net_hal,
            "line_disc_hal": line_disc_hal,
            "taxable_hal": taxable_hal,
            "tax_rate": tax_rate,
            "disc_rate": disc_rate,
        })
    subtotal_hal = sum(p["taxable_hal"] for p in parsed)
    if subtotal_hal <= 0:
        raise ValueError("الإجمالي الصافي بعد الخصومات يساوي صفرًا — راجع الأصناف والخصومات")

    inv_disc_hal = min(to_halalas(d.get("invoice_discount")), subtotal_hal)
    if inv_disc_hal > 0:
        shares = []
        for p in parsed:
            s = (_Dec(p["taxable_hal"]) * _Dec(inv_disc_hal) / _Dec(subtotal_hal))
            shares.append(int(s.quantize(_Dec("1"), rounding=_RHU)))
        diff = inv_disc_hal - sum(shares)
        if diff:
            best = max(range(len(parsed)),
                       key=lambda k: (_Dec(parsed[k]["taxable_hal"]) * _Dec(inv_disc_hal)
                                      / _Dec(subtotal_hal) % _Dec(1)))
            shares[best] += diff
        for k, p in enumerate(parsed):
            p["share_hal"] = max(0, shares[k])
            p["taxable_hal"] = max(0, p["taxable_hal"] - p["share_hal"])
    else:
        for p in parsed:
            p["share_hal"] = 0

    subtotal_final_hal = sum(p["taxable_hal"] for p in parsed)
    tax_total_hal = 0
    for p in parsed:
        p["tax_hal"] = _line_tax(p["taxable_hal"], p["tax_rate"])
        p["gross_hal"] = p["taxable_hal"] + p["tax_hal"]
        p["discount_amount_hal"] = p["line_disc_hal"] + p["share_hal"]
        tax_total_hal += p["tax_hal"]
    total_hal = subtotal_final_hal + tax_total_hal
    return {
        "lines": parsed,
        "subtotal_hal": subtotal_final_hal,
        "tax_hal": tax_total_hal,
        "total_hal": total_hal,
        "inv_disc_hal": inv_disc_hal,
    }


def _next_manual_number(conn) -> str:
    """رقم تسلسلي للفواتير اليدوية: M1, M2, M3 … (يتجنب الأرقام المحذوفة)."""
    mx = 0
    for r in conn.execute("SELECT invoice_number FROM invoices WHERE is_manual=1").fetchall():
        s = str(r["invoice_number"] or "")
        if s.startswith("M") and s[1:].isdigit():
            mx = max(mx, int(s[1:]))
    return f"M{mx + 1}"


def _normalize_manual_datetime(date_val, time_val) -> tuple[str, str]:
    """تطبيع مرن لتاريخ/وقت الفاتورة اليدوية — يقبل كل الصيغ الشائعة بلا استثناء.

    يقبل التاريخ: 'YYYY-MM-DD' أو ISO كامل، ويقبل الوقت: 'HH:MM' أو 'HH:MM:SS'
    (وما يرسله <input type=time> وهو 'HH:MM'، أو <input type=datetime-local>
    وهو 'YYYY-MM-DDTHH:MM'). يعيد (date, time) بصيغة التخزين '%Y-%m-%d' و '%H:%M:%S'.
    """
    from datetime import date as _date, datetime as _dt
    ds = (str(date_val or "").strip())
    ts = (str(time_val or "").strip())
    if not ds:
        ds = _date.today().isoformat()
    # قد يصل التاريخ مدمجًا مع الوقت (datetime-local): 'YYYY-MM-DDTHH:MM[:SS]'
    if "T" in ds:
        try:
            _c = _dt.fromisoformat(ds)
            return _c.strftime("%Y-%m-%d"), _c.strftime("%H:%M:%S")
        except ValueError:
            pass
        ds, _, _tp = ds.partition("T")
        ds = ds.strip()
        if _tp.strip():
            ts = _tp.strip()
    if not ts:
        ts = _dt.now().strftime("%H:%M:%S")
    # لو وصل الوقت مدمجًا مع تاريخ خذه من آخر جزء
    if " " in ts.strip() and len(ts.strip()) > 8:
        ts = ts.strip().split()[-1]
    ts = ts.strip().replace("Z", "")
    # إسقاط أجزاء الثانية/الميكرو الإضافية مع قبولها: 'HH:MM:SS.xxx' → 'HH:MM:SS'
    _m = __import__("re").match(r"^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", ts)
    if _m:
        _h, _mi, _ss = _m.groups()
        ts = f"{int(_h):02d}:{int(_mi):02d}:{int(_ss) if _ss is not None else 0:02d}"
    ts_norm = None
    for _fmt in ("%H:%M:%S", "%H:%M"):
        try:
            ts_norm = _dt.strptime(ts, _fmt).strftime("%H:%M:%S")
            break
        except ValueError:
            continue
    if ts_norm is None:
        try:
            ts_norm = _dt.fromisoformat(f"2000-01-01 {ts}").strftime("%H:%M:%S")
        except ValueError:
            raise ValueError("الوقت غير صحيح (مثال: 10:30 أو 10:30:00)")
    try:
        d_norm = _dt.strptime(ds[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        try:
            d_norm = _dt.fromisoformat(ds).strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError("التاريخ غير صحيح (يجب أن يكون بصيغة YYYY-MM-DD)")
    return d_norm, ts_norm


def _normalize_invoice_number(value) -> str:
    """تطبيع رقم الفاتورة قبل المقارنة (مسافات موحّدة + حروف كبيرة) لمنع التكرار بأشكال مختلفة."""
    return " ".join(str(value or "").split()).upper()


def _invoice_number_conflict(conn, number: str, customer_id=None, company_id=None,
                             exclude_id=None):
    """حماية الفواتير من التكرار: يُمنع تكرار «رقم الفاتورة» فقط عند تطابق
    (الشركة البائعة + العميل) معًا في فاتورة سابقة.

    - نفس الرقم لنفس الشركة + نفس العميل → مرفوض (رسالة: رقم الفاتورة مكرر
      لنفس العميل والشركة، يرجى اختيار رقم آخر).
    - نفس الرقم لعميل مختلف أو شركة مختلفة → مسموح.
    - التطبيع: مسافات موحّدة + حروف كبيرة قبل المقارنة.
    يعيد dict ببيانات التعارض أو None إذا لا تعارض.
    """
    norm = _normalize_invoice_number(number)
    if not norm:
        return None
    if not customer_id or not company_id:
        return None
    sql = (
        "SELECT i.id, i.customer_id, i.company_id, c.name AS customer_name, "
        "       co.name AS company_name "
        "FROM invoices i "
        "LEFT JOIN customers c ON c.id = i.customer_id "
        "LEFT JOIN companies co ON co.id = i.company_id "
        "WHERE UPPER(TRIM(i.invoice_number)) = ? "
        "AND i.customer_id = ? AND i.company_id = ?"
    )
    args = [norm, int(customer_id), int(company_id)]
    if exclude_id:
        sql += " AND i.id <> ?"
        args.append(int(exclude_id))
    row = conn.execute(sql + " LIMIT 1", args).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "invoice_number": number,
        "customer_id": row["customer_id"],
        "company_id": row["company_id"],
        "customer_name": row["customer_name"] or "",
        "company_name": row["company_name"] or "",
        "scope": "العميل والشركة",
        "message": ("رقم الفاتورة مكرر لنفس العميل والشركة، يرجى اختيار رقم آخر."),
    }


@bp.get("/admin/invoice-number/check")
def invoice_number_check():
    """فحص فوري لتفرّد رقم الفاتورة لنفس العميل/الشركة — لتظهر للمستخدم قبل الحفظ."""
    conn = g.conn
    number = _clean(request.args.get("number"), 60)
    if not number:
        return ok(number=number, available=True, message="")
    conflict = _invoice_number_conflict(
        conn, number,
        request.args.get("customer_id", type=int),
        request.args.get("company_id", type=int),
        request.args.get("exclude_id", type=int),
    )
    if conflict:
        return ok(number=number, available=False, message=conflict["message"],
                  conflict_id=conflict["id"])
    return ok(number=number, available=True,
              message=f"رقم الفاتورة «{number}» متاح للجهة المختارة")


@bp.post("/admin/manual-invoice")
def manual_invoice_create():
    """إنشاء فاتورة يدوية (مسودة أو معتمدة مباشرة) — محمي ببوابة المشرف."""
    from app.money import from_halalas as _fh
    conn = g.conn
    d = body()
    try:
        if not d.get("company_id") or not d.get("customer_id"):
            raise ValueError("اختر الشركة البائعة والعميل")
        company = conn.execute("SELECT id FROM companies WHERE id=?",
                               (int(d["company_id"]),)).fetchone()
        customer = conn.execute("SELECT id FROM customers WHERE id=?",
                                (int(d["customer_id"]),)).fetchone()
        if not company:
            raise ValueError("الشركة المختارة غير موجودة")
        if not customer:
            raise ValueError("العميل المختار غير موجود")

        calc = _calc_manual_invoice(d)

        number = _clean(d.get("invoice_number"), 40)
        if not number:
            number = _next_manual_number(conn)
        # ── حماية من التكرار: نفس الرقم لنفس الشركة + نفس العميل معًا فقط ──
        conflict = _invoice_number_conflict(conn, number, customer["id"], company["id"])
        if conflict:
            raise ValueError(conflict["message"])

        # ── نوع الباركود: بدون / المرحلة الأولى (TLV 1-5) / المرحلة الثانية (TLV 1-9) ──
        raw_qr_mode = str(d.get("qr_mode") or "none").strip().lower()
        if raw_qr_mode not in qr_svc.QR_MODES:
            raise ValueError("نوع الباركود غير صحيح — اختر: بدون باركود / المرحلة الأولى / المرحلة الثانية")
        qr_mode = raw_qr_mode

        # دالة مرنة: تقبل 'HH:MM' (ما يرسله <input type=time>) و 'HH:MM:SS' و fromisoformat
        invoice_date, invoice_time = _normalize_manual_datetime(
            d.get("invoice_date"), d.get("invoice_time"))
        payment_type = _clean(d.get("payment_type"), 20) or "نقدي"
        notes = _clean(d.get("notes"), 500)

        template_id = None
        if d.get("template_id"):
            tid = int(d["template_id"])
            trow = conn.execute("SELECT id FROM templates WHERE id=? AND type='invoice'",
                                (tid,)).fetchone()
            if not trow:
                raise ValueError("قالب الفاتورة المختار غير موجود")
            template_id = tid

        # موضع الباركود: ثابت في كل القوالب (أسفل «المبلغ كتابةً») — لا خيار للمستخدم
        qr_pos = "inplace"

        approve = bool(d.get("approve") in (True, "true", "1", 1, "on", "yes"))
        status = "approved" if approve else "draft"

        cur = conn.execute(
            """INSERT INTO invoices (batch_id, company_id, customer_id, invoice_number,
               invoice_date, invoice_time, payment_type, subtotal, tax_amount, total_amount,
               template_id, notes, qr_mode, qr_payload_b64, qr_position, discount_amount,
               is_manual, approval_status, created_at)
               VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,'inplace',?,1,?,?)""",
            (company["id"], customer["id"], number, invoice_date, invoice_time,
             payment_type, float(_fh(calc["subtotal_hal"])), float(_fh(calc["tax_hal"])),
             float(_fh(calc["total_hal"])), template_id, notes, qr_mode, "",
             float(_fh(calc["inv_disc_hal"])), status, dbm.now_iso()),
        )
        inv_id = cur.lastrowid

        for p in calc["lines"]:
            it = None
            if p.get("item_id"):
                it = conn.execute("SELECT id, unit FROM items WHERE id=?",
                                  (p["item_id"],)).fetchone()
            if it is None:
                it = conn.execute("SELECT id, unit FROM items WHERE name=? LIMIT 1",
                                  (p["name"],)).fetchone()
            # الوحدة: ما أرسلته الواجهة (من بطاقة الصنف) ثم وحدة الصنف في قاعدة البيانات
            unit = p.get("unit") or ((it["unit"] if it else "") or "")
            conn.execute(
                """INSERT INTO invoice_items (invoice_id, item_id, item_name, quantity, unit,
                   unit_price, discount_rate, discount_amount, line_total, line_tax, line_gross)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (inv_id, it["id"] if it else None, p["name"], float(p["qty"]), unit,
                 float(_fh(p["price_hal"])), float(p["disc_rate"] * 100),
                 float(_fh(p["discount_amount_hal"])), float(_fh(p["taxable_hal"])),
                 float(_fh(p["tax_hal"])), float(_fh(p["gross_hal"]))),
            )

        # ─ توليد الباركود (المرحلة الأولى/الثانية) بعد حفظ الأسطر — ويتبع بيانات الفاتورة ──
        if qr_mode in ("simple", "phase2"):
            saved = conn.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
            payload = qr_svc.build_payload_for_invoice(conn, saved, qr_mode)
            conn.execute("UPDATE invoices SET qr_payload_b64=? WHERE id=?", (payload, inv_id))

        conn.commit()
        return ok(id=inv_id, invoice_number=number, status=status,
                  qr_mode=qr_mode,
                  total=float(_fh(calc["total_hal"])))
    except (ValueError, TypeError) as exc:
        conn.rollback()          # لا تُحفظ فاتورة ناقصة عند فشل التحقق أو تعذّر توليد الباركود
        return err(str(exc))


@bp.post("/admin/manual-invoices/<int:inv_id>/approve")
def manual_invoice_approve(inv_id: int):
    """اعتماد فاتورة يدوية (مسودة → معتمدة) — محمي ببوابة المشرف."""
    conn = g.conn
    row = conn.execute("SELECT id, approval_status FROM invoices WHERE id=? AND is_manual=1",
                       (inv_id,)).fetchone()
    if not row:
        return err("الفاتورة اليدوية غير موجودة", 404)
    if row["approval_status"] == "approved":
        return ok(id=inv_id, status="approved")
    conn.execute("UPDATE invoices SET approval_status='approved' WHERE id=?", (inv_id,))
    conn.commit()
    return ok(id=inv_id, status="approved")


@bp.post("/admin/password")
def admin_password_change():
    """تغيير كلمة مرور بوابة المشرف (يتطلب الكلمة الحالية)."""
    d = body()
    try:
        dbm.change_admin_password(g.conn, d.get("current_password") or "",
                                  d.get("new_password") or "")
    except ValueError as exc:
        return err(str(exc), 403)
    return ok()
