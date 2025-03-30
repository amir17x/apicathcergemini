#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول یکپارچه‌سازی Twilio برای دریافت و استفاده از شماره‌های تلفن موقت.
این ماژول برای دریافت کدهای تایید پیامکی در فرآیند ثبت‌نام خودکار حساب Google استفاده می‌شود.
"""

import os
import re
import time
import logging
from typing import Tuple, Optional, Union, List, Dict, Any

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