#!/usr/bin/env python3
"""
✨ نقطه ورود اصلی برای برنامه ✨
این فایل تنظیمات دیتابیس و راه‌اندازی ربات تلگرام را انجام می‌دهد.
نسخه بهینه‌شده برای Railway با مکانیزم قفل فایل و پاکسازی کامل
"""

# بلوک پاکسازی - اجرای تمیز کننده در ابتدای کار برنامه
import os
import signal
import psutil
import sys

def perform_initial_cleanup():
    """پاکسازی اولیه همه فرآیندهای تلگرام قبل از شروع برنامه"""
    print("🧹 انجام پاکسازی اولیه...")
    
    # 1. کشتن فرآیندهای تلگرام قبلی
    current_pid = os.getpid()
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid != current_pid:
                cmdline = " ".join(proc.info['cmdline'] or []).lower()
                if any(keyword in cmdline for keyword in ['telegram', 'getupdate', 'bot']):
                    print(f"🔪 کشتن فرآیند با PID {proc.pid}")
                    try:
                        os.kill(proc.pid, signal.SIGKILL)
                        killed_count += 1
                    except Exception as e:
                        print(f"⚠️ خطا در کشتن فرآیند {proc.pid}: {e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    print(f"✅ {killed_count} فرآیند مرتبط با تلگرام کشته شد")
    
    # 2. پاکسازی فایل‌های قفل
    lock_files = [
        "/tmp/telegram_bot.lock",
        "./telegram_bot.lock",
        "/tmp/bot_instance.lock",
        "./bot_instance.lock"
    ]
    
    for lock_file in lock_files:
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                print(f"✅ فایل قفل {lock_file} حذف شد")
        except Exception as e:
            print(f"⚠️ خطا در حذف فایل قفل {lock_file}: {e}")
    
    print("✅ پاکسازی اولیه با موفقیت انجام شد")

# اجرای پاکسازی اولیه در ابتدای برنامه
perform_initial_cleanup()

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
    """راه‌اندازی ربات در یک ترد جداگانه با تشخیص هوشمند محیط"""
    # بررسی محیط اجرایی - با قابلیت غیرفعال‌سازی
    # DISABLE_ENV_CHECK=1 برای غیرفعال‌سازی این بررسی
    if os.environ.get('DISABLE_ENV_CHECK') != '1':
        is_replit = 'REPL_ID' in os.environ or 'REPLIT_DB_URL' in os.environ
        is_railway = any(key.startswith('RAILWAY_') for key in os.environ)
        
        if is_replit and not is_railway:
            logger.warning("⚠️ در محیط Replit هستیم، ربات را راه‌اندازی نمی‌کنیم تا با نمونه Railway تداخل نداشته باشد")
            logger.info("ℹ️ اگر می‌خواهید ربات را در Replit اجرا کنید، لطفاً ابتدا نمونه Railway را متوقف کنید")
            logger.info("💡 برای راه‌اندازی اجباری ربات در Replit، از پارامتر FORCE_BOT_START=1 استفاده کنید")
            
            # اگر کاربر به صورت اجباری خواسته باشد ربات راه‌اندازی شود
            if os.environ.get('FORCE_BOT_START') == '1':
                logger.warning("🔔 راه‌اندازی اجباری ربات در Replit...")
            else:
                # در صورتی که در Replit هستیم، فقط API را ارائه می‌دهیم و ربات را راه‌اندازی نمی‌کنیم
                logger.info("💡 فقط API وب ارائه می‌شود، ربات تلگرام راه‌اندازی نمی‌شود")
                return None
    else:
        logger.warning("⚠️ بررسی محیط غیرفعال شده است، ربات را در هر محیطی راه‌اندازی می‌کنیم")
    
    # راه‌اندازی ربات
    bot = setup_bot()
    if not bot:
        logger.error("❌ ربات راه‌اندازی نشد، ترد شروع نمی‌شود")
        return None
    
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
    return bot

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
    
    # بررسی وضعیت محیط
    is_replit = 'REPL_ID' in os.environ or 'REPLIT_DB_URL' in os.environ
    is_railway = any(key.startswith('RAILWAY_') for key in os.environ)
    
    environment = "ناشناخته"
    if is_replit and not is_railway:
        environment = "Replit"
    elif is_railway:
        environment = "Railway"
    
    # بررسی وضعیت webhook
    webhook_status = "غیرفعال"
    webhook_url = ""
    try:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        webhook_response = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=5)
        
        if webhook_response.status_code == 200 and webhook_response.json().get('ok', False):
            webhook_info = webhook_response.json().get('result', {})
            webhook_url = webhook_info.get('url', '')
            
            if webhook_url:
                webhook_status = "فعال"
            else:
                webhook_status = "غیرفعال"
    except Exception:
        pass
    
    result = {
        "bot_status": "در حال اجرا" if global_bot else "متوقف",
        "database_status": db_status,
        "user_count": user_count,
        "account_count": account_count,
        "environment": environment,
        "webhook_status": webhook_status,
        "webhook_url": webhook_url,
        "status": "ok",
        "environment_variables": {
            "REPL_ID": os.environ.get("REPL_ID", ""),
            "RAILWAY_STATIC_URL": os.environ.get("RAILWAY_STATIC_URL", ""),
            "RAILWAY_PUBLIC_DOMAIN": os.environ.get("RAILWAY_PUBLIC_DOMAIN", ""),
            "FORCE_BOT_START": os.environ.get("FORCE_BOT_START", "0") == "1",
            "DISABLE_ENV_CHECK": os.environ.get("DISABLE_ENV_CHECK", "0") == "1"
        }
    }
    
    return jsonify(result)

