#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت تنظیم Webhook در محیط Replit
این اسکریپت به صورت خودکار آدرس Replit را تشخیص داده و webhook تلگرام را تنظیم می‌کند.
"""

import os
import requests
import time
import json
import logging
import sys
from typing import Dict, Any, Tuple, Optional

# تنظیمات لاگینگ با رنگ‌های متفاوت
logging.basicConfig(
    level=logging.INFO,
    format='\033[1;36m%(asctime)s\033[0m - \033[1;33m%(name)s\033[0m - \033[1;35m%(levelname)s\033[0m - \033[0m%(message)s\033[0m',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

def get_bot_token() -> str:
    """دریافت توکن ربات از متغیرهای محیطی.
    
    Returns:
        str: توکن ربات
    """
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ توکن ربات تلگرام یافت نشد! لطفاً آن را در متغیرهای محیطی تنظیم کنید.")
        sys.exit(1)
    return token


def get_replit_url() -> str:
    """دریافت آدرس Replit از متغیرهای محیطی.
    
    Returns:
        str: آدرس Replit
    """
    repl_slug = os.environ.get('REPL_SLUG')
    repl_owner = os.environ.get('REPL_OWNER')
    
    if not (repl_slug and repl_owner):
        logger.error("❌ اطلاعات Replit یافت نشد! لطفاً مطمئن شوید که در محیط Replit هستید.")
        sys.exit(1)
    
    # آدرس Replit به صورت: https://{repl_slug}.{repl_owner}.repl.co
    url = f"https://{repl_slug}.{repl_owner}.repl.co"
    return url


def kill_telegram_processes() -> bool:
    """کشتن همه فرآیندهای مرتبط با تلگرام قبل از تنظیم webhook.
    
    Returns:
        bool: وضعیت موفقیت
    """
    try:
        # از اسکریپت force_reset_telegram.py استفاده می‌کنیم
        import force_reset_telegram
        reset_tool = force_reset_telegram.TelegramEmergencyReset()
        reset_tool.kill_telegram_processes()
        time.sleep(3)  # اندکی صبر برای اطمینان از بسته شدن فرآیندها
        logger.info("✅ فرآیندهای تلگرام با موفقیت کشته شدند")
        return True
    except Exception as e:
        logger.error(f"❌ خطا در کشتن فرآیندهای تلگرام: {str(e)}")
        # حتی در صورت خطا، ادامه می‌دهیم
        return False


def check_bot_connection(token: str) -> Tuple[bool, Dict[str, Any]]:
    """بررسی اتصال به API تلگرام.
    
    Args:
        token: توکن ربات تلگرام
        
    Returns:
        Tuple[bool, Dict[str, Any]]: وضعیت اتصال و اطلاعات ربات
    """
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if response.status_code == 200:
            bot_info = response.json()["result"]
            logger.info(f"✅ اتصال به ربات برقرار شد: @{bot_info['username']} (ID: {bot_info['id']})")
            return True, bot_info
        logger.error(f"❌ خطا در اتصال به ربات: {response.text}")
        return False, {}
    except Exception as e:
        logger.error(f"❌ خطا در اتصال به ربات: {str(e)}")
        return False, {}


def delete_webhook(token: str, drop_pending_updates: bool = True) -> bool:
    """حذف webhook فعلی.
    
    Args:
        token: توکن ربات تلگرام
        drop_pending_updates: آیا آپدیت‌های در انتظار نیز حذف شوند؟
        
    Returns:
        bool: وضعیت موفقیت
    """
    try:
        params = {"drop_pending_updates": drop_pending_updates}
        response = requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook", json=params, timeout=10)
        if response.status_code == 200:
            logger.info("✅ وبهوک با موفقیت حذف شد")
            if drop_pending_updates:
                logger.info("✅ همه آپدیت‌های در انتظار نیز حذف شدند")
            return True
        logger.error(f"❌ خطا در حذف وبهوک: {response.text}")
        return False
    except Exception as e:
        logger.error(f"❌ خطا در حذف وبهوک: {str(e)}")
        return False


def set_webhook(token: str, webhook_url: str) -> bool:
    """تنظیم webhook جدید.
    
    Args:
        token: توکن ربات تلگرام
        webhook_url: آدرس webhook
        
    Returns:
        bool: وضعیت موفقیت
    """
    # آدرس webhook باید به مسیر /webhook در سرور اشاره کند
    if not webhook_url.endswith('/webhook'):
        webhook_url = webhook_url.rstrip('/') + '/webhook'
    
    try:
        # تنظیمات پیشرفته‌تر برای webhook
        params = {
            "url": webhook_url,
            "max_connections": 100,  # حداکثر تعداد اتصالات همزمان
            "allowed_updates": ["message", "edited_message", "callback_query"],  # فقط آپدیت‌های مورد نیاز
            "drop_pending_updates": True  # حذف آپدیت‌های قبلی در انتظار
        }
        
        response = requests.post(f"https://api.telegram.org/bot{token}/setWebhook", json=params, timeout=10)
        if response.status_code == 200 and response.json().get("ok"):
            logger.info(f"✅ وبهوک با موفقیت تنظیم شد: {webhook_url}")
            return True
        logger.error(f"❌ خطا در تنظیم وبهوک: {response.text}")
        return False
    except Exception as e:
        logger.error(f"❌ خطا در تنظیم وبهوک: {str(e)}")
        return False


def check_webhook_info(token: str) -> Dict[str, Any]:
    """بررسی اطلاعات webhook فعلی.
    
    Args:
        token: توکن ربات تلگرام
        
    Returns:
        Dict[str, Any]: اطلاعات webhook
    """
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10)
        if response.status_code == 200:
            webhook_info = response.json()["result"]
            if webhook_info.get("url"):
                logger.info(f"ℹ️ وبهوک فعلی: {webhook_info['url']}")
                if webhook_info.get("last_error_date"):
                    last_error_timestamp = webhook_info["last_error_date"]
                    last_error_message = webhook_info.get("last_error_message", "Unknown error")
                    logger.warning(f"⚠️ آخرین خطای webhook: {last_error_message} (تاریخ: {last_error_timestamp})")
            else:
                logger.info("ℹ️ هیچ وبهوک فعالی وجود ندارد")
            
            pending_update_count = webhook_info.get("pending_update_count", 0)
            logger.info(f"ℹ️ تعداد آپدیت‌های در انتظار: {pending_update_count}")
            
            return webhook_info
        logger.error(f"❌ خطا در دریافت اطلاعات وبهوک: {response.text}")
        return {}
    except Exception as e:
        logger.error(f"❌ خطا در دریافت اطلاعات وبهوک: {str(e)}")
        return {}


def test_webhook(token: str, webhook_url: str) -> bool:
    """تست عملکرد webhook.
    
    Args:
        token: توکن ربات تلگرام
        webhook_url: آدرس webhook
        
    Returns:
        bool: وضعیت موفقیت
    """
    try:
        # ارسال یک درخواست ساده به آدرس webhook
        webhook_path = webhook_url.rstrip('/') + '/webhook'
        test_data = {"test": "payload", "timestamp": int(time.time())}
        response = requests.post(webhook_path, json=test_data, timeout=10)
        
        # هر پاسخی دریافت کنیم (حتی 404)، نشان‌دهنده‌ی این است که سرور در دسترس است
        logger.info(f"ℹ️ تست webhook با کد وضعیت HTTP {response.status_code} انجام شد")
        
        # بررسی وضعیت real-time آپدیت‌های webhook
        webhook_info = check_webhook_info(token)
        
        # اگر مشکلی در webhook گزارش نشده باشد، وبهوک احتمالاً کار می‌کند
        if not webhook_info.get("last_error_date"):
            logger.info("✅ وبهوک در حال کار کردن است")
            return True
        
        # در غیر این صورت، مشکلی وجود دارد
        logger.warning("⚠️ مشکلی در وبهوک وجود دارد. لطفاً لاگ‌ها را بررسی کنید.")
        return False
    except Exception as e:
        logger.error(f"❌ خطا در تست وبهوک: {str(e)}")
        return False


def main() -> int:
    """تابع اصلی برنامه.
    
    Returns:
        int: کد خروجی (0 برای موفقیت، 1 برای خطا)
    """
    print("\n" + "=" * 50)
    print("🚀 ابزار تنظیم Webhook در محیط Replit - نسخه 1.0.0")
    print("=" * 50 + "\n")
    
    # دریافت توکن ربات
    token = get_bot_token()
    
    # دریافت آدرس Replit
    replit_url = get_replit_url()
    logger.info(f"ℹ️ آدرس Replit شناسایی شد: {replit_url}")
    
    # کشتن فرآیندهای تلگرام قبلی
    kill_telegram_processes()
    
    # بررسی اتصال به API تلگرام
    connection_ok, bot_info = check_bot_connection(token)
    if not connection_ok:
        logger.error("❌ ارتباط با ربات برقرار نیست! لطفاً توکن ربات را بررسی کنید.")
        return 1
    
    # بررسی وضعیت webhook فعلی
    logger.info("🔍 بررسی وضعیت webhook فعلی...")
    webhook_info = check_webhook_info(token)
    
    # حذف webhook فعلی و آپدیت‌های در انتظار
    logger.info("🔄 در حال حذف webhook فعلی...")
    delete_webhook(token, drop_pending_updates=True)
    time.sleep(2)  # کمی صبر می‌کنیم
    
    # تنظیم webhook جدید
    logger.info(f"🔄 در حال تنظیم webhook جدید به آدرس {replit_url}/webhook...")
    if set_webhook(token, replit_url):
        # بررسی مجدد وضعیت webhook
        time.sleep(2)  # کمی صبر می‌کنیم
        logger.info("🔍 بررسی وضعیت webhook پس از تنظیم...")
        check_webhook_info(token)
        
        # تست webhook
        logger.info("🔄 در حال تست webhook...")
        test_webhook(token, replit_url)
        
        print("\n" + "=" * 50)
        print("✅ عملیات تنظیم Webhook با موفقیت انجام شد!")
        print(f"ℹ️ آدرس Webhook: {replit_url}/webhook")
        print("=" * 50 + "\n")
        return 0
    else:
        print("\n" + "=" * 50)
        print("❌ عملیات تنظیم Webhook با مشکل مواجه شد!")
        print("=" * 50 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())