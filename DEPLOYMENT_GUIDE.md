# 🚂 راهنمای استقرار برنامه در Railway

این راهنما به شما کمک می‌کند تا برنامه ربات تلگرام خود را به درستی در Railway استقرار دهید و مشکل‌های احتمالی را برطرف کنید.

## 📋 مراحل استقرار (گام به گام)

1. یک حساب کاربری در [Railway](https://railway.app/) ایجاد کنید (اگر ندارید)
2. مخزن گیت‌هاب خود را به Railway متصل کنید یا مستقیماً با CLI آپلود نمایید
3. یک سرویس دیتابیس PostgreSQL در Railway ایجاد کنید:
   - در داشبورد Railway، روی "New Service" کلیک کنید
   - گزینه "Database" و سپس "PostgreSQL" را انتخاب کنید
   - منتظر بمانید تا دیتابیس ایجاد شود
4. متغیرهای محیطی زیر را تنظیم کنید:
   - `TELEGRAM_BOT_TOKEN`: توکن ربات تلگرام شما
   - `DATABASE_URL`: به صورت خودکار تنظیم می‌شود (اگر از دیتابیس Railway استفاده می‌کنید)
   - سایر متغیرهای محیطی مورد نیاز مانند کلیدهای TWILIO اگر از آن استفاده می‌کنید
5. روش استقرار را بر اساس Dockerfile تنظیم کنید:
   - در تنظیمات سرویس، به بخش Settings بروید
   - در قسمت Deploy، اطمینان حاصل کنید که "Dockerfile" انتخاب شده باشد
6. استقرار را آغاز کنید با کلیک روی "Deploy"
7. لاگ‌ها را برای اطمینان از اجرای درست بررسی نمایید
8. آدرس نهایی برنامه شما در بخش "Deployments" قابل مشاهده خواهد بود

## ⚠️ مشکلات رایج و راه‌حل‌ها

### مشکل ۱: ModuleNotFoundError: No module named 'distutils'

در Python 3.12 که در Railway استفاده می‌شود، ماژول `distutils` حذف شده است. کتابخانه `undetected-chromedriver` به این ماژول وابسته است.

## راه‌حل‌ها

برای رفع این مشکل، چندین راه‌حل در اختیار شما قرار داده شده است. می‌توانید یکی از این روش‌ها را انتخاب کنید:

### روش ۱: استفاده از Dockerfile (توصیه شده)

فایل `Dockerfile` که در مخزن ارائه شده، یک محیط پایدار با Python 3.10 و تمام وابستگی‌های مورد نیاز ایجاد می‌کند. کافی است اطمینان حاصل کنید که Railway برای استقرار از Dockerfile استفاده می‌کند.

1. در تنظیمات پروژه Railway، به بخش Settings بروید
2. در قسمت Deploy، حالت را به "Nixpacks" یا "Docker" تغییر دهید
3. فایل `Dockerfile` باید به صورت خودکار شناسایی و استفاده شود

### روش ۲: استفاده از تنظیمات Railway

فایل `railway.toml` تنظیمات لازم برای نصب وابستگی‌های سیستمی و استفاده از Python 3.10 را فراهم می‌کند.

### روش ۳: استفاده از Procfile و اسکریپت تعمیر

فایل `Procfile` و اسکریپت `fix-distutils.py` به طور خودکار مشکل را قبل از اجرای اصلی برنامه برطرف می‌کنند.

### روش ۴: تغییر دستی فایل patcher.py

می‌توانید فایل `patcher.py` را مستقیماً در محیط Railway بعد از استقرار تغییر دهید:

1. به ترمینال SSH در Railway وصل شوید
2. مسیر کتابخانه را پیدا کنید:
   ```bash
   find /opt -name patcher.py | grep undetected_chromedriver
   ```
3. فایل را ویرایش کنید:
   ```bash
   nano [مسیر_فایل_پیدا_شده]
   ```
4. خط `from distutils.version import LooseVersion` را به `from packaging.version import parse as LooseVersion` تغییر دهید
5. ابتدا مطمئن شوید که `pip install packaging` را اجرا کرده‌اید

## نکات مهم

1. **متغیرهای محیطی**: مطمئن شوید که تمام متغیرهای محیطی لازم (TELEGRAM_BOT_TOKEN، TWILIO_ACCOUNT_SID و غیره) در تنظیمات Railway وارد شده‌اند.

2. **پورت**: Railway به صورت خودکار یک پورت را از طریق متغیر محیطی `PORT` اختصاص می‌دهد. در Dockerfile و Procfile، از `${PORT:-5000}` استفاده شده تا در صورت عدم تعریف متغیر، از پورت 5000 استفاده شود. اگر با خطای `'$PORT' is not a valid port number` مواجه شدید، حتماً از این روش استفاده کنید.

3. **دیتابیس**: اگر از پایگاه داده PostgreSQL استفاده می‌کنید، مطمئن شوید که یک خدمت دیتابیس در Railway تنظیم کرده‌اید و متغیر محیطی `DATABASE_URL` به درستی تنظیم شده است.

4. **بازبینی لاگ‌ها**: بعد از استقرار، لاگ‌ها را بررسی کنید تا از اجرای صحیح برنامه مطمئن شوید.

## عیب‌یابی

اگر همچنان با مشکل مواجه هستید:

1. **خطای PORT**: اگر با خطای `'$PORT' is not a valid port number` مواجه می‌شوید، مراحل زیر را انجام دهید:
   - در `Dockerfile` و `Procfile` از عبارت `${PORT:-5000}` به جای `$PORT` استفاده کنید
   - در تنظیمات پروژه Railway متغیر محیطی `PORT` را به صورت دستی با مقدار عددی (مثلاً ۵۰۰۰) تنظیم کنید
   - در فایل `railway.toml` در بخش `[variables]` مقدار `PORT = "5000"` را اضافه کنید
   - برای هر متغیر محیطی در `${VAR}` اطمینان حاصل کنید که یک مقدار پیش‌فرض مانند `${VAR:-default}` در نظر گرفته شده

2. **مشکل healthcheck**: اگر با خطای "Service unavailable" در healthcheck مواجه می‌شوید:
   - ساده‌ترین راه‌حل: مسیر healthcheck را در فایل `railway.toml` به `/healthz` تغییر دهید و مطمئن شوید که اندپوینت مربوطه در `main.py` پاسخ ساده‌ای مثل `"OK"` برمی‌گرداند
   - اگر با خطای persistent مواجه هستید، چندین مسیر healthcheck را امتحان کنید: `/healthz`، `/health` و `/_health`
   - `healthcheckTimeout` را به ۳۰ ثانیه و `healthcheckInterval` را به ۳۰ ثانیه تغییر دهید
   - در فایل `railway.toml` چندین مسیر healthcheck به صورت زیر تعریف کنید:
     ```toml
     [[healthchecks]]
     path = "/healthz"
     timeout = 30
     interval = 15
     grace = 120
     
     [[healthchecks]]
     path = "/health"
     timeout = 30
     interval = 15
     ```
   - اطمینان حاصل کنید که مسیرهای healthcheck به درستی در `main.py` پیاده‌سازی شده‌اند و پاسخ بسیار ساده‌ای می‌دهند
   - اگر باز هم مشکل ادامه داشت، سعی کنید `workers` را در Gunicorn به ۱ کاهش دهید تا بار کاری سرور کمتر شود

3. **استفاده از نسخه خاص کتابخانه**: می‌توانید به صورت دستی نسخه خاصی از undetected-chromedriver را نصب کنید که با Python 3.12 سازگار است.

4. **غیرفعال کردن موقت**: برای تست، می‌توانید با تغییر موقت کد، بخش‌های مربوط به جیمیل‌کریتور و اتوماسیون وب را غیرفعال کنید تا حداقل ربات تلگرام کار کند.

5. **پشتیبانی Railway**: می‌توانید از تیم پشتیبانی Railway درخواست کمک کنید یا به انجمن آن‌ها مراجعه کنید.

امیدوارم یکی از این راه‌حل‌ها مشکل شما را برطرف کند!

## 🔍 رفع خطای "Service Unavailable" در هنگام استقرار

اگر با خطای `Healthcheck Retry window: 2m0s` و `Attempt # failed with service unavailable` مواجه می‌شوید، این خطا نشان می‌دهد که Railway نمی‌تواند به مسیر سلامت‌سنجی برنامه دسترسی پیدا کند. برای رفع این مشکل موارد زیر را انجام دهید:

### راه‌حل فوری:

1. **ساده‌سازی اندپوینت healthcheck**:
   ```python
   @app.route('/healthz')
   def healthz():
       return "OK", 200
   ```
   
2. **اضافه کردن چندین مسیر healthcheck**:
   ```python
   @app.route('/health')
   def health():
       return "OK", 200
       
   @app.route('/_health')
   def _health():
       return "OK", 200
   ```

3. **تنظیم صحیح فایل railway.toml**:
   ```toml
   [deploy]
   healthcheckPath = "/healthz"
   healthcheckTimeout = 30
   healthcheckInterval = 30
   
   [[healthchecks]]
   path = "/healthz"
   timeout = 30
   interval = 15
   grace = 120
   ```

4. **تنظیم Gunicorn برای پاسخگویی سریع**:
   ```
   web: gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 2 --timeout 90 --keep-alive 5 main:app
   ```

5. **فعال کردن لاگ‌ها برای عیب‌یابی**:
   ```
   --access-logfile - --error-logfile -
   ```

با اعمال این تغییرات، مشکل "Service Unavailable" باید برطرف شود و استقرار با موفقیت انجام شود.