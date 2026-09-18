# -*- coding: utf-8 -*-
"""
محمّل القوالس المحترفة — استيراد القوالس من invoice-templates إلى قاعدة البيانات
Professional Templates Loader
"""
import sqlite3
from pathlib import Path

def get_professional_templates():
    """الحصول على قائمة القوالس المحترفة المتاحة"""
    templates_dir = Path(__file__).resolve().parent.parent / "invoice-templates"

    return [
        {
            "name": "قالب الشركات الاحترافي",
            "filename": "corporate-minimal.html",
            "type": "invoice",
            "description": "تصميم احترافي وبسيط مع رأس عصري وبيانات بنكية"
        },
        {
            "name": "قالب حديث",
            "filename": "modern-card.html",
            "type": "invoice",
            "description": "تصميم عصري مع رأس متدرج وبطاقات ورمز QR"
        },
        {
            "name": "قالب تقليدي رسمي",
            "filename": "classic-formal.html",
            "type": "invoice",
            "description": "تصميم تقليدي مع خطوط توقيع وشروط وأحكام"
        },
        {
            "name": "قالب الإيصالات",
            "filename": "compact-thermal.html",
            "type": "receipt",
            "description": "تصميم مضغوط لطابعات الإيصالات الحرارية (80 ملم)"
        },
    ]


def load_template_content(filename: str) -> str:
    """تحميل محتوى ملف قالب HTML"""
    templates_dir = Path(__file__).resolve().parent.parent / "invoice-templates"
    template_path = templates_dir / filename

    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return ""


def seed_professional_templates(conn: sqlite3.Connection) -> None:
    """
    زرع القوالس المحترفة الجديدة من invoice-templates
    Professional Templates Seeding — Load from invoice-templates directory
    """
    cur = conn.cursor()

    for template_info in get_professional_templates():
        name = template_info["name"]
        filename = template_info["filename"]
        ttype = template_info["type"]

        # تحميل محتوى الملف
        content = load_template_content(filename)

        if not content:
            print(f"⚠ تحذير: لم يتمكن من تحميل {filename}")
            continue

        # التحقق من وجود القالب بالفعل
        existing = cur.execute(
            "SELECT id FROM templates WHERE name=? AND type=?",
            (name, ttype)
        ).fetchone()

        if existing:
            # تحديث القالب الموجود
            cur.execute(
                "UPDATE templates SET html_content=? WHERE name=? AND type=?",
                (content, name, ttype)
            )
            print(f"✅ تم تحديث: {name}")
        else:
            # إنشاء قالب جديد
            cur.execute(
                "INSERT INTO templates (name, type, html_content) VALUES (?,?,?)",
                (name, ttype, content)
            )
            print(f"✨ تم إضافة: {name}")

    conn.commit()


def get_templates_info() -> dict:
    """الحصول على معلومات تفصيلية عن القوالس المحترفة"""
    return {
        "corporate-minimal": {
            "name_ar": "قالب الشركات الاحترافي",
            "name_en": "Corporate Minimal",
            "type": "invoice",
            "description_ar": "تصميم احترافي وبسيط مع رأس عصري وبيانات بنكية",
            "description_en": "Professional corporate design with modern header and bank details",
            "use_cases": ["B2B transactions", "Corporate invoices", "Standard business"],
            "features": ["Blue/Gray colors", "Professional layout", "VAT breakdown", "Bank details"],
            "file_size_kb": 12,
        },
        "modern-card": {
            "name_ar": "قالب حديث",
            "name_en": "Modern Card",
            "type": "invoice",
            "description_ar": "تصميم عصري مع رأس متدرج وبطاقات ورمز QR",
            "description_en": "Contemporary design with gradient header, cards, and QR code",
            "use_cases": ["Tech companies", "E-commerce", "Modern startups", "Digital-first"],
            "features": ["Gradient header", "Card layout", "QR code", "Responsive grid"],
            "file_size_kb": 14,
        },
        "classic-formal": {
            "name_ar": "قالب تقليدي رسمي",
            "name_en": "Classic Formal",
            "type": "invoice",
            "description_ar": "تصميم تقليدي مع خطوط توقيع وشروط وأحكام",
            "description_en": "Traditional formal layout with signature lines and T&C section",
            "use_cases": ["Government contracts", "Formal agreements", "Legal transactions", "Regulated"],
            "features": ["Heavy borders", "Signature blocks", "T&C section", "Formal appearance"],
            "file_size_kb": 16,
        },
        "compact-thermal": {
            "name_ar": "قالب الإيصالات",
            "name_en": "Compact Thermal",
            "type": "receipt",
            "description_ar": "تصميم مضغوط لطابعات الإيصالات الحرارية (80 ملم)",
            "description_en": "Receipt-style format optimized for 80mm thermal printers",
            "use_cases": ["Retail", "Restaurants", "Point-of-Sale", "Thermal printing"],
            "features": ["80mm width", "Monospace font", "QR code", "Receipt format"],
            "file_size_kb": 13,
        },
    }
