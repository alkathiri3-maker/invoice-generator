#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""نسخة مبسطة من التطبيق للتشخيص"""
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>مولد الفواتير</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Cairo', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                text-align: center;
                max-width: 500px;
            }
            h1 { color: #333; margin-bottom: 20px; font-size: 32px; }
            .status {
                color: green;
                font-size: 18px;
                margin: 20px 0;
                padding: 15px;
                background: #f0f8f0;
                border-radius: 10px;
            }
            p { color: #666; line-height: 1.6; margin: 10px 0; }
            .links { margin-top: 30px; }
            a {
                display: inline-block;
                margin: 10px;
                padding: 10px 20px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 5px;
            }
            a:hover { background: #764ba2; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎉 مولد الفواتير</h1>
            <div class="status">✅ التطبيق يعمل بنجاح!</div>
            <p>تم نشر تطبيق مولد الفواتير على Render</p>
            <div class="links">
                <a href="/">الرئيسية</a>
            </div>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
