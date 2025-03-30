"""
این اسکریپت برای رفع مشکل distutils در Python 3.12 در Railway استفاده می‌شود.
این اسکریپت را قبل از اجرای اصلی برنامه اجرا کنید.
"""

import os
import sys
import subprocess
import site
import shutil
from pathlib import Path
import time
import logging

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# لاگ ابتدایی برای اطمینان از اجرای این اسکریپت در Railway
print("=" * 80)
print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] RAILWAY INITIALIZATION - FIX-DISTUTILS STARTING")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print(f"Environment variables: PORT={os.environ.get('PORT', 'Not set')}")
print("=" * 80)

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
        if not backup_file.exists():
            shutil.copy2(patcher_file, backup_file)
            logger.info(f"نسخه پشتیبان در {backup_file} ایجاد شد.")
        
        # خواندن محتوای فایل
        with open(patcher_file, 'r') as file:
            content = file.read()
        
        # بررسی و اصلاح محتوا
        changes_made = False
        
        if "from distutils.version import LooseVersion" in content:
            logger.info("در حال اصلاح import distutils.version...")
            
            # جایگزینی import
            content = content.replace(
                "from distutils.version import LooseVersion",
                "from packaging.version import parse as LooseVersion  # Fixed import"
            )
            changes_made = True
        
        # تغییر کد مربوط به version_main
        if "self.version_main = release.version[0]" in content:
            logger.info("در حال اصلاح کد استخراج version_main...")
            
            content = content.replace(
                "self.version_main = release.version[0]",
                "self.version_main = int(str(release).split('.')[0])  # Fixed version extraction"
            )
            changes_made = True
            
        if changes_made:
            # نوشتن محتوای جدید
            with open(patcher_file, 'w') as file:
                file.write(content)
            
            logger.info("فایل patcher.py با موفقیت اصلاح شد!")
            return True
        else:
            logger.warning("الگوی مورد انتظار در فایل patcher.py پیدا نشد. ممکن است فایل قبلاً اصلاح شده باشد.")
            return False
        
    except Exception as e:
        logger.error(f"خطا در اصلاح undetected-chromedriver: {e}")
        return False

def install_required_packages():
    """نصب پکیج‌های مورد نیاز"""
    packages = ['packaging', 'undetected-chromedriver']
    
    for package in packages:
        try:
            logger.info(f"در حال نصب پکیج {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            logger.info(f"پکیج {package} با موفقیت نصب شد.")
        except Exception as e:
            logger.error(f"خطا در نصب پکیج {package}: {e}")

def copy_custom_patcher():
    """کپی کردن فایل patcher.py سفارشی به مسیر مورد نظر"""
    try:
        # مسیر فایل patcher.py سفارشی ما
        custom_patcher = 'patcher.py'
        
        if os.path.exists(custom_patcher):
            # پیدا کردن مسیر نصب undetected_chromedriver
            package_path = find_package_path("undetected_chromedriver")
            if not package_path:
                logger.error("پکیج undetected-chromedriver پیدا نشد!")
                return False
                
            destination = package_path / "patcher.py"
            
            # ساخت نسخه پشتیبان
            if destination.exists():
                backup = destination.with_suffix('.py.bak')
                if not backup.exists():
                    shutil.copy2(destination, backup)
                    logger.info(f"نسخه پشتیبان در {backup} ذخیره شد")
            
            # کپی فایل سفارشی
            shutil.copy2(custom_patcher, destination)
            logger.info(f"فایل patcher.py سفارشی با موفقیت به {destination} کپی شد")
            return True
        else:
            logger.warning("فایل patcher.py سفارشی پیدا نشد")
    
    except Exception as e:
        logger.error(f"خطا در کپی فایل سفارشی: {e}")
    
    return False

if __name__ == "__main__":
    print("شروع اصلاح مشکل distutils...")
    
    # نصب پکیج‌های مورد نیاز
    install_required_packages()
    
    # سعی در اصلاح فایل اصلی
    if fix_undetected_chromedriver():
        print("اصلاح با موفقیت انجام شد!")
    else:
        # اگر اصلاح فایل موفقیت‌آمیز نبود، از کپی فایل سفارشی استفاده می‌کنیم
        if copy_custom_patcher():
            print("فایل سفارشی با موفقیت جایگزین شد!")
        else:
            print("نتوانستیم مشکل را به طور خودکار رفع کنیم.")
            print("لطفاً از راه‌حل‌های جایگزین (Docker یا تغییر نسخه Python) استفاده کنید.")