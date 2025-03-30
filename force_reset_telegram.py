#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت اضطراری برای پاکسازی کامل وضعیت ربات تلگرام.
این اسکریپت تمام تنظیمات و فرآیندهای تلگرام را پاک می‌کند و خطای 409 را برطرف می‌سازد.
"""

import os
import requests
import time
import json
import logging
import subprocess
import signal
import sys
import atexit
from typing import Dict, Any, List, Optional, Tuple

# تنظیمات لاگینگ با رنگ‌های متفاوت
logging.basicConfig(
    level=logging.INFO,
    format='\033[1;36m%(asctime)s\033[0m - \033[1;33m%(name)s\033[0m - \033[1;35m%(levelname)s\033[0m - \033[0m%(message)s\033[0m',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

class TelegramEmergencyReset:
    """کلاس اضطراری برای پاکسازی کامل وضعیت ربات تلگرام."""
    
    def __init__(self):
        """مقداردهی اولیه کلاس."""
        self.bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            logger.error("❌ توکن ربات تلگرام یافت نشد! لطفاً آن را در متغیرهای محیطی تنظیم کنید.")
            sys.exit(1)
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.webhook_info = None
        self.bot_info = None
        
    def check_bot_connection(self) -> bool:
        """بررسی اتصال به ربات تلگرام.
        
        Returns:
            bool: وضعیت اتصال
        """
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=10)
            if response.status_code == 200:
                self.bot_info = response.json()["result"]
                logger.info(f"✅ اتصال به ربات برقرار شد: @{self.bot_info['username']} (ID: {self.bot_info['id']})")
                return True
            logger.error(f"❌ خطا در اتصال به ربات: {response.text}")
            return False
        except Exception as e:
            logger.error(f"❌ خطا در اتصال به ربات: {str(e)}")
            return False
    
    def get_webhook_info(self) -> Dict[str, Any]:
        """دریافت اطلاعات وبهوک فعلی.
        
        Returns:
            Dict[str, Any]: اطلاعات وبهوک
        """
        try:
            response = requests.get(f"{self.api_url}/getWebhookInfo", timeout=10)
            if response.status_code == 200:
                self.webhook_info = response.json()["result"]
                if self.webhook_info.get("url"):
                    logger.info(f"ℹ️ وبهوک فعلی: {self.webhook_info['url']}")
                else:
                    logger.info("ℹ️ هیچ وبهوک فعالی وجود ندارد")
                return self.webhook_info
            logger.error(f"❌ خطا در دریافت اطلاعات وبهوک: {response.text}")
            return {}
        except Exception as e:
            logger.error(f"❌ خطا در دریافت اطلاعات وبهوک: {str(e)}")
            return {}
    
    def delete_webhook(self, drop_pending_updates: bool = True) -> bool:
        """حذف وبهوک فعلی.
        
        Args:
            drop_pending_updates: آیا آپدیت‌های در انتظار نیز حذف شوند؟
            
        Returns:
            bool: وضعیت موفقیت
        """
        try:
            params = {"drop_pending_updates": drop_pending_updates}
            response = requests.post(f"{self.api_url}/deleteWebhook", json=params, timeout=10)
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

    def kill_telegram_processes(self) -> bool:
        """کشتن همه فرآیندهای مرتبط با تلگرام.
        
        Returns:
            bool: وضعیت موفقیت
        """
        try:
            # جستجوی همه فرآیندهای پایتون
            cmd = "ps aux | grep python"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            lines = result.stdout.split('\n')
            
            # فیلتر کردن فرآیندهای مرتبط با تلگرام
            telegram_processes = []
            current_pid = os.getpid()  # PID فرآیند فعلی
            
            for line in lines:
                if "telegram" in line.lower() and "python" in line.lower():
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            if pid != current_pid:  # اطمینان از عدم کشتن فرآیند فعلی
                                telegram_processes.append(pid)
                        except ValueError:
                            pass
            
            # کشتن فرآیندهای یافت شده
            killed = 0
            for pid in telegram_processes:
                try:
                    os.kill(pid, signal.SIGTERM)
                    logger.info(f"✅ فرآیند با PID {pid} کشته شد")
                    killed += 1
                except ProcessLookupError:
                    logger.warning(f"⚠️ فرآیند با PID {pid} یافت نشد")
                except PermissionError:
                    logger.error(f"❌ دسترسی لازم برای کشتن فرآیند با PID {pid} وجود ندارد")
                except Exception as e:
                    logger.error(f"❌ خطا در کشتن فرآیند با PID {pid}: {str(e)}")
            
            # کشتن فرآیندهای gunicorn که ممکن است ربات تلگرام را اجرا کنند
            cmd = "ps aux | grep gunicorn"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            lines = result.stdout.split('\n')
            
            gunicorn_processes = []
            for line in lines:
                if "main.py" in line or "main:app" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            if pid != current_pid:
                                gunicorn_processes.append(pid)
                        except ValueError:
                            pass
            
            for pid in gunicorn_processes:
                try:
                    # ابتدا SIGTERM را امتحان می‌کنیم
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(1)
                    
                    # بررسی می‌کنیم آیا هنوز زنده است
                    try:
                        os.kill(pid, 0)  # تست وجود فرآیند
                        # هنوز زنده است، از SIGKILL استفاده می‌کنیم
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        # قبلاً کشته شده است
                        pass
                    
                    logger.info(f"✅ فرآیند Gunicorn با PID {pid} کشته شد")
                    killed += 1
                except Exception as e:
                    logger.error(f"❌ خطا در کشتن فرآیند Gunicorn با PID {pid}: {str(e)}")
            
            logger.info(f"✅ تعداد {killed} فرآیند مرتبط با تلگرام کشته شدند")
            return True
        except Exception as e:
            logger.error(f"❌ خطا در کشتن فرآیندهای تلگرام: {str(e)}")
            return False

    def clear_update_queue(self) -> bool:
        """پاکسازی صف آپدیت‌ها با استفاده از getUpdates.
        
        Returns:
            bool: وضعیت موفقیت
        """
        try:
            # ابتدا با offset=-1 و limit=1 یک آپدیت دریافت می‌کنیم تا آخرین update_id را بدست آوریم
            response = requests.get(f"{self.api_url}/getUpdates", params={"offset": -1, "limit": 1, "timeout": 1}, timeout=5)
            if response.status_code != 200:
                logger.error(f"❌ خطا در دریافت آپدیت‌ها: {response.text}")
                return False
            
            data = response.json()
            if not data.get("ok"):
                logger.error(f"❌ خطا در دریافت آپدیت‌ها: {data}")
                return False
            
            updates = data.get("result", [])
            if not updates:
                logger.info("✅ هیچ آپدیتی در صف وجود ندارد")
                return True
            
            # آخرین update_id را بدست می‌آوریم و offset را update_id + 1 قرار می‌دهیم
            last_update_id = updates[-1]["update_id"]
            offset = last_update_id + 1
            
            # حالا با offset جدید، همه آپدیت‌ها را پاکسازی می‌کنیم
            response = requests.get(f"{self.api_url}/getUpdates", params={"offset": offset, "timeout": 1}, timeout=5)
            if response.status_code == 200:
                logger.info("✅ صف آپدیت‌ها با موفقیت پاکسازی شد")
                return True
            
            logger.error(f"❌ خطا در پاکسازی صف آپدیت‌ها: {response.text}")
            return False
        except requests.exceptions.RequestException as e:
            if "Conflict: terminated by other getUpdates request" in str(e):
                logger.error("❌ خطای 409: Conflict - نمونه دیگری از ربات در حال اجراست")
            else:
                logger.error(f"❌ خطا در پاکسازی صف آپدیت‌ها: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ خطا در پاکسازی صف آپدیت‌ها: {str(e)}")
            return False

    def force_reset_with_api(self) -> bool:
        """تلاش برای ریست کردن وضعیت ربات با استفاده از درخواست‌های API مستقیم.
        
        Returns:
            bool: وضعیت موفقیت
        """
        try:
            # 1. ابتدا با deleteWebhook همه آپدیت‌های در انتظار را پاک می‌کنیم
            self.delete_webhook(drop_pending_updates=True)
            time.sleep(2)
            
            # 2. سعی می‌کنیم با close صریح، ارتباط با تلگرام را ببندیم
            logger.info("🔄 در حال بستن اتصال به تلگرام...")
            response = requests.post(f"{self.api_url}/close", timeout=10)
            if response.status_code == 200:
                logger.info("✅ اتصال به تلگرام با موفقیت بسته شد")
            else:
                logger.warning(f"⚠️ بستن اتصال به تلگرام ناموفق بود: {response.text}")
            
            time.sleep(5)  # صبر می‌کنیم تا اتصال کاملاً بسته شود
            
            # 3. حالا دوباره اتصال را چک می‌کنیم
            return self.check_bot_connection()
        except Exception as e:
            logger.error(f"❌ خطا در ریست کردن وضعیت ربات: {str(e)}")
            return False

    def run_emergency_reset(self) -> bool:
        """اجرای فرآیند کامل ریست اضطراری.
        
        Returns:
            bool: وضعیت موفقیت
        """
        logger.info("🚨 شروع فرآیند ریست اضطراری ربات تلگرام...")
        
        # 1. بررسی اتصال اولیه به ربات
        if not self.check_bot_connection():
            logger.error("❌ ارتباط با ربات برقرار نیست! لطفاً توکن ربات را بررسی کنید.")
            return False
        
        # 2. بررسی وضعیت وبهوک
        self.get_webhook_info()
        
        # 3. کشتن همه فرآیندهای مرتبط با تلگرام
        logger.info("🔄 در حال کشتن فرآیندهای مرتبط با تلگرام...")
        self.kill_telegram_processes()
        time.sleep(3)  # اندکی صبر برای اطمینان از بسته شدن فرآیندها
        
        # 4. حذف وبهوک و آپدیت‌های در انتظار
        logger.info("🔄 در حال حذف وبهوک و پاکسازی آپدیت‌های در انتظار...")
        self.delete_webhook(drop_pending_updates=True)
        time.sleep(2)
        
        # 5. تلاش برای ریست کردن وضعیت ربات با استفاده از API
        logger.info("🔄 در حال ریست کردن وضعیت ربات...")
        self.force_reset_with_api()
        time.sleep(3)
        
        # 6. تلاش برای پاکسازی صف آپدیت‌ها
        logger.info("🔄 در حال پاکسازی صف آپدیت‌ها...")
        update_queue_cleared = False
        for i in range(3):  # تا 3 بار تلاش می‌کنیم
            if self.clear_update_queue():
                update_queue_cleared = True
                break
            logger.warning(f"⚠️ تلاش {i+1}/3 برای پاکسازی صف آپدیت‌ها ناموفق بود. تلاش مجدد...")
            time.sleep(5)
        
        # 7. بررسی نهایی
        if update_queue_cleared:
            logger.info("✅ ریست اضطراری با موفقیت انجام شد!")
            return True
        else:
            logger.warning("⚠️ ریست اضطراری انجام شد، اما همچنان مشکل 409 پابرجاست.")
            logger.info("ℹ️ پیشنهاد: کمی صبر کنید (حداقل 1 دقیقه) و دوباره تلاش کنید.")
            return False


def main():
    """تابع اصلی برنامه."""
    print("\n" + "=" * 50)
    print("🚨 ابزار ریست اضطراری ربات تلگرام - نسخه 1.0.0")
    print("=" * 50 + "\n")
    
    reset_tool = TelegramEmergencyReset()
    success = reset_tool.run_emergency_reset()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ ریست اضطراری با موفقیت انجام شد!")
        print("🔄 اکنون می‌توانید ربات را مجدداً راه‌اندازی کنید.")
    else:
        print("⚠️ عملیات ریست اضطراری با مشکل مواجه شد")
        print("🔄 لطفاً چند دقیقه صبر کنید و دوباره تلاش کنید.")
    print("=" * 50 + "\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())