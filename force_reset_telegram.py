#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت اضطراری برای پاکسازی کامل وضعیت ربات تلگرام.
این اسکریپت تمام تنظیمات و فرآیندهای تلگرام را پاک می‌کند و خطای 409 را برطرف می‌سازد.
"""

import os
import sys
import time
import logging
import requests
import subprocess
import signal
import json
from typing import Dict, Any, Optional, List, Tuple, Union, Set, TypeVar, Generic, cast

# تنظیمات لاگینگ با رنگ‌های زیبا برای خوانایی بهتر
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
        self.token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not self.token:
            logger.error("❌ توکن ربات تلگرام یافت نشد! لطفاً آن را در متغیرهای محیطی تنظیم کنید.")
            sys.exit(1)
            
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        
        # نمایش اطلاعات شروع برنامه
        print("\n" + "=" * 65)
        print("🧨 ابزار اضطراری پاکسازی کامل وضعیت ربات تلگرام - نسخه 1.0.0")
        print("=" * 65 + "\n")
        
    def check_bot_connection(self) -> bool:
        """بررسی اتصال به ربات تلگرام.
        
        Returns:
            bool: وضعیت اتصال
        """
        logger.info("🔄 در حال بررسی اتصال به API تلگرام...")
        
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=10)
            
            if response.status_code == 200 and response.json().get("ok"):
                bot_info = response.json().get("result", {})
                logger.info(f"✅ اتصال به ربات برقرار شد: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
                return True
            else:
                logger.error(f"❌ خطا در اتصال به API تلگرام: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ خطا در اتصال به API تلگرام: {str(e)}")
            return False
    
    def get_webhook_info(self) -> Dict[str, Any]:
        """دریافت اطلاعات وبهوک فعلی.
        
        Returns:
            Dict[str, Any]: اطلاعات وبهوک
        """
        logger.info("🔄 در حال بررسی وضعیت وبهوک فعلی...")
        
        try:
            response = requests.get(f"{self.api_url}/getWebhookInfo", timeout=10)
            
            if response.status_code == 200 and response.json().get("ok"):
                webhook_info = response.json().get("result", {})
                webhook_url = webhook_info.get("url", "")
                
                if webhook_url:
                    logger.info(f"ℹ️ وبهوک فعلی: {webhook_url}")
                else:
                    logger.info("ℹ️ هیچ وبهوکی تنظیم نشده است")
                
                return webhook_info
            else:
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
        logger.info(f"🔄 در حال حذف وبهوک و آپدیت‌های در انتظار (drop_pending_updates={drop_pending_updates})...")
        
        try:
            params = {"drop_pending_updates": drop_pending_updates}
            response = requests.post(f"{self.api_url}/deleteWebhook", json=params, timeout=15)
            
            if response.status_code == 200 and response.json().get("ok"):
                if drop_pending_updates:
                    logger.info("✅ وبهوک با موفقیت حذف شد و آپدیت‌های در انتظار پاک شدند")
                else:
                    logger.info("✅ وبهوک با موفقیت حذف شد")
                return True
            else:
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
        logger.info("🔄 در حال کشتن فرآیندهای مرتبط با تلگرام...")
        
        try:
            # کشتن فرآیندهای پایتون مرتبط با تلگرام
            killed = False
            
            # یافتن PID فرآیندهای مرتبط با تلگرام
            try:
                # جستجو برای فرآیندهای مرتبط با تلگرام
                result = subprocess.run(
                    ["ps", "aux"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                
                pids_to_kill = []
                for line in result.stdout.splitlines():
                    if "telegram" in line.lower() and "python" in line.lower():
                        parts = line.strip().split()
                        if len(parts) > 1:
                            try:
                                pid = int(parts[1])
                                pids_to_kill.append(pid)
                            except ValueError:
                                pass
                
                # کشتن فرآیندهای یافت شده
                for pid in pids_to_kill:
                    if pid != os.getpid():  # خودمان را نکشیم!
                        try:
                            os.kill(pid, signal.SIGKILL)
                            logger.info(f"✅ فرآیند با PID {pid} کشته شد")
                            killed = True
                        except Exception as e:
                            logger.error(f"❌ خطا در کشتن فرآیند با PID {pid}: {str(e)}")
                
                # استفاده از pkill برای اطمینان
                subprocess.run(["pkill", "-9", "-f", "telegram"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
                
                # استفاده از killall برای اطمینان بیشتر
                try:
                    subprocess.run(["killall", "-9", "python"], 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE)
                except:
                    pass
                
            except Exception as e:
                logger.error(f"❌ خطا در یافتن و کشتن فرآیندهای تلگرام: {str(e)}")
            
            if not killed:
                logger.info("ℹ️ هیچ فرآیند مرتبط با تلگرامی یافت نشد")
            
            return True
        except Exception as e:
            logger.error(f"❌ خطا در کشتن فرآیندهای تلگرام: {str(e)}")
            return False
    
    def clear_update_queue(self) -> bool:
        """پاکسازی صف آپدیت‌ها با استفاده از getUpdates.
        
        Returns:
            bool: وضعیت موفقیت
        """
        logger.info("🔄 در حال پاکسازی صف آپدیت‌ها...")
        
        try:
            # ابتدا آخرین update_id را دریافت می‌کنیم
            response = requests.get(
                f"{self.api_url}/getUpdates",
                params={'offset': -1, 'limit': 1, 'timeout': 5},
                timeout=10
            )
            
            if response.status_code == 200 and response.json().get('ok') and response.json().get('result'):
                updates = response.json().get('result')
                if updates:
                    last_update_id = updates[-1]["update_id"]
                    offset = last_update_id + 1
                    
                    # حذف همه‌ی آپدیت‌های قبلی
                    clear_response = requests.get(
                        f"{self.api_url}/getUpdates",
                        params={'offset': offset, 'limit': 1, 'timeout': 5},
                        timeout=10
                    )
                    
                    if clear_response.status_code == 200 and clear_response.json().get('ok'):
                        logger.info(f"✅ صف آپدیت‌ها با موفقیت پاک شد (offset={offset})")
                        return True
                    else:
                        logger.error(f"❌ خطا در پاکسازی صف آپدیت‌ها: {clear_response.text}")
                        return False
                else:
                    logger.info("ℹ️ صف آپدیت‌ها خالی است")
                    return True
            elif response.status_code == 409:
                logger.error("❌ خطای 409 - راهنما: https://core.telegram.org/bots/api#409-error")
                return False
            else:
                logger.error(f"❌ خطا در دریافت آپدیت‌ها: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ خطا در پاکسازی صف آپدیت‌ها: {str(e)}")
            return False
    
    def force_reset_with_api(self) -> bool:
        """تلاش برای ریست کردن وضعیت ربات با استفاده از درخواست‌های API مستقیم.
        
        Returns:
            bool: وضعیت موفقیت
        """
        logger.info("🧨 در حال انجام ریست اضطراری با روش‌های API...")
        
        # تلاش برای بستن همه اتصالات قبلی
        try:
            logger.info("🔄 تلاش برای بستن همه اتصالات فعلی...")
            close_response = requests.post(f"{self.api_url}/close", timeout=10)
            
            if close_response.status_code == 200 and close_response.json().get('ok'):
                logger.info("✅ همه اتصالات قبلی با موفقیت بسته شدند")
            else:
                logger.warning(f"⚠️ هشدار در بستن اتصالات: {close_response.text}")
        except Exception as e:
            logger.warning(f"⚠️ هشدار در بستن اتصالات: {str(e)}")
        
        # کمی صبر می‌کنیم
        time.sleep(2)
        
        # تلاش برای تنظیم مجدد وبهوک
        try:
            logger.info("🔄 در حال حذف وبهوک موجود...")
            delete_webhook_response = requests.post(
                f"{self.api_url}/deleteWebhook",
                json={"drop_pending_updates": True},
                timeout=15
            )
            
            if delete_webhook_response.status_code == 200 and delete_webhook_response.json().get('ok'):
                logger.info("✅ وبهوک با موفقیت حذف شد و آپدیت‌های در انتظار پاک شدند")
            else:
                logger.warning(f"⚠️ هشدار در حذف وبهوک: {delete_webhook_response.text}")
        except Exception as e:
            logger.warning(f"⚠️ هشدار در حذف وبهوک: {str(e)}")
        
        # کمی صبر می‌کنیم
        time.sleep(3)
        
        # تلاش برای دریافت آپدیت‌ها برای تنظیم offset
        try:
            logger.info("🔄 تلاش برای پاکسازی صف آپدیت‌ها...")
            
            # ابتدا یک آپدیت می‌گیریم
            get_updates_response = requests.get(
                f"{self.api_url}/getUpdates",
                params={"offset": -1, "limit": 1},
                timeout=10
            )
            
            if get_updates_response.status_code == 200 and get_updates_response.json().get('ok'):
                updates = get_updates_response.json().get('result', [])
                
                if updates:
                    last_update_id = updates[-1]["update_id"]
                    next_offset = last_update_id + 1
                    
                    # حذف همه آپدیت‌ها
                    clear_updates_response = requests.get(
                        f"{self.api_url}/getUpdates",
                        params={"offset": next_offset},
                        timeout=10
                    )
                    
                    if clear_updates_response.status_code == 200 and clear_updates_response.json().get('ok'):
                        logger.info(f"✅ صف آپدیت‌ها با موفقیت پاک شد (next offset: {next_offset})")
                else:
                    logger.info("ℹ️ هیچ آپدیتی در صف وجود ندارد")
            else:
                logger.warning(f"⚠️ هشدار در دریافت آپدیت‌ها: {get_updates_response.text}")
        except Exception as e:
            logger.warning(f"⚠️ هشدار در پاکسازی صف آپدیت‌ها: {str(e)}")
        
        return True
    
    def run_emergency_reset(self) -> bool:
        """اجرای فرآیند کامل ریست اضطراری.
        
        Returns:
            bool: وضعیت موفقیت
        """
        print("🚀 شروع فرآیند ریست اضطراری...")
        
        # مرحله 1: بررسی اتصال به ربات
        if not self.check_bot_connection():
            logger.error("❌ امکان اتصال به ربات وجود ندارد. توکن را بررسی کنید.")
            return False
        
        # مرحله 2: دریافت اطلاعات وبهوک فعلی
        self.get_webhook_info()
        
        # مرحله 3: کشتن فرآیندهای مرتبط با تلگرام
        self.kill_telegram_processes()
        
        # مرحله 4: حذف وبهوک و آپدیت‌های در انتظار
        self.delete_webhook(drop_pending_updates=True)
        
        # مرحله 5: پاکسازی صف آپدیت‌ها
        self.clear_update_queue()
        
        # مرحله 6: ریست اضطراری با روش‌های API
        self.force_reset_with_api()
        
        # مرحله 7: کمی صبر می‌کنیم تا همه تغییرات اعمال شوند
        logger.info("🕒 در حال انتظار برای تایم اوت شدن اتصالات (10 ثانیه)...")
        time.sleep(10)
        
        # مرحله 8: بررسی نهایی وضعیت وبهوک
        final_webhook_info = self.get_webhook_info()
        
        # مرحله 9: تست نهایی اتصال
        final_connection = self.check_bot_connection()
        
        print("\n" + "=" * 65)
        print("✅ فرآیند ریست اضطراری با موفقیت به پایان رسید")
        print("ℹ️ حالا می‌توانید اطمینان حاصل کنید که فقط یک نمونه از ربات اجرا می‌شود")
        print("=" * 65 + "\n")
        
        return True

def main():
    """تابع اصلی برنامه."""
    reset_tool = TelegramEmergencyReset()
    reset_tool.run_emergency_reset()

if __name__ == "__main__":
    main()