#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت پاکسازی کامل و اجرای سیستم.
این اسکریپت تمام فرآیندهای تلگرام را پاکسازی و برنامه را به صورت تمیز راه‌اندازی می‌کند.
"""

import os
import sys
import time
import logging
import requests
import subprocess
import signal
import psutil

# تنظیمات لاگینگ با رنگ‌های زیبا
logging.basicConfig(
    level=logging.INFO,
    format='\033[1;36m%(asctime)s\033[0m - \033[1;33m%(name)s\033[0m - \033[1;35m%(levelname)s\033[0m - \033[0m%(message)s\033[0m',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

def kill_all_telegram_processes():
    """کشتن تمام فرآیندهای مرتبط با تلگرام"""
    
    logger.info("🔄 در حال کشتن همه فرآیندهای مرتبط با تلگرام...")
    
    # کشتن فرآیندهای پایتون مرتبط با تلگرام با استفاده از psutil
    killed_count = 0
    current_pid = os.getpid()  # PID فرآیند فعلی
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # بررسی اگر این فرآیند مرتبط با تلگرام است و خودمان نیست
            if proc.pid != current_pid:
                cmdline = " ".join(proc.info['cmdline'] or []).lower()
                if any(keyword in cmdline for keyword in ['telegram', 'getupdate', 'bot']):
                    logger.info(f"🔪 کشتن فرآیند با PID {proc.pid}: {cmdline[:50]}...")
                    os.kill(proc.pid, signal.SIGKILL)
                    killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if killed_count > 0:
        logger.info(f"✅ {killed_count} فرآیند مرتبط با تلگرام با موفقیت کشته شدند")
    else:
        logger.info("✅ هیچ فرآیند مرتبط با تلگرام یافت نشد")
    
    return killed_count

def delete_telegram_webhook():
    """حذف وبهوک و آپدیت‌های در انتظار"""
    
    logger.info("🔄 در حال حذف وبهوک و آپدیت‌های در انتظار...")
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ توکن تلگرام یافت نشد!")
        return False
    
    try:
        # حذف وبهوک با drop_pending_updates=True
        response = requests.post(
            f"https://api.telegram.org/bot{token}/deleteWebhook",
            json={'drop_pending_updates': True},
            timeout=15
        )
        
        if response.status_code == 200 and response.json().get('ok'):
            logger.info("✅ وبهوک با موفقیت حذف شد و آپدیت‌های در انتظار پاک شدند")
            return True
        else:
            logger.error(f"❌ خطا در حذف وبهوک: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در حذف وبهوک: {str(e)}")
        return False

def close_telegram_connections():
    """بستن همه اتصالات فعلی تلگرام"""
    
    logger.info("🔄 در حال بستن همه اتصالات فعلی تلگرام...")
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ توکن تلگرام یافت نشد!")
        return False
    
    try:
        response = requests.post(f"https://api.telegram.org/bot{token}/close", timeout=10)
        
        if response.status_code == 200 and response.json().get('ok'):
            logger.info("✅ همه اتصالات تلگرام با موفقیت بسته شدند")
            return True
        else:
            # در صورت خطای 429، پیغام هشدار بدهیم ولی ادامه دهیم
            if response.status_code == 429:
                logger.warning(f"⚠️ محدودیت نرخ درخواست در close: {response.text}")
                return True
            else:
                logger.error(f"❌ خطا در بستن اتصالات: {response.text}")
                return False
    except Exception as e:
        logger.error(f"❌ خطا در بستن اتصالات: {str(e)}")
        return False

def clear_lock_files():
    """پاکسازی فایل‌های قفل"""
    
    logger.info("🔄 در حال پاکسازی فایل‌های قفل...")
    
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
                logger.info(f"✅ فایل قفل {lock_file} با موفقیت حذف شد")
        except Exception as e:
            logger.error(f"❌ خطا در حذف فایل قفل {lock_file}: {str(e)}")
    
    return True

def stop_existing_gunicorn():
    """توقف فرآیندهای gunicorn موجود"""
    
    logger.info("🔄 در حال بررسی و توقف فرآیندهای gunicorn...")
    
    killed_count = 0
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # بررسی اگر این فرآیند gunicorn است و خودمان نیست
            if proc.pid != current_pid:
                cmdline = " ".join(proc.info['cmdline'] or []).lower()
                if 'gunicorn' in cmdline:
                    logger.info(f"🔪 توقف فرآیند gunicorn با PID {proc.pid}...")
                    os.kill(proc.pid, signal.SIGTERM)  # استفاده از SIGTERM برای بستن تمیز
                    killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if killed_count > 0:
        logger.info(f"✅ {killed_count} فرآیند gunicorn با موفقیت متوقف شدند")
        # کمی صبر می‌کنیم تا فرآیندها متوقف شوند
        time.sleep(2)
    else:
        logger.info("✅ هیچ فرآیند gunicorn موجود یافت نشد")
    
    return killed_count

def run_clean_startup():
    """اجرای فرآیند پاکسازی و راه‌اندازی تمیز"""
    
    logger.info("🚀 شروع پاکسازی کامل و راه‌اندازی تمیز...")
    
    # مرحله 1: توقف فرآیندهای gunicorn موجود
    stop_existing_gunicorn()
    
    # مرحله 2: کشتن همه فرآیندهای مرتبط با تلگرام
    kill_all_telegram_processes()
    
    # مرحله 3: پاکسازی فایل‌های قفل
    clear_lock_files()
    
    # مرحله 4: حذف وبهوک تلگرام
    delete_telegram_webhook()
    
    # مرحله 5: بستن اتصالات تلگرام
    close_telegram_connections()
    
    # مرحله 6: کمی صبر می‌کنیم تا همه تغییرات اعمال شوند
    logger.info("🕒 در حال انتظار برای اعمال تغییرات (3 ثانیه)...")
    time.sleep(3)
    
    # مرحله 7: اجرای برنامه اصلی
    logger.info("🚀 راه‌اندازی برنامه اصلی...")
    
    # دریافت پورت از متغیر محیطی یا استفاده از پیش‌فرض 5000
    port = int(os.environ.get("PORT", 5000))
    
    # فراخوانی gunicorn به صورت مستقیم
    command = ["gunicorn", "--bind", f"0.0.0.0:{port}", "--reuse-port", "--reload", "main:app"]
    
    logger.info(f"🔄 اجرای فرمان: {' '.join(command)}")
    
    # اجرای فرمان با جایگزینی فرآیند فعلی (exec-like)
    os.execvp(command[0], command)

if __name__ == "__main__":
    try:
        # نمایش اطلاعات سیستم
        logger.info(f"🖥️ پلتفرم: {sys.platform}")
        logger.info(f"🔑 توکن تلگرام موجود است: {bool(os.environ.get('TELEGRAM_BOT_TOKEN'))}")
        
        # اجرای پاکسازی و راه‌اندازی
        run_clean_startup()
    except Exception as e:
        logger.critical(f"❌ خطای بحرانی در راه‌اندازی: {str(e)}")
        sys.exit(1)