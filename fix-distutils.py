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

def fix_undetected_chromedriver():
    """رفع مشکل ماژول undetected_chromedriver با تغییر import distutils به packaging"""
    try:
        # پیدا کردن مسیر نصب undetected_chromedriver
        site_packages = site.getsitepackages()[0]
        patcher_path = os.path.join(site_packages, 'undetected_chromedriver', 'patcher.py')
        
        if os.path.exists(patcher_path):
            print(f"فایل patcher.py در مسیر {patcher_path} پیدا شد")
            
            # خواندن محتوای فایل
            with open(patcher_path, 'r') as f:
                content = f.read()
            
            # جایگزینی import
            if 'from distutils.version import LooseVersion' in content:
                content = content.replace(
                    'from distutils.version import LooseVersion',
                    'from packaging.version import parse as LooseVersion'
                )
                
                # ذخیره فایل اصلاح شده
                with open(patcher_path, 'w') as f:
                    f.write(content)
                    
                print("فایل patcher.py با موفقیت اصلاح شد!")
                return True
            else:
                print("الگوی مورد نظر در فایل پیدا نشد")
        else:
            print(f"فایل patcher.py در مسیر {patcher_path} پیدا نشد")
    
    except Exception as e:
        print(f"خطا در اصلاح فایل: {str(e)}")
    
    return False

def install_required_packages():
    """نصب پکیج‌های مورد نیاز"""
    packages = ['packaging']
    
    for package in packages:
        try:
            print(f"در حال نصب {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"{package} با موفقیت نصب شد!")
        except Exception as e:
            print(f"خطا در نصب {package}: {str(e)}")

def copy_custom_patcher():
    """کپی کردن فایل patcher.py سفارشی به مسیر مورد نظر"""
    try:
        # مسیر فایل patcher.py سفارشی ما
        custom_patcher = 'patcher.py'
        
        if os.path.exists(custom_patcher):
            # پیدا کردن مسیر نصب undetected_chromedriver
            site_packages = site.getsitepackages()[0]
            destination = os.path.join(site_packages, 'undetected_chromedriver', 'patcher.py')
            
            # ساخت نسخه پشتیبان
            if os.path.exists(destination):
                backup = destination + '.bak'
                shutil.copy2(destination, backup)
                print(f"نسخه پشتیبان در {backup} ذخیره شد")
            
            # کپی فایل سفارشی
            shutil.copy2(custom_patcher, destination)
            print(f"فایل patcher.py سفارشی با موفقیت به {destination} کپی شد")
            return True
        else:
            print("فایل patcher.py سفارشی پیدا نشد")
    
    except Exception as e:
        print(f"خطا در کپی فایل سفارشی: {str(e)}")
    
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