# حل سريع لمشاكل عرض القوالس
# Quick Fix for Templates Issues

---

## ⚡ الحل السريع (5 دقائق)

### **الخطوة 1: أوقف التطبيق**
```
Ctrl + C  (في Terminal)
```

### **الخطوة 2: امسح ذاكرة المتصفح**
```
Ctrl + Shift + Delete
```
ثم:
- اختر "جميع الأوقات"
- ضع علامة على "الملفات والصور المخزنة مؤقتاً"
- انقر "مسح البيانات"

### **الخطوة 3: أعد تحميل القوالس**
```bash
cd "C:\Users\alkat\itqan-platform\invoice-generator"
python load_professional_templates.py
```

**يجب أن ترى:**
```
✅ تم تحديث: قالب الشركات الاحترافي
✅ تم تحديث: قالب حديث
✅ تم تحديث: قالب تقليدي رسمي
✅ تم تحديث: قالب الإيصالات
```

### **الخطوة 4: أعد تشغيل التطبيق**
```bash
python app.py
```

### **الخطوة 5: افتح الصفحة**
```
http://127.0.0.1:8788/
```

---

## ✅ إذا عمل - تم! 🎉

يجب أن تجد 4 قوالس جديدة في الجدول:
- 🏢 قالب الشركات الاحترافي
- 🎨 قالب حديث
- 📋 قالب تقليدي رسمي
- 🧾 قالب الإيصالات

---

## ❌ إذا لم ينجح - جرب هذا

### **الطريقة 1: مسح قاعدة البيانات والبدء من جديد**

```bash
# أوقف التطبيق (Ctrl + C)

# احذف قاعدة البيانات
rm data/itqan_invoices.db

# ثم أعد التشغيل
python app.py

# سيتم إنشاء قاعدة بيانات جديدة وتحميل القوالس تلقائياً
```

### **الطريقة 2: بحث خطأ المتصفح**

1. اضغط **F12** لفتح أدوات المطور
2. انقر على تبويب **Console**
3. ابحث عن رسائل خطأ حمراء
4. انسخ رسالة الخطأ وشارك

### **الطريقة 3: التحقق من الملفات**

```bash
# تحقق من وجود ملفات القوالس
ls -lh invoice-templates/*.html

# يجب أن تجد 4 ملفات على الأقل:
# - corporate-minimal.html
# - modern-card.html
# - classic-formal.html
# - compact-thermal.html
```

### **الطريقة 4: إعادة تثبيت المتطلبات**

```bash
pip install -r requirements.txt
python app.py
```

---

## 🔍 معلومات تشخيصية

### **اختبر قاعدة البيانات:**
```bash
python << 'EOF'
from app import db
conn = db.connect()
cur = conn.cursor()
templates = cur.execute(
    "SELECT id, name FROM templates WHERE name LIKE 'قالب%' OR name LIKE '%احترافي%'"
).fetchall()
if templates:
    print("✅ وجدت القوالس الجديدة:")
    for t in templates:
        print(f"   [{t[0]}] {t[1]}")
else:
    print("❌ لم أجد القوالس الجديدة - يجب تحميلها")
conn.close()
EOF
```

### **اختبر التطبيق:**
```bash
python << 'EOF'
from app import create_app
app = create_app()
print("✅ التطبيق يعمل")
EOF
```

---

## 📋 قائمة التحقق

- [ ] توقفت التطبيق (Ctrl + C)
- [ ] مسحت ذاكرة المتصفح (Ctrl + Shift + Delete)
- [ ] حملت القوالس يدويًا (`python load_professional_templates.py`)
- [ ] أعدت تشغيل التطبيق (`python app.py`)
- [ ] فتحت الصفحة (`http://127.0.0.1:8788/`)
- [ ] رأيت القوالس الجديدة في الجدول

---

## 🎯 المسار البسيط

```
1. Ctrl + C                    (أوقف التطبيق)
2. python load_professional_templates.py  (حمّل القوالس)
3. python app.py               (شغّل التطبيق)
4. افتح http://127.0.0.1:8788/
5. ستجد القوالس جاهزة! ✅
```

---

**هذا يجب أن يحل 99% من المشاكل في غضون 5 دقائق! ⚡**

إذا استمرت المشكلة، اقرأ `DIAGNOSTICS.md` للتفاصيل الكاملة.
