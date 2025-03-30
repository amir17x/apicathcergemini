#!/usr/bin/env python3
"""
✨ نقطه ورود اصلی برای برنامه ✨
این فایل تنظیمات دیتابیس و راه‌اندازی ربات تلگرام را انجام می‌دهد.
نسخه بهینه‌شده برای Railway با مکانیزم قفل فایل
"""

import os
import sys
import logging
import threading
import time
import requests
from flask import Flask, request, jsonify
from telegram_bot_inline import InlineTelegramBot
from models import db, User, Account
import datetime
from telegram_single_instance import TelegramSingleInstance

# کلاس سفارشی برای فرمت‌دهی لاگ با رنگ‌های شیک
class ColoredFormatter(logging.Formatter):
    """فرمتر سفارشی برای ایجاد لاگ‌های رنگی و زیبا"""
    
    # کدهای رنگی ANSI
    COLORS = {
        'DEBUG': '\033[1;36m',     # آبی فیروزه‌ای پررنگ
        'INFO': '\033[1;32m',      # سبز پررنگ
        'WARNING': '\033[1;33m',   # زرد پررنگ
        'ERROR': '\033[1;31m',     # قرمز پررنگ
        'CRITICAL': '\033[1;35m',  # بنفش پررنگ
        'RESET': '\033[0m'         # بازنشانی رنگ
    }
    
    # نمادهای زیبا برای هر سطح لاگ
    SYMBOLS = {
        'DEBUG': '🔍',
        'INFO': '✨',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    def format(self, record):
        # افزودن نماد مناسب به پیام
        symbol = self.SYMBOLS.get(record.levelname, '✧')
        
        # تنظیم رنگ مناسب بر اساس سطح لاگ
        color_code = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset_code = self.COLORS['RESET']
        
        # فرمت‌دهی زمان با سبک فارسی
        now = datetime.datetime.now()
        persianized_time = f"{now:%Y-%m-%d %H:%M:%S}"
        
        # ایجاد پیام نهایی با رنگ و نماد
        formatted_msg = f"{color_code}[{persianized_time}] - {record.name} - {symbol} {record.levelname}: {record.getMessage()}{reset_code}"
        
        return formatted_msg

# تنظیم لاگینگ فارسی و رنگی برای سازگاری با Railway
handler = logging.StreamHandler(sys.stdout)  # ارسال لاگ ها به stdout برای مشاهده در Railway
handler.setFormatter(ColoredFormatter())

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# اطلاعات شروع برنامه با طراحی زیبا
logger.info("╔" + "═" * 70 + "╗")
logger.info("║" + " " * 10 + "🚀 آغاز به کار سیستم ربات تلگرام - بهینه‌شده برای Railway" + " " * 10 + "║")
logger.info("║" + " " * 10 + "📅 تاریخ اجرا: " + datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S") + " " * 23 + "║")
logger.info("╚" + "═" * 70 + "╝")

# ایجاد Flask app برای API و دیتابیس
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "a secure secret key")

# تنظیم دیتابیس
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# راه‌اندازی دیتابیس با app
db.init_app(app)

# متغیر سراسری برای ربات تلگرام
global_bot = None

# ایجاد جداول دیتابیس
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ جداول دیتابیس با موفقیت ایجاد شدند")
    except Exception as e:
        logger.error(f"❌ خطا در ایجاد جداول دیتابیس: {e}")

def setup_bot():
    """ایجاد و راه‌اندازی نمونه ربات تلگرام"""
    global global_bot
    
    # اگر ربات قبلاً راه‌اندازی شده باشد، فقط وضعیت را گزارش می‌دهیم
    if global_bot:
        logger.info("ربات تلگرام قبلاً راه‌اندازی شده است")
        return global_bot
    
    logger.info("🔄 شروع راه‌اندازی ربات تلگرام")
    
    # دریافت توکن از متغیرهای محیطی
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ توکن ربات تلگرام یافت نشد - متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است")
        return None
    
    try:
        # ساخت نمونه ربات با ارسال Flask app برای دسترسی به دیتابیس
        bot = InlineTelegramBot(token=token, app=app)
        
        # تست اتصال به API تلگرام
        try:
            response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
            if response.status_code == 200 and response.json().get('ok'):
                bot_info = response.json().get('result', {})
                logger.info(f"✅ اتصال به ربات برقرار شد: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
                
                # استفاده از روش بهتر برای پاکسازی آپدیت‌های قبلی - ابتدا حذف webhook
                try:
                    # ابتدا webhook را حذف می‌کنیم و آپدیت‌های در انتظار را پاک می‌کنیم
                    webhook_delete_response = requests.post(
                        f"https://api.telegram.org/bot{token}/deleteWebhook",
                        json={'drop_pending_updates': True},
                        timeout=10
                    )
                    
                    if webhook_delete_response.status_code == 200 and webhook_delete_response.json().get('ok'):
                        logger.info("✅ وبهوک با موفقیت حذف شد و آپدیت‌های در انتظار پاک شدند")
                        time.sleep(2)  # کمی صبر می‌کنیم تا تغییرات اعمال شود
                    
                    # حالا برای اطمینان از طریق getUpdates هم تلاش می‌کنیم
                    response = requests.get(
                        f"https://api.telegram.org/bot{token}/getUpdates",
                        params={'offset': -1, 'limit': 1, 'timeout': 5},
                        timeout=10
                    )
                    
                    if response.status_code == 200 and response.json().get('ok') and response.json().get('result'):
                        updates = response.json().get('result')
                        if updates:
                            last_update_id = updates[-1]["update_id"]
                            offset = last_update_id + 1
                            # حذف همه‌ی آپدیت‌های قبلی
                            clear_response = requests.get(
                                f"https://api.telegram.org/bot{token}/getUpdates",
                                params={'offset': offset, 'limit': 1, 'timeout': 5},
                                timeout=10
                            )
                            
                            if clear_response.status_code == 200 and clear_response.json().get('ok'):
                                logger.info(f"✅ همه‌ی آپدیت‌های قبلی پاک شدند - تنظیم آفست به {offset}")
                    
                    # در نهایت، تلاش می‌کنیم اتصال قبلی را ببندیم
                    try:
                        close_response = requests.post(f"https://api.telegram.org/bot{token}/close", timeout=10)
                        if close_response.status_code == 200:
                            logger.info("✅ اتصال قبلی بسته شد")
                        time.sleep(2)  # کمی صبر می‌کنیم تا اتصال کاملاً بسته شود
                    except Exception as close_error:
                        logger.error(f"❌ خطا در بستن اتصال قبلی: {close_error}")
                        
                except Exception as e:
                    logger.error(f"❌ خطا در پاکسازی آپدیت‌های قبلی: {e}")
                
                # تنظیم ربات سراسری
                global_bot = bot
                return bot
            else:
                logger.error(f"❌ خطا در اتصال به API تلگرام: {response.text}")
                return None
        except Exception as e:
            logger.error(f"❌ خطا در اتصال به API تلگرام: {e}")
            return None
    except Exception as e:
        logger.error(f"❌ خطا در راه‌اندازی ربات تلگرام: {e}")
        return None

def start_bot_in_thread():
    """راه‌اندازی ربات در یک ترد جداگانه"""
    bot = setup_bot()
    if not bot:
        logger.error("❌ ربات راه‌اندازی نشد، ترد شروع نمی‌شود")
        return
    
    def bot_runner():
        try:
            logger.info("🚀 شروع حلقه‌ی اصلی ربات")
            # اجرای حلقه‌ی اصلی ربات
            bot.run()
        except Exception as e:
            logger.error(f"❌ ترد ربات با خطا متوقف شد: {e}")
    
    # ایجاد و شروع ترد
    bot_thread = threading.Thread(target=bot_runner, name="TelegramBotThread")
    bot_thread.daemon = True  # اجازه می‌دهد برنامه اصلی بدون منتظر ماندن برای ترد، خاتمه یابد
    bot_thread.start()
    logger.info(f"✅ ترد ربات با شناسه {bot_thread.ident} شروع به کار کرد")

# مسیرهای Flask برای سلامت‌سنجی
@app.route('/')
def index():
    """مسیر اصلی و سلامت‌سنجی ساده"""
    # راه‌اندازی ربات اگر هنوز شروع نشده باشد
    if not global_bot:
        start_bot_in_thread()
    return "ربات تلگرام در حال اجراست."

@app.route('/status')
def status():
    """مسیر بررسی وضعیت ربات"""
    # راه‌اندازی ربات اگر هنوز شروع نشده باشد
    if not global_bot:
        start_bot_in_thread()
    
    # بررسی وضعیت دیتابیس
    with app.app_context():
        try:
            user_count = User.query.count()
            account_count = Account.query.count()
            db_status = "متصل"
        except Exception as e:
            logger.error(f"❌ خطا در اتصال به دیتابیس: {e}")
            user_count = 0
            account_count = 0
            db_status = f"خطا: {str(e)}"
    
    return jsonify({
        "bot_status": "در حال اجرا" if global_bot else "متوقف",
        "database_status": db_status,
        "user_count": user_count,
        "account_count": account_count,
        "status": "ok"
    })

@app.route('/healthz')
def healthz():
    """مسیر سلامت‌سنجی ساده برای Railway"""
    return "OK", 200

@app.route('/health')
def health():
    """مسیر پشتیبان سلامت‌سنجی"""
    return "OK", 200

@app.route('/restart', methods=['POST'])
def restart_bot():
    """مسیر راه‌اندازی مجدد ربات"""
    global global_bot
    global_bot = None  # پاک کردن ربات فعلی
    start_bot_in_thread()  # راه‌اندازی مجدد
    return jsonify({"status": "ربات با موفقیت راه‌اندازی مجدد شد"})

@app.route('/webhook', methods=['POST'])
def webhook():
    """دریافت آپدیت‌های تلگرام از طریق webhook"""
    if request.method == 'POST':
        try:
            update = request.get_json()
            logger.info(f"Webhook received: {update}")
            
            # راه‌اندازی ربات اگر هنوز شروع نشده باشد
            if not global_bot:
                start_bot_in_thread()
                
            if global_bot:
                # ارسال آپدیت به ربات برای پردازش
                global_bot.handle_updates([update])
            
            return jsonify({"status": "ok"})
        except Exception as e:
            logger.error(f"Error in webhook handler: {e}")
            return jsonify({"status": "error", "message": str(e)})
    
    return jsonify({"status": "ok"})

@app.route('/set_webhook')
def set_webhook():
    """تنظیم وبهوک تلگرام برای Railway"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return jsonify({"status": "error", "message": "No bot token found"})
    
    # آدرس سرویس Railway را از محیط دریافت می‌کنیم
    railway_url = os.environ.get("RAILWAY_STATIC_URL")
    if not railway_url:
        railway_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    
    if not railway_url:
        # تلاش برای استفاده از آدرس درخواست فعلی
        host = request.host
        if host:
            railway_url = host
        else:
            return jsonify({"status": "error", "message": "Railway URL not found"})
    
    webhook_url = f"https://{railway_url}/webhook"
    logger.info(f"Setting webhook to: {webhook_url}")
    
    try:
        # ابتدا پاکسازی کامل و اطمینان از بسته شدن اتصال‌های قبلی
        # حذف webhook با drop_pending_updates=True
        logger.info("🔄 حذف webhook قبلی و آپدیت‌های در انتظار...")
        delete_response = requests.post(
            f"https://api.telegram.org/bot{token}/deleteWebhook",
            json={'drop_pending_updates': True},
            timeout=10
        )
        
        if delete_response.status_code == 200 and delete_response.json().get('ok'):
            logger.info("✅ وبهوک قبلی با موفقیت حذف شد و آپدیت‌های در انتظار پاک شدند")
        else:
            logger.warning(f"⚠️ خطا در حذف وبهوک قبلی: {delete_response.text}")
        
        # تلاش برای بستن اتصال‌های قبلی
        try:
            close_response = requests.post(f"https://api.telegram.org/bot{token}/close", timeout=10)
            if close_response.status_code == 200:
                logger.info("✅ همه اتصال‌های قبلی بسته شدند")
            time.sleep(2)  # کمی صبر می‌کنیم تا تغییرات اعمال شوند
        except Exception as close_error:
            logger.error(f"خطا در بستن اتصال‌های قبلی: {close_error}")
        
        # تنظیم webhook جدید با گزینه‌های بیشتر
        logger.info(f"🔄 تنظیم webhook جدید به آدرس: {webhook_url}")
        response = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={
                "url": webhook_url,
                "max_connections": 40,  # افزایش تعداد اتصال‌های همزمان برای کارایی بهتر
                "allowed_updates": ["message", "edited_message", "callback_query"]  # محدود کردن انواع آپدیت‌ها
            },
            timeout=15
        )
        
        # بررسی وضعیت فعلی webhook
        status_response = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo")
        
        return jsonify({
            "status": "ok", 
            "response": response.json(),
            "webhook_info": status_response.json(),
            "webhook_url": webhook_url
        })
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/remove_webhook')
def remove_webhook():
    """حذف وبهوک تلگرام و استفاده از روش long polling"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return jsonify({"status": "error", "message": "No bot token found"})
    
    try:
        # استفاده از روش بهتر برای پاکسازی - حذف وبهوک با drop_pending_updates
        response = requests.post(
            f"https://api.telegram.org/bot{token}/deleteWebhook",
            json={'drop_pending_updates': True},
            timeout=10
        )
        
        logger.info("✅ وبهوک با موفقیت حذف شد و آپدیت‌های در انتظار پاک شدند")
        
        # تلاش برای بستن اتصال‌های قبلی
        try:
            close_response = requests.post(f"https://api.telegram.org/bot{token}/close", timeout=10)
            if close_response.status_code == 200:
                logger.info("✅ همه اتصال‌های قبلی بسته شدند")
        except Exception as close_error:
            logger.error(f"خطا در بستن اتصال‌های قبلی: {close_error}")
        
        # کمی صبر می‌کنیم تا همه تغییرات اعمال شوند
        time.sleep(3)
        
        # راه‌اندازی مجدد ربات با حالت long polling
        global global_bot
        global_bot = None  # پاک کردن ربات فعلی
        start_bot_in_thread()  # راه‌اندازی مجدد
        
        return jsonify({
            "status": "ok", 
            "response": response.json(),
            "message": "Webhook removed, bot started in long polling mode"
        })
    except Exception as e:
        logger.error(f"Error removing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)})

# راه‌اندازی ربات در هنگام شروع برنامه - با مکانیزم قفل فایل
def run_bot_with_lock():
    """راه‌اندازی ربات تلگرام با مکانیزم قفل فایل برای جلوگیری از اجرای چند نمونه"""
    logger.info("🔄 شروع راه‌اندازی ربات با مکانیزم قفل فایل")
    
    def bot_main_function():
        """تابع اصلی ربات که در صورت موفقیت در گرفتن قفل اجرا می‌شود"""
        try:
            # ابتدا بررسی می‌کنیم آیا webhook فعال شده است
            logger.info("🔄 بررسی وضعیت webhook قبل از راه‌اندازی ربات")
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            webhook_response = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo")
            
            if webhook_response.status_code == 200 and webhook_response.json().get('ok', False):
                webhook_info = webhook_response.json().get('result', {})
                webhook_url = webhook_info.get('url', '')
                
                if webhook_url:
                    logger.info(f"✅ Webhook فعال است: {webhook_url}")
                    # وقتی webhook فعال است، نیازی به راه‌اندازی long polling نیست
                    if '/webhook' in webhook_url:
                        logger.info("⚠️ Webhook فعال است، long polling راه‌اندازی نمی‌شود")
                        global_bot = setup_bot()
                        if global_bot:
                            global_bot.webhook_mode = True  # تنظیم حالت webhook
                            logger.info("✅ ربات در حالت webhook آماده است")
                    else:
                        logger.info("🔄 تلاش برای راه‌اندازی ربات در شروع برنامه")
                        start_bot_in_thread()
                else:
                    logger.info("🔄 Webhook فعال نیست، راه‌اندازی ربات در حالت long polling")
                    start_bot_in_thread()
            else:
                logger.warning(f"⚠️ خطا در بررسی وضعیت webhook: {webhook_response.text}")
                logger.info("🔄 تلاش برای راه‌اندازی ربات در شروع برنامه")
                start_bot_in_thread()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ خطا در راه‌اندازی ربات: {e}")
            return False
    
    # ایجاد نمونه مدیریت تک‌نمونه برای ربات تلگرام
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ توکن ربات تلگرام یافت نشد! لطفاً آن را در متغیرهای محیطی تنظیم کنید.")
        return False
    
    instance_manager = TelegramSingleInstance(telegram_bot_token=token)
    result = instance_manager.run_as_single_instance(bot_main_function)
    
    return result

# اجرای تابع راه‌اندازی با مکانیزم قفل فایل
try:
    run_bot_with_lock()
except Exception as e:
    logger.error(f"❌ خطا در راه‌اندازی ربات با مکانیزم قفل فایل: {e}")
    # در صورت خطا، تلاش برای راه‌اندازی به روش معمولی
    try:
        logger.info("🔄 تلاش برای راه‌اندازی به روش معمولی...")
        start_bot_in_thread()
    except Exception as fallback_error:
        logger.critical(f"❌ خطای بحرانی در راه‌اندازی ربات: {fallback_error}")
        # در اینجا می‌توان کد مدیریت خطای بیشتری اضافه کرد

# اجرای Flask app در حالت مستقل
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 شروع وب سرور Flask در پورت {port}")
    app.run(host="0.0.0.0", port=port)