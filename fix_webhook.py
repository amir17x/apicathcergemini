#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت برای رفع مشکل خطای 409 Conflict در تلگرام.
این اسکریپت webhook را حذف و تنظیمات را پاکسازی می‌کند.
"""

import os
import sys
import logging
import requests
import time

# تنظیمات لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

def delete_webhook():
    """حذف webhook فعلی تلگرام برای جلوگیری از خطای 409."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ توکن ربات تلگرام یافت نشد! لطفاً آن را در متغیرهای محیطی تنظیم کنید.")
        return False
        
    # دریافت اطلاعات webhook فعلی
    try:
        webhook_info_response = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10)
        
        if webhook_info_response.status_code == 200 and webhook_info_response.json().get("ok"):
            webhook_info = webhook_info_response.json().get("result", {})
            webhook_url = webhook_info.get("url", "")
            
            if webhook_url:
                logger.info(f"وبهوک فعلی: {webhook_url}")
            else:
                logger.info("هیچ وبهوکی تنظیم نشده است")
        else:
            logger.error(f"خطا در دریافت اطلاعات وبهوک: {webhook_info_response.text}")
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات وبهوک: {str(e)}")
    
    # حذف webhook فعلی
    try:
        logger.info("در حال حذف webhook و آپدیت‌های در انتظار...")
        
        delete_webhook_response = requests.post(
            f"https://api.telegram.org/bot{token}/deleteWebhook",
            json={"drop_pending_updates": True},
            timeout=15
        )
        
        if delete_webhook_response.status_code == 200 and delete_webhook_response.json().get("ok"):
            logger.info("✅ وبهوک با موفقیت حذف شد و آپدیت‌های در انتظار پاک شدند")
        else:
            logger.error(f"❌ خطا در حذف وبهوک: {delete_webhook_response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در حذف وبهوک: {str(e)}")
        return False
    
    # تلاش برای بستن همه اتصالات فعلی
    try:
        logger.info("در حال بستن همه اتصالات فعلی...")
        
        close_response = requests.post(f"https://api.telegram.org/bot{token}/close", timeout=10)
        
        if close_response.status_code == 200 and close_response.json().get('ok'):
            logger.info("✅ همه اتصالات فعلی با موفقیت بسته شدند")
        else:
            logger.warning(f"⚠️ هشدار در بستن اتصالات: {close_response.text}")
    except Exception as e:
        logger.warning(f"⚠️ هشدار در بستن اتصالات: {str(e)}")
    
    # کمی صبر کنیم تا همه تغییرات اعمال شوند
    logger.info("در حال انتظار برای تایم اوت شدن اتصالات (5 ثانیه)...")
    time.sleep(5)
    
    logger.info("✅ عملیات با موفقیت به پایان رسید")
    logger.info("ℹ️ حالا می‌توانید برنامه اصلی را اجرا کنید")
    
    return True

if __name__ == "__main__":
    print("\n=== ابزار رفع خطای 409 Conflict تلگرام ===\n")
    delete_webhook()
    print("\n=== عملیات با موفقیت به پایان رسید ===\n")