#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
نسخة محسّنة مع نظام تسجيل دخول وإدارة المستخدمين
"""
from flask import Flask, render_template_string, request, session, redirect, url_for
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# نموذج بيانات المستخدمين (في الإنتاج: استخدم قاعدة بيانات)
USERS = {
    "admin": {
        "password": "admin123",
        "role": "مشرف",
        "name": "المشرف"
    },
    "trainee": {
        "password": "trainee123",
        "role": "متدرب",
        "name": "المتدرب"
    }
}

# صفحة تسجيل الدخول
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>تسجيل الدخول - مولد الفواتير</title>
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
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 400px;
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header h1 {
            color: #333;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .login-header p {
            color: #666;
            font-size: 14px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
        }
        input[type="text"],
        input[type="password"],
        select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            font-family: inherit;
        }
        input:focus,
        select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        .btn-login {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.3s;
        }
        .btn-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .demo-users {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            font-size: 13px;
            color: #666;
        }
        .demo-users p {
            margin-bottom: 8px;
        }
        .error {
            background: #fee;
            color: #c33;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>🎉 مولد الفواتير</h1>
            <p>نظام إدارة الفواتير والمحاسبة</p>
        </div>

        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}

        <form method="POST">
            <div class="form-group">
                <label>اسم المستخدم</label>
                <input type="text" name="username" required placeholder="أدخل اسم المستخدم">
            </div>

            <div class="form-group">
                <label>كلمة المرور</label>
                <input type="password" name="password" required placeholder="أدخل كلمة المرور">
            </div>

            <button type="submit" class="btn-login">تسجيل الدخول</button>
        </form>

        <div class="demo-users">
            <p><strong>📝 بيانات تجريبية:</strong></p>
            <p><strong>مشرف:</strong> admin / admin123</p>
            <p><strong>متدرب:</strong> trainee / trainee123</p>
        </div>
    </div>
</body>
</html>
"""

