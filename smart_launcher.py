#!/usr/bin/env python3
"""
اسکریپت راه‌اندازی هوشمند ربات تلگرام با پشتیبانی از حالت‌های Webhook و Long Polling.
"""

import os
import sys
import logging
import requests
import json
import subprocess
import time

# تنظیم لاگینگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    stream=sys.stdout  # ارسال لاگ‌ها به stdout
)
logger = logging.getLogger("SmartLauncher")

class TelegramLauncher:
    """راه‌اندازی هوشمند ربات تلگرام"""
    
    def __init__(self):
        """مقداردهی اولیه با بررسی توکن تلگرام"""
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            logger.error("❌ توکن ربات تلگرام یافت نشد")
            sys.exit(1)
            
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        # بررسی محیط
        self.is_railway = "RAILWAY_ENVIRONMENT" in os.environ or "RAILWAY_SERVICE_ID" in os.environ
        if self.is_railway:
            logger.info("🚂 شناسایی محیط Railway")
            
    def check_connection(self):
        """بررسی اتصال به API تلگرام"""
        logger.info("🔍 بررسی اتصال به API تلگرام...")
        
        try:
            response = requests.get(f"{self.base_url}/getMe", timeout=10)
            
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
            
    def check_webhook(self):
        """بررسی وضعیت webhook فعلی"""
        logger.info("🔍 بررسی وضعیت webhook...")
        
        try:
            response = requests.get(f"{self.base_url}/getWebhookInfo", timeout=10)
            
            if response.status_code == 200 and response.json().get("ok"):
                webhook_info = response.json().get("result", {})
                webhook_url = webhook_info.get("url", "")
                
                if webhook_url:
                    logger.info(f"🌐 Webhook فعال است: {webhook_url}")
                    return webhook_url
                else:
                    logger.info("ℹ️ هیچ webhook فعالی وجود ندارد")
                    return None
            else:
                logger.error(f"❌ خطا در بررسی وضعیت webhook: {response.text}")
                return None
        except Exception as e:
            logger.error(f"❌ خطا در بررسی وضعیت webhook: {e}")
            return None
            
    def delete_webhook(self):
        """حذف webhook فعلی و آپدیت‌های در انتظار"""
        logger.info("🔄 حذف webhook فعلی و آپدیت‌های در انتظار...")
        
        try:
            response = requests.get(
                f"{self.base_url}/deleteWebhook", 
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
    
    def set_webhook(self, url):
        """تنظیم webhook جدید"""
        logger.info(f"🔄 تنظیم webhook جدید به آدرس {url}...")
        
        try:
            response = requests.get(
                f"{self.base_url}/setWebhook", 
                params={
                    "url": url,
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
    
    def kill_running_instances(self):
        """کشتن فرآیندهای ربات تلگرام در حال اجرا"""
        logger.info("🔪 در حال کشتن فرآیندهای ربات تلگرام...")
        
        try:
            # کشتن فرآیندهای احتمالی قبلی Python مرتبط با اسکریپت تلگرام
            subprocess.run(
                ["pkill", "-f", "python.*telegram_bot_inline"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=False
            )
            
            # کمی صبر کنیم تا فرآیندها کاملاً خاتمه یابند
            time.sleep(2)
            
            logger.info("✅ فرآیندهای مرتبط با ربات کشته شدند")
            return True
        except Exception as e:
            logger.error(f"❌ خطا در کشتن فرآیندها: {e}")
            return False
    
    def prepare_for_launch(self):
        """آماده‌سازی برای راه‌اندازی ربات"""
        logger.info("🚀 آماده‌سازی برای راه‌اندازی ربات...")
        
        # مرحله 1: بررسی اتصال
        if not self.check_connection():
            logger.error("❌ ابتدا مشکل اتصال به API تلگرام را برطرف کنید")
            return False
            
        # مرحله 2: کشتن فرآیندهای قبلی
        self.kill_running_instances()
            
        # مرحله 3: حذف webhook فعلی برای اطمینان از نبود تداخل
        self.delete_webhook()
        
        # مرحله 4: تنظیم متغیر محیطی برای مشخص کردن حالت راه‌اندازی
        if self.is_railway:
            # در محیط Railway، احتمالاً به webhook نیاز داریم
            os.environ["BOT_MODE"] = "webhook"
            logger.info("🌐 حالت راه‌اندازی: webhook (Railway)")
        else:
            # در محیط‌های دیگر، از long polling استفاده می‌کنیم
            os.environ["BOT_MODE"] = "polling"
            logger.info("🔄 حالت راه‌اندازی: long polling (محیط محلی)")
        
        logger.info("✅ آماده‌سازی با موفقیت انجام شد")
        return True
            
def main():
    """تابع اصلی برای راه‌اندازی ربات"""
    print("\n" + "=" * 60)
    print("🚀 راه‌انداز هوشمند ربات تلگرام - نسخه 1.0.0")
    print("=" * 60 + "\n")
    
    launcher = TelegramLauncher()
    
    # آماده‌سازی برای راه‌اندازی
    if launcher.prepare_for_launch():
        logger.info("✅ آماده‌سازی با موفقیت انجام شد - می‌توانید Flask app را اجرا کنید")
        
        # در صورت نیاز، وب سرور Flask را اینجا راه‌اندازی کنید
        if "RUN_SERVER" in os.environ and os.environ["RUN_SERVER"].lower() == "true":
            try:
                logger.info("🌐 در حال راه‌اندازی وب سرور Flask...")
                os.system("python main.py")
            except Exception as e:
                logger.error(f"❌ خطا در راه‌اندازی وب سرور Flask: {e}")
    else:
        logger.error("❌ آماده‌سازی ربات با مشکل مواجه شد")
        sys.exit(1)

if __name__ == "__main__":
    main()