# ربات تلگرام برای ساخت حساب Gmail و دریافت API Key از Google Gemini

این ربات تلگرام به طور خودکار حساب‌های Gmail جدید ایجاد می‌کند و برای آن‌ها کلید API گوگل جمینی را دریافت می‌کند. تمامی این فرایندها با استفاده از اتوماسیون سلنیوم و به صورت کاملاً خودکار انجام می‌شود.

## قابلیت‌های اصلی

- ساخت خودکار حساب Gmail با اطلاعات تصادفی
- دریافت خودکار کلیدهای API گوگل جمینی
- تست اعتبار API Key‌های دریافت شده
- پشتیبانی از پروکسی برای دور زدن محدودیت‌های IP
- ذخیره اطلاعات حساب‌ها در پایگاه داده PostgreSQL
- رابط کاربری زیبا با استفاده از دکمه‌های شیشه‌ای (Inline Keyboard) تلگرام
- پشتیبانی از زبان فارسی

## نیازمندی‌ها

- Python 3.10 یا بالاتر
- PostgreSQL
- تمام کتابخانه‌های ذکر شده در `pyproject.toml`
- حداقل یک شماره تلفن برای احراز هویت (ترجیحاً با استفاده از Twilio)

## راه‌اندازی محلی

1. کلون کردن مخزن:
   ```bash
   git clone https://github.com/yourusername/telegram-gmail-api-bot.git
   cd telegram-gmail-api-bot
   ```

2. نصب وابستگی‌ها:
   ```bash
   pip install -e .
   ```

3. تنظیم متغیرهای محیطی:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   DATABASE_URL=postgresql://username:password@localhost:5432/database_name
   TWILIO_ACCOUNT_SID=your_twilio_sid
   TWILIO_AUTH_TOKEN=your_twilio_token
   TWILIO_PHONE_NUMBER=your_twilio_phone
   ```

4. اجرای برنامه:
   ```bash
   python main.py
   ```

## استقرار در Railway

برای اطلاعات دقیق در مورد استقرار در Railway و رفع مشکل `distutils`, به فایل [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) مراجعه کنید.

## مشکل distutils در Python 3.12

اگر با خطای `ModuleNotFoundError: No module named 'distutils'` مواجه شدید، به فایل [alternative_import.md](alternative_import.md) مراجعه کنید یا از یکی از راه‌حل‌های زیر استفاده کنید:

1. استفاده از Dockerfile ارائه شده
2. تنظیم Railway با فایل railway.toml
3. استفاده از اسکریپت monkey_patch.py
4. استفاده از فایل fix-distutils.py 

## ساختار پروژه

```
├── main.py                  # نقطه ورود اصلی برنامه
├── telegram_bot_inline.py   # پیاده‌سازی ربات تلگرام با منوی شیشه‌ای
├── gmail_creator.py         # ماژول ساخت حساب Gmail
├── api_key_generator.py     # ماژول دریافت کلید API از Google Gemini
├── gemini_api_validator.py  # اعتبارسنجی کلیدهای API
├── twilio_integration.py    # یکپارچه‌سازی با Twilio برای تأیید شماره تلفن
├── proxy_manager.py         # مدیریت پروکسی‌ها
├── models.py                # مدل‌های پایگاه داده
├── monkey_patch.py          # ترمیم مشکل distutils
├── fix-distutils.py         # اسکریپت رفع مشکل distutils
├── Dockerfile               # فایل Docker برای استقرار
├── railway.toml             # تنظیمات Railway
├── Procfile                 # برای استقرار در Railway یا Heroku
└── DEPLOYMENT_GUIDE.md      # راهنمای استقرار
```

## استفاده

1. به ربات تلگرام خود پیام `/start` را ارسال کنید
2. از منوی اصلی، گزینه‌ی "ساخت حساب و دریافت API Key" را انتخاب کنید
3. اگر نیاز به استفاده از پروکسی دارید، گزینه‌ی مربوط به پروکسی را انتخاب کنید
4. منتظر بمانید تا ربات به طور خودکار حساب Gmail را بسازد و کلید API را دریافت کند
5. پس از تکمیل فرآیند، ربات اطلاعات حساب و کلید API را برای شما ارسال می‌کند

## مساهمت

پیشنهادات و مشارکت‌های شما استقبال می‌شود. لطفاً برای هرگونه تغییر، یک درخواست pull ارسال کنید.

## مجوز

این پروژه تحت مجوز MIT منتشر شده است.