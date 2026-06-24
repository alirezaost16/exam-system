# سامانه آزمون آنلاین — Online Exam System

پروژه درس مهندسی نرم‌افزار | ساخته‌شده با FastAPI + SQLite + Jinja2

---

## 🚀 راه‌اندازی سریع

```bash
# ۱. نصب وابستگی‌ها
pip install -r requirements.txt

# ۲. اجرای سرور
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# یا با اسکریپت آماده:
bash run.sh
```

سپس مرورگر را باز کنید: **http://localhost:8000**

---

## 🔑 اطلاعات ورود پیش‌فرض

| نقش | نام کاربری | رمز عبور |
|-----|-----------|---------|
| مدیر سیستم | `admin` | `admin123` |
| استاد | `teacher1` | `teacher123` |
| دانشجو | `student1` | `student123` |

---

## 📁 ساختار پروژه

```
exam_system/
├── main.py              ← اپلیکیشن اصلی FastAPI
├── database.py          ← تنظیمات SQLAlchemy
├── models.py            ← مدل‌های پایگاه داده
├── requirements.txt     ← وابستگی‌ها
├── run.sh               ← اسکریپت راه‌اندازی
├── static/
│   ├── css/main.css     ← استایل Dark Modern Minimal
│   └── js/main.js       ← جاوااسکریپت تعاملی
├── templates/
│   ├── base.html        ← قالب پایه با sidebar
│   ├── index.html       ← صفحه اصلی
│   ├── login.html       ← صفحه ورود
│   ├── register.html    ← صفحه ثبت‌نام
│   ├── dashboard_student.html
│   ├── dashboard_teacher.html
│   ├── dashboard_admin.html
│   ├── exam_create.html
│   ├── exam_questions.html
│   ├── exam_take.html   ← با تایمر و auto-save
│   ├── exam_closed.html
│   ├── result_view.html ← با انیمیشن score ring
│   └── transcript.html  ← کارنامه با نمودار
└── docs/
    ├── system_analysis.md      ← مستند تحلیل سیستم
    ├── uml_diagrams.html       ← دیاگرام‌های UML
    └── work_division_report.md ← گزارش تقسیم کار
```

---

## ✨ قابلیت‌ها

- 🔐 **احراز هویت** با session token و cookie
- 👥 **سه نقش**: مدیر / استاد / دانشجو
- 📝 **ایجاد آزمون** با سوالات تستی و تشریحی
- ⏱ **تایمر هوشمند** با ارسال خودکار پس از اتمام وقت
- 💾 **ذخیره خودکار** پاسخ‌ها در localStorage
- ✅ **تصحیح فوری** سوالات تستی
- 📊 **کارنامه** با نمودار روند نمرات
- 🎨 **تم Dark Modern Minimal** کاملاً فارسی
- 📱 **واکنش‌گرا** برای موبایل

---

## 📐 مستندات

- `docs/system_analysis.md` — تحلیل نیازمندی‌ها و سناریوها
- `docs/uml_diagrams.html` — دیاگرام‌های Use Case، Class، Sequence، Activity

---

*تاریخ تحویل: ۱۴۰۵/۰۴/۲۱*
