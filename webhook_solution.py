#!/usr/bin/env python3
"""
اسکریپت کمکی برای عیب‌یابی و رفع مشکلات webhook تلگرام.
این اسکریپت اطلاعات دقیقی درباره وضعیت webhook نمایش می‌دهد و مشکلات رایج را برطرف می‌کند.
"""

import os
import sys
import logging
import requests
import json
import time
import subprocess
from urllib.parse import urlparse
import socket

# تنظیم لاگینگ با رنگ‌های زیبا
logging.basicConfig(
    format="\033[1;36m%(asctime)s\033[0m - \033[1;33m%(name)s\033[0m - \033[1;35m%(levelname)s\033[0m - \033[0m%(message)s\033[0m", 
    level=logging.INFO
)
logger = logging.getLogger("WebhookSolution")

class WebhookDiagnostic:
    """کلاس تشخیص و رفع مشکلات webhook تلگرام."""
    
    def __init__(self):
        """مقداردهی اولیه با بررسی توکن تلگرام."""
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            logger.error("❌ توکن ربات تلگرام یافت نشد!")
            sys.exit(1)
            
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        # بررسی محیط
        self.is_railway = "RAILWAY_ENVIRONMENT" in os.environ or "RAILWAY_SERVICE_ID" in os.environ
        self.railway_url = None
        if self.is_railway:
            self.railway_url = os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
            if self.railway_url:
                logger.info(f"🚂 شناسایی محیط Railway: {self.railway_url}")
            else:
                logger.warning("⚠️ محیط Railway شناسایی شد، اما URL در دسترس نیست")
        
    def check_connection(self):
        """بررسی اتصال به API تلگرام."""
        logger.info("🔍 بررسی اتصال به API تلگرام...")
        
        try:
            response = requests.get(f"{self.base_url}/getMe", timeout=10)
            
            if response.status_code == 200 and response.json().get("ok"):
                bot_info = response.json().get("result", {})
                logger.info(f"✅ اتصال به API تلگرام موفقیت‌آمیز بود: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
                return True, bot_info
            else:
                logger.error(f"❌ خطا در اتصال به API تلگرام: {response.text}")
                return False, None
        except Exception as e:
            logger.error(f"❌ خطا در اتصال به API تلگرام: {e}")
            return False, None
    
    def get_webhook_info(self):
        """دریافت اطلاعات کامل webhook فعلی."""
        logger.info("🔍 دریافت اطلاعات webhook فعلی...")
        
        try:
            response = requests.get(f"{self.base_url}/getWebhookInfo", timeout=10)
            
            if response.status_code == 200 and response.json().get("ok"):
                webhook_info = response.json().get("result", {})
                return webhook_info
            else:
                logger.error(f"❌ خطا در دریافت اطلاعات webhook: {response.text}")
                return None
        except Exception as e:
            logger.error(f"❌ خطا در دریافت اطلاعات webhook: {e}")
            return None
    
    def analyze_webhook(self, webhook_info):
        """تحلیل وضعیت webhook و شناسایی مشکلات."""
        if not webhook_info:
            return False
            
        webhook_url = webhook_info.get("url", "")
        
        if not webhook_url:
            logger.info("ℹ️ هیچ webhook فعالی وجود ندارد")
            return True
            
        logger.info(f"🌐 Webhook فعال است: {webhook_url}")
        
        # بررسی خطاهای رایج
        has_issues = False
        
        # بررسی آپدیت‌های در انتظار
        pending_updates = webhook_info.get("pending_update_count", 0)
        if pending_updates > 0:
            logger.warning(f"⚠️ {pending_updates} آپدیت در صف انتظار است")
            has_issues = True
        
        # بررسی خطای آخر
        last_error_date = webhook_info.get("last_error_date")
        last_error_message = webhook_info.get("last_error_message")
        if last_error_date and last_error_message:
            last_error_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_error_date))
            logger.error(f"❌ آخرین خطای webhook در {last_error_time}: {last_error_message}")
            has_issues = True
        
        # بررسی URL از نظر امنیت
        parsed_url = urlparse(webhook_url)
        if parsed_url.scheme != "https":
            logger.error("❌ URL webhook باید HTTPS باشد")
            has_issues = True
        
        # بررسی مسیر URL
        if not parsed_url.path or parsed_url.path == "/":
            logger.warning("⚠️ مسیر URL webhook مشخص نشده است (توصیه می‌شود از /webhook استفاده کنید)")
            has_issues = True
        
        # بررسی انطباق با Railway
        if self.is_railway and self.railway_url:
            if self.railway_url not in webhook_url:
                logger.warning(f"⚠️ URL webhook با دامنه Railway ({self.railway_url}) مطابقت ندارد")
                has_issues = True
        
        # بررسی قابلیت دسترسی به URL
        try:
            hostname = parsed_url.netloc
            port = 443  # HTTPS پیش‌فرض
            
            # تست اتصال
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((hostname, port))
            sock.close()
            
            if result != 0:
                logger.error(f"❌ نمی‌توان به سرور webhook متصل شد: {hostname}:{port}")
                has_issues = True
            else:
                # تست HTTP
                try:
                    test_response = requests.get(f"{parsed_url.scheme}://{hostname}", timeout=10)
                    logger.info(f"✅ سرور webhook در دسترس است (کد وضعیت: {test_response.status_code})")
                except Exception as http_error:
                    logger.warning(f"⚠️ پاسخ HTTP از سرور webhook دریافت نشد: {http_error}")
                    has_issues = True
                    
        except Exception as e:
            logger.error(f"❌ خطا در بررسی قابلیت دسترسی به URL: {e}")
            has_issues = True
        
        return not has_issues
    
    def delete_webhook(self):
        """حذف webhook فعلی."""
        logger.info("🔄 حذف webhook فعلی...")
        
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
    
    def set_railway_webhook(self):
        """تنظیم webhook برای محیط Railway."""
        if not self.is_railway or not self.railway_url:
            logger.error("❌ این دستور فقط در محیط Railway با URL معتبر قابل استفاده است")
            return False
            
        webhook_url = f"https://{self.railway_url}/webhook"
        logger.info(f"🔄 تنظیم webhook برای Railway: {webhook_url}...")
        
        try:
            response = requests.get(
                f"{self.base_url}/setWebhook", 
                params={
                    "url": webhook_url,
                    "drop_pending_updates": True,
                    "allowed_updates": json.dumps(["message", "edited_message", "callback_query"])
                },
                timeout=10
            )
            
            if response.status_code == 200 and response.json().get("ok"):
                logger.info("✅ Webhook برای Railway با موفقیت تنظیم شد")
                return True
            else:
                logger.error(f"❌ خطا در تنظیم webhook: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ خطا در تنظیم webhook: {e}")
            return False
    
    def set_custom_webhook(self, url):
        """تنظیم webhook سفارشی."""
        logger.info(f"🔄 تنظیم webhook سفارشی: {url}...")
        
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
                logger.info("✅ Webhook سفارشی با موفقیت تنظیم شد")
                return True
            else:
                logger.error(f"❌ خطا در تنظیم webhook: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ خطا در تنظیم webhook: {e}")
            return False
    
    def fix_railway_webhook(self):
        """رفع مشکلات webhook در محیط Railway."""
        if not self.is_railway:
            logger.error("❌ این دستور فقط در محیط Railway قابل استفاده است")
            return False
            
        # ابتدا webhook فعلی را حذف می‌کنیم
        if not self.delete_webhook():
            logger.error("❌ حذف webhook با مشکل مواجه شد")
            return False
            
        # صبر کوتاه
        time.sleep(1)
            
        # تنظیم مجدد webhook برای Railway
        if not self.set_railway_webhook():
            logger.error("❌ تنظیم مجدد webhook با مشکل مواجه شد")
            return False
            
        # بررسی نهایی
        webhook_info = self.get_webhook_info()
        return self.analyze_webhook(webhook_info)
    
    def check_system(self):
        """بررسی وضعیت سیستم برای اجرای صحیح webhook."""
        logger.info("🔍 بررسی وضعیت سیستم...")
        
        # بررسی وضعیت فرآیندهای مرتبط با ربات
        try:
            logger.info("🔍 بررسی فرآیندهای Python...")
            
            result = subprocess.run(
                ["ps", "aux"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            output = result.stdout
            processes = []
            for line in output.splitlines():
                if "python" in line and "telegram_bot" in line:
                    processes.append(line)
            
            if len(processes) > 1:
                logger.warning(f"⚠️ {len(processes)} فرآیند مرتبط با ربات تلگرام در حال اجراست")
                for i, process in enumerate(processes):
                    logger.warning(f"  {i+1}: {process.strip()}")
            elif len(processes) == 1:
                logger.info("✅ یک فرآیند مرتبط با ربات تلگرام در حال اجراست (صحیح)")
            else:
                logger.info("ℹ️ هیچ فرآیند مرتبط با ربات تلگرام در حال اجرا نیست")
        except Exception as e:
            logger.error(f"❌ خطا در بررسی فرآیندها: {e}")
        
        # بررسی وضعیت شبکه
        try:
            logger.info("🔍 بررسی اتصال شبکه...")
            
            # تست DNS
            socket.gethostbyname("api.telegram.org")
            logger.info("✅ DNS به درستی کار می‌کند")
            
            # تست HTTPS
            requests.get("https://api.telegram.org", timeout=5)
            logger.info("✅ اتصال HTTPS به سرور تلگرام برقرار است")
        except Exception as e:
            logger.error(f"❌ خطا در بررسی شبکه: {e}")
        
        # بررسی متغیرهای محیطی
        try:
            logger.info("🔍 بررسی متغیرهای محیطی...")
            
            required_vars = ["TELEGRAM_BOT_TOKEN"]
            for var in required_vars:
                if var in os.environ:
                    logger.info(f"✅ متغیر محیطی {var} تنظیم شده است")
                else:
                    logger.error(f"❌ متغیر محیطی {var} تنظیم نشده است")
            
            if self.is_railway:
                railway_vars = ["RAILWAY_STATIC_URL", "RAILWAY_PUBLIC_DOMAIN"]
                found = False
                for var in railway_vars:
                    if var in os.environ:
                        logger.info(f"✅ متغیر محیطی Railway {var} تنظیم شده است: {os.environ.get(var)}")
                        found = True
                        break
                if not found:
                    logger.error("❌ هیچ‌یک از متغیرهای محیطی دامنه Railway تنظیم نشده است")
        except Exception as e:
            logger.error(f"❌ خطا در بررسی متغیرهای محیطی: {e}")

def print_menu():
    """نمایش منوی اصلی."""
    print("\n" + "=" * 50)
    print("🛠️  ابزار عیب‌یابی و رفع مشکلات Webhook تلگرام")
    print("=" * 50)
    print("1. بررسی وضعیت webhook فعلی")
    print("2. حذف webhook فعلی")
    print("3. تنظیم webhook برای Railway")
    print("4. تنظیم webhook سفارشی")
    print("5. رفع کامل مشکل در Railway")
    print("6. بررسی وضعیت سیستم")
    print("0. خروج")
    print("=" * 50)
    return input("لطفاً یک گزینه انتخاب کنید: ")

def main():
    """تابع اصلی برنامه."""
    diagnostic = WebhookDiagnostic()
    
    # ابتدا اتصال به API تلگرام را بررسی می‌کنیم
    connection_ok, bot_info = diagnostic.check_connection()
    if not connection_ok:
        print("\n❌ اتصال به API تلگرام برقرار نشد. لطفاً ابتدا این مشکل را برطرف کنید.")
        return
    
    while True:
        choice = print_menu()
        
        if choice == "1":
            webhook_info = diagnostic.get_webhook_info()
            if webhook_info:
                print("\n📋 اطلاعات کامل webhook:")
                print(json.dumps(webhook_info, indent=2, ensure_ascii=False))
                diagnostic.analyze_webhook(webhook_info)
        
        elif choice == "2":
            diagnostic.delete_webhook()
            
        elif choice == "3":
            if diagnostic.is_railway and diagnostic.railway_url:
                diagnostic.set_railway_webhook()
            else:
                print("\n❌ محیط Railway شناسایی نشد یا URL در دسترس نیست.")
                
        elif choice == "4":
            url = input("\nلطفاً URL webhook سفارشی را وارد کنید (باید با https:// شروع شود): ")
            if url.startswith("https://"):
                diagnostic.set_custom_webhook(url)
            else:
                print("\n❌ URL نامعتبر است. URL باید با https:// شروع شود.")
                
        elif choice == "5":
            if diagnostic.is_railway:
                print("\n🚀 در حال رفع مشکل webhook در Railway...")
                if diagnostic.fix_railway_webhook():
                    print("\n✅ مشکل webhook با موفقیت برطرف شد.")
                else:
                    print("\n❌ رفع مشکل webhook ناموفق بود.")
            else:
                print("\n❌ این دستور فقط در محیط Railway قابل استفاده است.")
                
        elif choice == "6":
            diagnostic.check_system()
            
        elif choice == "0":
            print("\n👋 خداحافظ!")
            break
            
        else:
            print("\n❌ گزینه نامعتبر است.")
        
        input("\nبرای ادامه، Enter را فشار دهید...")

if __name__ == "__main__":
    main()