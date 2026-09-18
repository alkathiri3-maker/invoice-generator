#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
نسخة مبسطة من التطبيق للتطوير السريع
"""
import os
import sys

def main():
    try:
        print("🔍 جاري تحميل التطبيق...", file=sys.stderr)

        # استيراد Flask بشكل آمن
        try:
            import flask
            print(f"✅ Flask {flask.__version__} loaded", file=sys.stderr)
        except Exception as e:
            print(f"❌ Flask import error: {e}", file=sys.stderr)
            return 1

        # استيراد التطبيق
        try:
            from app import create_app
            print("✅ App module imported", file=sys.stderr)
        except Exception as e:
            print(f"❌ App import error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return 1

        # إنشاء التطبيق
        try:
            app = create_app()
            print("✅ App instance created", file=sys.stderr)
        except Exception as e:
            print(f"❌ App creation error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return 1

        # الحصول على المنفذ
        port = int(os.environ.get("PORT", 5000))
        print(f"✅ Starting Flask on port {port}", file=sys.stderr)

        # تشغيل التطبيق
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False
        )

    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
