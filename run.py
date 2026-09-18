#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
تشغيل التطبيق للاستضافة على Render
"""
import os
import sys

try:
    from app import create_app
    print("✅ App module loaded successfully", file=sys.stderr)

    app = create_app()
    print("✅ App created successfully", file=sys.stderr)

    # الحصول على المنفذ من البيئة (Render يعين PORT)
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"

    print(f"✅ Starting app on port {port}, debug={debug}", file=sys.stderr)

    # تشغيل التطبيق
    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
        use_reloader=False
    )
except Exception as e:
    print(f"❌ Error: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
