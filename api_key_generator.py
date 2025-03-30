#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول دریافت API Key از Google Gemini.
این ماژول برای اتوماسیون فرآیند ورود به Google AI Studio و دریافت API Key استفاده می‌شود.
با پشتیبانی از حل خودکار CAPTCHA به روش‌های مختلف.
"""

import logging
import time
import os
import re
import random
import traceback
import json
import subprocess
import sys
from typing import Dict, Optional, Tuple, Union, Any, List

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

# استفاده از ماژول آماده‌سازی کروم برای رفع خودکار مشکلات
try:
    from prepare_chrome import prepare_chrome_driver
    PREPARE_CHROME_AVAILABLE = True
except ImportError:
    PREPARE_CHROME_AVAILABLE = False
    # روش قدیمی - فقط در صورتی که ماژول جدید در دسترس نباشد
    try:
        from monkey_patch import monkey_patch_distutils
        monkey_patch_distutils()
    except ImportError:
        logging.warning("ماژول monkey_patch پیدا نشد. ممکن است با خطا مواجه شوید.")

# حالا undetected_chromedriver را import کنیم
import undetected_chromedriver as uc

# تابع اختصاصی برای رفع مشکل 'Version' object has no attribute 'version'
def create_uc_driver_with_version_fix(options):
    """
    ایجاد یک نمونه از درایور undetected_chromedriver با رفع مشکل نسخه.
    این تابع مشکل 'Version' object has no attribute 'version' را رفع می‌کند.
    
    Args:
        options: تنظیمات مربوط به ChromeOptions
        
    Returns:
        uc.Chrome: یک نمونه از درایور Chrome
    """
    if PREPARE_CHROME_AVAILABLE:
        # استفاده از ماژول آماده‌سازی جدید
        return prepare_chrome_driver(
            headless=options._arguments.count("--headless") > 0,
            proxy=None  # پروکسی قبلاً در options تنظیم شده است
        )
    
    logging.info("Using version fix for undetected_chromedriver...")
    
    # ساخت یک نمونه از patcher بدون استفاده از auto()
    try:
        # ایجاد پچر بدون فراخوانی auto
        chrome_instance = uc.Chrome(options=options, enable_cdp_events=True, headless=options._arguments.count("--headless") > 0, use_subprocess=True)
        logging.info("Successfully created ChromeDriver with version fix!")
        return chrome_instance
    except Exception as e:
        logging.error(f"Failed to create driver with version fix: {e}")
        
        # روش جایگزین با استفاده از monkey patching پچر
        try:
            # دسترسی به پچر و تنظیم دستی version_main
            uc_patcher = uc.patcher.Patcher()
            # تنظیم دستی نسخه
            uc_patcher.version_main = 123  # مقدار دلخواه
            # ساخت دستی مسیر درایور
            chrome_instance = uc.Chrome(options=options, patcher=uc_patcher)
            logging.info("Successfully created ChromeDriver with manual patcher!")
            return chrome_instance
        except Exception as sub_e:
            logging.error(f"Failed with manual patcher too: {sub_e}")
            raise RuntimeError("Could not initialize ChromeDriver with any method") from sub_e

# ایمپورت ماژول حل CAPTCHA
try:
    from captcha_solver import CaptchaSolver
    CAPTCHA_SOLVER_AVAILABLE = True
except ImportError:
    CAPTCHA_SOLVER_AVAILABLE = False

# تنظیم لاگینگ
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# وارد کردن ماژول‌های داخلی برنامه
try:
    from twilio_integration import TwilioManager
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("ماژول twilio_integration در دسترس نیست. قابلیت تأیید خودکار شماره تلفن غیرفعال خواهد بود.")

try:
    from gemini_api_validator import GeminiAPIValidator
    API_VALIDATOR_AVAILABLE = True
except ImportError:
    API_VALIDATOR_AVAILABLE = False
    logger.warning("ماژول gemini_api_validator در دسترس نیست. قابلیت تست اعتبار API Key غیرفعال خواهد بود.")

def validate_api_key(api_key: str) -> Dict[str, Any]:
    """
    بررسی اعتبار یک API Key و تست عملکرد آن.
    
    Args:
        api_key: کلید API که می‌خواهیم اعتبار آن را بررسی کنیم
        
    Returns:
        Dict[str, Any]: نتیجه بررسی اعتبار
    """
    if not API_VALIDATOR_AVAILABLE:
        logger.warning("ماژول gemini_api_validator در دسترس نیست. بررسی اعتبار انجام نمی‌شود.")
        return {
            'validation_performed': False,
            'message': 'ماژول gemini_api_validator در دسترس نیست.'
        }
    
    try:
        validator = GeminiAPIValidator()
        validator_result = validator.get_api_key_details(api_key)
        
        logger.info(f"نتیجه بررسی اعتبار API Key: معتبر = {validator_result.get('is_valid', False)}")
        
        return {
            'validation_performed': True,
            'is_valid': validator_result.get('is_valid', False),
            'is_working': validator_result.get('is_working', False),
            'details': validator_result
        }
    except Exception as e:
        logger.error(f"خطا در بررسی اعتبار API Key: {e}")
        return {
            'validation_performed': True,
            'is_valid': False,
            'error': str(e)
        }

def handle_phone_verification(driver: uc.Chrome, wait: WebDriverWait) -> Tuple[bool, str]:
    """
    مدیریت تأیید شماره تلفن در فرآیند ثبت‌نام یا ورود به حساب گوگل.
    این نسخه بهبودیافته از سرویس PhoneVerificationService برای مدیریت بهینه تأیید شماره استفاده می‌کند.
    
    Args:
        driver: نمونه درایور Selenium
        wait: شیء WebDriverWait برای انتظار
        
    Returns:
        Tuple[bool, str]: نتیجه تأیید (موفقیت یا شکست) و پیام
    """
    if not TWILIO_AVAILABLE:
        logger.warning("ماژول twilio_integration در دسترس نیست. تأیید خودکار شماره تلفن امکان‌پذیر نیست.")
        return False, "ماژول twilio_integration در دسترس نیست."
    
    try:
        # ایجاد سرویس تأیید شماره تلفن
        from twilio_integration import PhoneVerificationService
        phone_service = PhoneVerificationService()
        
        if not phone_service.is_available:
            return False, "سرویس تأیید شماره تلفن در دسترس نیست."
        
        # دریافت شماره تلفن (استفاده از شماره پیش‌فرض یا خرید شماره جدید)
        success, phone_number, message = phone_service.get_verification_phone_number("US")
        if not success or not phone_number:
            return False, f"خطا در دریافت شماره تلفن: {message}"
            
        logger.info(f"شماره تلفن برای تأیید دریافت شد: {phone_number}")
        
        # بررسی وجود فرم ورود شماره تلفن
        phone_field = None
        try:
            # تلاش برای یافتن فیلد شماره تلفن با استراتژی‌های مختلف
            for selector in [
                (By.ID, "phoneNumberId"),
                (By.XPATH, "//input[contains(@id, 'phone')]"),
                (By.XPATH, "//input[contains(@name, 'phone')]"),
                (By.XPATH, "//div[contains(text(), 'Phone')]/following::input[1]")
            ]:
                try:
                    phone_field = wait.until(EC.presence_of_element_located(selector))
                    if phone_field:
                        break
                except:
                    continue
                    
            if not phone_field:
                # پاکسازی منابع در صورت نیاز
                phone_service.cleanup_phone_number(phone_number)
                return False, "فیلد شماره تلفن یافت نشد."
                
            # وارد کردن شماره تلفن در فرم
            phone_field.clear()
            phone_field.send_keys(phone_number)
            time.sleep(1)
            
            # تعریف تابع callback برای ارسال فرم شماره تلفن
            def submit_phone_form():
                # کلیک روی دکمه ارسال کد با استراتژی‌های مختلف
                for button_selector in [
                    (By.XPATH, "//span[text()='Next']/parent::button"),
                    (By.XPATH, "//span[text()='Send']/parent::button"),
                    (By.XPATH, "//button[contains(@type, 'submit')]"),
                    (By.XPATH, "//input[contains(@type, 'submit')]")
                ]:
                    try:
                        button = wait.until(EC.element_to_be_clickable(button_selector))
                        if button:
                            button.click()
                            logger.info("دکمه ارسال کد تأیید کلیک شد.")
                            return True
                    except:
                        continue
                
                raise Exception("دکمه ارسال کد تأیید یافت نشد.")
            
            # تعریف تابع callback برای وارد کردن کد تأیید
            def enter_verification_code(code):
                # یافتن فیلد ورود کد تأیید
                code_field = None
                for code_selector in [
                    (By.ID, "code"),
                    (By.XPATH, "//input[contains(@id, 'code')]"),
                    (By.XPATH, "//input[contains(@id, 'verification')]"),
                    (By.XPATH, "//div[contains(text(), 'verification')]/following::input[1]")
                ]:
                    try:
                        code_field = wait.until(EC.presence_of_element_located(code_selector))
                        if code_field:
                            break
                    except:
                        continue
                
                if not code_field:
                    raise Exception("فیلد ورود کد تأیید یافت نشد.")
                
                # وارد کردن کد تأیید
                code_field.clear()
                code_field.send_keys(code)
                time.sleep(1)
                
                # کلیک روی دکمه تأیید
                for verify_selector in [
                    (By.XPATH, "//span[text()='Verify']/parent::button"),
                    (By.XPATH, "//button[contains(@type, 'submit')]"),
                    (By.XPATH, "//input[contains(@type, 'submit')]")
                ]:
                    try:
                        verify_button = wait.until(EC.element_to_be_clickable(verify_selector))
                        if verify_button:
                            verify_button.click()
                            logger.info("دکمه تأیید کد کلیک شد.")
                            return True
                    except:
                        continue
                
                raise Exception("دکمه تأیید کد یافت نشد.")
            
            # استفاده از سرویس تأیید شماره با callback‌های تعریف شده
            success, message = phone_service.verify_phone_number_with_callback(
                phone_number=phone_number,
                submit_callback=submit_phone_form,
                code_entry_callback=enter_verification_code,
                timeout=90  # زمان بیشتر برای اطمینان
            )
            
            # پاکسازی منابع
            phone_service.cleanup_phone_number(phone_number)
            
            # بررسی موفقیت‌آمیز بودن تأیید شماره تلفن
            if success:
                # تأیید اضافی با بررسی محتوای صفحه
                time.sleep(5)  # انتظار برای بارگذاری صفحه بعدی
                if ("verification successful" in driver.page_source.lower() or 
                    "verify" not in driver.page_source.lower() or
                    "continue" in driver.page_source.lower()):
                    return True, "تأیید شماره تلفن با موفقیت انجام شد."
                else:
                    # ممکن است تأیید موفق بوده ولی صفحه آن را منعکس نکرده باشد
                    logger.warning("تأیید انجام شد اما تغییری در صفحه مشاهده نشد.")
                    return True, "تأیید شماره تلفن انجام شد."
            else:
                return False, f"خطا در تأیید شماره تلفن: {message}"
                
        except Exception as e:
            logger.error(f"خطا در یافتن فیلد شماره تلفن: {e}")
            # پاکسازی منابع
            phone_service.cleanup_phone_number(phone_number)
            return False, f"خطا در یافتن فیلد شماره تلفن: {str(e)}"
            
    except Exception as e:
        logger.error(f"خطا در فرآیند تأیید شماره تلفن: {e}")
        return False, f"خطا در فرآیند تأیید شماره تلفن: {str(e)}"

def generate_api_key(gmail, password, proxy=None, test_key=True, telegram_chat_id=None):
    """
    دریافت کلید API از Google Gemini با استفاده از اتوماسیون Selenium.
    
    Args:
        gmail: آدرس ایمیل Gmail برای ورود
        password: رمز عبور حساب Gmail
        proxy: تنظیمات پروکسی (اختیاری)
        test_key: آیا اعتبار API Key پس از دریافت بررسی شود؟ (پیش‌فرض: True)
        telegram_chat_id: شناسه چت تلگرام برای ارسال CAPTCHA (اختیاری)
        
    Returns:
        dict: یک دیکشنری با وضعیت موفقیت و کلید API یا اطلاعات خطا
    """
    logger.info(f"Starting API key generation for {gmail}")
    
    driver = None
    try:
        # Setup Chrome options
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--lang=en-US")
        options.add_argument("--headless")  # بسیار مهم برای اجرا در محیط Replit
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
        
        # Configure proxy if provided
        if proxy:
            logger.info(f"Using proxy: {proxy}")
            if isinstance(proxy, dict):
                proxy_string = f"{proxy.get('protocol', 'http')}://{proxy.get('host')}:{proxy.get('port')}"
                if proxy.get('username') and proxy.get('password'):
                    auth = f"{proxy['username']}:{proxy['password']}"
                    options.add_argument(f'--proxy-server={proxy_string}')
                    # Add proxy authentication if needed
                else:
                    options.add_argument(f'--proxy-server={proxy_string}')
            else:
                # Assuming proxy is a string in format protocol://host:port
                options.add_argument(f'--proxy-server={proxy}')
        
        # Initialize the driver with our custom ChromeDriver
        logger.info("Initializing undetected-chromedriver with custom ChromeDriver...")
        
        # تلاش برای ایجاد driver با مدیریت خطاهای مختلف
        try:
            # روش اول: استفاده از نصب مستقیم درایور سفارشی
            chromedriver_path = os.path.expanduser("~/bin/chromedriver")
            if os.path.exists(chromedriver_path):
                logger.info(f"Using custom ChromeDriver from {chromedriver_path}")
                try:
                    driver = uc.Chrome(driver_executable_path=chromedriver_path, options=options)
                    logger.info("ChromeDriver successfully initialized with custom driver!")
                except Exception as e1:
                    logger.warning(f"Error using custom ChromeDriver: {e1}")
                    logger.info("Trying alternative method...")
                    
                    # روش دوم: استفاده از روش پیش‌فرض
                    try:
                        driver = uc.Chrome(options=options, use_subprocess=True)
                        logger.info("ChromeDriver successfully initialized with use_subprocess=True!")
                    except Exception as e2:
                        logger.warning(f"Error using default method with subprocess: {e2}")
                        
                        # روش سوم: استفاده از یک ویژگی خاص برای رفع مشکل نسخه
                        logger.info("Trying to fix version issue...")
                        # کدنویسی دستی تابع version_main برای حل مشکل
                        driver = create_uc_driver_with_version_fix(options)
            else:
                # ChromeDriver سفارشی پیدا نشد، استفاده از روش پیش‌فرض
                logger.info("Custom ChromeDriver not found, using default method")
                try:
                    driver = uc.Chrome(options=options, use_subprocess=True)
                    logger.info("ChromeDriver successfully initialized!")
                except Exception as e:
                    logger.warning(f"Error using default method: {e}")
                    # استفاده از روش سوم در صورت شکست
                    logger.info("Trying to fix version issue...")
                    driver = create_uc_driver_with_version_fix(options)
                    
        except Exception as e:
            # خطا در تمام روش‌ها
            logger.error(f"Failed to initialize ChromeDriver: {e}")
            raise
        
        # Set explicit wait
        wait = WebDriverWait(driver, 15)
        
        # Step 1: Navigate to Google AI Studio
        logger.info("Navigating to Google AI Studio...")
        driver.get("https://aistudio.google.com/")
        time.sleep(3)
        
        # Click on Sign In if not already signed in
        try:
            logger.info("Looking for Sign in button...")
            sign_in_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Sign in')]/parent::button")))
            logger.info("Clicking Sign in button...")
            sign_in_button.click()
            time.sleep(3)
        except TimeoutException:
            logger.info("No sign-in button found, user might already be signed in or page structure has changed")
        
        # Step 2: Enter Gmail
        try:
            logger.info("Entering Gmail address...")
            email_field = wait.until(EC.presence_of_element_located((By.ID, "identifierId")))
            email_field.clear()
            email_field.send_keys(gmail)
            time.sleep(1)
            
            # Click Next
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']/parent::button")))
            next_button.click()
            time.sleep(3)
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"Failed to enter Gmail address: {e}")
            return {
                'success': False,
                'error': 'Failed to enter Gmail address. Sign-in page structure may have changed.'
            }
        
        # Step 3: Enter Password
        try:
            logger.info("Entering password...")
            password_field = wait.until(EC.presence_of_element_located((By.NAME, "Passwd")))
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(1)
            
            # Click Next
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']/parent::button")))
            next_button.click()
            time.sleep(5)
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"Failed to enter password: {e}")
            return {
                'success': False,
                'error': 'Failed to enter password. Password page structure may have changed.'
            }
        
        # Check for verification required
        if "verify it's you" in driver.page_source.lower() or "2-step verification" in driver.page_source.lower():
            logger.warning("Verification required for sign-in")
            # Take screenshot for debugging
            screenshot_path = f"/tmp/verification_required_signin_{gmail.split('@')[0]}.png"
            driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
            
            # Check for CAPTCHA first
            if CAPTCHA_SOLVER_AVAILABLE:
                logger.info("Checking for CAPTCHA...")
                captcha_solver = CaptchaSolver(telegram_bot_token=os.environ.get('TELEGRAM_BOT_TOKEN'))
                has_captcha, captcha_type, captcha_info = captcha_solver.detect_captcha(driver)
                
                if has_captcha:
                    logger.info(f"CAPTCHA detected! Type: {captcha_type}")
                    
                    # First try to bypass CAPTCHA
                    bypass_success, bypass_message = captcha_solver.bypass_captcha(driver)
                    if bypass_success:
                        logger.info(f"Successfully bypassed CAPTCHA: {bypass_message}")
                        # Continue with the process
                        time.sleep(3)
                    else:
                        logger.info(f"Could not bypass CAPTCHA: {bypass_message}")
                        
                        # Try audio method for reCAPTCHA
                        if captcha_type == 'recaptcha':
                            audio_success, audio_message = captcha_solver.solve_recaptcha_audio(driver)
                            if audio_success:
                                logger.info(f"Successfully solved reCAPTCHA using audio method: {audio_message}")
                                # Continue with the process
                                time.sleep(3)
                            else:
                                logger.warning(f"Failed to solve reCAPTCHA using audio method: {audio_message}")
                                
                                # As last resort, try telegram-based CAPTCHA solving if chat_id is provided
                                if telegram_chat_id:
                                    logger.info(f"Attempting to solve CAPTCHA via Telegram with chat_id: {telegram_chat_id}")
                                    telegram_success, telegram_message = captcha_solver.solve_captcha_via_telegram(driver, telegram_chat_id)
                                    if telegram_success:
                                        logger.info(f"Successfully solved CAPTCHA via Telegram: {telegram_message}")
                                        time.sleep(3)
                                    else:
                                        logger.warning(f"Failed to solve CAPTCHA via Telegram: {telegram_message}")
                                        # Fall back to manual verification
                                else:
                                    logger.warning("No Telegram chat_id provided, can't use Telegram for CAPTCHA solving")
                                    # Fall back to manual verification
                
                # Check if we still have verification required after CAPTCHA solving
                if "verify it's you" in driver.page_source.lower() or "2-step verification" in driver.page_source.lower():
                    logger.warning("Still need verification after CAPTCHA check")
                    return {
                        'success': False,
                        'error': 'Additional verification required for sign-in. Manual intervention needed.'
                    }
            else:
                return {
                    'success': False,
                    'error': 'Additional verification required for sign-in. Manual intervention needed.'
                }
        
        # Step 4: Navigate to API key page
        logger.info("Navigating to API keys page...")
        try:
            # Wait to be redirected to AI Studio page
            time.sleep(5)
            
            # Check for CAPTCHA on the AI Studio page
            if CAPTCHA_SOLVER_AVAILABLE:
                logger.info("Checking for CAPTCHA on AI Studio page...")
                captcha_solver = CaptchaSolver(telegram_bot_token=os.environ.get('TELEGRAM_BOT_TOKEN'))
                has_captcha, captcha_type, captcha_info = captcha_solver.detect_captcha(driver)
                
                if has_captcha:
                    logger.info(f"CAPTCHA detected on AI Studio page! Type: {captcha_type}")
                    
                    # Try to bypass CAPTCHA
                    bypass_success, bypass_message = captcha_solver.bypass_captcha(driver)
                    if bypass_success:
                        logger.info(f"Successfully bypassed CAPTCHA: {bypass_message}")
                        time.sleep(3)
                    else:
                        logger.info(f"Could not bypass CAPTCHA: {bypass_message}")
                        
                        # Try audio method for reCAPTCHA
                        if captcha_type == 'recaptcha':
                            audio_success, audio_message = captcha_solver.solve_recaptcha_audio(driver)
                            if audio_success:
                                logger.info(f"Successfully solved reCAPTCHA using audio method: {audio_message}")
                                time.sleep(3)
                            else:
                                logger.warning(f"Failed to solve reCAPTCHA using audio method: {audio_message}")
                                
                                # As last resort, try telegram-based CAPTCHA solving if chat_id is provided
                                if telegram_chat_id:
                                    logger.info(f"Attempting to solve CAPTCHA via Telegram with chat_id: {telegram_chat_id}")
                                    telegram_success, telegram_message = captcha_solver.solve_captcha_via_telegram(driver, telegram_chat_id)
                                    if telegram_success:
                                        logger.info(f"Successfully solved CAPTCHA via Telegram: {telegram_message}")
                                        time.sleep(3)
                                    else:
                                        logger.warning(f"Failed to solve CAPTCHA via Telegram: {telegram_message}")
                                else:
                                    logger.warning("No Telegram chat_id provided, can't use Telegram for CAPTCHA solving")
                                # Continue anyway, may still work
            
            # Click on API keys tab
            api_keys_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'api-keys')]")))
            api_keys_link.click()
            time.sleep(3)
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"Failed to navigate to API keys page: {e}")
            
            # Check if user needs to agree to terms first
            if "agree" in driver.page_source.lower() or "terms" in driver.page_source.lower():
                try:
                    logger.info("Attempting to accept terms...")
                    agree_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Agree')]/parent::button")))
                    agree_button.click()
                    time.sleep(3)
                except:
                    logger.error("Failed to accept terms")
            
            return {
                'success': False,
                'error': 'Failed to navigate to API keys page. AI Studio interface may have changed.'
            }
        
        # Step 5: Create a new API key
        try:
            logger.info("Creating new API key...")
            create_key_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Create API key')]/parent::button")))
            create_key_button.click()
            time.sleep(3)
            
            # Sometimes there's a dialog to name the key
            try:
                logger.info("Checking for key name input...")
                key_name_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter API key name']")))
                key_name_input.clear()
                key_name_input.send_keys(f"Key for {gmail}")
                time.sleep(1)
                
                create_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Create')]/parent::button")))
                create_button.click()
                time.sleep(3)
            except:
                logger.info("No key name input found, proceeding...")
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"Failed to create API key: {e}")
            return {
                'success': False,
                'error': 'Failed to create API key. The button may not be available or the interface has changed.'
            }
        
        # Step 6: Copy the API key
        try:
            logger.info("Extracting API key...")
            # Look for the key display element or copy button
            api_key_text = None
            
            # Try to find displayed key
            try:
                api_key_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//input[contains(@aria-label, 'API key')]")))
                api_key_text = api_key_element.get_attribute("value")
            except:
                logger.info("Could not find API key input field, trying alternative methods...")
            
            # If we couldn't find the key directly, try using the copy button
            if not api_key_text:
                try:
                    copy_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Copy API key')]")))
                    copy_button.click()
                    time.sleep(1)
                    
                    # Use JavaScript to get clipboard data (this won't work in most cases due to security)
                    # We'll need to look for the key in another way
                    logger.info("Clicked copy button, trying to extract key from page...")
                    
                    # Take screenshot for debugging
                    screenshot_path = f"/tmp/api_key_page_{gmail.split('@')[0]}.png"
                    driver.save_screenshot(screenshot_path)
                    logger.info(f"Screenshot saved to {screenshot_path}")
                    
                    # Look for visible text that looks like an API key
                    page_source = driver.page_source
                    key_pattern = re.compile(r'AI[a-zA-Z0-9_\-]{30,100}')
                    key_match = key_pattern.search(page_source)
                    if key_match:
                        api_key_text = key_match.group(0)
                except:
                    logger.warning("Could not use copy button method")
            
            # If we still don't have the key, try one more method
            if not api_key_text:
                try:
                    # Look for any element that might contain the key
                    key_containers = driver.find_elements(By.XPATH, "//div[contains(@class, 'key') or contains(@class, 'token')]")
                    for container in key_containers:
                        text = container.text
                        if text and text.startswith("AI") and len(text) > 30:
                            api_key_text = text
                            break
                except:
                    logger.warning("Could not find key container elements")
            
            if api_key_text:
                logger.info(f"Successfully extracted API key: {api_key_text[:10]}...")
                
                # بررسی اعتبار API Key اگر درخواست شده باشد
                validation_result = None
                if test_key and API_VALIDATOR_AVAILABLE:
                    logger.info("Testing the API key validity...")
                    try:
                        validation_result = validate_api_key(api_key_text)
                        logger.info(f"API key validation result: {validation_result}")
                    except Exception as e:
                        logger.error(f"Error validating API key: {e}")
                
                return {
                    'success': True,
                    'api_key': api_key_text,
                    'validation_result': validation_result
                }
            else:
                logger.error("Could not extract API key")
                return {
                    'success': False,
                    'error': 'API key was created but could not be extracted from the page.'
                }
            
        except Exception as e:
            logger.error(f"Failed to copy API key: {e}")
            return {
                'success': False,
                'error': 'Failed to copy API key. Interface may have changed.'
            }
        
    except Exception as e:
        logger.error(f"Exception during API key generation: {e}")
        logger.error(traceback.format_exc())
        
        # Try to capture screenshot if possible
        if driver:
            try:
                screenshot_path = f"/tmp/error_api_key_{gmail.split('@')[0]}.png"
                driver.save_screenshot(screenshot_path)
                logger.info(f"Error screenshot saved to {screenshot_path}")
            except:
                pass
        
        return {
            'success': False,
            'error': f'Error generating API key: {str(e)}'
        }
    finally:
        # Close the browser
        if driver:
            logger.info("Closing browser")
            try:
                driver.quit()
            except:
                pass
