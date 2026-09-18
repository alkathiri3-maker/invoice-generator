# -*- coding: utf-8 -*-
"""
توليد HTML للمستندات من القوالب المخزنة في القاعدة (Jinja2):
تفقيط، QR، شعار، علامة مائية حمراء "نسخة تدريبية"، ودمج عدة مستندات في ملف واحد.

+ دعم المحرر المرئي المتقدم (TPL_STYLE):
  كل قالب فاتورة يمكن أن يحمل تعليقًا اختياريًا بأعلى الملف:
    <!--TPL_STYLE:{"qr_position":"below_totals", ...}-->
  يُقرأ عند العرض ويُترجم إلى CSS override + نقل موضع QR — بدون تعديل
  بنية القالب الأصلية وبدون أي تغيير في مخطط قاعدة البيانات.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import datetime
from pathlib import Path

from app import db as dbm
from app.money import to_halalas, fmt_money, fmt_qty
from app.tafqit import tafqit_money
from app.qr_service import qr_image_data_uri, qr_note_for

WATERMARK_TEXT = "نسخة تدريبية"
FOOTER_NOTICE = "نسخة تدريبية - غير صالحة للاستخدام الرسمي"

_BODY_RE = re.compile(r"<body[^>]*>(.*)</body>", re.DOTALL | re.IGNORECASE)
_STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_FONT_LINK_RE = re.compile(r"<link[^>]*fonts\.googleapis[^>]*>", re.IGNORECASE)

# روابط Google Fonts لكل خط مدعوم (تُحقن حسب إعداد المظهر)
_FONT_LINKS = {
    "Cairo": "Cairo:wght@400;600;700;800",
    "Tajawal": "Tajawal:wght@400;500;700;800",
    "Amiri": "Amiri:wght@400;700",
    "Noto Kufi Arabic": "Noto+Kufi+Arabic:wght@400;600;700;800",
    "Almarai": "Almarai:wght@400;700;800",
}

_TPL_STYLE_RE = re.compile(r"<!--\s*TPL_STYLE:(.*?)-->", re.DOTALL)

DEFAULT_TPL_STYLE = {
    "qr_position": "below_totals",
    "qr_size": "54",
    # رأس الجدول والصفوف
    "th_bg": "", "th_color": "", "th_size": "", "th_bold": "",
    "alt_bg": "",
    "row_color": "",
    # الحدود والمسافات
    "border_color": "", "border_width": "", "border_style": "", "cell_padding": "",
    # العناوين والنصوص والإجماليات
    "header_color": "", "header_size": "", "header_bold": "",
    "body_color": "", "body_size": "",
    "total_color": "", "total_size": "", "total_bold": "",
    # الهيدر واللوجو وبيانات الشركة
    "logo_size": "", "logo_align": "", "show_logo": "",
    "header_bg": "",
    "company_color": "", "company_size": "",
    "meta_color": "", "meta_size": "",
    "show_company_tax": "", "show_company_cr": "", "show_company_addr": "",
    # عنوان المستند وبطاقة العميل
    "title_color": "", "title_size": "",
    "cust_card_bg": "", "cust_color": "",
    "show_cust_tax": "", "show_cust_cr": "", "show_cust_addr": "", "show_cust_phone": "",
    # صندوق المبالغ والذيل (Footer) وشروط الطباعة
    "total_bg": "", "total_label_bg": "",
    "footer_text": "", "footer_color": "", "footer_bg": "", "footer_size": "",
    "show_footer": "", "terms_text": "",
}

_QR_BLOCK_RE = re.compile(
    r"<div[^>]*>\s*<img[^>]*inv-qr[^>]*>\s*(?:<div[^>]*>.*?</div>\s*)?</div>",
    re.DOTALL | re.IGNORECASE,
)


def parse_tpl_style(html: str) -> dict:
    """استخراج إعدادات المحرر المرئي من تعليق TPL_STYLE (مع الدمج مع الافتراضي)."""
    style = dict(DEFAULT_TPL_STYLE)
    if not html:
        return style
    try:
        m = _TPL_STYLE_RE.search(html)
        if m:
            data = json.loads(m.group(1).strip())
            if isinstance(data, dict):
                for k in style:
                    if data.get(k) not in (None, ""):
                        style[k] = str(data[k]).strip()
    except Exception:
        pass
    return style


def _esc(v: str) -> str:
    return re.sub(r"[<>\"';]", "", str(v or ""))[:20]


def _esc_text(v: str, cap: int = 400) -> str:
    """تهريب نص يُحقن كمحتوى HTML (نصوص التذييل/الشروط) — وليس قيمة CSS."""
    import html as _htmllib
    return _htmllib.escape(str(v or ""), quote=True)[:cap]


def tpl_style_css(s: dict) -> str:
    """بناء CSS override من إعدادات المحرر المرئي (محددات عامة لكل القوالب)."""
    css: list[str] = []
    if s.get("th_bg"):
        css.append("table thead th,table thead td{background:" + _esc(s["th_bg"]) + " !important}")
    if s.get("th_color"):
        css.append("table thead th,table thead td{color:" + _esc(s["th_color"]) + " !important}")
    if s.get("th_size"):
        css.append("table thead th{font-size:" + _esc(s["th_size"]) + "px !important}")
    if s.get("th_bold") in ("1", "0"):
        w = "800" if s["th_bold"] == "1" else "400"
        css.append("table thead th{font-weight:" + w + " !important}")
    if s.get("alt_bg"):
        css.append("table tbody tr:nth-child(even) td{background:" + _esc(s["alt_bg"]) + " !important}")
    if s.get("border_width"):
        css.append("table th,table td{border-width:" + _esc(s["border_width"]) + "px !important}")
    if s.get("border_color"):
        css.append("table,table th,table td{border-color:" + _esc(s["border_color"]) + " !important}")
    if s.get("border_style") in ("solid", "dashed", "dotted", "double"):
        css.append("table th,table td{border-style:" + s["border_style"] + " !important}")
    if s.get("cell_padding"):
        css.append("table th,table td{padding:" + _esc(s["cell_padding"]) + "px !important}")
    if s.get("header_color"):
        css.append("h1,h2,.e2-t-ar,.e2-company{color:" + _esc(s["header_color"]) + " !important}")
    if s.get("header_size"):
        css.append(".e2-t-ar{font-size:" + _esc(s["header_size"]) + "px !important}")
    if s.get("header_bold") in ("1", "0"):
        w2 = "800" if s["header_bold"] == "1" else "400"
        css.append("h1,h2,.e2-t-ar,.e2-company{font-weight:" + w2 + " !important}")
    if s.get("body_color"):
        css.append("body{color:" + _esc(s["body_color"]) + " !important}")
    if s.get("body_size"):
        css.append("body,table tbody td{font-size:" + _esc(s["body_size"]) + "px !important}")
    if s.get("total_color"):
        css.append("td.num{color:" + _esc(s["total_color"]) + " !important}")
    if s.get("total_size"):
        css.append("td.num{font-size:" + _esc(s["total_size"]) + "px !important}")
    if s.get("total_bold") in ("1", "0"):
        w3 = "800" if s["total_bold"] == "1" else "400"
        css.append("td.num{font-weight:" + w3 + " !important}")
    # ── الهيدر واللوجو وبيانات الشركة ──
    if s.get("logo_size"):
        lz = _esc(s["logo_size"])
        css.append(".tpl-logo{width:" + lz + "mm !important;max-width:" + lz
                   + "mm !important;max-height:" + lz + "mm !important;height:auto !important}")
    if s.get("logo_align") in ("right", "center", "left"):
        css.append(".tpl-logo-wrap{text-align:" + s["logo_align"] + " !important}")
    if s.get("header_bg"):
        css.append(".tpl-header{background:" + _esc(s["header_bg"]) + " !important}")
    if s.get("company_color"):
        css.append(".tpl-company{color:" + _esc(s["company_color"]) + " !important}")
    if s.get("company_size"):
        css.append(".tpl-company{font-size:" + _esc(s["company_size"]) + "px !important}")
    if s.get("meta_color"):
        css.append(".tpl-meta{color:" + _esc(s["meta_color"]) + " !important}")
    if s.get("meta_size"):
        css.append(".tpl-meta{font-size:" + _esc(s["meta_size"]) + "px !important}")
    # ── عنوان المستند وبطاقة العميل ──
    if s.get("title_color"):
        t = _esc(s["title_color"])
        css.append(".tpl-title{color:" + t + " !important;border-color:" + t + " !important}")
        css.append(".tpl-title-badge{background:" + t + " !important;border-color:" + t + " !important}")
    if s.get("title_size"):
        css.append(".tpl-title,.tpl-title-badge{font-size:" + _esc(s["title_size"]) + "px !important}")
    if s.get("cust_card_bg"):
        css.append(".tpl-cust{background:" + _esc(s["cust_card_bg"]) + " !important}")
    if s.get("cust_color"):
        css.append(".tpl-cust{color:" + _esc(s["cust_color"]) + " !important}")
    # ── لون نص صفوف البنود ──
    if s.get("row_color"):
        css.append("table tbody td{color:" + _esc(s["row_color"]) + " !important}")
    # ── صندوق المبالغ ──
    if s.get("total_bg"):
        css.append(".tpl-gtotal td,.tpl-gtotal{background:" + _esc(s["total_bg"]) + " !important}")
    if s.get("total_label_bg"):
        css.append("table td.lbl{background:" + _esc(s["total_label_bg"]) + " !important}")
    # ── الذيل (Footer) وشروط الطباعة ──
    if s.get("footer_color"):
        css.append(".tpl-foot,.tpl-footer-custom{color:" + _esc(s["footer_color"]) + " !important}")
    if s.get("footer_bg"):
        css.append(".tpl-foot,.tpl-footer-custom{background:" + _esc(s["footer_bg"]) + " !important}")
    if s.get("footer_size"):
        css.append(".tpl-foot,.tpl-footer-custom{font-size:" + _esc(s["footer_size"]) + "px !important}")
    if s.get("show_footer") == "1":
        css.append(".tpl-foot{display:none !important}")
    try:
        qz = int(s.get("qr_size") or 54)
    except (TypeError, ValueError):
        qz = 54
    qz = max(30, min(80, qz))
    css.append("img.inv-qr{width:" + str(qz) + "mm !important;height:" + str(qz) + "mm !important}")
    pos = (s.get("qr_position") or "below_totals").strip()
    if pos == "hidden":
        css.append(".tpl-qr-pos,img.inv-qr{display:none !important}")
    elif pos in ("footer_left", "footer_right", "footer_center"):
        align = {"footer_left": "left", "footer_right": "right"}.get(pos, "center")
        css.append(".tpl-qr-pos{text-align:" + align + " !important;margin:4mm 0 0 !important}")
        css.append(".tpl-qr-pos img.inv-qr{margin:0 !important;display:inline-block !important}")
    elif pos == "header_side":
        css.append(".tpl-qr-pos{text-align:left !important;margin:0 0 3mm !important}")
        css.append(".tpl-qr-pos img.inv-qr{margin:0 !important;display:inline-block !important;width:38mm !important;height:38mm !important}")
    elif pos == "header_top":
        css.append(".tpl-qr-pos{text-align:center !important;margin:0 0 3mm !important}")
        css.append(".tpl-qr-pos img.inv-qr{margin:0 auto !important}")
    return "".join(css)


def _move_qr_block(html: str, pos: str) -> str:
    """نقل كتلة QR بعد التصيير إلى الهيدر أو الذيل حسب اختيار المحرر."""
    if pos in (None, "", "below_totals", "hidden"):
        return html
    m = _QR_BLOCK_RE.search(html)
    if not m:
        return html
    block = m.group(0)
    html_wo = html[:m.start()] + html[m.end():]
    wrap = '<div class="tpl-qr-pos tpl-qr-' + pos + '">' + block + "</div>"
    low = html_wo.lower()
    if pos in ("header_top", "header_side"):
        bi = low.find("<body")
        if bi != -1:
            end = html_wo.find(">", bi)
            if end != -1:
                return html_wo[:end + 1] + wrap + html_wo[end + 1:]
        return wrap + html_wo
    bi = low.rfind("</body>")
    if bi != -1:
        return html_wo[:bi] + wrap + html_wo[bi:]
    return html_wo + wrap


def _theme_font_html(theme: dict) -> str:
    """لينك خط Google + تجاوز CSS للخط وحجمه — يُطبق على كل المستندات."""
    fam = (theme.get("font_family") or "Cairo").strip() or "Cairo"
    try:
        size = int(theme.get("font_size") or 13)
    except (TypeError, ValueError):
        size = 13
    link = ""
    if fam in _FONT_LINKS:
        link = (f'<link href="https://fonts.googleapis.com/css2'
                f'?family={_FONT_LINKS[fam]}&display=swap" rel="stylesheet">')
    css = (f"<style>body{{font-family:'{fam}','Noto Sans Arabic','Segoe UI',"
           f"Tahoma,sans-serif !important;font-size:{size}px !important;}}</style>")
    return link + css


# ─ تثبيت باركود الفاتورة أسفل «المبلغ كتابةً» في كل القوالب ──
# أُلغي خيار «موقع الباركود»: الموضع موحّد الآن (وسط الأسفل أسفل المبلغ كتابةً) وهو
# الموضع المثالي للطباعة، والصور تُولَّد بتباين كامل (أسود/أبيض) وحدّة عالية.
_QR_FIXED_CSS = (
    "<style>"
    "img.inv-qr{display:block !important;image-rendering:pixelated;image-rendering:crisp-edges;"
    "-ms-interpolation-mode:nearest-neighbor;margin:3mm auto 0 !important;"
    "background:#ffffff !important;"
    "visibility:visible !important;opacity:1 !important;"
    "page-break-inside:avoid;break-inside:avoid;}"
    "@media print{"
    "*{-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;}"
    "img.inv-qr{width:54mm !important;height:54mm !important;object-fit:contain;"
    "background:#ffffff !important;}"
    "}"
    "</style>"
)


def _apply_tpl_style_ctx(ctx: dict, ts: dict) -> None:
    """تطبيق مفاتيح الإظهار/الإخفاء على سياق العرض: تفريغ القيمة يجعل الصفوف
    الشرطية {% if %} في أي قالب (فواتير وسندات) تخفي العنصر تلقائيًا."""
    comp = ctx.get("company")
    if isinstance(comp, dict):
        if ts.get("show_logo") == "1":
            comp["logo_data_uri"] = ""
        if ts.get("show_company_tax") == "1":
            comp["tax_number"] = ""
        if ts.get("show_company_cr") == "1":
            comp["cr_number"] = ""
        if ts.get("show_company_addr") == "1":
            comp["address"] = ""
    cust = ctx.get("customer")
    if isinstance(cust, dict):
        for flag, key in (("show_cust_tax", "tax_number"), ("show_cust_cr", "cr_number"),
                          ("show_cust_addr", "address"), ("show_cust_phone", "phone")):
            if ts.get(flag) == "1":
                cust[key] = ""


def _custom_footer_html(s: dict) -> str:
    """تذييل مخصص + شروط طباعة يُحقنان نهاية المستند من إعدادات المحرر المرئي."""
    parts: list[str] = []
    terms = (s.get("terms_text") or "").strip()
    ftext = (s.get("footer_text") or "").strip()
    if terms or ftext:
        parts.append(
            "<style>.tpl-terms{margin-top:4mm;padding-top:2mm;border-top:1px dashed #94a3b8;"
            "font-size:10.5px;color:#475569;text-align:center;line-height:1.7}"
            ".tpl-footer-custom{margin-top:3mm;padding:2mm 3mm;border-radius:6px;"
            "text-align:center;font-weight:700;line-height:1.7}</style>"
        )
    if terms:
        parts.append('<div class="tpl-terms">📄 شروط الطباعة: ' + _esc_text(terms) + "</div>")
    if ftext:
        parts.append('<div class="tpl-footer-custom">' + _esc_text(ftext) + "</div>")
    return "".join(parts)


def _inject_theme_overrides(html, theme, tpl_style=None):
    # إزالة كتلة TPL_STYLE من الناتج النهائي (إعدادات المحرر لا تُطبع)
    html = _TPL_STYLE_RE.sub("", html)
    frags = [_theme_font_html(theme), _QR_FIXED_CSS]
    if tpl_style:
        css = tpl_style_css(tpl_style)
        if css:
            frags.append("<style>" + css + "</style>")
    frag = "".join(frags)
    low = html.lower()
    if "</head>" in low:
        i = low.rindex("</head>")
        html = html[:i] + frag + html[i:]
    else:
        html = frag + html
    # تذييل مخصص + شروط الطباعة (تُحقن نهاية المستند قبل إغلاق body)
    if tpl_style:
        cf = _custom_footer_html(tpl_style)
        if cf:
            low = html.lower()
            bi = low.rfind("</body>")
            if bi != -1:
                html = html[:bi] + cf + html[bi:]
            else:
                html = html + cf
    return html



def _logo_data_uri(path: str) -> str:
    """تحويل مسار الشعار إلى Data URI (يعمل في المتصفح وPDF)."""
    if not path:
        return ""
    p = Path(path)
    if not p.is_absolute():
        p = dbm.UPLOAD_DIR / p
    if not p.exists():
        return ""
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _fmt_date(s: str) -> str:
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return s or ""


def _company_ctx(row) -> dict:
    return {
        "name": row["name"],
        "address": row["address"] or "",
        "tax_number": row["tax_number"] or "",
        "cr_number": row["cr_number"] or "",
        "color": row["color"] or "#0e7490",
        "logo_data_uri": _logo_data_uri(row["logo_path"] or ""),
    }


def _customer_ctx(row) -> dict:
    return {
        "name": row["name"] if row else "",
        "address": (row["address"] if row else "") or "",
        "tax_number": (row["tax_number"] if row else "") or "",
        # السجل التجاري: يُعرض في الفاتورة والطباعة فقط إذا كان مكتوبًا (يُخفى تمامًا إذا فرغ)
        "cr_number": ((row["cr_number"] if "cr_number" in row.keys() else "") if row else "") or "",
        "phone": (row["phone"] if row else "") or "",
    }


def invoice_context(conn, inv_row, built_inv=None) -> dict:
    """سياق جاهز لتمريره إلى قالب الفاتورة.
    built_inv: كائن BuiltInvoice من المحرك (معاينة بدون تخزين) — يستبدل قراءة الأسطر من القاعدة."""
    company = conn.execute("SELECT * FROM companies WHERE id=?",
                           (inv_row["company_id"],)).fetchone()
    customer = conn.execute("SELECT * FROM customers WHERE id=?",
                            (inv_row["customer_id"],)).fetchone()

    if built_inv is not None:
        lines = [{
            "name": ln.item.name,
            "code": ln.item.code,
            "unit": ln.item.unit or "حبة",
            "quantity": int(ln.display_quantity),
            "quantity_display": str(int(ln.display_quantity)),
            "unit_price_display": fmt_money(ln.item.price),
            "line_net_display": fmt_money(ln.net),
            "line_tax_display": fmt_money(ln.tax),
            "line_gross_display": fmt_money(ln.gross),
            "group_name": getattr(ln.item, "group_name", "") or "",
        } for ln in built_inv.lines]
    else:
        item_rows = conn.execute(
            "SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id", (inv_row["id"],)
        ).fetchall()
        lines = []
        for r in item_rows:
            it = conn.execute(
                """SELECT i.code, i.unit, g.name AS group_name
                   FROM items i LEFT JOIN item_groups g ON g.id=i.group_id
                   WHERE i.id=?""", (r["item_id"],)
            ).fetchone()
            qty_int = int(r["quantity"])
            # وحدة الصنف ديناميكيًا: الوحدة المحفوظة مع سطر الفاتورة أولًا (تسمح بوحدات
            # حرة في الفواتير اليدوية) ثم وحدة الصنف المرتبط في قاعدة البيانات
            stored_unit = ((r["unit"] if "unit" in r.keys() else "") or "").strip()
            item_unit = ((it["unit"] if it else "") or "").strip()
            lines.append({
                "name": r["item_name"],
                "code": (it["code"] if it else "") or "",
                "unit": stored_unit or item_unit or "حبة",
                "quantity": qty_int,
                "quantity_display": str(qty_int),
                "unit_price_display": fmt_money(to_halalas(r["unit_price"])),
                "line_net_display": fmt_money(to_halalas(r["line_total"])),
                "line_tax_display": fmt_money(to_halalas(r["line_tax"])),
                "line_gross_display": fmt_money(to_halalas(r["line_gross"])),
                "group_name": (it["group_name"] if it else "") or "",
            })

    total_halalas = to_halalas(inv_row["total_amount"])
    qr_mode = inv_row["qr_mode"] or "none"
    theme = dbm.get_theme(conn)
    return {
        "company": _company_ctx(company) if company else {"name": "", "address": "", "tax_number": "", "cr_number": "", "color": "#0e7490", "logo_data_uri": ""},
        "customer": _customer_ctx(customer),
        "inv": {
            "id": inv_row["id"],
            "number": inv_row["invoice_number"],
            "date_display": _fmt_date(inv_row["invoice_date"]),
            "time_display": inv_row["invoice_time"] or "",
            "payment_type": inv_row["payment_type"] or "نقدي",
            "notes": inv_row["notes"] or "",
            "lines": lines,
            "subtotal_display": fmt_money(to_halalas(inv_row["subtotal"])),
            "tax_display": fmt_money(to_halalas(inv_row["tax_amount"])),
            "total_display": fmt_money(total_halalas),
            "total_halalas": total_halalas,
            "total_words": tafqit_money(total_halalas),
            "qr_img": qr_image_data_uri(inv_row["qr_payload_b64"] or ""),
            "qr_note": qr_note_for(qr_mode) if (inv_row["qr_payload_b64"] or "") else "",
            # موضع الباركود ثابت في كل القوالب: أسفل «المبلغ كتابةً»
            "qr_pos": "inplace",
        },
        "doc_title": "فاتورة ضريبية",
        "theme": theme,
        "watermark_text": theme["watermark_text"],
        "footer_notice": theme["footer_notice"],
        "generated_note": "مولّد الفواتير التدريبي — إتقان",
    }

def receipt_context(conn, rc_row) -> dict:
    """سياق جاهز لتمريره إلى قالب السند."""
    company = conn.execute("SELECT * FROM companies WHERE id=?",
                           (rc_row["company_id"],)).fetchone()
    customer = conn.execute("SELECT * FROM customers WHERE id=?",
                            (rc_row["customer_id"],)).fetchone()
    total_halalas = to_halalas(rc_row["amount"])
    related = None
    if rc_row["related_invoice_id"]:
        related = conn.execute("SELECT invoice_number FROM invoices WHERE id=?",
                               (rc_row["related_invoice_id"],)).fetchone()
    theme = dbm.get_theme(conn)
    return {
        "company": _company_ctx(company) if company else {"name": "", "address": "", "tax_number": "", "cr_number": "", "color": "#0e7490", "logo_data_uri": ""},
        "customer": _customer_ctx(customer),
        "rc": {
            "id": rc_row["id"],
            "number": rc_row["receipt_number"],
            "type": rc_row["type"],
            "doc_title": f"سند {rc_row['type']}",
            "date_display": _fmt_date(rc_row["receipt_date"]),
            "time_display": rc_row["receipt_time"] or "",
            "amount_display": fmt_money(total_halalas),
            "amount_words": tafqit_money(total_halalas),
            "related_invoice": related["invoice_number"] if related else "",
            "notes": rc_row["notes"] or "",
        },
        "doc_title": f"سند {rc_row['type']}",
        "theme": theme,
        "watermark_text": theme["watermark_text"],
        "footer_notice": theme["footer_notice"],
        "generated_note": "مولّد الفواتير التدريبي — إتقان",
    }


def _template_content(conn, template_id: int | None, kind: str) -> str:
    if template_id:
        row = conn.execute("SELECT html_content FROM templates WHERE id=?",
                           (template_id,)).fetchone()
        if row:
            return row["html_content"]
    row = conn.execute(
        "SELECT html_content FROM templates WHERE type=? ORDER BY id LIMIT 1", (kind,)
    ).fetchone()
    return row["html_content"] if row else _fallback_template(kind)


def _fallback_template(kind: str) -> str:
    return dbm._default_template(kind)


def _sample_qr_ctx() -> tuple[str, str]:
    """(qr_img_data_uri, qr_note) نموذجيان لمعاينة القوالب — وسوم 1-5."""
    import base64
    from zatca_qr import tlv
    from app.qr_service import qr_image_data_uri, qr_note_for
    payload = base64.b64encode(
        tlv(1, "شركة ركن الهلال للأقمشة") + tlv(2, "311187605900003")
        + tlv(3, "2026-08-12T10:30:45Z") + tlv(4, "400.09") + tlv(5, "52.19")
    ).decode("ascii")
    return qr_image_data_uri(payload), qr_note_for("simple")


def render_sample(template_html: str, kind: str = "invoice") -> str:
    """معاينة قالب ببيانات نموذجية (بدون قاعدة بيانات) — لشاشة القوالب."""
    from flask import render_template_string

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
    total = 34790    # 347.90 ريال بالهللة
    _qr_img, _qr_note = _sample_qr_ctx()
    ctx = {
        "company": {
            "name": "شركة ركن الهلال للأقمشة",
            "address": "الرياض - حي الصناعية الجديدة، شارع الأولين",
            "tax_number": "311187605900003", "cr_number": "1010473355",
            "color": "#0e7490", "logo_data_uri": "",
        },
        "customer": {
            "name": "شركة الواحة للمقاولات",
            "address": "الرياض - حي الملقا",
            "tax_number": "310982736500003", "cr_number": "1010223344",
            "phone": "0555102938",
        },
        "inv": {
            "id": 0, "number": "1023", "date_display": "12/08/2026",
            "time_display": "10:30:45", "payment_type": "آجل",
            "notes": "دفعة تحت الحساب", "lines": lines,
            "subtotal_display": "347.90", "tax_display": "52.19",
            "total_display": "400.09", "total_halalas": total,
            "total_words": tafqit_money(total),
            "qr_img": _qr_img, "qr_note": _qr_note,
        } if kind == "invoice" else {},
        "rc": {
            "id": 0, "number": "5001", "type": "قبض",
            "doc_title": "سند قبض", "date_display": "12/08/2026",
            "time_display": "11:05:00", "amount_display": "400.09",
            "amount_words": tafqit_money(total),
            "related_invoice": "1023", "notes": "سند مرافق للفاتورة رقم 1023",
        } if kind == "receipt" else {},
        "doc_title": "فاتورة ضريبية" if kind == "invoice" else "سند قبض",
        "theme": dict(dbm.THEME_DEFAULTS),
        "watermark_text": dbm.THEME_DEFAULTS["watermark_text"],
        "footer_notice": dbm.THEME_DEFAULTS["footer_notice"],
        "generated_note": "مولّد الفواتير التدريبي — إتقان",
        "standalone": True,
    }
    ts = parse_tpl_style(template_html)
    _apply_tpl_style_ctx(ctx, ts)
    html = render_template_string(template_html, **ctx)
    injected = _inject_theme_overrides(html, ctx["theme"], ts)
    return _move_qr_block(injected, ts.get("qr_position", "below_totals"))


def render_invoice(conn, inv_row, template_html: str | None = None, built_inv=None) -> str:
    ctx = invoice_context(conn, inv_row, built_inv)
    ctx["standalone"] = True
    from flask import render_template_string
    tpl = template_html or _template_content(conn, inv_row["template_id"], "invoice")
    ts = parse_tpl_style(tpl)
    _apply_tpl_style_ctx(ctx, ts)
    out = render_template_string(tpl, **ctx)
    injected = _inject_theme_overrides(out, ctx["theme"], ts)
    return _move_qr_block(injected, ts.get("qr_position", "below_totals"))


def render_receipt(conn, rc_row, template_html: str | None = None) -> str:
    ctx = receipt_context(conn, rc_row)
    ctx["standalone"] = True
    from flask import render_template_string
    tpl = template_html or _template_content(conn, rc_row["template_id"], "receipt")
    ts = parse_tpl_style(tpl)
    _apply_tpl_style_ctx(ctx, ts)
    out = render_template_string(tpl, **ctx)
    injected = _inject_theme_overrides(out, ctx["theme"], ts)
    # دعم موضع الباركود في السندات أيضًا (لا أثر له إذا كان القالب بلا QR)
    return _move_qr_block(injected, ts.get("qr_position", "below_totals"))


def render_combined(conn, kind: str, rows: list) -> str:
    """دمج عدة مستندات في HTML واحد (كل مستند في صفحة مستقلة)."""
    bodies: list[str] = []
    styles: list[str] = []
    font_links: list[str] = []
    seen_styles: set[str] = set()
    seen_links: set[str] = set()
    for row in rows:
        html = render_invoice(conn, row) if kind == "invoice" else render_receipt(conn, row)
        for style in _STYLE_RE.findall(html):
            if style not in seen_styles:
                seen_styles.add(style)
                styles.append(style)
        for link in _FONT_LINK_RE.findall(html):
            if link not in seen_links:
                seen_links.add(link)
                font_links.append(link)
        m = _BODY_RE.search(html)
        bodies.append(m.group(1) if m else html)
    inner = "<div class='export-doc'>" + "</div><div class='export-doc'>".join(bodies) + "</div>"
    return (
        "<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
        "<title>مستندات تدريبية</title>"
        + "".join(font_links)
        + "".join(f"<style>{s}</style>" if not s.lower().startswith("<style") else s for s in styles)
        + "<style>.export-doc{page-break-after:always;} .export-doc:last-child{page-break-after:auto;}</style>"
        + "</head><body>" + inner + "</body></html>"
    )


