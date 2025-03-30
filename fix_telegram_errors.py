#!/usr/bin/env python3
"""
اسکریپت اختصاصی برای رفع مشکلات Telegram API.
این اسکریپت به طور خاص برای رفع خطای 409 Conflict طراحی شده است.
"""

import os
import sys
import logging
import requests
import time
import signal
import subprocess
import json

# تنظیم لاگینگ با رنگ‌های زیبا
logging.basicConfig(
    format="\033[1;36m%(asctime)s\033[0m - \033[1;33m%(name)s\033[0m - \033[1;35m%(levelname)s\033[0m - \033[0m%(message)s\033[0m", 
    level=logging.INFO
)
logger = logging.getLogger("TelegramFixer")

class TelegramFixer:
    """کلاس اختصاصی برای رفع مشکلات API تلگرام."""
    
    def __init__(self):
        """مقداردهی اولیه با بررسی توکن تلگرام."""
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            logger.error("❌ توکن ربات تلگرام یافت نشد!")
            sys.exit(1)
            
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
    def check_connection(self):
        """بررسی اتصال به API تلگرام."""
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
        """بررسی وضعیت webhook فعلی."""
        logger.info("🔍 بررسی وضعیت webhook...")
        
        try:
            response = requests.get(f"{self.base_url}/getWebhookInfo", timeout=10)
            
            if response.status_code == 200 and response.json().get("ok"):
                webhook_info = response.json().get("result", {})
                webhook_url = webhook_info.get("url", "")
                
                if webhook_url:
                    logger.warning(f"⚠️ Webhook فعال است: {webhook_url}")
                    return webhook_url
                else:
                    logger.info("✅ هیچ webhook فعالی وجود ندارد")
                    return None
            else:
                logger.error(f"❌ خطا در بررسی وضعیت webhook: {response.text}")
                return None
        except Exception as e:
            logger.error(f"❌ خطا در بررسی وضعیت webhook: {e}")
            return None
            
    def delete_webhook(self):
        """حذف webhook فعلی و آپدیت‌های در انتظار."""
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
            
    def kill_running_instances(self):
        """کشتن همه فرآیندهای مرتبط با ربات تلگرام."""
        logger.info("🔪 در حال کشتن فرآیندهای ربات تلگرام...")
        
        try:
            # کشتن فرآیندهای Python مرتبط با اسکریپت تلگرام
            subprocess.run(
                ["pkill", "-f", "python.*telegram_bot.*"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=False
            )
            
            # کشتن سرورهای gunicorn در حال اجرا
            subprocess.run(
                ["pkill", "-f", "gunicorn"], 
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
    
    def set_webhook(self, url):
        """تنظیم webhook جدید."""
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
    
    def check_updates(self):
        """بررسی دریافت آپدیت‌ها و تلاش برای رفع خطای 409."""
        logger.info("🔍 بررسی وضعیت آپدیت‌ها...")
        
        try:
            response = requests.get(
                f"{self.base_url}/getUpdates", 
                params={"timeout": 1},
                timeout=5
            )
            
            if response.status_code == 200 and response.json().get("ok"):
                updates = response.json().get("result", [])
                if updates:
                    logger.info(f"✅ {len(updates)} آپدیت دریافت شد")
                    
                    # آخرین شناسه آپدیت + 1 برای حذف آپدیت‌های قدیمی
                    last_update_id = updates[-1]["update_id"]
                    new_offset = last_update_id + 1
                    
                    # درخواست با آفست جدید برای حذف آپدیت‌های قدیمی
                    clear_response = requests.get(
                        f"{self.base_url}/getUpdates", 
                        params={"offset": new_offset, "timeout": 1},
                        timeout=5
                    )
                    
                    if clear_response.status_code == 200 and clear_response.json().get("ok"):
                        logger.info(f"✅ آپدیت‌های قدیمی پاکسازی شدند (آفست جدید: {new_offset})")
                        return True
                    else:
                        logger.error(f"❌ خطا در پاکسازی آپدیت‌ها: {clear_response.text}")
                        return False
                else:
                    logger.info("ℹ️ هیچ آپدیتی برای پردازش وجود ندارد")
                    return True
            else:
                if "Conflict: terminated by other getUpdates request" in response.text:
                    logger.error("❌ خطای 409: Conflict - نمونه دیگری از ربات در حال اجراست")
                    return False
                else:
                    logger.error(f"❌ خطا در دریافت آپدیت‌ها: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"❌ خطا در بررسی آپدیت‌ها: {e}")
            return False
    
    def fix_409_error(self):
        """رفع خطای 409 Conflict."""
        logger.info("🚀 شروع فرآیند رفع خطای 409...")
        
        # مرحله 1: بررسی اتصال
        if not self.check_connection():
            logger.error("❌ ابتدا مشکل اتصال به API تلگرام را برطرف کنید")
            return False
            
        # مرحله 2: بررسی و حذف webhook
        webhook_url = self.check_webhook()
        if webhook_url:
            if not self.delete_webhook():
                logger.error("❌ حذف webhook با خطا مواجه شد")
                return False
                
        # مرحله 3: کشتن فرآیندهای در حال اجرا
        if not self.kill_running_instances():
            logger.warning("⚠️ خطا در کشتن فرآیندها، ادامه فرآیند...")
            
        # مرحله 4: تلاش برای پاکسازی آپدیت‌ها
        time.sleep(2)  # کمی صبر کنیم
        for i in range(3):  # تلاش چند باره
            if self.check_updates():
                logger.info("✅ وضعیت آپدیت‌ها با موفقیت بررسی شد")
                break
            else:
                logger.warning(f"⚠️ تلاش {i+1}/3 برای بررسی آپدیت‌ها با مشکل مواجه شد، تلاش مجدد...")
                time.sleep(2)
                    
        # مرحله 5: بررسی نهایی اتصال
        if self.check_connection():
            logger.info("🎉 فرآیند رفع خطای 409 با موفقیت به پایان رسید!")
            return True
        else:
            logger.error("❌ رفع خطای 409 با مشکل مواجه شد")
            return False

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("🛠️  ابزار رفع مشکلات ربات تلگرام - نسخه 1.0.0")
    print("=" * 50 + "\n")
    
    fixer = TelegramFixer()
    success = fixer.fix_409_error()
    
    if success:
        print("\n" + "=" * 50)
        print("✅ عملیات با موفقیت به پایان رسید")
        print("=" * 50 + "\n")
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ عملیات با خطا مواجه شد")
        print("=" * 50 + "\n")
        sys.exit(1)