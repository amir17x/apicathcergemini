#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول آماده‌سازی درایور کروم برای استفاده کاربران.

این ماژول مشکل 'Version' object has no attribute 'version' را در undetected-chromedriver
برطرف می‌کند و توابع helper برای ایجاد راحت‌تر نمونه‌های درایور فراهم می‌کند.
"""

import logging
import os
import time
import sys
from typing import Optional, Dict, Any, Tuple, Union

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ابتدا از ماژول monkey_patch استفاده کنیم
try:
    from monkey_patch import monkey_patch_distutils
    monkey_patch_distutils()
except ImportError:
    logger.warning("ماژول monkey_patch یافت نشد.")

# به صورت global درایور undetected_chromedriver را import کنیم
import undetected_chromedriver as uc

def prepare_chrome_driver(
    headless: bool = True,
    proxy: Optional[Union[Dict[str, Any], str]] = None,
    user_agent: Optional[str] = None,
    window_size: Tuple[int, int] = (1920, 1080)
) -> uc.Chrome:
    """
    آماده‌سازی و ایجاد یک نمونه از درایور کروم با تنظیمات داده شده
    
    Args:
        headless: آیا در حالت headless (بدون UI) اجرا شود؟
        proxy: تنظیمات پروکسی (اختیاری)
        user_agent: رشته User-Agent سفارشی (اختیاری)
        window_size: سایز پنجره مرورگر (پیش‌فرض: 1920x1080)
        
    Returns:
        uc.Chrome: یک نمونه از درایور کروم آماده به کار
    """
    # تنظیم ChromeOptions
    options = uc.ChromeOptions()
    
    # تنظیمات عمومی
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=en-US")
    
    # حالت headless
    if headless:
        options.add_argument("--headless")
    
    # User-Agent
    if user_agent:
        options.add_argument(f"--user-agent={user_agent}")
    else:
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    
    # پروکسی
    if proxy:
        if isinstance(proxy, dict):
            proxy_string = f"{proxy.get('protocol', 'http')}://{proxy.get('host')}:{proxy.get('port')}"
            if proxy.get('username') and proxy.get('password'):
                auth = f"{proxy['username']}:{proxy['password']}"
                options.add_argument(f'--proxy-server={proxy_string}')
                # کد مربوط به افزونه احراز هویت پروکسی در اینجا اضافه می‌شود
            else:
                options.add_argument(f'--proxy-server={proxy_string}')
        else:
            # فرض می‌کنیم پروکسی یک رشته به فرمت protocol://host:port است
            options.add_argument(f'--proxy-server={proxy}')
    
    # تلاش برای ایجاد driver با تنظیمات ساده
    logger.info("در حال راه‌اندازی undetected-chromedriver...")
    try:
        # ساده‌ترین حالت
        driver = uc.Chrome(options=options)
        logger.info("ChromeDriver با موفقیت راه‌اندازی شد!")
        return driver
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ChromeDriver: {e}")
        raise

if __name__ == "__main__":
    # تست ساده ماژول
    logger.info("=== تست ساده ماژول prepare_chrome ===")
    print(f"Python version: {sys.version}")
    print(f"UC version: {uc.__version__}")
    print("تست به پایان رسید.")