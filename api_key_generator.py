#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول دریافت API Key از Google Gemini.
این ماژول برای اتوماسیون فرآیند ورود به Google AI Studio و دریافت API Key استفاده می‌شود.
"""

import logging
import time
import os
import re
import random
import traceback
import json
from typing import Dict, Optional, Tuple, Union, Any, List

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager

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
        # بررسی وجود فرم ورود شماره تلفن
        phone_field = None
        try:
            phone_field = wait.until(EC.presence_of_element_located((By.ID, "phoneNumberId")))
        except:
            try:
                phone_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@id, 'phone')]")))
            except:
                logger.info("فرم ورود شماره تلفن یافت نشد.")
                return False, "فرم ورود شماره تلفن یافت نشد."
        
        if not phone_field:
            return False, "فیلد شماره تلفن یافت نشد."
            
        # ایجاد یک مدیر Twilio و دریافت شماره تلفن موقت
        twilio_manager = TwilioManager()
        if not twilio_manager.available:
            return False, "اتصال به Twilio برقرار نشد."
            
        # دریافت شماره تلفن
        success, phone_number, message = twilio_manager.get_phone_number("US")
        if not success or not phone_number:
            return False, f"خطا در دریافت شماره تلفن: {message}"
            
        logger.info(f"شماره تلفن موقت دریافت شد: {phone_number}")
        
        # وارد کردن شماره تلفن در فرم
        phone_field.clear()
        phone_field.send_keys(phone_number)
        time.sleep(1)
        
        # کلیک روی دکمه ارسال کد
        next_button = None
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']/parent::button")))
        except:
            try:
                next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Send']/parent::button")))
            except:
                try:
                    next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@type, 'submit')]")))
                except:
                    return False, "دکمه ارسال کد تأیید یافت نشد."
                    
        if next_button:
            next_button.click()
            logger.info("دکمه ارسال کد تأیید کلیک شد.")
            time.sleep(5)
        else:
            return False, "دکمه ارسال کد تأیید یافت نشد."
            
        # انتظار برای دریافت کد تأیید
        success, verification_code, message = twilio_manager.wait_for_sms(phone_number, timeout=60, interval=5)
        if not success or not verification_code:
            # آزادسازی شماره تلفن
            twilio_manager.release_phone_number(phone_number)
            return False, f"خطا در دریافت کد تأیید: {message}"
            
        logger.info(f"کد تأیید دریافت شد: {verification_code}")
        
        # وارد کردن کد تأیید
        code_field = None
        try:
            code_field = wait.until(EC.presence_of_element_located((By.ID, "code")))
        except:
            try:
                code_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@id, 'code') or contains(@id, 'verification')]")))
            except:
                # آزادسازی شماره تلفن
                twilio_manager.release_phone_number(phone_number)
                return False, "فیلد ورود کد تأیید یافت نشد."
                
        if code_field:
            code_field.clear()
            code_field.send_keys(verification_code)
            time.sleep(1)
            
            # کلیک روی دکمه تأیید
            verify_button = None
            try:
                verify_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Verify']/parent::button")))
            except:
                try:
                    verify_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@type, 'submit')]")))
                except:
                    # آزادسازی شماره تلفن
                    twilio_manager.release_phone_number(phone_number)
                    return False, "دکمه تأیید کد یافت نشد."
                    
            if verify_button:
                verify_button.click()
                logger.info("دکمه تأیید کد کلیک شد.")
                time.sleep(5)
            else:
                # آزادسازی شماره تلفن
                twilio_manager.release_phone_number(phone_number)
                return False, "دکمه تأیید کد یافت نشد."
        else:
            # آزادسازی شماره تلفن
            twilio_manager.release_phone_number(phone_number)
            return False, "فیلد ورود کد تأیید یافت نشد."
            
        # آزادسازی شماره تلفن پس از استفاده
        twilio_manager.release_phone_number(phone_number)
        
        # بررسی موفقیت‌آمیز بودن تأیید شماره تلفن
        if "verification successful" in driver.page_source.lower() or "verify" not in driver.page_source.lower():
            return True, "تأیید شماره تلفن با موفقیت انجام شد."
        else:
            return False, "تأیید شماره تلفن ناموفق بود."
            
    except Exception as e:
        logger.error(f"خطا در فرآیند تأیید شماره تلفن: {e}")
        return False, str(e)

def generate_api_key(gmail, password, proxy=None, test_key=True):
    """
    دریافت کلید API از Google Gemini با استفاده از اتوماسیون Selenium.
    
    Args:
        gmail: آدرس ایمیل Gmail برای ورود
        password: رمز عبور حساب Gmail
        proxy: تنظیمات پروکسی (اختیاری)
        test_key: آیا اعتبار API Key پس از دریافت بررسی شود؟ (پیش‌فرض: True)
        
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
        
        # Initialize the driver
        logger.info("Initializing undetected-chromedriver...")
        driver = uc.Chrome(options=options)
        
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
            
            return {
                'success': False,
                'error': 'Additional verification required for sign-in. Manual intervention needed.'
            }
        
        # Step 4: Navigate to API key page
        logger.info("Navigating to API keys page...")
        try:
            # Wait to be redirected to AI Studio page
            time.sleep(5)
            
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
