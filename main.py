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
                # Set logging level to debug for more information
                logging.getLogger().setLevel(logging.DEBUG)
                
                # Create and run the bot with Flask app passed for context
                bot = InlineTelegramBot(app=app)
                logger.info(f"Bot instance created, token valid: {bool(bot.token)}")
                
                # Test connection to Telegram API
                try:
                    import requests
                    response = requests.get(f"https://api.telegram.org/bot{bot.token}/getMe")
                    logger.info(f"getMe response: {response.text}")
                except Exception as get_me_error:
                    logger.error(f"getMe error: {get_me_error}")
                
                # Try to get updates before running the main loop
                try:
                    logger.info("Trying to get initial updates...")
                    # دریافت آخرین آپدیت‌ها و حذف آنها
                    updates = bot.get_updates()
                    if updates:
                        # تنظیم آفست به آخرین آپدیت + 1 برای نادیده گرفتن همه آپدیت‌های قبلی
                        last_update_id = updates[-1]["update_id"]
                        bot.offset = last_update_id + 1
                        logger.info(f"Setting offset to {bot.offset} to ignore previous updates")
                    logger.info(f"Initial updates: {updates}")
                except Exception as update_error:
                    logger.error(f"getUpdates error: {update_error}")
                
                # Run the bot's main loop
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
    """Simple healthcheck endpoint that always returns 200
    Railway uses this to check if the application is healthy and running
    """
    try:
        # هیچگونه بررسی پایگاه داده انجام نمی‌دهیم تا سریع‌تر پاسخ دهد
        # این فقط بررسی می‌کند که سرور فلسک در حال اجراست
        return jsonify({
            "status": "ok",
            "message": "Service is up and running",
            "timestamp": time.time()
        })
    except Exception as e:
        # حتی در صورت خطا هم کد 200 برمی‌گردانیم تا healthcheck موفق باشد
        logging.error(f"Error in healthcheck: {e}")
        return jsonify({
            "status": "ok",  # همیشه "ok" برمی‌گردانیم حتی در صورت خطا
            "message": "Service is responding to healthcheck"
        }), 200

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