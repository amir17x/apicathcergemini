#!/usr/bin/env python3
"""
اسکریپت برای رفع مشکل خطای 409 Conflict در تلگرام.
این اسکریپت webhook را حذف و تنظیمات را پاکسازی می‌کند.
"""

import os
import sys
import logging
import requests
import time

# تنظیم لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def delete_webhook():
    """حذف webhook فعلی تلگرام برای جلوگیری از خطای 409."""
    print("\n" + "=" * 50)
    print("🛠️  ابزار رفع خطای 409 Conflict در تلگرام")
    print("=" * 50 + "\n")
    
    # دریافت توکن از متغیرهای محیطی
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ توکن ربات تلگرام یافت نشد")
        sys.exit(1)
    
    base_url = f"https://api.telegram.org/bot{token}"
    
    # بررسی اتصال به API تلگرام
    logger.info("🔍 بررسی اتصال به API تلگرام...")
    try:
        response = requests.get(f"{base_url}/getMe", timeout=10)
        
        if response.status_code == 200 and response.json().get("ok"):
            bot_info = response.json().get("result", {})
            logger.info(f"✅ اتصال برقرار شد: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
        else:
            logger.error(f"❌ خطا در اتصال به API تلگرام: {response.text}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ خطا در اتصال به API تلگرام: {e}")
        sys.exit(1)
    
    # بررسی وضعیت webhook فعلی
    logger.info("🔍 بررسی وضعیت webhook فعلی...")
    try:
        response = requests.get(f"{base_url}/getWebhookInfo", timeout=10)
        
        if response.status_code == 200 and response.json().get("ok"):
            webhook_info = response.json().get("result", {})
            webhook_url = webhook_info.get("url", "")
            
            if webhook_url:
                logger.info(f"🌐 Webhook فعال است: {webhook_url}")
                
                # حذف webhook
                logger.info("🔄 در حال حذف webhook...")
                try:
                    response = requests.get(
                        f"{base_url}/deleteWebhook", 
                        params={"drop_pending_updates": True},
                        timeout=10
                    )
                    
                    if response.status_code == 200 and response.json().get("ok"):
                        logger.info("✅ Webhook با موفقیت حذف شد")
                    else:
                        logger.error(f"❌ خطا در حذف webhook: {response.text}")
                        sys.exit(1)
                except Exception as e:
                    logger.error(f"❌ خطا در حذف webhook: {e}")
                    sys.exit(1)
            else:
                logger.info("ℹ️ هیچ webhook فعالی وجود ندارد")
        else:
            logger.error(f"❌ خطا در بررسی وضعیت webhook: {response.text}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ خطا در بررسی وضعیت webhook: {e}")
        sys.exit(1)
    
    # پاکسازی آپدیت‌های در انتظار
    logger.info("🔄 پاکسازی آپدیت‌های در انتظار...")
    try:
        # ابتدا یک آپدیت دریافت می‌کنیم تا شناسه آخرین آپدیت را بدست آوریم
        response = requests.get(
            f"{base_url}/getUpdates",
            params={"timeout": 1},
            timeout=5
        )
        
        if response.status_code == 200 and response.json().get("ok"):
            updates = response.json().get("result", [])
            
            if updates:
                last_update_id = updates[-1]["update_id"]
                offset = last_update_id + 1
                
                # حذف همه آپدیت‌های قبلی با تنظیم آفست
                response = requests.get(
                    f"{base_url}/getUpdates",
                    params={"offset": offset, "timeout": 1},
                    timeout=5
                )
                
                if response.status_code == 200 and response.json().get("ok"):
                    logger.info(f"✅ آپدیت‌های در انتظار پاکسازی شدند (آفست جدید: {offset})")
                else:
                    logger.error(f"❌ خطا در پاکسازی آپدیت‌ها: {response.text}")
            else:
                logger.info("ℹ️ هیچ آپدیتی برای پاکسازی وجود ندارد")
        else:
            logger.error(f"❌ خطا در دریافت آپدیت‌ها: {response.text}")
    except Exception as e:
        logger.error(f"❌ خطا در پاکسازی آپدیت‌ها: {e}")
    
    # بررسی نهایی
    logger.info("🔍 بررسی نهایی...")
    try:
        # بررسی وضعیت webhook
        response = requests.get(f"{base_url}/getWebhookInfo", timeout=10)
        
        if response.status_code == 200 and response.json().get("ok"):
            webhook_info = response.json().get("result", {})
            webhook_url = webhook_info.get("url", "")
            
            if not webhook_url:
                logger.info("✅ Webhook با موفقیت غیرفعال شد")
                
                # تست دریافت آپدیت‌ها
                response = requests.get(
                    f"{base_url}/getUpdates",
                    params={"timeout": 1},
                    timeout=5
                )
                
                if response.status_code == 200 and response.json().get("ok"):
                    logger.info("✅ دریافت آپدیت‌ها با موفقیت انجام شد")
                    
                    print("\n" + "=" * 50)
                    print("✅ خطای 409 با موفقیت برطرف شد")
                    print("=" * 50 + "\n")
                    
                    # تنظیم متغیر محیطی برای اطلاع‌رسانی به سایر اسکریپت‌ها
                    os.environ["BOT_MODE"] = "polling"
                    
                    return True
                else:
                    logger.error(f"❌ خطا در تست دریافت آپدیت‌ها: {response.text}")
            else:
                logger.error(f"❌ Webhook هنوز فعال است: {webhook_url}")
        else:
            logger.error(f"❌ خطا در بررسی نهایی وضعیت webhook: {response.text}")
    except Exception as e:
        logger.error(f"❌ خطا در بررسی نهایی: {e}")
    
    print("\n" + "=" * 50)
    print("⚠️ فرآیند با مشکل مواجه شد")
    print("=" * 50 + "\n")
    
    return False

if __name__ == "__main__":
    delete_webhook()