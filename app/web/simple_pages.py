# -*- coding: utf-8 -*-
"""مسارات مبسطة بدون dependencies معقدة"""
from flask import Blueprint, render_template
from flask import g

bp = Blueprint("simple", __name__)

@bp.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>مولد الفواتير</title>
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; background: #f5f5f5; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
            h1 { color: #333; }
            .status { color: green; font-size: 18px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎉 مولد الفواتير</h1>
            <p class="status">✅ التطبيق يعمل بنجاح!</p>
            <p>تم نشر التطبيق على Render بنجاح</p>
        </div>
    </body>
    </html>
    """
