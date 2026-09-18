#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت محمّل القوالس المحترفة
Professional Templates Loader Script

الاستخدام:
  python load_professional_templates.py

يقوم بتحميل القوالس المحترفة الجديدة من invoice-templates إلى قاعدة البيانات.
"""

import sys
from pathlib import Path

# إضافة مسار التطبيق
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from app import db as dbm
from app.templates_loader import seed_professional_templates, get_professional_templates


def main():
    print("=" * 70)
    print("🚀 محمّل القوالس المحترفة — Professional Templates Loader")
    print("=" * 70)
    print()

    # التحقق من وجود ملفات القوالس
    print("📂 التحقق من ملفات القوالس...")
    templates_dir = BASE_DIR / "invoice-templates"

    if not templates_dir.exists():
        print(f"❌ خطأ: لم يتم العثور على مجلد {templates_dir}")
        return 1

    print(f"✅ تم العثور على: {templates_dir}")
    print()

    # عرض قائمة القوالس المتاحة
    print("📋 القوالس المتاحة:")
    templates = get_professional_templates()
    for i, tpl in enumerate(templates, 1):
        filename = tpl["filename"]
        filepath = templates_dir / filename
        exists = "✅" if filepath.exists() else "❌"
        size = f"{filepath.stat().st_size / 1024:.1f} KB" if filepath.exists() else "N/A"
        print(f"  {i}. {exists} {tpl['name']}")
        print(f"     └─ {filename} ({size})")

    print()

    # الاتصال بقاعدة البيانات
    print("🔌 الاتصال بقاعدة البيانات...")
    try:
        conn = dbm.connect()
        print(f"✅ تم الاتصال بـ: {dbm.DB_PATH}")
        print()
    except Exception as e:
        print(f"❌ خطأ في الاتصال: {e}")
        return 1

    # تحميل القوالس
    print("⏳ جاري تحميل القوالس...")
    print("-" * 70)
    try:
        seed_professional_templates(conn)
        print("-" * 70)
        print("✅ تمت عملية التحميل بنجاح!")
        print()

        # عرض الإحصائيات
        cur = conn.cursor()
        total = cur.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
        invoices = cur.execute("SELECT COUNT(*) FROM templates WHERE type='invoice'").fetchone()[0]
        receipts = cur.execute("SELECT COUNT(*) FROM templates WHERE type='receipt'").fetchone()[0]

        print("📊 إحصائيات قاعدة البيانات:")
        print(f"  • إجمالي القوالس: {total}")
        print(f"  • قوالس الفواتير: {invoices}")
        print(f"  • قوالس الإيصالات: {receipts}")
        print()

        # عرض قائمة القوالس في قاعدة البيانات
        print("📑 القوالس في قاعدة البيانات:")
        rows = cur.execute("SELECT id, name, type FROM templates ORDER BY type, name").fetchall()
        for row in rows:
            ttype = "🧾 فاتورة" if row[2] == "invoice" else "📄 سند"
            print(f"  {ttype} [{row[0]:2d}] {row[1]}")

        conn.close()
        print()
        print("=" * 70)
        print("🎉 اكتملت العملية! القوالس جاهزة للاستخدام.")
        print("=" * 70)
        return 0

    except Exception as e:
        print(f"❌ خطأ أثناء التحميل: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