# صفحة لوحة التحكم للمشرف
ADMIN_DASHBOARD = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>لوحة المشرف</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Cairo', Arial, sans-serif;
            background: #f5f5f5;
        }
        .navbar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .navbar h1 { font-size: 24px; }
        .navbar .user-info { text-align: right; }
        .navbar .user-info p { margin: 5px 0; font-size: 14px; }
        .container {
            max-width: 1200px;
            margin: 40px auto;
            padding: 0 20px;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
        }
        .card h2 { color: #667eea; font-size: 32px; margin: 10px 0; }
        .card p { color: #666; font-size: 14px; }
        .menu {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .menu-item {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-decoration: none;
            color: #333;
            text-align: center;
            transition: 0.3s;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .menu-item:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }
        .menu-item .icon { font-size: 32px; margin-bottom: 10px; }
        .logout-btn {
            background: #dc2626;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        .logout-btn:hover { background: #991b1b; }
    </style>
</head>
<body>
    <div class="navbar">
        <div>
            <h1>🎉 مولد الفواتير - لوحة المشرف</h1>
        </div>
        <div class="user-info">
            <p><strong>مرحباً: {{ user_name }}</strong></p>
            <form method="POST" action="/logout" style="margin-top: 10px;">
                <button type="submit" class="logout-btn">تسجيل الخروج</button>
            </form>
        </div>
    </div>

    <div class="container">
        <h2 style="margin-bottom: 30px; color: #333;">📊 الإحصائيات</h2>
        <div class="dashboard-grid">
            <div class="card">
                <div style="font-size: 40px;">📄</div>
                <h2>0</h2>
                <p>الفواتير الكلية</p>
            </div>
            <div class="card">
                <div style="font-size: 40px;">👥</div>
                <h2>0</h2>
                <p>المتدربون</p>
            </div>
            <div class="card">
                <div style="font-size: 40px;">💰</div>
                <h2>0.00</h2>
                <p>إجمالي المبيعات</p>
            </div>
        </div>

        <h2 style="margin-bottom: 20px; color: #333;">⚙️ الخيارات</h2>
        <div class="menu">
            <div class="menu-item">
                <div class="icon">📝</div>
                <div>إدارة الفواتير</div>
            </div>
            <div class="menu-item">
                <div class="icon">👥</div>
                <div>إدارة المتدربين</div>
            </div>
            <div class="menu-item">
                <div class="icon">🏢</div>
                <div>إدارة الشركات</div>
            </div>
            <div class="menu-item">
                <div class="icon">📊</div>
                <div>التقارير والإحصائيات</div>
            </div>
            <div class="menu-item">
                <div class="icon">⚙️</div>
                <div>الإعدادات</div>
            </div>
            <div class="menu-item">
                <div class="icon">📚</div>
                <div>المساعدة والدعم</div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# صفحة لوحة التحكم للمتدرب
TRAINEE_DASHBOARD = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>لوحة المتدرب</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Cairo', Arial, sans-serif;
            background: #f5f5f5;
        }
        .navbar {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .navbar h1 { font-size: 24px; }
        .navbar .user-info { text-align: right; }
        .navbar .user-info p { margin: 5px 0; font-size: 14px; }
        .container {
            max-width: 1200px;
            margin: 40px auto;
            padding: 0 20px;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
        }
        .card h2 { color: #10b981; font-size: 32px; margin: 10px 0; }
        .card p { color: #666; font-size: 14px; }
        .menu {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .menu-item {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-decoration: none;
            color: #333;
            text-align: center;
            transition: 0.3s;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .menu-item:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(16, 185, 129, 0.3);
        }
        .menu-item .icon { font-size: 32px; margin-bottom: 10px; }
        .logout-btn {
            background: #dc2626;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        .logout-btn:hover { background: #991b1b; }
    </style>
</head>
<body>
    <div class="navbar">
        <div>
            <h1>🎓 مولد الفواتير - لوحة المتدرب</h1>
        </div>
        <div class="user-info">
            <p><strong>مرحباً: {{ user_name }}</strong></p>
            <form method="POST" action="/logout" style="margin-top: 10px;">
                <button type="submit" class="logout-btn">تسجيل الخروج</button>
            </form>
        </div>
    </div>

    <div class="container">
        <h2 style="margin-bottom: 30px; color: #333;">📊 إحصائياتي</h2>
        <div class="dashboard-grid">
            <div class="card">
                <div style="font-size: 40px;">📄</div>
                <h2>0</h2>
                <p>فواتيري</p>
            </div>
            <div class="card">
                <div style="font-size: 40px;">✅</div>
                <h2>0%</h2>
                <p>نسبة الإنجاز</p>
            </div>
            <div class="card">
                <div style="font-size: 40px;">🎓</div>
                <h2>0</h2>
                <p>نقاطي</p>
            </div>
        </div>

        <h2 style="margin-bottom: 20px; color: #333;">⚙️ خياراتي</h2>
        <div class="menu">
            <div class="menu-item">
                <div class="icon">✍️</div>
                <div>إنشاء فاتورة</div>
            </div>
            <div class="menu-item">
                <div class="icon">📋</div>
                <div>الفواتير الخاصة بي</div>
            </div>
            <div class="menu-item">
                <div class="icon">📊</div>
                <div>تقديمي</div>
            </div>
            <div class="menu-item">
                <div class="icon">🎖️</div>
                <div>شهاداتي</div>
            </div>
            <div class="menu-item">
                <div class="icon">⚙️</div>
                <div>إعداداتي</div>
            </div>
            <div class="menu-item">
                <div class="icon">❓</div>
                <div>المساعدة</div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username in USERS and USERS[username]["password"] == password:
            session["user"] = username
            session["role"] = USERS[username]["role"]
            session["name"] = USERS[username]["name"]
            return redirect(url_for("dashboard"))
        else:
            return render_template_string(LOGIN_HTML, error="اسم المستخدم أو كلمة المرور غير صحيحة")

    return render_template_string(LOGIN_HTML)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    user_name = session.get("name", "المستخدم")
    role = session.get("role", "")

    if role == "مشرف":
        return render_template_string(ADMIN_DASHBOARD, user_name=user_name)
    else:
        return render_template_string(TRAINEE_DASHBOARD, user_name=user_name)

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
