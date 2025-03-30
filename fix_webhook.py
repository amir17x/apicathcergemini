#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت جامع برای رفع مشکل خطای 409 Conflict در تلگرام.
این اسکریپت اتصالات موجود را پاکسازی، webhook را حذف، و تمام فرآیندهای مرتبط را متوقف می‌کند.
"""

import os
import sys
import logging
import requests
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

class TelegramFixer:
    """کلاس جامع برای رفع خطای 409 و مشکلات اتصال تلگرام."""
    
    def __init__(self):
        """مقداردهی اولیه با بررسی توکن تلگرام."""
        self.token = os.environ.get('TELEGRAM_BOT_TOKEN')
        
        if not self.token:
            logger.error("❌ توکن ربات تلگرام یافت نشد! لطفاً آن را در متغیرهای محیطی تنظیم کنید.")
            raise ValueError("Telegram bot token not found")
        
        # مسیرهای فایل‌های قفل
        self.lock_files = [
            '/tmp/telegram_bot.lock',
            './telegram_bot.lock',
            '/tmp/bot_instance.lock',
            './bot_instance.lock'
        ]
    
    def get_bot_info(self):
        """دریافت اطلاعات ربات برای بررسی صحت ارتباط."""
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{self.token}/getMe",
                timeout=10
            )
            
            if response.status_code == 200 and response.json().get('ok'):
                bot_info = response.json().get('result', {})
                logger.info(f"✅ اتصال به ربات برقرار شد: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
                return bot_info
            else:
                logger.error(f"❌ خطا در اتصال به API تلگرام: {response.text}")
                return None
        except Exception as e:
            logger.error(f"❌ خطا در ارتباط با API تلگرام: {e}")
            return None
    
    def get_webhook_info(self):
        """دریافت اطلاعات webhook فعلی."""
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{self.token}/getWebhookInfo",
                timeout=10
            )
            
            if response.status_code == 200 and response.json().get('ok'):
                webhook_info = response.json().get('result', {})
                webhook_url = webhook_info.get('url', '')
                
                if webhook_url:
                    logger.info(f"ℹ️ وبهوک فعلی: {webhook_url}")
                else:
                    logger.info("ℹ️ هیچ وبهوکی تنظیم نشده است")
                
                return webhook_info
            else:
                logger.error(f"❌ خطا در دریافت اطلاعات وبهوک: {response.text}")
                return None
        except Exception as e:
            logger.error(f"❌ خطا در دریافت اطلاعات وبهوک: {e}")
            return None
    
    def delete_webhook(self):
        """حذف webhook فعلی تلگرام برای جلوگیری از خطای 409."""
        try:
            # حذف webhook و همه‌ی آپدیت‌های در انتظار
            logger.info("🔄 در حال حذف webhook و آپدیت‌های در انتظار...")
            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/deleteWebhook",
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
            logger.error(f"❌ خطا در ارتباط با API تلگرام: {e}")
            return False
    
    def close_connections(self):
        """بستن همه اتصالات فعلی API تلگرام."""
        try:
            # دستور close برای بستن همه اتصالات فعلی
            logger.info("🔄 در حال بستن همه اتصالات فعلی...")
            
            try:
                close_response = requests.post(
                    f"https://api.telegram.org/bot{self.token}/close", 
                    timeout=10
                )
                
                if close_response.status_code == 200 and close_response.json().get('ok'):
                    logger.info("✅ همه اتصالات فعلی بسته شدند")
                    return True
                else:
                    # حتی اگر با خطا مواجه شویم، ادامه می‌دهیم
                    logger.warning(f"⚠️ بستن اتصالات با کد {close_response.status_code} مواجه شد")
                    if close_response.status_code == 429:
                        logger.info("⏳ دریافت خطای محدودیت نرخ. در حال انتظار...")
                        time.sleep(5)  # انتظار کمی بیشتر برای محدودیت نرخ
            except Exception as e:
                logger.warning(f"⚠️ خطا در بستن اتصالات: {e}")
            
            # صبر می‌کنیم تا تغییرات اعمال شوند - حتی در صورت خطا
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"❌ خطا در بستن اتصالات: {e}")
            return False
    
    def clear_updates_directly(self):
        """پاکسازی مستقیم صف آپدیت‌ها با استفاده از getUpdates."""
        try:
            logger.info("🔄 در حال پاکسازی مستقیم صف آپدیت‌ها...")
            
            # ابتدا یک getUpdates با آفست -1 می‌زنیم تا آخرین آپدیت را بگیریم
            get_response = requests.get(
                f"https://api.telegram.org/bot{self.token}/getUpdates",
                params={'offset': -1, 'limit': 1, 'timeout': 5},
                timeout=10
            )
            
            if get_response.status_code == 200 and get_response.json().get('ok'):
                updates = get_response.json().get('result', [])
                
                if updates:
                    # آخرین آپدیت را پیدا کردیم
                    last_update_id = updates[-1]["update_id"]
                    offset = last_update_id + 1
                    
                    # حذف همه‌ی آپدیت‌های قبلی
                    logger.info(f"🔄 پاکسازی آپدیت‌ها با آفست {offset}...")
                    clear_response = requests.get(
                        f"https://api.telegram.org/bot{self.token}/getUpdates",
                        params={'offset': offset, 'limit': 1, 'timeout': 5},
                        timeout=10
                    )
                    
                    if clear_response.status_code == 200 and clear_response.json().get('ok'):
                        logger.info(f"✅ همه‌ی آپدیت‌های قبلی پاک شدند")
                        return True
                    else:
                        logger.warning(f"⚠️ خطا در پاکسازی آپدیت‌ها: {clear_response.text}")
                else:
                    logger.info("ℹ️ هیچ آپدیتی در صف نیست")
                    return True
            else:
                if "Conflict" in get_response.text:
                    logger.warning("⚠️ خطای 409 Conflict در getUpdates. این نشان‌دهنده وجود نمونه دیگری از ربات است.")
                    return False
                else:
                    logger.warning(f"⚠️ خطا در بررسی آپدیت‌ها: {get_response.text}")
                    return False
        except Exception as e:
            logger.error(f"❌ خطا در پاکسازی آپدیت‌ها: {e}")
            return False
    
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
        return killed_count > 0
    
    def remove_lock_files(self):
        """حذف فایل‌های قفل مربوط به ربات تلگرام."""
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
                logger.error(f"⚠️ خطا در حذف فایل قفل {lock_file}: {e}")
        
        logger.info(f"✅ {removed_count} فایل قفل حذف شد")
        return removed_count > 0
    
    def full_reset(self):
        """اجرای فرآیند کامل پاکسازی و رفع خطای 409."""
        logger.info("🚀 شروع فرآیند پاکسازی کامل و رفع خطای 409...")
        
        # 1. بررسی اتصال به ربات
        bot_info = self.get_bot_info()
        if not bot_info:
            logger.error("❌ نمی‌توان به ربات تلگرام متصل شد")
            return False
        
        # 2. بررسی وضعیت وبهوک
        self.get_webhook_info()
        
        # 3. کشتن فرآیندهای مرتبط با تلگرام
        self.kill_telegram_processes()
        
        # 4. حذف فایل‌های قفل
        self.remove_lock_files()
        
        # 5. بستن همه اتصالات فعلی
        self.close_connections()
        
        # کمی صبر می‌کنیم
        time.sleep(2)
        
        # 6. حذف webhook و آپدیت‌های در انتظار
        success = self.delete_webhook()
        if not success:
            logger.warning("⚠️ خطا در حذف وبهوک، ادامه می‌دهیم...")
        
        # 7. پاکسازی مستقیم صف آپدیت‌ها
        self.clear_updates_directly()
        
        # 8. بررسی مجدد برای اطمینان
        time.sleep(2)
        final_bot_info = self.get_bot_info()
        if final_bot_info:
            logger.info("✅ فرآیند پاکسازی کامل با موفقیت انجام شد")
            return True
        else:
            logger.error("❌ فرآیند پاکسازی کامل با خطا مواجه شد")
            return False

def fix_telegram_409():
    """تابع اصلی برای رفع خطای 409 Conflict."""
    try:
        fixer = TelegramFixer()
        return fixer.full_reset()
    except Exception as e:
        logger.error(f"❌ خطای کلی در فرآیند رفع مشکل: {e}")
        return False

if __name__ == "__main__":
    # بنر اطلاعاتی
    print("="*60)
    print("🛠️  ابزار رفع خطای 409 Conflict تلگرام  🛠️")
    print("="*60)
    print()
    
    result = fix_telegram_409()
    
    if result:
        print("\n✅ فرآیند پاکسازی و رفع خطای 409 با موفقیت انجام شد")
        sys.exit(0)
    else:
        print("\n❌ فرآیند پاکسازی و رفع خطای 409 با مشکل مواجه شد")
        sys.exit(1)