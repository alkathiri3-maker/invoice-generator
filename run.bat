@echo off
chcp 65001 > nul
title مولّد الفواتير التدريبي — إتقان
cd /d "%~dp0"

set PY=python
where python > nul 2>&1
if errorlevel 1 set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"

%PY% -c "import flask" 2> nul
if errorlevel 1 (
    echo [تثبيت المتطلبات لأول مرة...]
    %PY% -m pip install -r requirements.txt --disable-pip-version-check
)

echo.
echo   تشغيل مولّد الفواتير التدريبي ... سيفتح المتصفح تلقائيًا
echo.
%PY% run.py --no-browser
pause
