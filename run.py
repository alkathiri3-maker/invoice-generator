#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
تشغيل التطبيق للاستضافة على Render
"""
import os
from app import create_app

if __name__ == "__main__":
    app = create_app()

    # الحصول على المنفذ من البيئة (Render يعين PORT)
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"

    # تشغيل التطبيق
    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug
    )
