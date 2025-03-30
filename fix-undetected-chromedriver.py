#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اسکریپت اختصاصی برای رفع مشکل 'Version' object has no attribute 'version' در undetected-chromedriver.
این اسکریپت فایل patcher.py را در پکیج undetected-chromedriver پیدا و اصلاح می‌کند.
"""

import os
import sys
import site
import logging
import shutil
import subprocess
from pathlib import Path

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_package_path(package_name):
    """
    پیدا کردن مسیر یک پکیج نصب شده.
    
    Args:
        package_name: نام پکیج
        
    Returns:
        Path: مسیر پکیج یا None اگر پیدا نشد
    """
    try:
        # فهرست مسیرهای جستجو
        search_paths = sys.path + [site.getusersitepackages()] + site.getsitepackages()
        
        # جستجو در مسیرها
        for search_path in search_paths:
            path = Path(search_path) / package_name
            if path.exists() and path.is_dir():
                return path
        
        return None
    except Exception as e:
        logger.error(f"خطا در جستجوی پکیج {package_name}: {e}")
        return None

def fix_undetected_chromedriver():
    """
    رفع مشکل 'Version' object has no attribute 'version' در undetected-chromedriver.
    
    Returns:
        bool: وضعیت موفقیت
    """
    try:
        logger.info("در حال جستجوی پکیج undetected-chromedriver...")
        package_path = find_package_path("undetected_chromedriver")
        
        if not package_path:
            logger.error("پکیج undetected-chromedriver پیدا نشد!")
            return False
        
        logger.info(f"پکیج undetected-chromedriver در مسیر {package_path} پیدا شد.")
        
        # مسیر فایل patcher.py
        patcher_file = package_path / "patcher.py"
        
        if not patcher_file.exists():
            logger.error(f"فایل patcher.py در مسیر {package_path} پیدا نشد!")
            return False
        
        logger.info(f"فایل patcher.py در مسیر {patcher_file} پیدا شد.")
        
        # ایجاد نسخه پشتیبان
        backup_file = patcher_file.with_suffix('.py.bak')
        shutil.copy2(patcher_file, backup_file)
        logger.info(f"نسخه پشتیبان در {backup_file} ایجاد شد.")
        
        # خواندن محتوای فایل
        with open(patcher_file, 'r') as file:
            content = file.read()
        
        # بررسی و اصلاح محتوا
        if "from distutils.version import LooseVersion" in content:
            logger.info("در حال اصلاح import distutils.version...")
            
            # جایگزینی import
            content = content.replace(
                "from distutils.version import LooseVersion",
                "from packaging.version import parse as LooseVersion  # Fixed import"
            )
            
            # تغییر کد مربوط به version_main
            if "self.version_main = release.version[0]" in content:
                logger.info("در حال اصلاح کد استخراج version_main...")
                
                content = content.replace(
                    "self.version_main = release.version[0]",
                    "self.version_main = int(str(release).split('.')[0])  # Fixed version extraction"
                )
            
            # نوشتن محتوای جدید
            with open(patcher_file, 'w') as file:
                file.write(content)
            
            logger.info("فایل patcher.py با موفقیت اصلاح شد!")
            
            # نصب پکیج packaging اگر نصب نشده باشد
            try:
                import packaging
                logger.info("پکیج packaging قبلاً نصب شده است.")
            except ImportError:
                logger.info("در حال نصب پکیج packaging...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "packaging"])
                logger.info("پکیج packaging با موفقیت نصب شد.")
            
            return True
        else:
            logger.warning("الگوی مورد انتظار در فایل patcher.py پیدا نشد. ممکن است فایل قبلاً اصلاح شده باشد.")
            return False
        
    except Exception as e:
        logger.error(f"خطا در اصلاح undetected-chromedriver: {e}")
        return False

def main():
    """تابع اصلی برنامه."""
    logger.info("=== ابزار رفع خطای 'Version' object has no attribute 'version' در undetected-chromedriver ===")
    
    success = fix_undetected_chromedriver()
    
    if success:
        logger.info("✅ عملیات با موفقیت به پایان رسید.")
    else:
        logger.error("❌ عملیات با خطا مواجه شد.")
    
    logger.info("=== پایان عملیات ===")

if __name__ == "__main__":
    main()