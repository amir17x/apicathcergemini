#!/usr/bin/env python3
"""
اسکریپت مخصوص تنظیم Webhook تلگرام برای استقرار در Railway.
این اسکریپت به طور خودکار آدرس Railway را تشخیص داده و webhook تلگرام را تنظیم می‌کند.
"""

import os
import sys
import logging
import requests
import json
import time

# تنظیم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout  # ارسال لاگ‌ها به stdout برای مشاهده در Railway
)
logger = logging.getLogger("RailwayWebhook")

def get_bot_token():
    """دریافت توکن ربات از متغیرهای محیطی."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN یافت نشد")
        sys.exit(1)
    return token

def get_railway_url():
    """دریافت آدرس Railway از متغیرهای محیطی."""
    railway_url = os.environ.get("RAILWAY_STATIC_URL")
    if not railway_url:
        railway_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    
    if not railway_url:
        logger.error("❌ آدرس Railway یافت نشد")
        sys.exit(1)
    
    return railway_url

def check_bot_connection(token):
    """بررسی اتصال به API تلگرام."""
    logger.info("🔍 بررسی اتصال به API تلگرام...")
    
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        
        if response.status_code == 200 and response.json().get("ok"):
            bot_info = response.json().get("result", {})
            logger.info(f"✅ اتصال به API تلگرام موفقیت‌آمیز بود: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
            return True
        else:
            logger.error(f"❌ خطا در اتصال به API تلگرام: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در اتصال به API تلگرام: {e}")
        return False

def delete_webhook(token):
    """حذف webhook فعلی."""
    logger.info("🔄 حذف webhook فعلی...")
    
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{token}/deleteWebhook", 
            params={"drop_pending_updates": True},
            timeout=10
        )
        
        if response.status_code == 200 and response.json().get("ok"):
            logger.info("✅ Webhook با موفقیت حذف شد")
            return True
        else:
            logger.error(f"❌ خطا در حذف webhook: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در حذف webhook: {e}")
        return False

def set_webhook(token, webhook_url):
    """تنظیم webhook جدید."""
    logger.info(f"🔄 تنظیم webhook جدید به آدرس {webhook_url}...")
    
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{token}/setWebhook", 
            params={
                "url": webhook_url,
                "drop_pending_updates": True,
                "allowed_updates": json.dumps(["message", "edited_message", "callback_query"])
            },
            timeout=10
        )
        
        if response.status_code == 200 and response.json().get("ok"):
            logger.info("✅ Webhook با موفقیت تنظیم شد")
            return True
        else:
            logger.error(f"❌ خطا در تنظیم webhook: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در تنظیم webhook: {e}")
        return False

def check_webhook_info(token):
    """بررسی اطلاعات webhook فعلی."""
    logger.info("🔍 بررسی اطلاعات webhook فعلی...")
    
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10)
        
        if response.status_code == 200 and response.json().get("ok"):
            webhook_info = response.json().get("result", {})
            webhook_url = webhook_info.get("url", "")
            
            if webhook_url:
                logger.info(f"🌐 Webhook فعال است: {webhook_url}")
                
                # بررسی خطاهای رایج
                pending_updates = webhook_info.get("pending_update_count", 0)
                if pending_updates > 0:
                    logger.warning(f"⚠️ {pending_updates} آپدیت در صف انتظار است")
                
                last_error_date = webhook_info.get("last_error_date")
                last_error_message = webhook_info.get("last_error_message")
                if last_error_date and last_error_message:
                    last_error_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_error_date))
                    logger.error(f"❌ آخرین خطای webhook در {last_error_time}: {last_error_message}")
            else:
                logger.info("ℹ️ هیچ webhook فعالی وجود ندارد")
            
            # برگرداندن جزئیات کامل
            return webhook_info
        else:
            logger.error(f"❌ خطا در بررسی اطلاعات webhook: {response.text}")
            return None
    except Exception as e:
        logger.error(f"❌ خطا در بررسی اطلاعات webhook: {e}")
        return None

def main():
    """تابع اصلی برای تنظیم webhook در Railway."""
    print("\n" + "=" * 50)
    print("🚂 تنظیم Webhook تلگرام برای Railway - نسخه 1.0.0")
    print("=" * 50 + "\n")
    
    # دریافت توکن و آدرس
    token = get_bot_token()
    railway_url = get_railway_url()
    webhook_url = f"https://{railway_url}/webhook"
    
    logger.info(f"🚂 آدرس Railway: {railway_url}")
    logger.info(f"🌐 آدرس webhook: {webhook_url}")
    
    # بررسی اتصال به API تلگرام
    if not check_bot_connection(token):
        logger.error("❌ اتصال به API تلگرام برقرار نشد")
        sys.exit(1)
    
    # بررسی وضعیت فعلی webhook
    webhook_info = check_webhook_info(token)
    
    # حذف webhook قبلی
    if not delete_webhook(token):
        logger.error("❌ حذف webhook قبلی با مشکل مواجه شد")
    
    # صبر کوتاه
    time.sleep(1)
    
    # تنظیم webhook جدید
    if not set_webhook(token, webhook_url):
        logger.error("❌ تنظیم webhook جدید با مشکل مواجه شد")
        sys.exit(1)
    
    # بررسی نهایی
    final_info = check_webhook_info(token)
    
    if final_info and final_info.get("url") == webhook_url:
        print("\n" + "=" * 50)
        print("✅ تنظیم webhook با موفقیت انجام شد")
        print("=" * 50 + "\n")
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ تنظیم webhook با مشکل مواجه شد")
        print("=" * 50 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    main()