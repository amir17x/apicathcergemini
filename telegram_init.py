#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ابزار هوشمند راه‌اندازی ربات تلگرام
این اسکریپت محیط اجرایی را تشخیص داده و بر اساس آن عمل می‌کند.
اگر در Replit باشیم، فقط وضعیت را چک می‌کند و ربات را راه‌اندازی نمی‌کند.
اگر در Railway باشیم، ربات را به صورت کامل راه‌اندازی می‌کند.
"""

import os
import sys
import logging
import requests
import json
import time
import signal
import psutil
from pathlib import Path

# تنظیمات لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

class TelegramInitializer:
    """کلاس راه‌اندازی هوشمند ربات تلگرام با تشخیص محیط."""
    
    def __init__(self, force_mode=None):
        """مقداردهی اولیه با تنظیمات مورد نیاز."""
        # دریافت توکن تلگرام
        self.telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.telegram_bot_token:
            logger.error("❌ توکن ربات تلگرام یافت نشد! لطفاً آن را در متغیرهای محیطی تنظیم کنید.")
            sys.exit(1)
            
        self.api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}"
        
        # مسیرهای فایل‌های قفل
        self.lock_files = [
            '/tmp/telegram_bot.lock',
            './telegram_bot.lock',
            '/tmp/bot_instance.lock',
            './bot_instance.lock'
        ]
        
        # تشخیص محیط اجرایی
        self.environment = force_mode or self._detect_environment()
        logger.info(f"🌐 محیط تشخیص داده شده: {self.environment}")
        
    def _detect_environment(self):
        """تشخیص محیط اجرایی (Replit یا Railway)."""
        # بررسی متغیرهای محیطی Railway
        if any(key.startswith('RAILWAY_') for key in os.environ):
            return "railway"
            
        # بررسی متغیرهای محیطی Replit
        if 'REPL_ID' in os.environ or 'REPLIT_DB_URL' in os.environ:
            return "replit"
            
        # اگر تشخیص داده نشد، به عنوان محیط ناشناخته در نظر می‌گیریم
        return "unknown"
        
    def check_bot_connection(self):
        """بررسی اتصال به ربات تلگرام."""
        try:
            logger.info("🔄 بررسی اتصال به API تلگرام...")
            response = requests.get(f"{self.api_url}/getMe", timeout=10)
            
            if response.status_code == 200 and response.json().get("ok"):
                bot_info = response.json().get("result", {})
                logger.info(f"✅ اتصال به ربات برقرار شد: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
                return bot_info
            else:
                logger.error(f"❌ خطا در اتصال به API تلگرام: {response.text}")
                return None
        except Exception as e:
            logger.error(f"❌ خطا در اتصال به API تلگرام: {e}")
            return None
            
    def check_webhook_status(self):
        """بررسی وضعیت webhook."""
        try:
            logger.info("🔄 بررسی وضعیت webhook...")
            response = requests.get(f"{self.api_url}/getWebhookInfo", timeout=10)
            
            if response.status_code == 200 and response.json().get("ok"):
                webhook_info = response.json().get("result", {})
                webhook_url = webhook_info.get("url", "")
                
                if webhook_url:
                    logger.info(f"ℹ️ Webhook فعلی: {webhook_url}")
                    logger.info(f"ℹ️ وضعیت Webhook: {json.dumps(webhook_info, indent=2, ensure_ascii=False)}")
                    return webhook_info
                else:
                    logger.info("ℹ️ هیچ webhook تنظیم نشده است")
                    return {}
            else:
                logger.error(f"❌ خطا در دریافت اطلاعات webhook: {response.text}")
                return None
        except Exception as e:
            logger.error(f"❌ خطا در دریافت اطلاعات webhook: {e}")
            return None
            
    def kill_telegram_processes(self):
        """کشتن همه فرآیندهای مرتبط با تلگرام."""
        logger.info("🔄 در حال کشتن فرآیندهای مرتبط با تلگرام...")
        current_pid = os.getpid()
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # از کشتن فرآیند فعلی خودداری می‌کنیم
                if proc.pid != current_pid:
                    cmdline = " ".join(proc.info['cmdline'] or []).lower()
                    if any(keyword in cmdline for keyword in ['telegram', 'getupdate', 'bot']):
                        logger.info(f"🔪 کشتن فرآیند با PID {proc.pid}")
                        try:
                            os.kill(proc.pid, signal.SIGKILL)
                            killed_count += 1
                        except Exception as e:
                            logger.error(f"⚠️ خطا در کشتن فرآیند {proc.pid}: {e}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        logger.info(f"✅ {killed_count} فرآیند مرتبط با تلگرام کشته شد")
        
    def remove_lock_files(self):
        """حذف فایل‌های قفل موجود."""
        logger.info("🔄 در حال حذف فایل‌های قفل...")
        removed_count = 0
        
        for lock_file in self.lock_files:
            try:
                lock_path = Path(lock_file)
                if lock_path.exists():
                    lock_path.unlink()
                    logger.info(f"✅ فایل قفل {lock_file} حذف شد")
                    removed_count += 1
            except Exception as e:
                logger.warning(f"⚠️ خطا در حذف فایل قفل {lock_file}: {e}")
                
        logger.info(f"✅ {removed_count} فایل قفل حذف شد")
        
    def close_telegram_connections(self):
        """بستن همه اتصالات فعلی تلگرام."""
        try:
            logger.info("🔄 در حال بستن همه اتصالات تلگرام...")
            
            # ابتدا وبهوک را حذف می‌کنیم و آپدیت‌های در انتظار را پاک می‌کنیم
            webhook_response = requests.post(
                f"{self.api_url}/deleteWebhook",
                json={"drop_pending_updates": True},
                timeout=10
            )
            
            if webhook_response.status_code == 200 and webhook_response.json().get("ok"):
                logger.info("✅ وبهوک با موفقیت حذف شد و آپدیت‌های در انتظار پاک شدند")
            else:
                logger.warning(f"⚠️ خطا در حذف وبهوک: {webhook_response.text}")
                
            # کمی صبر می‌کنیم تا تغییرات اعمال شوند
            time.sleep(2)
            
            # حالا برای اطمینان از طریق getUpdates هم تلاش می‌کنیم
            update_response = requests.get(
                f"{self.api_url}/getUpdates",
                params={"offset": -1, "limit": 1, "timeout": 5},
                timeout=10
            )
            
            if update_response.status_code == 200 and update_response.json().get("ok"):
                updates = update_response.json().get("result", [])
                
                if updates:
                    # آخرین آپدیت را پیدا کردیم، آفست را تنظیم می‌کنیم تا آپدیت‌ها پاک شوند
                    last_update_id = updates[-1]["update_id"]
                    offset = last_update_id + 1
                    
                    clear_response = requests.get(
                        f"{self.api_url}/getUpdates",
                        params={"offset": offset, "limit": 1, "timeout": 5},
                        timeout=10
                    )
                    
                    if clear_response.status_code == 200 and clear_response.json().get("ok"):
                        logger.info("✅ همه‌ی آپدیت‌های قبلی با موفقیت پاک شدند")
            
            # در نهایت، تلاش می‌کنیم اتصال قبلی را ببندیم
            try:
                close_response = requests.post(f"{self.api_url}/close", timeout=10)
                
                if close_response.status_code == 200 and close_response.json().get("ok"):
                    logger.info("✅ همه اتصالات فعلی بسته شدند")
                else:
                    logger.warning(f"⚠️ بستن اتصالات با خطا مواجه شد: {close_response.text}")
            except Exception as e:
                logger.warning(f"⚠️ خطا در بستن اتصالات: {e}")
                
            # کمی صبر می‌کنیم تا تغییرات اعمال شوند
            time.sleep(3)
            
            return True
        except Exception as e:
            logger.error(f"❌ خطا در بستن اتصالات تلگرام: {e}")
            return False
            
    def setup_webhook(self, webhook_url):
        """تنظیم webhook برای استفاده در Railway."""
        if not webhook_url:
            logger.error("❌ آدرس webhook خالی است!")
            return False
            
        try:
            logger.info(f"🔄 در حال تنظیم webhook به آدرس: {webhook_url}")
            
            # ابتدا وبهوک قبلی را حذف می‌کنیم
            delete_response = requests.post(
                f"{self.api_url}/deleteWebhook",
                json={"drop_pending_updates": True},
                timeout=10
            )
            
            if delete_response.status_code == 200 and delete_response.json().get("ok"):
                logger.info("✅ وبهوک قبلی با موفقیت حذف شد")
            else:
                logger.warning(f"⚠️ خطا در حذف وبهوک قبلی: {delete_response.text}")
                
            # حالا وبهوک جدید را تنظیم می‌کنیم
            set_response = requests.post(
                f"{self.api_url}/setWebhook",
                json={
                    "url": webhook_url,
                    "max_connections": 40,
                    "allowed_updates": ["message", "edited_message", "callback_query"]
                },
                timeout=15
            )
            
            if set_response.status_code == 200 and set_response.json().get("ok"):
                logger.info("✅ وبهوک با موفقیت تنظیم شد")
                
                # بررسی وضعیت فعلی وبهوک
                webhook_info = self.check_webhook_status()
                return True
            else:
                logger.error(f"❌ خطا در تنظیم وبهوک: {set_response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ خطا در تنظیم وبهوک: {e}")
            return False
            
    def initialize_based_on_environment(self):
        """راه‌اندازی بر اساس محیط تشخیص داده شده."""
        # بررسی اتصال به ربات
        bot_info = self.check_bot_connection()
        if not bot_info:
            logger.error("❌ اتصال به ربات برقرار نشد، نمی‌توان ادامه داد")
            return False
            
        # بررسی وضعیت webhook
        webhook_info = self.check_webhook_status()
        
        # عملکرد بر اساس محیط
        if self.environment == "railway":
            logger.info("🚂 در محیط Railway هستیم، در حال تنظیم وبهوک...")
            
            # حذف فایل‌های قفل
            self.remove_lock_files()
            
            # بستن همه اتصالات قبلی
            self.close_telegram_connections()
            
            # تنظیم وبهوک برای Railway
            railway_url = os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
            if railway_url:
                webhook_url = f"https://{railway_url}/webhook"
                self.setup_webhook(webhook_url)
            else:
                logger.error("❌ آدرس Railway یافت نشد، نمی‌توان وبهوک را تنظیم کرد")
                return False
                
            logger.info("✅ راه‌اندازی در محیط Railway با موفقیت انجام شد")
            return True
            
        elif self.environment == "replit":
            logger.info("🔄 در محیط Replit هستیم، در حال تنظیم حالت توسعه...")
            
            # در محیط Replit، ربات را راه‌اندازی نمی‌کنیم چون احتمالاً نمونه دیگری روی Railway در حال اجراست
            logger.info("⚠️ توجه: در محیط Replit، ربات را راه‌اندازی نمی‌کنیم تا با نمونه Railway تداخل نداشته باشد")
            logger.info("ℹ️ اگر می‌خواهید ربات را در Replit اجرا کنید، لطفاً ابتدا نمونه Railway را متوقف کنید")
            
            # پیشنهاد استفاده از توکن تست برای توسعه
            logger.info("💡 پیشنهاد: برای توسعه و تست در Replit، از یک توکن ربات تست جداگانه استفاده کنید")
            
            # برای نمایش اطلاعات وضعیت ربات در محیط Replit
            webhook_url = webhook_info.get("url", "") if webhook_info else "نامشخص"
            logger.info(f"ℹ️ وضعیت فعلی ربات: webhook = {webhook_url}")
            
            return True
            
        else:
            logger.info("🌐 در محیط ناشناخته هستیم، عملکرد پیش‌فرض...")
            
            # حذف فایل‌های قفل
            self.remove_lock_files()
            
            # بستن همه اتصالات قبلی
            self.close_telegram_connections()
            
            logger.info("✅ راه‌اندازی با موفقیت انجام شد")
            return True

def main():
    """تابع اصلی برنامه."""
    print("\n" + "="*60)
    print("🚀 ابزار راه‌اندازی هوشمند ربات تلگرام")
    print("="*60 + "\n")
    
    # اگر پارامتر محیط به صورت دستی مشخص شده باشد، از آن استفاده می‌کنیم
    if len(sys.argv) > 1:
        force_mode = sys.argv[1]
        print(f"ℹ️ حالت اجبار شده: {force_mode}")
    else:
        force_mode = None
        
    initializer = TelegramInitializer(force_mode)
    result = initializer.initialize_based_on_environment()
    
    if result:
        print("\n✅ راه‌اندازی با موفقیت انجام شد\n")
        sys.exit(0)
    else:
        print("\n❌ راه‌اندازی با خطا مواجه شد\n")
        sys.exit(1)

if __name__ == "__main__":
    main()