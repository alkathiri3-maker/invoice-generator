#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
نسخة محسّنة مع نظام تسجيل دخول وإدارة المستخدمين
"""
from flask import Flask, render_template_string, request, session, redirect, url_for
import os
from datetime import datetime

app = Flask(__name__)
# مفتاح سري فريد يتغير في كل مرة لإلغاء الجلسات القديمة
app.secret_key = os.environ.get("SECRET_KEY", "new-secret-key-2026-09-18-v2")

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

# CSS مشترك للجميع
COMMON_CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html { font-size: 16px; }
    body { font-family: 'Cairo', Arial, sans-serif; }
    @media (max-width: 768px) {
        html { font-size: 14px; }
    }
    @media (max-width: 480px) {
        html { font-size: 13px; }
    }
"""

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
        html { font-size: 16px; }
        body {
            font-family: 'Cairo', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 400px;
        }
        .login-header { text-align: center; margin-bottom: 30px; }
        .login-header h1 { color: #333; font-size: 28px; margin-bottom: 10px; }
        .login-header p { color: #666; font-size: 14px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; color: #333; font-weight: 600; font-size: 14px; }
        input[type="text"], input[type="password"] {
            width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px;
            font-size: 14px; font-family: inherit; -webkit-appearance: none;
        }
        input:focus { outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        .btn-login {
            width: 100%; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600;
            cursor: pointer; transition: 0.3s; -webkit-appearance: none;
        }
        .btn-login:active { transform: scale(0.98); }
        .btn-login:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4); }
        .demo-users {
            background: #f5f5f5; padding: 15px; border-radius: 8px; margin-top: 20px;
            font-size: 13px; color: #666;
        }
        .demo-users p { margin-bottom: 8px; word-break: break-all; }
        .error { background: #fee; color: #c33; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }

        @media (max-width: 768px) {
            body { padding: 15px; }
            .login-container { padding: 30px 20px; border-radius: 12px; }
            .login-header { margin-bottom: 25px; }
            .login-header h1 { font-size: 24px; margin-bottom: 8px; }
            .login-header p { font-size: 13px; }
            .form-group { margin-bottom: 18px; }
            label { font-size: 13px; margin-bottom: 7px; }
            input[type="text"], input[type="password"] { padding: 11px; font-size: 16px; }
            .btn-login { padding: 11px; font-size: 15px; }
            .demo-users { padding: 12px; margin-top: 18px; font-size: 12px; }
            .demo-users p { margin-bottom: 6px; }
        }

        @media (max-width: 480px) {
            body { padding: 10px; }
            .login-container { padding: 25px 15px; border-radius: 10px; }
            .login-header { margin-bottom: 20px; }
            .login-header h1 { font-size: 20px; margin-bottom: 6px; }
            .login-header p { font-size: 12px; }
            .form-group { margin-bottom: 15px; }
            label { font-size: 12px; margin-bottom: 6px; }
            input[type="text"], input[type="password"] { padding: 10px; font-size: 16px; border-radius: 6px; }
            .btn-login { padding: 10px; font-size: 14px; border-radius: 6px; }
            .demo-users { padding: 10px; margin-top: 15px; font-size: 11px; border-radius: 6px; }
            .demo-users p { margin-bottom: 5px; }
            .error { padding: 10px; font-size: 12px; margin-bottom: 15px; }
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
        body { font-family: 'Cairo', Arial, sans-serif; background: #f5f5f5; }
        .navbar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 20px; display: flex; justify-content: space-between;
            align-items: center; flex-wrap: wrap; gap: 15px;
        }
        .navbar h1 { font-size: 24px; }
        .navbar .user-info { text-align: right; }
        .navbar .user-info p { margin: 5px 0; font-size: 14px; }
        .container { max-width: 1200px; margin: 40px auto; padding: 0 20px; }
        .dashboard-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px; margin-bottom: 40px;
        }
        .card {
            background: white; padding: 25px; border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center;
        }
        .card h2 { color: #667eea; font-size: 32px; margin: 10px 0; }
        .card p { color: #666; font-size: 14px; }
        .menu {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .menu-item {
            background: white; padding: 20px; border-radius: 10px;
            text-decoration: none; color: #333; text-align: center; transition: 0.3s;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .menu-item:hover { transform: translateY(-5px); box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3); }
        .menu-item .icon { font-size: 32px; margin-bottom: 10px; }
        .logout-btn {
            background: #dc2626; color: white; padding: 10px 20px; border: none;
            border-radius: 6px; cursor: pointer; font-size: 14px;
        }
        .logout-btn:hover { background: #991b1b; }

        @media (max-width: 768px) {
            .navbar { flex-direction: column; text-align: center; padding: 15px; }
            .navbar h1 { font-size: 20px; }
            .navbar .user-info { text-align: center; width: 100%; }
            .navbar .user-info p { font-size: 13px; }
            .logout-btn { width: 100%; padding: 10px; font-size: 13px; }
            .container { padding: 0 15px; margin: 25px auto; }
            .dashboard-grid { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; }
            .card { padding: 20px 15px; }
            .card h2 { font-size: 24px; }
            .card p { font-size: 12px; }
            .menu { grid-template-columns: repeat(2, 1fr); gap: 12px; }
            .menu-item { padding: 15px; font-size: 13px; }
            .menu-item .icon { font-size: 28px; margin-bottom: 8px; }
        }

        @media (max-width: 480px) {
            .navbar { padding: 12px; gap: 10px; }
            .navbar h1 { font-size: 16px; }
            .navbar .user-info p { font-size: 11px; }
            .logout-btn { padding: 8px 12px; font-size: 11px; }
            .container { margin: 15px auto; padding: 0 10px; }
            .dashboard-grid { grid-template-columns: 1fr; gap: 12px; margin-bottom: 20px; }
            .card { padding: 15px; }
            .card h2 { font-size: 20px; }
            .card p { font-size: 11px; }
            h2 { font-size: 16px !important; margin-bottom: 15px !important; }
            .menu { grid-template-columns: 1fr; gap: 10px; }
            .menu-item { padding: 12px; font-size: 12px; }
            .menu-item .icon { font-size: 24px; }
        }
    </style>
</head>
<body>
    <div class="navbar">
        <div><h1>🎉 لوحة المشرف</h1></div>
        <div class="user-info">
            <p><strong>مرحباً: {{ user_name }}</strong></p>
            <form method="POST" action="/logout">
                <button type="submit" class="logout-btn">تسجيل الخروج</button>
            </form>
        </div>
    </div>
    <div class="container">
        <h2 style="margin-bottom: 30px; color: #333;">📊 الإحصائيات</h2>
        <div class="dashboard-grid">
            <div class="card"><div style="font-size: 40px;">📄</div><h2>0</h2><p>الفواتير الكلية</p></div>
            <div class="card"><div style="font-size: 40px;">👥</div><h2>0</h2><p>المتدربون</p></div>
            <div class="card"><div style="font-size: 40px;">💰</div><h2>0.00</h2><p>إجمالي المبيعات</p></div>
        </div>
        <h2 style="margin-bottom: 20px; color: #333;">⚙️ الخيارات</h2>
        <div class="menu">
            <div class="menu-item"><div class="icon">📝</div><div>إدارة الفواتير</div></div>
            <div class="menu-item"><div class="icon">👥</div><div>إدارة المتدربين</div></div>
            <div class="menu-item"><div class="icon">🏢</div><div>إدارة الشركات</div></div>
            <div class="menu-item"><div class="icon">📊</div><div>التقارير والإحصائيات</div></div>
            <div class="menu-item"><div class="icon">⚙️</div><div>الإعدادات</div></div>
            <div class="menu-item"><div class="icon">📚</div><div>المساعدة والدعم</div></div>
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
        body { font-family: 'Cairo', Arial, sans-serif; background: #f5f5f5; }
        .navbar {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white; padding: 20px; display: flex; justify-content: space-between;
            align-items: center; flex-wrap: wrap; gap: 15px;
        }
        .navbar h1 { font-size: 24px; }
        .navbar .user-info { text-align: right; }
        .navbar .user-info p { margin: 5px 0; font-size: 14px; }
        .container { max-width: 1200px; margin: 40px auto; padding: 0 20px; }
        .dashboard-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px; margin-bottom: 40px;
        }
        .card {
            background: white; padding: 25px; border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center;
        }
        .card h2 { color: #10b981; font-size: 32px; margin: 10px 0; }
        .card p { color: #666; font-size: 14px; }
        .menu {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .menu-item {
            background: white; padding: 20px; border-radius: 10px;
            text-decoration: none; color: #333; text-align: center; transition: 0.3s;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .menu-item:hover { transform: translateY(-5px); box-shadow: 0 5px 15px rgba(16, 185, 129, 0.3); }
        .menu-item .icon { font-size: 32px; margin-bottom: 10px; }
        .logout-btn {
            background: #dc2626; color: white; padding: 10px 20px; border: none;
            border-radius: 6px; cursor: pointer; font-size: 14px;
        }
        .logout-btn:hover { background: #991b1b; }

        @media (max-width: 768px) {
            .navbar { flex-direction: column; text-align: center; padding: 15px; }
            .navbar h1 { font-size: 20px; }
            .navbar .user-info { text-align: center; width: 100%; }
            .logout-btn { width: 100%; padding: 10px; font-size: 13px; }
            .container { padding: 0 15px; margin: 25px auto; }
            .dashboard-grid { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; }
            .card { padding: 20px 15px; }
            .card h2 { font-size: 24px; }
            .menu { grid-template-columns: repeat(2, 1fr); gap: 12px; }
            .menu-item { padding: 15px; font-size: 13px; }
        }

        @media (max-width: 480px) {
            .navbar { padding: 12px; gap: 10px; }
            .navbar h1 { font-size: 16px; }
            .logout-btn { padding: 8px 12px; font-size: 11px; }
            .container { margin: 15px auto; padding: 0 10px; }
            .dashboard-grid { grid-template-columns: 1fr; gap: 12px; }
            .card { padding: 15px; }
            .card h2 { font-size: 20px; }
            .menu { grid-template-columns: 1fr; gap: 10px; }
            .menu-item { padding: 12px; font-size: 12px; }
        }
    </style>
</head>
<body>
    <div class="navbar">
        <div><h1>🎓 لوحة المتدرب</h1></div>
        <div class="user-info">
            <p><strong>مرحباً: {{ user_name }}</strong></p>
            <form method="POST" action="/logout">
                <button type="submit" class="logout-btn">تسجيل الخروج</button>
            </form>
        </div>
    </div>
    <div class="container">
        <h2 style="margin-bottom: 30px; color: #333;">📊 إحصائياتي</h2>
        <div class="dashboard-grid">
            <div class="card"><div style="font-size: 40px;">📄</div><h2>0</h2><p>فواتيري</p></div>
            <div class="card"><div style="font-size: 40px;">✅</div><h2>0%</h2><p>نسبة الإنجاز</p></div>
            <div class="card"><div style="font-size: 40px;">🎓</div><h2>0</h2><p>نقاطي</p></div>
        </div>
        <h2 style="margin-bottom: 20px; color: #333;">⚙️ خياراتي</h2>
        <div class="menu">
            <div class="menu-item"><div class="icon">✍️</div><div>إنشاء فاتورة</div></div>
            <div class="menu-item"><div class="icon">📋</div><div>الفواتير الخاصة بي</div></div>
            <div class="menu-item"><div class="icon">📊</div><div>تقديمي</div></div>
            <div class="menu-item"><div class="icon">🎖️</div><div>شهاداتي</div></div>
            <div class="menu-item"><div class="icon">⚙️</div><div>إعداداتي</div></div>
            <div class="menu-item"><div class="icon">❓</div><div>المساعدة</div></div>
        </div>
    </div>
</body>
</html>
"""

# Middleware: فرض تسجيل الدخول على جميع الصفحات ما عدا /login و /health
@app.before_request
def before_request():
    if request.endpoint and request.endpoint not in ["login", "health", "static"]:
        if "user" not in session:
            return redirect(url_for("login"))

@app.route("/")
def index():
    # الصفحة الرئيسية: اذهب مباشرة إلى Dashboard
    return redirect(url_for("dashboard"))

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
    # الحماية من middleware
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