@app.route('/env')
def environment_info():
    """مسیر نمایش اطلاعات محیط اجرایی"""
    # بررسی وضعیت محیط
    is_replit = 'REPL_ID' in os.environ or 'REPLIT_DB_URL' in os.environ
    is_railway = any(key.startswith('RAILWAY_') for key in os.environ)
    
    environment = "ناشناخته"
    if is_replit and not is_railway:
        environment = "Replit"
    elif is_railway:
        environment = "Railway"
    
    # متغیرهای محیطی مهم
    env_vars = {}
    important_vars = [
        "REPL_ID", "REPLIT_DB_URL", 
        "RAILWAY_STATIC_URL", "RAILWAY_PUBLIC_DOMAIN",
        "FORCE_BOT_START", "DISABLE_ENV_CHECK",
        "PORT", "DATABASE_URL"
    ]
    
    for var in important_vars:
        env_vars[var] = os.environ.get(var, "تنظیم نشده")
    
    # قابلیت دسترسی به توکن ربات (بدون نمایش آن)
    has_bot_token = bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
    
    # اطلاعات سیستم
    system_info = {
        "pid": os.getpid(),
        "python_version": sys.version,
        "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hostname": os.uname().nodename if hasattr(os, 'uname') else "unknown"
    }
    
    return jsonify({
        "environment": environment,
        "has_bot_token": has_bot_token,
        "environment_variables": env_vars,
        "system_info": system_info
    })

@app.route('/bot_status')
def bot_detailed_status():
    """مسیر نمایش وضعیت دقیق ربات تلگرام با اطلاعات کامل‌تر"""
    # همه کدهای درخواست به API خارجی را حذف کرده‌ایم
    
    # وضعیت فعلی ربات در برنامه - این بخش سریع است و تایم‌اوت نمی‌شود
    bot_app_status = {
        "is_running": global_bot is not None,
        "webhook_mode": getattr(global_bot, 'webhook_mode', False) if global_bot else False,
        "environment_check_disabled": os.environ.get('DISABLE_ENV_CHECK') == '1',
        "force_bot_start": os.environ.get('FORCE_BOT_START') == '1'
    }
    
    # وضعیت محیط
    is_replit = 'REPL_ID' in os.environ or 'REPLIT_DB_URL' in os.environ
    is_railway = any(key.startswith('RAILWAY_') for key in os.environ)
    
    environment = "ناشناخته"
    if is_replit and not is_railway:
        environment = "Replit"
    elif is_railway:
        environment = "Railway"
    
    # اطلاعات سیستم
    system_info = {
        "pid": os.getpid(),
        "python_version": sys.version,
        "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hostname": os.uname().nodename if hasattr(os, 'uname') else "unknown"
    }
    
    # بسیار ساده و سریع
    result = {
        "status": "ok",
        "bot_app_status": bot_app_status,
        "environment": environment,
        "system_info": system_info,
        "has_token": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": "اطلاعات API تلگرام به دلیل محدودیت زمانی ارائه نشده‌اند. برای دریافت آن‌ها از /bot_status_full استفاده کنید."
    }
    
    return jsonify(result)

