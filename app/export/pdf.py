# -*- coding: utf-8 -*-
"""
تحويل HTML إلى PDF:
  1) WeasyPrint إن كانت مثبتة وتعمل (تتطلب مكتبات GTK/Pango على Windows).
  2) وإلا Microsoft Edge (أو Chrome) بوضع headless — متوفر على كل أنظمة Windows
     الحديثة ويدعم العربية بشكل ممتاز.
مع تصدير: ملف PDF واحد مجمّع، أو ملفات منفصلة داخل ZIP.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

from app import db as dbm
from app.export import render as rnd

CREATE_NO_WINDOW = 0x08000000  # إخفاء نافذة العملية على Windows

_ENGINE_USED = "?"

_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def browser_exe() -> str | None:
    for cand in _EDGE_CANDIDATES:
        if Path(cand).exists():
            return cand
    return None


def _try_weasyprint(html: str, out_pdf: Path) -> bool:
    global _ENGINE_USED
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return False
    try:
        HTML(string=html, base_url=str(dbm.BASE_DIR)).write_pdf(str(out_pdf))
        _ENGINE_USED = "weasyprint"
        return out_pdf.exists() and out_pdf.stat().st_size > 500
    except Exception:
        return False


def _with_browser(html: str, out_pdf: Path) -> bool:
    global _ENGINE_USED
    exe = browser_exe()
    if not exe:
        return False
    tmp_html = dbm.TMP_DIR / f"doc_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.html"
    tmp_html.write_text(html, encoding="utf-8")
    profile = Path(tempfile.mkdtemp(prefix="browser_prof_"))   # عزل العملية (منع تسليم المثيل القائم)
    try:
        cmd = [
            exe, f"--user-data-dir={profile}", "--headless", "--disable-gpu",
            "--no-first-run", "--no-pdf-header-footer", "--disable-extensions",
            f"--print-to-pdf={out_pdf}",
            tmp_html.as_uri(),
        ]
        for attempt in range(3):
            subprocess.run(cmd, timeout=240, capture_output=True, creationflags=CREATE_NO_WINDOW)
            if _valid_pdf(out_pdf):
                break
            time.sleep(1.2)      # إعادة المحاولة عند فشل كتابة الملف
    finally:
        try:
            tmp_html.unlink(missing_ok=True)
        except OSError:
            pass
        shutil.rmtree(profile, ignore_errors=True)
    _ENGINE_USED = "edge" if "msedge" in exe.lower() else "chrome"
    return _valid_pdf(out_pdf)


def _valid_pdf(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size > 500 and path.read_bytes()[:5] == b"%PDF-"
    except OSError:
        return False


def html_to_pdf(html: str, out_pdf: Path) -> Path:
    """تحويل HTML إلى PDF عبر WeasyPrint ثم Edge كبديل. يرفع خطأ عند الفشل."""
    out_pdf = Path(out_pdf)
    if _try_weasyprint(html, out_pdf):
        return out_pdf
    if _with_browser(html, out_pdf):
        return out_pdf
    raise RuntimeError(
        "تعذر توليد PDF: لا WeasyPrint مثبتة ولا متصفح Edge/Chrome متاح. "
        "ثبّت WeasyPrint أو Microsoft Edge."
    )

def _safe_name(base: str) -> str:
    """تنظيف اسم الملف من المحارف الممنوعة في Windows."""
    return re.sub(r'[\\/:*?"<>|]+', "-", base).strip() or "doc"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def export_single_pdf(conn, kind: str, row) -> Path:
    """تصدير مستند واحد إلى PDF — يعيد مسار الملف."""
    html = rnd.render_invoice(conn, row) if kind == "invoice" else rnd.render_receipt(conn, row)
    if kind == "invoice":
        name = f"فاتورة_{row['invoice_number']}"
    else:
        name = f"سند_{row['type']}_{row['receipt_number']}"
    out = dbm.EXPORT_DIR / f"{_safe_name(name)}.pdf"
    return html_to_pdf(html, out)


def export_combined_pdf(conn, kind: str, rows: list, label: str = "مستندات") -> Path:
    """تصدير عدة مستندات في ملف PDF واحد."""
    if not rows:
        raise ValueError("لا توجد مستندات للتصدير")
    html = rnd.render_combined(conn, kind, rows)
    out = dbm.EXPORT_DIR / f"{_safe_name(label)}_{_stamp()}.pdf"
    return html_to_pdf(html, out)


def export_zip(conn, kind: str, rows: list, label: str = "مستندات") -> Path:
    """تصدير كل مستند في ملف PDF مستقل ثم ضغطها في ZIP واحد."""
    if not rows:
        raise ValueError("لا توجد مستندات للتصدير")
    pdf_paths: list[Path] = []
    for row in rows:
        pdf_paths.append(export_single_pdf(conn, kind, row))
    zip_path = dbm.EXPORT_DIR / f"{_safe_name(label)}_منفصلة_{_stamp()}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in pdf_paths:
            zf.write(p, arcname=p.name)
    return zip_path


def last_engine() -> str:
    """اسم محرك التحويل المستخدم آخر مرة (weasyprint/edge/chrome)."""
    return _ENGINE_USED

