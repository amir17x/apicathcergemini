# راه‌حل‌های رفع خطای 409 (Conflict) در Telegram Bot API

## مشکل چیست؟
خطای 409 Conflict در Telegram Bot API زمانی رخ می‌دهد که چندین نمونه از ربات شما همزمان در حال تلاش برای دریافت آپدیت‌ها هستند. این مشکل معمولاً در محیط Railway و سایر سرویس‌های ابری که چندین نمونه از برنامه را اجرا می‌کنند، رایج است.

## پیام خطا
```
Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
```

## راه‌حل‌های سریع

### 1. استفاده از اسکریپت رفع خطا

اجرای اسکریپت `fix_telegram_errors.py`:

```bash
python fix_telegram_errors.py
```

این اسکریپت به طور خودکار:
- اتصال به API تلگرام را بررسی می‌کند
- webhook فعلی را حذف می‌کند
- فرآیندهای ربات در حال اجرا را متوقف می‌کند
- آپدیت‌های در انتظار را پاک می‌کند

### 2. حذف دستی Webhook

```bash
# جایگزین کردن YOUR_TOKEN با توکن ربات شما
curl "https://api.telegram.org/botYOUR_TOKEN/deleteWebhook?drop_pending_updates=true"
```

سپس برنامه را راه‌اندازی مجدد کنید:
```bash
# در Railway
# ویرایش یک متغیر محیطی (بدون تغییر دادن مقدار آن) برای راه‌اندازی مجدد خودکار
```

### 3. تنظیم مجدد Webhook (برای محیط Railway)

اجرای اسکریپت `railway_webhook_setup.py`:

```bash
python railway_webhook_setup.py
```

این اسکریپت به طور خودکار webhook را با آدرس صحیح دامنه Railway تنظیم می‌کند.

## راه‌حل‌های پایدار

### 1. استفاده از اسکریپت راه‌انداز هوشمند

اسکریپت `smart_launcher.py` به طور هوشمند وضعیت را بررسی کرده و راه‌اندازی مناسب را انجام می‌دهد:

```bash
python smart_launcher.py
```

این اسکریپت:
- محیط را تشخیص می‌دهد (Railway یا غیره)
- حالت مناسب (webhook یا long polling) را انتخاب می‌کند
- از اجرای چندین نمونه جلوگیری می‌کند

### 2. تنظیم صحیح متغیرهای محیطی

برای جلوگیری از خطای 409، یکی از دو حالت زیر را انتخاب کنید:

**حالت Webhook (توصیه شده برای Railway):**
```
BOT_MODE=webhook
```

**حالت Long Polling (برای محیط‌های دیگر):**
```
BOT_MODE=polling
```

### 3. محدود کردن تعداد نمونه‌ها در Railway

در تنظیمات Railway:
1. تعداد نمونه‌ها را به 1 محدود کنید
2. از autoscaling استفاده نکنید
3. گزینه Always On را فعال کنید

## بررسی وضعیت

برای بررسی وضعیت فعلی webhook:

```bash
# جایگزین کردن YOUR_TOKEN با توکن ربات شما
curl "https://api.telegram.org/botYOUR_TOKEN/getWebhookInfo"
```

## راه‌حل نهایی برای Railway

1. اطمینان حاصل کنید که `BOT_MODE=webhook` تنظیم شده است
2. اسکریپت `fix_telegram_errors.py` را اجرا کنید
3. سپس اسکریپت `railway_webhook_setup.py` را اجرا کنید
4. برنامه را راه‌اندازی مجدد کنید

## توجه
هر بار که کد را به Railway پوش می‌کنید، ممکن است چندین نمونه برای مدت کوتاهی اجرا شوند. این رفتار طبیعی است و پس از استقرار کامل، فقط یک نمونه باقی می‌ماند.