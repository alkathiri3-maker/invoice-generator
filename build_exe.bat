@echo off
chcp 65001 > nul
title بناء ملف EXE — مولّد الفواتير التدريبي
cd /d "%~dp0"

set PY=python
where python > nul 2>&1
if errorlevel 1 set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"

%PY% -m PyInstaller --version > nul 2>&1
if errorlevel 1 (
    echo [تثبيت PyInstaller...]
    %PY% -m pip install pyinstaller --disable-pip-version-check
)

echo [بناء EXE...]
%PY% -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name InvoiceGenerator ^
  --add-data "app\doc_templates;app\doc_templates" ^
  --add-data "app\web\templates;app\web\templates" ^
  --add-data "app\web\static;app\web\static" ^
  run.py

if exist dist\InvoiceGenerator\InvoiceGenerator.exe (
    echo.
    echo   ✅ تم البناء: dist\InvoiceGenerator\InvoiceGenerator.exe
    echo   ملاحظة: قاعدة البيانات تُنشأ تلقائيًا في data\ بجانب الملف التنفيذي.
) else (
    echo   ❌ فشل البناء — راجع المخرجات أعلاه.
)
pause
