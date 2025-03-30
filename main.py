#!/usr/bin/env python3
"""
Main entry point for the application.
This file implements the database configuration and runs the Telegram bot.
"""

import os
import logging
import sys
import time
import threading
from flask import Flask, request, jsonify
from telegram_bot_inline import InlineTelegramBot
from models import db, User, Account

# Initialize Flask app for the API and database
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "a secret key")

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# Initialize database with app
db.init_app(app)

# Create global variable to track bot thread
_bot_thread = None

# Configure logging to file for better debugging
import os
from logging.handlers import RotatingFileHandler

# Make sure log file exists and is writable
log_file = "/tmp/telegram_bot.log"
try:
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    # Create empty file if it doesn't exist
    if not os.path.exists(log_file):
        with open(log_file, 'w') as f:
            f.write('')
    # Test that we can write to it
    with open(log_file, 'a') as f:
        f.write('')
except Exception as e:
    print(f"WARNING: Cannot create or write to log file: {e}")
    log_file = None

handlers = [logging.StreamHandler()]  # Always log to console
if log_file:
    # Add rotating file handler to avoid large log files
    file_handler = RotatingFileHandler(
        log_file, maxBytes=1024*1024*5, backupCount=3
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    handlers.append(file_handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("=" * 50)
logger.info("TELEGRAM BOT APPLICATION STARTING")
logger.info("=" * 50)

# Create database tables
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")

def start_bot_thread():
    """Start the bot in a separate thread if not already running"""
    global _bot_thread
    
    # اگر ترد قبلی وجود داشته باشد، ابتدا آن را متوقف می‌کنیم
    if _bot_thread and _bot_thread.is_alive():
        logger.info(f"🛑 ترد قبلی ربات با شناسه {_bot_thread.ident} در حال اجراست. فعلاً نمونه جدیدی راه‌اندازی نمی‌شود.")
        return  # اگر ربات در حال اجراست، نمونه جدیدی راه‌اندازی نمی‌کنیم
    
    # ثبت یک فایل قفل برای جلوگیری از اجرای همزمان چند ربات
    lock_file = '/tmp/telegram_bot.lock'
    
    # بررسی اینکه آیا قفل قبلی وجود دارد
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                pid = f.read().strip()
                # بررسی اینکه آیا پروسه قبلی هنوز در حال اجراست
                try:
                    os.kill(int(pid), 0)  # سیگنال 0 فقط برای بررسی وجود پروسه است
                    logger.info(f"🛑 یک نمونه دیگر از ربات با PID {pid} در حال اجراست.")
                    return
                except OSError:
                    # پروسه دیگر وجود ندارد، فایل قفل را حذف می‌کنیم
                    logger.info(f"🔓 فایل قفل قدیمی متعلق به PID {pid} پیدا شد اما پروسه در حال اجرا نیست. قفل حذف می‌شود.")
                    os.remove(lock_file)
        except Exception as e:
            logger.error(f"❌ خطا در بررسی فایل قفل: {e}")
            # حذف فایل قفل مشکوک
            try:
                os.remove(lock_file)
            except:
                pass
    
    # ایجاد قفل جدید
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        
        logger.info("🚀 شروع ربات در یک ترد جداگانه")
        
        def bot_runner():
            try:
                logger.info("Creating Inline Telegram Bot instance in thread")
                # تنظیم سطح لاگ به DEBUG برای دریافت اطلاعات بیشتر
                logging.getLogger().setLevel(logging.DEBUG)
                
                # ساخت نمونه‌ی ربات با ارسال فلسک اپ برای دسترسی به دیتابیس
                bot = InlineTelegramBot(app=app)
                logger.info(f"Bot instance created, token valid: {bool(bot.token)}")
                
                # تست اتصال به API تلگرام
                try:
                    import requests
                    response = requests.get(f"https://api.telegram.org/bot{bot.token}/getMe", timeout=10)
                    logger.info(f"getMe response: {response.text}")
                    
                    # بررسی صحت پاسخ دریافتی
                    if not response.json().get('ok'):
                        logger.error(f"Telegram API returned error: {response.text}")
                        return  # خروج در صورت خطا
                except Exception as get_me_error:
                    logger.error(f"getMe error: {get_me_error}")
                    return  # خروج در صورت خطا در اتصال
                
                # حذف آپدیت‌های قبلی برای شروع تمیز
                try:
                    logger.info("Getting and clearing previous updates...")
                    response = requests.get(
                        f"https://api.telegram.org/bot{bot.token}/getUpdates",
                        params={'offset': -1, 'limit': 1, 'timeout': 1},
                        timeout=10
                    )
                    if response.json().get('ok') and response.json().get('result'):
                        updates = response.json().get('result')
                        if updates:
                            # تنظیم آفست به آخرین آپدیت + 1
                            last_update_id = updates[-1]["update_id"]
                            offset = last_update_id + 1
                            # حذف همه‌ی آپدیت‌های قبلی
                            requests.get(
                                f"https://api.telegram.org/bot{bot.token}/getUpdates",
                                params={'offset': offset, 'limit': 1, 'timeout': 1},
                                timeout=10
                            )
                            logger.info(f"Cleared all previous updates, set offset to {offset}")
                except Exception as clear_error:
                    logger.error(f"Error clearing updates: {clear_error}")
                
                # اجرای حلقه‌ی اصلی ربات
                logger.info("Starting bot.run()...")
                bot.run()
            except Exception as e:
                logger.error(f"Bot thread crashed: {e}")
        
        _bot_thread = threading.Thread(target=bot_runner, name="InlineTelegramBotThread")
        _bot_thread.daemon = True
        _bot_thread.start()
        logger.info(f"Bot thread started with ID: {_bot_thread.ident}")
    except Exception as e:
        logger.error(f"❌ خطا در راه‌اندازی ربات: {e}")
        
    # اگر ترد قبلاً در حال اجرا بود، اعلام می‌کنیم
    if _bot_thread and _bot_thread.is_alive():
        logger.info(f"✅ ترد ربات با شناسه {_bot_thread.ident} در حال اجراست.")

# Define routes for the Flask app
@app.route('/')
def index():
    """Simple health check endpoint"""
    # Start the bot thread if it's not already running
    start_bot_thread()
    return "Telegram bot is running in the background."

@app.route('/status')
def status():
    """Endpoint to check bot status"""
    try:
        if _bot_thread and _bot_thread.is_alive():
            status = "running"
        else:
            status = "stopped"
            # Try to start the bot thread if it's not running
            start_bot_thread()
        
        # Also get database status
        with app.app_context():
            try:
                user_count = User.query.count()
                account_count = Account.query.count()
                db_status = "connected"
            except Exception as e:
                logger.error(f"Database error in status endpoint: {e}")
                user_count = 0
                account_count = 0
                db_status = f"error: {str(e)}"
        
        return jsonify({
            "bot_status": status,
            "database_status": db_status,
            "user_count": user_count,
            "account_count": account_count,
            "status": "ok"  # Always include an ok status for healthcheck
        })
    except Exception as e:
        logger.error(f"Error in status endpoint: {e}")
        # Always return a successful response for healthcheck
        return jsonify({
            "status": "ok",
            "error": str(e)
        }), 200  # Force 200 response for healthcheck


@app.route('/healthz')
def healthz():
    """
    مسیر سلامت ساده که همیشه کد 200 برمی‌گرداند.
    Railway از این مسیر برای بررسی سلامت برنامه استفاده می‌کند.
    """
    # ساده‌ترین پاسخ ممکن بدون هیچ بررسی اضافی
    return "OK", 200

# اضافه کردن مسیرهای پشتیبان دیگر برای سلامت‌سنجی
@app.route('/health')
def health():
    """مسیر پشتیبان سلامت‌سنجی"""
    return "OK", 200

@app.route('/_health')
def _health():
    """مسیر پشتیبان دیگر سلامت‌سنجی"""
    return "OK", 200

@app.route('/restart', methods=['POST'])
def restart_bot():
    """Endpoint to restart the bot thread"""
    global _bot_thread
    
    if _bot_thread and _bot_thread.is_alive():
        logger.info("Request to restart bot received, but cannot stop thread directly")
        # We can't really stop the thread safely, but we can start a new one
        # which will take over on next polling cycle
        _bot_thread = None
    
    start_bot_thread()
    return jsonify({"status": "Bot thread restart initiated"})

if __name__ == "__main__":
    logger.info("Running as standalone Flask app")
    # Start the bot thread
    start_bot_thread()
    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask app on port {port}")
    # Run the Flask app
    app.run(host="0.0.0.0", port=port, debug=True)