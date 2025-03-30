#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
مکانیزم قفل فایل برای اطمینان از اجرای فقط یک نمونه از ربات تلگرام.
این اسکریپت از چند نمونه‌ای شدن ربات جلوگیری می‌کند و خطای 409 را برطرف می‌سازد.
"""

import os
import sys
import fcntl
import atexit
import logging
import requests
import time

# تنظیمات لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='\033[1;36m%(asctime)s\033[0m - \033[1;33m%(name)s\033[0m - \033[1;35m%(levelname)s\033[0m - \033[0m%(message)s\033[0m',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

class TelegramSingleInstance:
    """کلاس مدیریت تک‌نمونه بودن ربات تلگرام با استفاده از قفل فایل."""
    
    def __init__(self, telegram_bot_token=None, lock_file_path="/tmp/telegram_bot.lock"):
        """مقداردهی اولیه کلاس با تنظیمات مورد نیاز."""
        self.telegram_bot_token = telegram_bot_token or os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.telegram_bot_token:
            logger.error("❌ توکن ربات تلگرام یافت نشد! لطفاً آن را در متغیرهای محیطی تنظیم کنید.")
            sys.exit(1)
            
        self.api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}"
        self.lock_file_path = lock_file_path
        self.lock_file = None
        self.is_locked = False
        
        # ثبت تابع پاکسازی برای اجرا هنگام خروج برنامه
        atexit.register(self.cleanup)
        
    def acquire_lock(self):
        """تلاش برای گرفتن قفل فایل.
        
        Returns:
            bool: وضعیت موفقیت در گرفتن قفل
        """
        try:
            # باز کردن فایل قفل (ایجاد در صورت عدم وجود)
            self.lock_file = open(self.lock_file_path, 'w')
            
            # تلاش برای گرفتن قفل غیرمسدودکننده
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # نوشتن PID پروسه فعلی در فایل قفل
            self.lock_file.write(f"{os.getpid()}\n")
            self.lock_file.flush()
            
            self.is_locked = True
            logger.info(f"✅ قفل فایل با موفقیت گرفته شد (PID: {os.getpid()})")
            return True
            
        except IOError:
            # در صورتی که قفل قبلاً گرفته شده باشد
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
                
            # تلاش برای خواندن PID پروسه دارنده قفل
            try:
                with open(self.lock_file_path, 'r') as f:
                    pid = f.read().strip()
                    logger.error(f"❌ یک نمونه دیگر از ربات در حال اجراست (PID: {pid})!")
            except:
                logger.error("❌ یک نمونه دیگر از ربات در حال اجراست!")
                
            return False
            
        except Exception as e:
            logger.error(f"❌ خطا در گرفتن قفل فایل: {str(e)}")
            return False
    
    def release_lock(self):
        """آزاد کردن قفل فایل."""
        if self.is_locked and self.lock_file:
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
                self.lock_file.close()
                self.lock_file = None
                self.is_locked = False
                logger.info("✅ قفل فایل با موفقیت آزاد شد")
                return True
            except Exception as e:
                logger.error(f"❌ خطا در آزاد کردن قفل فایل: {str(e)}")
                return False
        return True
    
    def cleanup(self):
        """پاکسازی منابع هنگام خروج از برنامه."""
        self.release_lock()
        
        # تلاش برای پاکسازی فایل قفل اگر این پروسه مالک آن است
        try:
            if os.path.exists(self.lock_file_path):
                with open(self.lock_file_path, 'r') as f:
                    pid = f.read().strip()
                    if pid == str(os.getpid()):
                        os.remove(self.lock_file_path)
                        logger.info("✅ فایل قفل حذف شد")
        except Exception as e:
            logger.error(f"❌ خطا در پاکسازی فایل قفل: {str(e)}")
    
    def reset_telegram_connection(self):
        """ریست کردن اتصال به API تلگرام و حذف وبهوک."""
        logger.info("🔄 در حال ریست کردن اتصال به API تلگرام...")
        
        # بررسی اتصال به API تلگرام
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=10)
            if response.status_code == 200 and response.json().get("ok"):
                bot_info = response.json().get("result", {})
                logger.info(f"✅ اتصال به API تلگرام برقرار است: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
            else:
                logger.error(f"❌ خطا در اتصال به API تلگرام: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ خطا در اتصال به API تلگرام: {str(e)}")
            return False
        
        # حذف وبهوک و پاکسازی آپدیت‌های در انتظار
        try:
            params = {"drop_pending_updates": True}
            response = requests.get(f"{self.api_url}/deleteWebhook", params=params, timeout=10)
            
            if response.status_code == 200 and response.json().get("ok"):
                logger.info("✅ وبهوک با موفقیت حذف شد و آپدیت‌های در انتظار پاک شدند")
            else:
                logger.error(f"❌ خطا در حذف وبهوک: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ خطا در حذف وبهوک: {str(e)}")
            return False
        
        # بستن همه اتصالات فعلی
        try:
            response = requests.post(f"{self.api_url}/close", timeout=10)
            if response.status_code == 200 and response.json().get("ok"):
                logger.info("✅ همه اتصالات فعلی با موفقیت بسته شدند")
            else:
                # در صورت خطای 429، نیازی به توقف نیست، فقط لاگ می‌کنیم
                if response.status_code == 429:
                    logger.warning(f"⚠️ محدودیت نرخ درخواست در close: {response.text}")
                else:
                    logger.warning(f"⚠️ هشدار در بستن اتصالات: {response.text}")
        except Exception as e:
            logger.warning(f"⚠️ هشدار در بستن اتصالات: {str(e)}")
        
        # کمی صبر کنیم تا همه اتصالات تایم اوت شوند
        logger.info("🕒 در حال انتظار برای تایم اوت شدن اتصالات...")
        time.sleep(3)
        
        return True
    
    def run_as_single_instance(self, callback_function, *args, **kwargs):
        """اجرای کد به صورت تک‌نمونه.
        
        Args:
            callback_function: تابعی که باید اجرا شود
            *args, **kwargs: پارامترهای مورد نیاز تابع
            
        Returns:
            mixed: نتیجه اجرای تابع callback_function یا None در صورت خطا
        """
        # تلاش برای گرفتن قفل فایل
        if not self.acquire_lock():
            logger.error("❌ امکان اجرای تک‌نمونه وجود ندارد. لطفاً نمونه‌های دیگر را متوقف کنید.")
            sys.exit(1)
            
        # ریست کردن اتصال به API تلگرام
        if not self.reset_telegram_connection():
            logger.warning("⚠️ خطا در ریست کردن اتصال به API تلگرام. ادامه برنامه...")
            
        # اجرای تابع اصلی
        try:
            logger.info("🚀 شروع اجرای برنامه به صورت تک‌نمونه...")
            result = callback_function(*args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"❌ خطا در اجرای برنامه: {str(e)}")
            return None
        finally:
            # آزاد کردن قفل در پایان (البته atexit هم این کار را انجام می‌دهد)
            self.release_lock()


# مثال استفاده
if __name__ == "__main__":
    def example_bot_function():
        """این تابع به عنوان مثال استفاده می‌شود."""
        logger.info("✨ ربات تلگرام در حال اجراست (مثال)")
        try:
            # شبیه‌سازی اجرای طولانی‌مدت
            for i in range(5):
                logger.info(f"🕒 ربات در حال اجرا... ({i+1}/5)")
                time.sleep(2)
            logger.info("✅ اجرای ربات با موفقیت به پایان رسید")
            return True
        except KeyboardInterrupt:
            logger.info("⚠️ اجرای ربات با دستور کاربر متوقف شد")
            return False
            
    # اجرای مثال
    instance_manager = TelegramSingleInstance()
    instance_manager.run_as_single_instance(example_bot_function)