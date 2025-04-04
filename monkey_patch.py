"""
این اسکریپت برای پچ کردن ماژول distutils در محیط‌های بدون این ماژول (مانند Python 3.12) استفاده می‌شود.
این اسکریپت باید قبل از هر import دیگری اجرا شود یا به عنوان ماژول در ابتدای برنامه import شود.
"""

import sys
import logging
from types import ModuleType
from importlib import import_module

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def monkey_patch_distutils():
    """
    اضافه کردن یک ماژول distutils مجازی به sys.modules برای جلوگیری از خطای ImportError.
    این روش مخصوصاً برای patcher.py در undetected-chromedriver مفید است.
    """
    # همیشه ماژول‌ها را بازنویسی کنیم (حتی اگر قبلاً بارگذاری شده باشند)
    if "distutils" in sys.modules:
        # حذف ماژول قبلی
        del sys.modules["distutils"]
        if "distutils.version" in sys.modules:
            del sys.modules["distutils.version"]
        logger.info("ماژول‌های distutils قبلی حذف شدند و بازسازی می‌شوند.")
    
    logger.info("در حال پچ کردن ماژول distutils...")
    
    # سعی در نصب و import کردن packaging
    try:
        # ابتدا مطمئن شویم که packaging نصب شده است
        import packaging.version
        logger.info("ماژول packaging با موفقیت import شد.")
    except ImportError:
        logger.warning("ماژول packaging نصب نشده است. در حال نصب...")
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "packaging"])
            import packaging.version
            logger.info("ماژول packaging با موفقیت نصب و import شد.")
        except Exception as e:
            logger.error(f"خطا در نصب packaging: {e}")
            return False
    
    # ایجاد ماژول‌های مجازی
    try:
        # ایجاد ماژول distutils
        distutils_module = ModuleType("distutils")
        sys.modules["distutils"] = distutils_module
        
        # ایجاد زیرماژول distutils.version
        version_module = ModuleType("distutils.version")
        sys.modules["distutils.version"] = version_module
        distutils_module.version = version_module
        
        # تعریف LooseVersion با استفاده از packaging.version.parse
        from packaging.version import parse
        
        class LooseVersion:
            """
            پیاده‌سازی مجازی LooseVersion با استفاده از packaging.version.parse
            این کلاس API مشابه distutils.version.LooseVersion را شبیه‌سازی می‌کند.
            """
            def __init__(self, vstring):
                self.vstring = vstring
                self._parse = parse(vstring)
                self.version = self._get_version_tuple()
            
            def _get_version_tuple(self):
                """تبدیل نسخه به tuple برای برطرف کردن مشکل version"""
                try:
                    # تلاش برای استخراج اجزای نسخه
                    version_parts = self.vstring.split('.')
                    # تبدیل اجزا به عدد در صورت امکان
                    version_parts = [int(part) if part.isdigit() else part for part in version_parts]
                    return version_parts
                except:
                    return [0]  # مقدار پیش‌فرض در صورت خطا
                
            def __str__(self):
                return self.vstring
            
            def __repr__(self):
                return f"LooseVersion('{self.vstring}')"
        
        # اضافه کردن LooseVersion به ماژول version
        version_module.LooseVersion = LooseVersion
        
        logger.info("ماژول‌های مجازی distutils و distutils.version با موفقیت ایجاد شدند.")
        return True
    
    except Exception as e:
        logger.error(f"خطا در پچ کردن distutils: {e}")
        return False

# اجرای پچ در زمان import شدن ماژول
monkey_patch_distutils()

# برای اجرای مستقیم
if __name__ == "__main__":
    success = monkey_patch_distutils()
    if success:
        print("پچ distutils با موفقیت اجرا شد!")
    else:
        print("پچ distutils با خطا مواجه شد.")