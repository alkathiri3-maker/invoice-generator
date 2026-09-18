# -*- coding: utf-8 -*-
"""
النسخ الاحتياطية — إنشاء/استعادة/حذف نسخة ZIP كاملة من بيانات البرنامج.
محتوى النسخة: قاعدة البيانات SQLite (لقطة متسقة) + مجلد الشعارات + المفاتيح
التدريبية + meta.json (معلومات النسخة). تُحفظ النسخ في data/backups/.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from app import db as dbm

BACKUP_DIR = dbm.DATA_DIR / "backups"
MAX_BACKUPS = 30                       # أقصى عدد نسخ محفوظة (تُحذف الأقدم تلقائيًا)
DB_ENTRY = "db/itqan_invoices.db"      # مسار قاعدة البيانات داخل النسخة
REQUIRED_TABLES = ("companies", "customers", "items", "templates",
                    "invoices", "app_settings")


def _ensure_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def _table_counts(db_path: Path) -> dict:
    try:
        conn = sqlite3.connect(str(db_path))
        counts = {}
        for t in ("companies", "customers", "items", "templates",
                  "invoices", "receipts", "batches"):
            try:
                counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except sqlite3.Error:
                counts[t] = 0
        conn.close()
        return counts
    except sqlite3.Error:
        return {}


def create_backup(conn: sqlite3.Connection | None = None,
                  db_path: Path | None = None,
                  tag: str = "يدوي") -> Path:
    """إنشاء نسخة احتياطية ZIP — لقطة متسقة للقاعدة عبر sqlite3 backup API."""
    _ensure_dir()
    src_db = Path(db_path) if db_path else dbm.DB_PATH
    if not src_db.exists():
        raise ValueError("ملف قاعدة البيانات غير موجود")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]   # مع المللي ثانية لضمان تفرّد الاسم
    out = BACKUP_DIR / f"itqan_backup_{stamp}.zip"

    tmp_dir = Path(tempfile.mkdtemp(prefix="inv_bak_"))
    try:
        tmp_db = tmp_dir / "snapshot.db"
        src = sqlite3.connect(str(src_db))
        try:
            dst = sqlite3.connect(str(tmp_db))
            try:
                src.backup(dst)          # لقطة متسقة حتى أثناء وجود اتصالات نشطة
            finally:
                dst.close()
        finally:
            src.close()

        meta = {
            "app": "itqan-invoice-generator",
            "tag": tag,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "counts": _table_counts(tmp_db),
        }
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(tmp_db, DB_ENTRY)
            if dbm.UPLOAD_DIR.exists():
                for f in dbm.UPLOAD_DIR.iterdir():
                    if f.is_file():
                        z.write(f, f"uploads/{f.name}")
            if dbm.KEYS_DIR.exists():
                for f in dbm.KEYS_DIR.iterdir():
                    if f.is_file():
                        z.write(f, f"keys/{f.name}")
            z.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    _prune_old()
    return out


def _prune_old() -> None:
    """حذف أقدم النسخ عند تجاوز الحد الأقصى."""
    files = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime)
    if len(files) > MAX_BACKUPS:
        for f in files[:-MAX_BACKUPS]:
            try:
                f.unlink()
            except OSError:
                pass


def _read_meta(zf: zipfile.ZipFile) -> dict:
    try:
        return json.loads(zf.read("meta.json").decode("utf-8"))
    except (KeyError, ValueError, json.JSONDecodeError):
        return {}


def list_backups() -> list[dict]:
    """قائمة النسخ الاحتياطية (من الأحدث إلى الأقدم) مع معلوماتها."""
    if not BACKUP_DIR.exists():
        return []
    out = []
    for p in sorted(BACKUP_DIR.glob("*.zip"),
                    key=lambda x: x.stat().st_mtime, reverse=True):
        created, tag, counts = "", "", {}
        try:
            with zipfile.ZipFile(p) as z:
                meta = _read_meta(z)
                created = meta.get("created_at", "")
                tag = meta.get("tag", "")
                counts = meta.get("counts", {})
        except (zipfile.BadZipFile, OSError):
            continue
        if not created:
            created = datetime.fromtimestamp(p.stat().st_mtime)\
                .strftime("%Y-%m-%d %H:%M:%S")
        out.append({
            "name": p.name,
            "size": p.stat().st_size,
            "size_h": f"{p.stat().st_size / 1024:.1f} ك.ب",
            "created_at": created,
            "tag": tag or "يدوي",
            "counts": counts,
        })
    return out


def last_backup_info() -> dict | None:
    """أحدث نسخة احتياطية (أو None إن لم توجد)."""
    items = list_backups()
    return items[0] if items else None


def _validate_zip(zip_path: Path) -> tuple[Path, tempfile.TemporaryDirectory]:
    """التحقق من النسخة وإرجاع (مسار قاعدة مؤقتة صالحة، مجلد مؤقت)."""
    tmp = tempfile.TemporaryDirectory(prefix="inv_restore_")
    tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            if DB_ENTRY not in names:
                # دعم نسخ تحتوي القاعدة في الجذر مباشرة
                alt = [n for n in names if n.endswith(".db")]
                if not alt:
                    raise ValueError("النسخة لا تحتوي على قاعدة بيانات")
                entry = alt[0]
            else:
                entry = DB_ENTRY
            z.extract(entry, tmp_path)
            db_tmp = tmp_path / entry   # extract يحافظ على مسار الأرشيف (db/…)

            # فحص سلامة القاعدة وجود الجداول الأساسية
            conn = sqlite3.connect(str(db_tmp))
            try:
                ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
                if ok != "ok":
                    raise ValueError("قاعدة البيانات داخل النسخة تالفة")
                tables = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                missing = [t for t in REQUIRED_TABLES if t not in tables]
                if missing:
                    raise ValueError(f"جداول مفقودة في النسخة: {', '.join(missing)}")
            finally:
                conn.close()

            for sub in ("uploads", "keys"):
                for n in (x for x in names if x.startswith(f"{sub}/") and not x.endswith("/")):
                    dest = tmp_path / n
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(n) as fsrc, open(dest, "wb") as fdst:
                        shutil.copyfileobj(fsrc, fdst)
        return db_tmp, tmp
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        tmp.cleanup()
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"ملف النسخة غير صالح: {exc}") from exc


def restore_backup(zip_path: Path, db_path: Path | None = None) -> dict:
    """
    استعادة نسخة احتياطية. يُنشئ نسخة أمان تلقائية قبل الاستعادة،
    ثم يستبدل القاعدة والمرفقات. ملاحظة Windows: يجب أن يكون اتصال
    قاعدة البيانات الخاص بالطلب مغلقًا قبل استدعاء هذه الدالة.
    """
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise ValueError("ملف النسخة الاحتياطية غير موجود")
    target_db = Path(db_path) if db_path else dbm.DB_PATH
    db_tmp, tmp = _validate_zip(zip_path)
    try:
        # نسخة أمان قبل الاستعادة (تحفظ الحالة الحالية)
        try:
            create_backup(db_path=target_db, tag="قبل الاستعادة")
        except (OSError, sqlite3.Error, ValueError):
            pass  # لا نمنع الاستعادة إذا فشل الأرشيف الاحتياطي

        # استبدال قاعدة البيانات
        os.replace(str(db_tmp), str(target_db))

        # استبدال الشعارات والمفاتيح
        tmp_path = Path(tmp.name)
        dir_of = {"uploads": dbm.UPLOAD_DIR, "keys": dbm.KEYS_DIR}
        for sub in ("uploads", "keys"):
            dest_dir = target_db.parent / sub if db_path else dir_of[sub]
            dest_dir.mkdir(parents=True, exist_ok=True)
            for f in dest_dir.iterdir():
                if f.is_file():
                    f.unlink()
            src_dir = tmp_path / sub
            if src_dir.exists():
                for f in src_dir.iterdir():
                    shutil.copy2(f, dest_dir / f.name)
        return {"restored_from": zip_path.name}
    finally:
        tmp.cleanup()


def delete_backup(name: str) -> None:
    """حذف نسخة احتياطية بالاسم (مع التحقق من المسار)."""
    safe = Path(name).name
    if not safe.endswith(".zip") or safe.startswith("."):
        raise ValueError("اسم ملف غير صالح")
    p = BACKUP_DIR / safe
    if not p.exists():
        raise ValueError("النسخة غير موجودة")
    p.unlink()


def backup_age_days() -> int | None:
    """عدد الأيام منذ أحدث نسخة (None إن لم توجد نسخ)."""
    last = last_backup_info()
    if not last:
        return None
    try:
        d = datetime.strptime(last["created_at"][:10], "%Y-%m-%d")
        return (datetime.now() - d).days
    except ValueError:
        return None


def maybe_auto_backup() -> bool:
    """نسخة تلقائية يومية عند بدء التشغيل إذا كان الخيار مفعّلًا."""
    conn = dbm.connect()
    try:
        if not dbm.get_setting(conn, "backup_auto", False):
            return False
        last = dbm.get_setting(conn, "last_auto_backup", "") or ""
        today = datetime.now().strftime("%Y-%m-%d")
        if last == today:
            return False
        create_backup(conn=conn, tag="تلقائي")
        dbm.set_setting(conn, "last_auto_backup", today)
        return True
    finally:
        conn.close()

    """أحدث نسخة احتياطية (أو None إن لم توجد)."""
    items = list_backups()
    return items[0] if items else None
