# -*- coding: utf-8 -*-
"""مصنع تطبيق Flask — مولّد الفواتير التدريبي للمحاسبين."""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from flask import Flask, g, request  # noqa: E402

from app import db as dbm  # noqa: E402
from app.money import fmt_qty  # noqa: E402

APP_NAME = "مولّد الفواتير التدريبي"
APP_VERSION = "1.0.0"


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "web" / "templates"),
        static_folder=str(Path(__file__).parent / "web" / "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024   # 8MB (شعارات)
    _init_conn = dbm.init_db()
    # سر دائم للجلسات (يُحفظ في القاعدة ليبقى ثابتًا بعد إعادة التشغيل)
    app.secret_key = dbm.get_or_create_session_secret(_init_conn)
    _init_conn.close()   # لا نُبقي اتصالًا يقفل ملف القاعدة (مطلوب للاستعادة على Windows)

    # نسخة احتياطية تلقائية يومية عند بدء التشغيل (إن فُعّلت من الإعدادات)
    try:
        from app import backup as _bk
        _bk.maybe_auto_backup()
    except Exception:  # لا تمنع تشغيل البرنامج إذا فشل الأرشيف التلقائي
        pass

    # ── فلاتر عرض عربية ──
    @app.template_filter("sar")
    def sar(v):
        try:
            return f"{float(v or 0):,.2f}"
        except (TypeError, ValueError):
            return "0.00"

    @app.template_filter("qty")
    def qty(v):
        return fmt_qty(v)

    @app.template_filter("adate")
    def adate(s):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(str(s)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return s or ""

    @app.context_processor
    def inject_globals():
        return {"APP_NAME": APP_NAME, "APP_VERSION": APP_VERSION}

    # ── اتصال قاعدة بيانات لكل طلب ──
    @app.before_request
    def _open_db():
        g.conn = dbm.connect()

    @app.teardown_appcontext
    def _close_db(exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    # ── بوابة حماية المشرف (Admin Gateway) ──
    # كل صفحات وواجهات البرنامج محمية بكلمة مرور المشرف (الافتراضية admin123)
    # إلا: صفحة تسجيل الدخول/الخروج، الملفات الثابتة، والملفات المرفوعة/المصدّرة.
    @app.before_request
    def _admin_gate():
        from flask import redirect, session, url_for, jsonify as _jsonify
        ep = request.endpoint
        if ep is None:
            return None
        if ep in ("static", "pages.login", "pages.admin_login", "pages.admin_logout",
                  "pages.uploads", "pages.exports"):
            return None
        if session.get("admin_ok"):
            return None
        if request.path.startswith("/api/"):
            return _jsonify({"ok": False, "error": "تسجيل دخول المشرف مطلوب (كلمة المرور الافتراضية: admin123)"}), 401
        return redirect(url_for("pages.admin_login", next=request.full_path))

    # ── المسارات ──
    from app.web.pages import bp as pages_bp
    from app.web.api import bp as api_bp
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app


