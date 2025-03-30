#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت پاکسازی کامل اتصالات تلگرام.
این اسکریپت تمام اتصالات فعلی به API تلگرام را بسته و وبهوک را حذف می‌کند.
"""

import os
import sys
import time
import logging
import requests
import subprocess

# تنظیمات لاگینگ با رنگ‌های زیبا
logging.basicConfig(
    level=logging.INFO,
    format='\033[1;36m%(asctime)s\033[0m - \033[1;33m%(name)s\033[0m - \033[1;35m%(levelname)s\033[0m - \033[0m%(message)s\033[0m',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

def clean_telegram_connections():
    """پاکسازی تمام اتصالات به API تلگرام."""
    print("\n" + "=" * 50)
    print("🧹 ابزار پاکسازی کامل اتصالات تلگرام - نسخه 1.0.0")
    print("=" * 50 + "\n")
    
    # دریافت توکن ربات تلگرام
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("❌ توکن ربات تلگرام یافت نشد! لطفاً آن را در متغیرهای محیطی تنظیم کنید.")
        return False
        
    api_url = f"https://api.telegram.org/bot{bot_token}"
    
    # مرحله 1: کشتن تمام فرآیندهای مرتبط با تلگرام
    logger.info("🔄 در حال کشتن فرآیندهای مرتبط با تلگرام...")
    
    try:
        # کشتن فرآیندهای پایتون مرتبط با تلگرام
        os.system("pkill -9 -f telegram")
        logger.info("✅ درخواست کشتن فرآیندهای تلگرام ارسال شد")
        
        # کشتن فرآیندهای گوئیکورن
        os.system("pkill -9 -f gunicorn")
        logger.info("✅ درخواست کشتن فرآیندهای گوئیکورن ارسال شد")
        
    except Exception as e:
        logger.error(f"❌ خطا در کشتن فرآیندها: {str(e)}")
    
    # کمی صبر کنیم تا فرآیندها متوقف شوند
    time.sleep(2)
    
    # مرحله 2: بررسی اتصال به API تلگرام
    logger.info("🔄 در حال بررسی اتصال به API تلگرام...")
    
    try:
        response = requests.get(f"{api_url}/getMe", timeout=10)
        
        if response.status_code == 200 and response.json().get("ok"):
            bot_info = response.json().get("result", {})
            logger.info(f"✅ اتصال به ربات برقرار شد: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
        else:
            logger.error(f"❌ خطا در اتصال به API تلگرام: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در اتصال به API تلگرام: {str(e)}")
        return False
    
    # مرحله 3: حذف وبهوک و پاکسازی آپدیت‌های در انتظار
    logger.info("🔄 در حال حذف وبهوک و پاکسازی آپدیت‌های در انتظار...")
    
    try:
        params = {"drop_pending_updates": True}
        response = requests.get(f"{api_url}/deleteWebhook", params=params, timeout=10)
        
        if response.status_code == 200 and response.json().get("ok"):
            logger.info("✅ وبهوک با موفقیت حذف شد و آپدیت‌های در انتظار پاک شدند")
        else:
            logger.error(f"❌ خطا در حذف وبهوک: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در حذف وبهوک: {str(e)}")
        return False
    
    # مرحله 4: بستن همه اتصالات فعلی
    logger.info("🔄 در حال بستن همه اتصالات فعلی...")
    
    try:
        response = requests.post(f"{api_url}/close", timeout=10)
        
        if response.status_code == 200 and response.json().get("ok"):
            logger.info("✅ همه اتصالات فعلی با موفقیت بسته شدند")
        else:
            if response.status_code == 429:
                retry_after = response.json().get("parameters", {}).get("retry_after", 30)
                logger.warning(f"⚠️ محدودیت نرخ درخواست (Rate Limit): باید {retry_after} ثانیه صبر کنیم")
                logger.info(f"🕒 در حال انتظار برای {retry_after} ثانیه...")
                time.sleep(retry_after)
                
                # تلاش مجدد پس از انتظار
                response = requests.post(f"{api_url}/close", timeout=10)
                if response.status_code == 200 and response.json().get("ok"):
                    logger.info("✅ همه اتصالات فعلی با موفقیت بسته شدند")
                else:
                    logger.warning(f"⚠️ هشدار در بستن اتصالات پس از انتظار: {response.text}")
            else:
                logger.warning(f"⚠️ هشدار در بستن اتصالات: {response.text}")
    except Exception as e:
        logger.warning(f"⚠️ هشدار در بستن اتصالات: {str(e)}")
    
    # مرحله 5: حذف فایل‌های قفل
    logger.info("🔄 در حال حذف فایل‌های قفل...")
    
    lock_files = [
        "/tmp/telegram_bot.lock",
        "bot.lock",
        "./bot.lock",
        "telegram.lock",
        "./telegram.lock"
    ]
    
    for lock_file in lock_files:
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info(f"✅ فایل قفل {lock_file} با موفقیت حذف شد")
        except Exception as e:
            logger.warning(f"⚠️ خطا در حذف فایل قفل {lock_file}: {str(e)}")
    
    # مرحله 6: کمی صبر کنیم تا همه اتصالات تایم اوت شوند
    logger.info("🕒 در حال انتظار برای تایم اوت شدن اتصالات (10 ثانیه)...")
    time.sleep(10)
    
    logger.info("✅ پاکسازی کامل اتصالات تلگرام با موفقیت انجام شد")
    print("\n" + "=" * 50)
    print("✅ عملیات پاکسازی با موفقیت به پایان رسید")
    print("=" * 50 + "\n")
    
    return True

if __name__ == "__main__":
    clean_telegram_connections()