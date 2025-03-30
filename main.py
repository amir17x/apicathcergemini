#!/usr/bin/env python3
"""
نقطه ورود اصلی برای برنامه.
این فایل تنظیمات دیتابیس و راه‌اندازی ربات تلگرام را انجام می‌دهد.
نسخه بهینه‌شده برای Railway با حذف مکانیزم قفل فایل
"""

import os
import logging
import threading
import time
import requests
from flask import Flask, request, jsonify
from telegram_bot_inline import InlineTelegramBot
from models import db, User, Account

# تنظیم لاگینگ کاربردی
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# اطلاعات شروع برنامه
logger.info("=" * 50)
logger.info("TELEGRAM BOT APPLICATION STARTING - RAILWAY OPTIMIZED")
logger.info("=" * 50)

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
                
                # پاکسازی آپدیت‌های قبلی برای شروع تمیز
                try:
                    response = requests.get(
                        f"https://api.telegram.org/bot{token}/getUpdates",
                        params={'offset': -1, 'limit': 1, 'timeout': 5},
                        timeout=10
                    )
                    if response.json().get('ok') and response.json().get('result'):
                        updates = response.json().get('result')
                        if updates:
                            last_update_id = updates[-1]["update_id"]
                            offset = last_update_id + 1
                            # حذف همه‌ی آپدیت‌های قبلی
                            requests.get(
                                f"https://api.telegram.org/bot{token}/getUpdates",
                                params={'offset': offset, 'limit': 1, 'timeout': 5},
                                timeout=10
                            )
                            logger.info(f"✅ همه‌ی آپدیت‌های قبلی پاک شدند - تنظیم آفست به {offset}")
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

# راه‌اندازی ربات در هنگام شروع برنامه
logger.info("🔄 تلاش برای راه‌اندازی ربات در شروع برنامه")
start_bot_in_thread()

# اجرای Flask app در حالت مستقل
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 شروع وب سرور Flask در پورت {port}")
    app.run(host="0.0.0.0", port=port)