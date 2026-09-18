# رفع التطبيق على Render.com (مجاني)
# Deploy to Render.com (Free)

---

## 📋 الخطوات الكاملة

### **الخطوة 1: إعداد GitHub**

#### 1.1 إنشاء حساب GitHub (إن لم يكن موجوداً)
- اذهب إلى https://github.com
- اضغط Sign Up
- أكمل التسجيل

#### 1.2 إنشاء Repository جديد
1. اضغط `+` في الزاوية العلوية اليسار
2. اختر `New repository`
3. أسمِ المشروع: `invoice-generator`
4. اختر `Public`
5. اضغط `Create repository`

#### 1.3 رفع الملفات إلى GitHub

افتح Command Prompt في مجلد المشروع وشغّل:

```bash
# تهيئة git
git init
git add .
git commit -m "Initial commit: Invoice Generator App"

# إضافة remote (استبدل USERNAME بمستخدم GitHub)
git remote add origin https://github.com/USERNAME/invoice-generator.git
git branch -M main
git push -u origin main
```

---

### **الخطوة 2: إعداد Render.com**

#### 2.1 إنشاء حساب Render
1. اذهب إلى https://render.com
2. اضغط `Sign Up`
3. استخدم GitHub account
4. أعط الأذن لربط GitHub

#### 2.2 إنشاء Web Service جديد
1. من Dashboard، اضغط `New +`
2. اختر `Web Service`
3. اختر GitHub repository: `invoice-generator`
4. اضغط `Connect`

#### 2.3 إعدادات البناء
```
Name:              invoice-generator
Environment:       Python 3
Region:            (اختر الأقرب)
Branch:            main
Build Command:     pip install -r requirements.txt
Start Command:     python run.py
```

#### 2.4 متغيرات البيئة
اضغط `Add Environment Variable`:

```
FLASK_ENV      = production
FLASK_APP      = run.py
```

#### 2.5 النشر
اضغط `Create Web Service`

- سيبدأ البناء (يستغرق 5-10 دقائق)
- بعد انتهاء البناء، ستحصل على URL مثل:
  ```
  https://invoice-generator.onrender.com
  ```

---

## ✅ التحقق من النشر

### في Render Dashboard:
- ✅ Status: `Live` (أخضر)
- ✅ Build Logs: بدون أخطاء

### في المتصفح:
```
https://invoice-generator.onrender.com
```

يجب أن تجد:
- ✅ الصفحة الرئيسية تحمّل
- ✅ صفحة تسجيل الدخول تظهر
- ✅ جميع الوظائف تعمل

---

## 🔧 حل المشاكل الشائعة

### المشكلة: `Application failed to start`

**الحل:**
1. اذهب إلى Logs في Render
2. ابحث عن الخطأ
3. تأكد من:
   - `requirements.txt` موجود
   - `Procfile` صحيح
   - `run.py` موجود

### المشكلة: قاعدة البيانات فارغة

**الحل:**
```bash
# في Render Shell (من الـ Dashboard):
python -c "from app import db; conn = db.connect(); db.seed_demo(conn)"
```

### المشكلة: الموقع بطيء جداً

**السبب:** Render قد يوقف التطبيق بعد 15 دقيقة عدم استخدام
**الحل:** ترقِ إلى خطة مدفوعة ($7/شهر) للحصول على تطبيق دائم

---

## 📱 الوصول للتطبيق

### من أي جهاز:
```
https://invoice-generator.onrender.com
```

### تسجيل الدخول:
- **Username:** admin
- **Password:** admin123

---

## 🚀 التحديثات المستقبلية

عند تحديث الكود:

```bash
# في جهازك:
git add .
git commit -m "Update description"
git push origin main
```

Render سيقوم تلقائياً بـ:
- ✅ البناء
- ✅ النشر
- ✅ إعادة التشغيل

**لا حاجة لأي خطوات إضافية!**

---

## 💡 نصائح

1. **النسخ الاحتياطية:** احفظ نسخة من `data/itqan_invoices.db` محلياً
2. **الأمان:** غيّر كلمة المرور الافتراضية `admin123`
3. **المراقبة:** فعّل Render's error notifications

---

## 📞 الدعم

إذا حدثت مشكلة:
1. تحقق من Render Logs
2. اقرأ error messages
3. جرّب إعادة Deploy من Render Dashboard

---

**تم! التطبيق الآن على الإنترنت! 🎉**

الرابط النهائي:
```
https://invoice-generator.onrender.com
```