@app.route('/bot_status_full')
def bot_detailed_status_full():
    """مسیر نمایش وضعیت کامل ربات تلگرام با همه جزئیات و اطلاعات API"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return jsonify({
            "status": "error",
            "message": "توکن ربات تلگرام یافت نشد!"
        })
    
    # وضعیت فعلی ربات در برنامه
    bot_app_status = {
        "is_running": global_bot is not None,
        "webhook_mode": getattr(global_bot, 'webhook_mode', False) if global_bot else False,
        "environment_check_disabled": os.environ.get('DISABLE_ENV_CHECK') == '1',
        "force_bot_start": os.environ.get('FORCE_BOT_START') == '1'
    }
    
    # بررسی وضعیت ربات
    bot_info = {}
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=2)
        if response.status_code == 200 and response.json().get('ok', False):
            bot_data = response.json().get('result', {})
            bot_info = {
                "id": bot_data.get('id'),
                "username": bot_data.get('username'),
                "first_name": bot_data.get('first_name'),
                "is_bot": bot_data.get('is_bot'),
                "can_join_groups": bot_data.get('can_join_groups'),
                "can_read_all_group_messages": bot_data.get('can_read_all_group_messages'),
                "supports_inline_queries": bot_data.get('supports_inline_queries')
            }
    except Exception as e:
        bot_info = {"error": str(e)}
    
    # بررسی وضعیت webhook
    webhook_info = {}
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=2)
        if response.status_code == 200 and response.json().get('ok', False):
            webhook_data = response.json().get('result', {})
            webhook_info = {
                "url": webhook_data.get('url', ''),
                "has_custom_certificate": webhook_data.get('has_custom_certificate', False),
                "pending_update_count": webhook_data.get('pending_update_count', 0),
                "last_error_date": webhook_data.get('last_error_date'),
                "last_error_message": webhook_data.get('last_error_message', ''),
                "max_connections": webhook_data.get('max_connections', 40),
                "allowed_updates": webhook_data.get('allowed_updates', [])
            }
    except Exception as e:
        webhook_info = {"error": str(e)}
    
    # بررسی محدودیت‌های API
    api_limits = {}
    try:
        # تلاش برای فراخوانی یک متد ساده برای بررسی وضعیت محدودیت
        response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates?limit=1&timeout=1", timeout=1)
        if response.status_code == 429:
            rate_limit_data = response.json()
            api_limits = {
                "error_code": rate_limit_data.get('error_code'),
                "description": rate_limit_data.get('description'),
                "retry_after": rate_limit_data.get('parameters', {}).get('retry_after', 0)
            }
        elif response.status_code == 409:
            api_limits = {
                "error_code": 409,
                "description": "Conflict: another instance of the bot is running",
                "error_message": response.json().get('description', 'Unknown error')
            }
        else:
            api_limits = {"status": "ok", "limits_reached": False}
    except Exception as e:
        api_limits = {"error": str(e)}
    
    # وضعیت فرآیندهای مرتبط با ربات
    processes_info = {}
    try:
        import psutil
        current_pid = os.getpid()
        current_process = psutil.Process(current_pid)
        
        processes_info = {
            "current_pid": current_pid,
            "parent_pid": current_process.ppid(),
            "threads_count": current_process.num_threads(),
            "memory_usage_mb": current_process.memory_info().rss / (1024 * 1024),
            "cpu_percent": current_process.cpu_percent(interval=0.1)
        }
    except Exception as e:
        processes_info = {"error": str(e)}
    
    return jsonify({
        "status": "ok",
        "bot_info": bot_info,
        "webhook_info": webhook_info,
        "api_limits": api_limits,
        "bot_app_status": bot_app_status,
        "processes_info": processes_info,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/healthz')
def healthz():
    """مسیر سلامت‌سنجی ساده برای Railway"""
    return "OK", 200

@app.route('/health')
def health():
    """مسیر پشتیبان سلامت‌سنجی"""
    return "OK", 200

@app.route('/running_bots')
def running_bots():
    """مسیر نمایش وضعیت ربات‌های در حال اجرا"""
    import psutil
    import threading
    from models import db, User, Account
    
    # لیست ترد‌های فعال برنامه
    active_threads = []
    for thread in threading.enumerate():
        active_threads.append({
            "name": thread.name,
            "id": thread.ident,
            "daemon": thread.daemon,
            "alive": thread.is_alive()
        })
    
    # لیست فرآیندهای مربوط به تلگرام
    telegram_processes = []
    current_pid = os.getpid()
    current_process = psutil.Process(current_pid)
    
    # بررسی فرآیند فعلی و فرزندان آن
    process_info = {
        "pid": current_process.pid,
        "name": current_process.name(),
        "status": current_process.status(),
        "cpu_percent": current_process.cpu_percent(interval=0.1),
        "memory_percent": current_process.memory_percent(),
        "create_time": datetime.datetime.fromtimestamp(current_process.create_time()).strftime("%Y-%m-%d %H:%M:%S"),
        "threads_count": current_process.num_threads()
    }
    telegram_processes.append(process_info)
    
    # بررسی وضعیت محیط
    is_replit = 'REPL_ID' in os.environ or 'REPLIT_DB_URL' in os.environ
    is_railway = any(key.startswith('RAILWAY_') for key in os.environ)
    
    environment = "ناشناخته"
    if is_replit and not is_railway:
        environment = "Replit"
    elif is_railway:
        environment = "Railway"
    
    # بررسی وضعیت ربات
    bot_status = {
        "is_running": global_bot is not None,
        "webhook_mode": getattr(global_bot, 'webhook_mode', False) if global_bot else False,
        "environment_check_disabled": os.environ.get('DISABLE_ENV_CHECK') == '1',
        "force_bot_start": os.environ.get('FORCE_BOT_START') == '1'
    }
    
    # اطلاعات دیتابیس
    try:
        users_count = db.session.query(User).count()
        accounts_count = db.session.query(Account).count()
        
        # آخرین اکانت‌های ساخته شده
        latest_accounts = []
        for account in db.session.query(Account).order_by(Account.created_at.desc()).limit(5):
            latest_accounts.append({
                "id": account.id,
                "gmail": account.gmail,
                "status": account.status,
                "created_at": account.created_at.strftime("%Y-%m-%d %H:%M:%S") if account.created_at else None,
                "has_api_key": bool(account.api_key)
            })
            
        db_info = {
            "users_count": users_count,
            "accounts_count": accounts_count,
            "latest_accounts": latest_accounts,
            "status": "connected"
        }
    except Exception as db_error:
        logger.error(f"خطا در دسترسی به دیتابیس: {db_error}")
        db_info = {
            "status": "error",
            "error": str(db_error)
        }
    
    return jsonify({
        "status": "ok",
        "bot_status": bot_status,
        "environment": environment,
        "active_threads": active_threads,
        "telegram_processes": telegram_processes,
        "database": db_info,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/restart', methods=['POST'])
def restart_bot():
    """مسیر راه‌اندازی مجدد ربات"""
    global global_bot
    global_bot = None  # پاک کردن ربات فعلی
    start_bot_in_thread()  # راه‌اندازی مجدد
    return jsonify({"status": "ربات با موفقیت راه‌اندازی مجدد شد"})

@app.route('/force_start', methods=['POST'])
def force_start_bot():
    """مسیر راه‌اندازی اجباری ربات با نادیده گرفتن محیط اجرایی"""
    global global_bot
    
    # قبل از راه‌اندازی، متغیر محیطی را تنظیم می‌کنیم
    os.environ["FORCE_BOT_START"] = "1"
    os.environ["DISABLE_ENV_CHECK"] = "1"
    
    logger.warning("🔔 راه‌اندازی اجباری ربات...")
    
    # پاک کردن ربات فعلی اگر وجود دارد
    if global_bot:
        logger.info("🔄 پاکسازی نمونه فعلی ربات...")
        global_bot = None
    
    # اطمینان از پاکسازی وبهوک
    try:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if token:
            delete_response = requests.post(
                f"https://api.telegram.org/bot{token}/deleteWebhook",
                json={'drop_pending_updates': True},
                timeout=10
            )
            if delete_response.status_code == 200:
                logger.info("✅ وبهوک با موفقیت حذف شد")
    except Exception as e:
        logger.error(f"❌ خطا در حذف وبهوک: {e}")
    
    # راه‌اندازی ربات
    bot = setup_bot()
    if bot:
        global_bot = bot
        
        # راه‌اندازی ربات در ترد جداگانه
        bot_thread = threading.Thread(target=lambda: bot.run(), name="TelegramBotThread")
        bot_thread.daemon = True
        bot_thread.start()
        logger.info(f"✅ ترد ربات با شناسه {bot_thread.ident} شروع به کار کرد")
        
        return jsonify({
            "status": "ok",
            "message": "ربات با موفقیت به صورت اجباری راه‌اندازی شد",
            "bot_info": {
                "username": bot.get_me().username if hasattr(bot, 'get_me') else "نامشخص",
                "version": "2.1.0",
                "thread_id": bot_thread.ident
            }
        })
    else:
        return jsonify({
            "status": "error",
            "message": "خطا در راه‌اندازی اجباری ربات"
        })

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

@app.route('/gemini_status')
def gemini_status():
    """مسیر بررسی وضعیت و اعتبار API Key های Google Gemini"""
    from gemini_api_validator import GeminiAPIValidator
    from models import db, Account
    
    # دریافت API Key‌ها از دیتابیس
    api_keys = []
    try:
        # فقط API Key‌های غیر تکراری را دریافت می‌کنیم
        accounts_with_api = db.session.query(Account).filter(Account.api_key.isnot(None)).filter(Account.api_key != '').all()
        
        # استخراج API Key‌ها
        api_keys = list(set([account.api_key for account in accounts_with_api]))
        
        logger.info(f"تعداد {len(api_keys)} کلید API در دیتابیس یافت شد")
    except Exception as e:
        logger.error(f"خطا در دریافت API Key‌ها از دیتابیس: {e}")
    
    # نمونه API Key برای تست (اگر در متغیرهای محیطی تنظیم شده باشد)
    sample_key = os.environ.get('GEMINI_API_KEY')
    if sample_key and sample_key not in api_keys:
        api_keys.append(sample_key)
        logger.info("API Key نمونه از متغیرهای محیطی اضافه شد")
    
    # بررسی اعتبار API Key‌ها (حداکثر 5 کلید)
    validator = GeminiAPIValidator()
    validation_results = {}
    
    for i, api_key in enumerate(api_keys[:5]):  # محدود به 5 کلید برای جلوگیری از کندی
        logger.info(f"در حال بررسی اعتبار API Key {i+1}/{min(len(api_keys), 5)}")
        masked_key = api_key[:10] + "..." + api_key[-5:] if len(api_key) > 15 else api_key
        
        try:
            success, details = validator.validate_api_key(api_key)
            validation_results[masked_key] = {
                "valid": success,
                "details": details
            }
        except Exception as e:
            logger.error(f"خطا در بررسی اعتبار API Key: {e}")
            validation_results[masked_key] = {
                "valid": False,
                "error": str(e)
            }
    
    # نمایش نتایج
    return jsonify({
        "status": "ok",
        "api_keys_count": len(api_keys),
        "api_keys_tested": min(len(api_keys), 5),
        "validation_results": validation_results,
        "db_accounts_with_api": len(accounts_with_api) if 'accounts_with_api' in locals() else 0,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/twilio_status')
def twilio_status():
    """مسیر بررسی وضعیت و اعتبار Twilio"""
    from twilio_integration import is_twilio_available, TwilioManager
    
    # بررسی دسترسی به Twilio
    twilio_available = is_twilio_available()
    
    # اطلاعات دقیق‌تر در صورت دسترسی
    details = {}
    if twilio_available:
        try:
            # ایجاد مدیر Twilio
            twilio_manager = TwilioManager()
            
            # دریافت موجودی حساب
            success, balance, message = twilio_manager.get_account_balance()
            details["balance"] = {
                "success": success,
                "value": balance,
                "message": message
            }
            
            # بررسی شماره پیش‌فرض
            phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
            details["default_phone"] = {
                "available": bool(phone_number),
                "number": phone_number if phone_number else None
            }
            
        except Exception as e:
            logger.error(f"خطا در دریافت اطلاعات Twilio: {e}")
            details["error"] = str(e)
    
    # نمایش نتایج
    return jsonify({
        "status": "ok",
        "twilio_available": twilio_available,
        "details": details,
        "environment": {
            "TWILIO_ACCOUNT_SID": bool(os.environ.get('TWILIO_ACCOUNT_SID')),
            "TWILIO_AUTH_TOKEN": bool(os.environ.get('TWILIO_AUTH_TOKEN')),
            "TWILIO_PHONE_NUMBER": bool(os.environ.get('TWILIO_PHONE_NUMBER'))
        },
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/proxy_status')
def proxy_status():
    """مسیر بررسی وضعیت پروکسی‌ها"""
    from proxy_manager import get_public_proxies, test_proxy
    import concurrent.futures
    
    # دریافت پروکسی‌های فعلی (حداکثر 20 مورد برای تست سریع‌تر)
    proxies = get_public_proxies()[:20]
    
    # تست همزمان پروکسی‌ها
    working_proxies = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_proxy = {executor.submit(test_proxy, proxy, 2): proxy for proxy in proxies}
        for future in concurrent.futures.as_completed(future_to_proxy):
            proxy = future_to_proxy[future]
            try:
                is_working = future.result()
                if is_working:
                    working_proxies.append(proxy)
            except Exception as e:
                logger.error(f"خطا در تست پروکسی: {e}")
    
    # نمایش نتایج
    return jsonify({
        "status": "ok",
        "total_proxies": len(proxies),
        "working_proxies": len(working_proxies),
        "proxies_tested": proxies,
        "working_proxies_details": working_proxies,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

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
# ابتدا سعی می‌کنیم همه اتصالات تلگرام را پاکسازی کنیم
try:
    from force_reset_telegram import TelegramEmergencyReset
    reset_tool = TelegramEmergencyReset()
    reset_tool.delete_webhook(drop_pending_updates=True)
    reset_tool.force_reset_with_api()
    logger.info("✅ پاکسازی اتصالات تلگرام با موفقیت انجام شد")
    # کمی صبر می‌کنیم تا همه تغییرات اعمال شوند
    time.sleep(5)
except Exception as reset_error:
    logger.error(f"❌ خطا در پاکسازی اتصالات تلگرام: {reset_error}")

# حالا با مکانیزم قفل فایل اجرا می‌کنیم
try:
    run_bot_with_lock()
except Exception as e:
    logger.error(f"❌ خطا در راه‌اندازی ربات با مکانیزم قفل فایل: {e}")
    # در صورت خطا، تلاش برای راه‌اندازی به روش معمولی
    try:
        logger.info("🔄 تلاش برای راه‌اندازی به روش معمولی...")
        # قبل از راه‌اندازی، حداقل وبهوک را حذف می‌کنیم
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if token:
            requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook", json={'drop_pending_updates': True}, timeout=10)
            logger.info("✅ وبهوک با موفقیت حذف شد")
            # کمی صبر می‌کنیم
            time.sleep(2)
        start_bot_in_thread()
    except Exception as fallback_error:
        logger.critical(f"❌ خطای بحرانی در راه‌اندازی ربات: {fallback_error}")
        # در اینجا می‌توان کد مدیریت خطای بیشتری اضافه کرد

# اجرای Flask app در حالت مستقل
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🌐 شروع وب سرور Flask در پورت {port}")
    app.run(host="0.0.0.0", port=port)