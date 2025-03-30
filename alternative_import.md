# راهنمای جایگزینی import distutils

در پایتون 3.12، ماژول `distutils` به عنوان یک ماژول مستقل حذف شده و فقط از طریق `setuptools` در دسترس است.
برای حل این مشکل، می‌توانید از یکی از راه‌حل‌های زیر استفاده کنید:

## ۱. تغییر فایل patcher.py در کتابخانه undetected-chromedriver

در فایل patcher.py در مسیر نصب کتابخانه undetected-chromedriver (معمولاً در site-packages)، خط زیر را:

```python
from distutils.version import LooseVersion
```

به یکی از این حالات تغییر دهید:

```python
# گزینه ۱: استفاده از packaging (توصیه شده)
from packaging.version import parse as LooseVersion

# گزینه ۲: استفاده از setuptools 
from setuptools.distutils.version import LooseVersion

# گزینه ۳: import با خطاگیری
try:
    from distutils.version import LooseVersion
except ImportError:
    from packaging.version import parse as LooseVersion
```

## ۲. ایجاد یک ماژول مجازی distutils

می‌توانید یک پکیج مجازی distutils ایجاد کنید که version.py را شامل شود:

```
mkdir -p distutils
touch distutils/__init__.py
```

سپس در فایل `distutils/version.py` بنویسید:

```python
from packaging.version import parse as LooseVersion
```

سپس `PYTHONPATH` را به گونه‌ای تنظیم کنید که این پوشه در مسیر پایتون قرار گیرد.

## ۳. نصب setuptools قبل از اجرای اسکریپت

```bash
pip install setuptools
```

## ۴. استفاده از نسخه قدیمی‌تر پایتون 

در Railway می‌توانید از پایتون 3.10 یا 3.11 استفاده کنید که هنوز از distutils پشتیبانی می‌کنند:

```toml
[nixpacks]
python = { version = "3.10" }
```

## ۵. پچ کردن sys.modules

این روش پیشرفته‌تر است و قبل از import کردن undetected-chromedriver، یک ماژول distutils مجازی در sys.modules تزریق می‌کند:

```python
import sys
from types import ModuleType

# ایجاد ماژول‌های مجازی
distutils_module = ModuleType("distutils")
version_module = ModuleType("distutils.version")
sys.modules["distutils"] = distutils_module
sys.modules["distutils.version"] = version_module

# پیاده‌سازی LooseVersion
from packaging.version import parse

class LooseVersion(parse):
    pass

# اضافه کردن به ماژول version
version_module.LooseVersion = LooseVersion

# حالا undetected_chromedriver را import کنید
import undetected_chromedriver as uc
```