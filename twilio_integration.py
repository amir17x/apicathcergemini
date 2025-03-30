#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول یکپارچه‌سازی Twilio برای دریافت و استفاده از شماره‌های تلفن موقت.
این ماژول برای دریافت کدهای تایید پیامکی در فرآیند ثبت‌نام خودکار حساب Google استفاده می‌شود.

این ماژول شامل قابلیت‌های زیر است:
- مدیریت شماره‌های تلفن Twilio (استفاده از شماره موجود یا خرید شماره جدید)
- انتظار هوشمند برای دریافت پیامک‌های حاوی کد تأیید
- تشخیص خودکار الگوهای مختلف کد تأیید در پیام‌های دریافتی
- مدیریت خطاها و تلاش مجدد در صورت شکست عملیات
- آزادسازی منابع پس از استفاده
"""

import os
import re
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple, Optional, Union, List, Dict, Any, Callable, TypeVar

# برای حل مشکل LSP در Callable
T = TypeVar('T')

# تنظیم لاگینگ
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("کتابخانه twilio نصب نشده است. برخی قابلیت‌ها غیرفعال می‌شوند.")

class TwilioManager:
    """مدیریت عملیات مرتبط با Twilio برای دریافت شماره تلفن موقت و پیام‌های SMS."""
    
    def __init__(self, account_sid: Optional[str] = None, auth_token: Optional[str] = None):
        """
        مقداردهی اولیه مدیر Twilio.
        
        Args:
            account_sid: شناسه حساب Twilio (اختیاری، به طور پیش‌فرض از متغیرهای محیطی خوانده می‌شود)
            auth_token: توکن احراز هویت Twilio (اختیاری، به طور پیش‌فرض از متغیرهای محیطی خوانده می‌شود)
        """
        self.available = False
        
        if not TWILIO_AVAILABLE:
            logger.warning("کتابخانه twilio در دسترس نیست. TwilioManager غیرفعال خواهد بود.")
            return
        
        # دریافت اطلاعات اعتبارسنجی از پارامترها یا متغیرهای محیطی
        self.account_sid = account_sid or os.environ.get('TWILIO_ACCOUNT_SID')
        self.auth_token = auth_token or os.environ.get('TWILIO_AUTH_TOKEN')
        
        # بررسی وجود اطلاعات اعتبارسنجی
        if not self.account_sid or not self.auth_token:
            logger.warning("اطلاعات اعتبارسنجی Twilio در دسترس نیست. TWILIO_ACCOUNT_SID و TWILIO_AUTH_TOKEN نیاز است.")
            return
        
        try:
            # ایجاد کلاینت Twilio
            self.client = Client(self.account_sid, self.auth_token)
            self.available = True
            logger.info("TwilioManager با موفقیت مقداردهی شد.")
        except Exception as e:
            logger.error(f"خطا در مقداردهی TwilioManager: {e}")
    
    def get_phone_number(self, country_code: str = "US") -> Tuple[bool, Union[str, None], str]:
        """
        دریافت یک شماره تلفن موقت برای استفاده در ثبت‌نام.
        
        Args:
            country_code: کد کشور برای دریافت شماره تلفن (پیش‌فرض: "US")
            
        Returns:
            Tuple[bool, Union[str, None], str]: وضعیت موفقیت، شماره تلفن (یا None در صورت شکست) و پیام
        """
        if not self.available:
            return False, None, "TwilioManager در دسترس نیست."
        
        try:
            # جستجو برای شماره‌های تلفن موجود
            available_numbers = self.client.available_phone_numbers(country_code).local.list(limit=1)
            
            if not available_numbers:
                return False, None, f"هیچ شماره تلفنی در کشور {country_code} یافت نشد."
            
            # خرید شماره تلفن
            phone_number = self.client.incoming_phone_numbers.create(
                phone_number=available_numbers[0].phone_number
            )
            
            logger.info(f"شماره تلفن جدید خریداری شد: {phone_number.phone_number}")
            return True, phone_number.phone_number, "شماره تلفن با موفقیت دریافت شد."
            
        except TwilioRestException as e:
            logger.error(f"خطای Twilio در دریافت شماره تلفن: {e}")
            return False, None, f"خطای Twilio: {e.msg}"
        except Exception as e:
            logger.error(f"خطای عمومی در دریافت شماره تلفن: {e}")
            return False, None, f"خطا: {str(e)}"
    
    def wait_for_sms(self, phone_number: str, timeout: int = 60, interval: int = 5) -> Tuple[bool, Union[str, None], str]:
        """
        منتظر دریافت پیام SMS برای یک شماره تلفن مشخص.
        
        Args:
            phone_number: شماره تلفنی که منتظر دریافت پیام برای آن هستیم
            timeout: حداکثر زمان انتظار به ثانیه (پیش‌فرض: 60)
            interval: فاصله زمانی بین بررسی‌های متوالی به ثانیه (پیش‌فرض: 5)
            
        Returns:
            Tuple[bool, Union[str, None], str]: وضعیت موفقیت، کد تأیید استخراج شده (یا None در صورت شکست) و پیام
        """
        if not self.available:
            return False, None, "TwilioManager در دسترس نیست."
        
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                # دریافت پیام‌های اخیر
                messages = self.client.messages.list(to=phone_number, limit=10)
                
                if messages:
                    for message in messages:
                        body = message.body
                        logger.info(f"پیام دریافت شد: {body}")
                        
                        # جستجو برای کد تأیید (معمولاً یک عدد 6 رقمی)
                        verification_code = self._extract_verification_code(body)
                        if verification_code:
                            logger.info(f"کد تأیید یافت شد: {verification_code}")
                            return True, verification_code, "کد تأیید با موفقیت دریافت شد."
                
                # انتظار برای بررسی مجدد
                logger.info(f"در انتظار دریافت پیام SMS... ({int(time.time() - start_time)} ثانیه گذشته)")
                time.sleep(interval)
            
            return False, None, f"زمان انتظار برای دریافت پیام SMS به پایان رسید (بیشتر از {timeout} ثانیه)."
            
        except TwilioRestException as e:
            logger.error(f"خطای Twilio در دریافت پیام SMS: {e}")
            return False, None, f"خطای Twilio: {e.msg}"
        except Exception as e:
            logger.error(f"خطای عمومی در دریافت پیام SMS: {e}")
            return False, None, f"خطا: {str(e)}"
    
    def _extract_verification_code(self, text: str) -> Optional[str]:
        """
        استخراج کد تأیید از متن پیام.
        
        Args:
            text: متن پیام دریافت شده
            
        Returns:
            Optional[str]: کد تأیید استخراج شده یا None اگر کدی یافت نشد
        """
        # الگوهای مختلف برای کدهای تأیید
        patterns = [
            r'(\d{6})',  # 6 رقم پشت سر هم
            r'code[^\d]*(\d{6})',  # کلمه "code" و سپس 6 رقم
            r'verification[^\d]*(\d{6})',  # کلمه "verification" و سپس 6 رقم
            r'verify[^\d]*(\d{6})',  # کلمه "verify" و سپس 6 رقم
            r'G-(\d{6})'  # الگوی خاص Google: G- و سپس 6 رقم
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def release_phone_number(self, phone_number: str) -> Tuple[bool, str]:
        """
        آزادسازی (حذف) یک شماره تلفن خریداری شده.
        
        Args:
            phone_number: شماره تلفنی که می‌خواهیم آزاد کنیم
            
        Returns:
            Tuple[bool, str]: وضعیت موفقیت و پیام
        """
        if not self.available:
            return False, "TwilioManager در دسترس نیست."
        
        try:
            # یافتن شماره تلفن در حساب
            incoming_numbers = self.client.incoming_phone_numbers.list(phone_number=phone_number)
            
            if not incoming_numbers:
                logger.warning(f"شماره تلفن {phone_number} در حساب یافت نشد.")
                return False, "شماره تلفن در حساب یافت نشد."
            
            # حذف شماره تلفن
            for number in incoming_numbers:
                number.delete()
                logger.info(f"شماره تلفن {phone_number} با موفقیت حذف شد.")
            
            return True, "شماره تلفن با موفقیت آزاد شد."
            
        except TwilioRestException as e:
            logger.error(f"خطای Twilio در آزادسازی شماره تلفن: {e}")
            return False, f"خطای Twilio: {e.msg}"
        except Exception as e:
            logger.error(f"خطای عمومی در آزادسازی شماره تلفن: {e}")
            return False, f"خطا: {str(e)}"
    
    def get_account_balance(self) -> Tuple[bool, Union[float, None], str]:
        """
        دریافت موجودی حساب Twilio.
        
        Returns:
            Tuple[bool, Union[float, None], str]: وضعیت موفقیت، موجودی حساب (یا None در صورت شکست) و پیام
        """
        if not self.available:
            return False, None, "TwilioManager در دسترس نیست."
        
        try:
            # دریافت اطلاعات حساب
            account = self.client.api.accounts(self.account_sid).fetch()
            balance = float(account.balance)
            
            logger.info(f"موجودی حساب Twilio: {balance}")
            return True, balance, f"موجودی حساب: {balance}"
            
        except TwilioRestException as e:
            logger.error(f"خطای Twilio در دریافت موجودی حساب: {e}")
            return False, None, f"خطای Twilio: {e.msg}"
        except Exception as e:
            logger.error(f"خطای عمومی در دریافت موجودی حساب: {e}")
            return False, None, f"خطا: {str(e)}"


class PhoneVerificationService:
    """
    سرویس تأیید شماره تلفن با استفاده از Twilio.
    این کلاس یک رابط ساده و کارآمد برای عملیات مرتبط با تأیید شماره تلفن فراهم می‌کند.
    """
    
    def __init__(self):
        """مقداردهی اولیه سرویس تأیید شماره تلفن."""
        self.twilio_manager = TwilioManager()
        self.default_phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
        self.is_available = self.twilio_manager.available
        
        if self.default_phone_number:
            logger.info(f"شماره تلفن پیش‌فرض Twilio پیکربندی شده است: {self.default_phone_number}")
        else:
            logger.warning("شماره تلفن پیش‌فرض Twilio پیکربندی نشده است. از متغیر محیطی TWILIO_PHONE_NUMBER استفاده کنید.")
        
    def get_verification_phone_number(self, country_code: str = "US") -> Tuple[bool, Optional[str], str]:
        """
        دریافت یک شماره تلفن برای استفاده در فرآیند تأیید.
        اگر شماره پیش‌فرض تنظیم شده باشد، از آن استفاده می‌کند؛ در غیر این صورت یک شماره جدید خریداری می‌کند.
        
        Args:
            country_code: کد کشور برای خرید شماره تلفن جدید (در صورت نیاز)
            
        Returns:
            Tuple[bool, Optional[str], str]: وضعیت موفقیت، شماره تلفن و پیام
        """
        if not self.is_available:
            return False, None, "سرویس تأیید شماره تلفن در دسترس نیست."
        
        # استفاده از شماره تلفن پیش‌فرض اگر موجود باشد
        if self.default_phone_number:
            logger.info(f"استفاده از شماره تلفن پیش‌فرض: {self.default_phone_number}")
            return True, self.default_phone_number, "استفاده از شماره تلفن پیش‌فرض."
        
        # خرید شماره تلفن جدید
        logger.info("شماره تلفن پیش‌فرض موجود نیست. در حال خرید شماره جدید...")
        return self.twilio_manager.get_phone_number(country_code)
    
    def wait_for_verification_code(self, phone_number: str, timeout: int = 60, interval: int = 5, 
                               retry_count: int = 3) -> Tuple[bool, Optional[str], str]:
        """
        انتظار برای دریافت کد تأیید با تلاش‌های مجدد خودکار.
        
        Args:
            phone_number: شماره تلفنی که منتظر دریافت کد تأیید برای آن هستیم
            timeout: حداکثر زمان انتظار به ثانیه برای هر تلاش
            interval: فاصله زمانی بین بررسی‌های متوالی به ثانیه
            retry_count: تعداد تلاش‌های مجدد در صورت شکست
            
        Returns:
            Tuple[bool, Optional[str], str]: وضعیت موفقیت، کد تأیید و پیام
        """
        if not self.is_available:
            return False, None, "سرویس تأیید شماره تلفن در دسترس نیست."
        
        for attempt in range(retry_count):
            logger.info(f"تلاش {attempt + 1}/{retry_count} برای دریافت کد تأیید...")
            success, code, message = self.twilio_manager.wait_for_sms(phone_number, timeout, interval)
            
            if success and code:
                return True, code, message
            
            if attempt < retry_count - 1:
                logger.warning(f"تلاش ناموفق: {message}. در حال تلاش مجدد...")
                time.sleep(interval)  # انتظار کوتاه قبل از تلاش مجدد
        
        return False, None, f"پس از {retry_count} تلاش، کد تأیید دریافت نشد."
    
    def cleanup_phone_number(self, phone_number: str) -> None:
        """
        پاکسازی و آزادسازی منابع مرتبط با شماره تلفن.
        اگر از شماره پیش‌فرض استفاده شده باشد، آن را آزاد نمی‌کند.
        
        Args:
            phone_number: شماره تلفنی که می‌خواهیم منابع آن را پاکسازی کنیم
        """
        if not self.is_available:
            logger.warning("سرویس تأیید شماره تلفن در دسترس نیست. پاکسازی انجام نشد.")
            return
        
        # اگر شماره تلفن، شماره پیش‌فرض است، آن را آزاد نکن
        if phone_number == self.default_phone_number:
            logger.info(f"شماره تلفن {phone_number} شماره پیش‌فرض است و آزاد نمی‌شود.")
            return
        
        # آزادسازی شماره تلفن خریداری شده
        success, message = self.twilio_manager.release_phone_number(phone_number)
        if success:
            logger.info(f"شماره تلفن {phone_number} با موفقیت آزاد شد.")
        else:
            logger.warning(f"خطا در آزادسازی شماره تلفن {phone_number}: {message}")
    
    def verify_phone_number_with_callback(self, phone_number: str, 
                                     submit_callback: Callable[[], Any], 
                                     code_entry_callback: Callable[[str], Any],
                                     timeout: int = 60) -> Tuple[bool, str]:
        """
        تأیید شماره تلفن با استفاده از callbacks برای ثبت شماره و ورود کد.
        
        Args:
            phone_number: شماره تلفنی که می‌خواهیم تأیید کنیم
            submit_callback: تابعی که برای ارسال فرم شماره تلفن فراخوانی می‌شود
            code_entry_callback: تابعی که برای وارد کردن کد تأیید فراخوانی می‌شود
            timeout: حداکثر زمان انتظار به ثانیه
            
        Returns:
            Tuple[bool, str]: وضعیت موفقیت و پیام
        """
        if not self.is_available:
            return False, "سرویس تأیید شماره تلفن در دسترس نیست."
        
        try:
            # ارسال فرم شماره تلفن
            submit_callback()
            logger.info("فرم شماره تلفن ارسال شد. در انتظار دریافت کد تأیید...")
            
            # انتظار برای دریافت کد تأیید
            success, code, message = self.wait_for_verification_code(phone_number, timeout)
            if not success or not code:
                return False, f"خطا در دریافت کد تأیید: {message}"
            
            # وارد کردن کد تأیید
            code_entry_callback(code)
            logger.info("کد تأیید وارد شد.")
            
            return True, "تأیید شماره تلفن با موفقیت انجام شد."
            
        except Exception as e:
            logger.error(f"خطا در فرآیند تأیید شماره تلفن: {e}")
            return False, f"خطا: {str(e)}"


def is_twilio_available() -> bool:
    """
    بررسی در دسترس بودن Twilio.
    
    Returns:
        bool: True اگر Twilio در دسترس باشد، False در غیر این صورت
    """
    if not TWILIO_AVAILABLE:
        return False
        
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token:
        return False
    
    try:
        client = Client(account_sid, auth_token)
        client.api.accounts(account_sid).fetch()
        return True
    except:
        return False


# برای تست مستقیم
if __name__ == "__main__":
    print(f"Twilio کتابخانه نصب شده: {TWILIO_AVAILABLE}")
    print(f"Twilio در دسترس: {is_twilio_available()}")
    
    if is_twilio_available():
        manager = TwilioManager()
        balance_success, balance, message = manager.get_account_balance()
        print(f"موجودی: {balance} ({message})")
        
        # تست سرویس تأیید شماره تلفن
        service = PhoneVerificationService()
        if service.is_available:
            print(f"شماره تلفن پیش‌فرض: {service.default_phone_number}")
            success, phone, message = service.get_verification_phone_number()
            print(f"شماره تلفن: {phone} ({message})")
            
            if success and phone:
                print("این یک تست است. سرویس در حال اجرا و فعال است.")