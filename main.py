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
        logger.info(f"Stopping previous bot thread with ID: {_bot_thread.ident}")
        # ما نمی‌توانیم به طور مستقیم ترد را متوقف کنیم، اما می‌توانیم آن را نادیده بگیریم
        _bot_thread = None
        # کمی صبر می‌کنیم تا ترد قبلی بسته شود
        time.sleep(2)
    
    if not _bot_thread or not _bot_thread.is_alive():
        logger.info("Starting bot in a separate thread")
        
        def bot_runner():
            try:
                logger.info("Creating Inline Telegram Bot instance in thread")
                # Set logging level to debug for more information
                logging.getLogger().setLevel(logging.DEBUG)
                
                # Create and run the bot
                bot = InlineTelegramBot()
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
    else:
        logger.info(f"Bot thread already running with ID: {_bot_thread.ident}")

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
    if _bot_thread and _bot_thread.is_alive():
        status = "running"
    else:
        status = "stopped"
    
    # Also get database status
    with app.app_context():
        try:
            user_count = User.query.count()
            account_count = Account.query.count()
            db_status = "connected"
        except Exception as e:
            user_count = 0
            account_count = 0
            db_status = f"error: {str(e)}"
    
    return jsonify({
        "bot_status": status,
        "database_status": db_status,
        "user_count": user_count,
        "account_count": account_count
    })

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
    # Run the Flask app
    app.run(host="0.0.0.0", port=5000, debug=True)