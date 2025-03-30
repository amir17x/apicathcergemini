#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول حل CAPTCHA به صورت رایگان
این ماژول روش‌های مختلفی برای حل CAPTCHA بدون استفاده از سرویس‌های پولی ارائه می‌دهد:
1. تقلید رفتار افزونه Buster برای حل reCAPTCHA از طریق صدا
2. اسکرین‌شات گرفتن و ارسال به کاربر تلگرام برای حل دستی
3. استفاده از تکنیک‌های bypass برای دور زدن CAPTCHA در برخی موارد
4. تلاش برای استخراج فایل صوتی و تبدیل آن به متن
"""

import logging
import os
import time
import tempfile
import subprocess
import random
import json
import base64
import re
import requests
from typing import Dict, List, Tuple, Any, Optional, Callable, Union
from pathlib import Path
import uuid

# تنظیم لاگینگ
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    SELENIUM_AVAILABLE = True
except ImportError:
    logger.warning("سلنیوم در دسترس نیست. برخی قابلیت‌های حل CAPTCHA غیرفعال خواهند بود.")
    SELENIUM_AVAILABLE = False

class CaptchaSolver:
    """کلاس اصلی برای حل CAPTCHA با روش‌های مختلف"""
    
    def __init__(self, telegram_bot_token=None, default_chat_id=None):
        """مقداردهی اولیه کلاس با تنظیمات مورد نیاز
        
        Args:
            telegram_bot_token: توکن ربات تلگرام برای ارسال اسکرین‌شات
            default_chat_id: شناسه چت پیش‌فرض برای ارسال اسکرین‌شات
        """
        self.telegram_bot_token = telegram_bot_token
        self.default_chat_id = default_chat_id
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"مسیر موقت برای فایل‌های CAPTCHA: {self.temp_dir}")
        
        # بررسی وجود ffmpeg برای پردازش صدا
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.ffmpeg_available = True
            logger.info("ffmpeg در دسترس است.")
        except (FileNotFoundError, subprocess.SubprocessError):
            self.ffmpeg_available = False
            logger.warning("ffmpeg پیدا نشد. برخی از قابلیت‌های پردازش صدا غیرفعال خواهند بود.")
        
        # بررسی وجود کتابخانه‌های پردازش صدا
        try:
            import speech_recognition as sr
            self.sr_available = True
            self.recognizer = sr.Recognizer()
            logger.info("کتابخانه SpeechRecognition در دسترس است.")
        except ImportError:
            self.sr_available = False
            self.recognizer = None
            logger.warning("کتابخانه SpeechRecognition پیدا نشد. تشخیص CAPTCHA صوتی غیرفعال خواهد بود.")
            
    def detect_captcha(self, driver: webdriver.Chrome) -> Tuple[bool, str, Dict[str, Any]]:
        """تشخیص وجود CAPTCHA در صفحه فعلی
        
        Args:
            driver: نمونه درایور سلنیوم
            
        Returns:
            Tuple[bool, str, Dict[str, Any]]: وضعیت وجود CAPTCHA، نوع CAPTCHA و اطلاعات بیشتر
        """
        if not SELENIUM_AVAILABLE:
            return False, "selenium_not_available", {}
            
        try:
            page_source = driver.page_source.lower()
            
            # بررسی انواع reCAPTCHA
            if "recaptcha" in page_source or "g-recaptcha" in page_source:
                # فریم reCAPTCHA را پیدا کنید
                recaptcha_frames = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha')]")
                if recaptcha_frames:
                    logger.info("reCAPTCHA در صفحه شناسایی شد.")
                    return True, "recaptcha", {"frames": len(recaptcha_frames)}
            
            # بررسی انواع hCaptcha
            if "hcaptcha" in page_source:
                hcaptcha_frames = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'hcaptcha')]")
                if hcaptcha_frames:
                    logger.info("hCaptcha در صفحه شناسایی شد.")
                    return True, "hcaptcha", {"frames": len(hcaptcha_frames)}
            
            # بررسی متن‌های معمول مرتبط با CAPTCHA
            common_captcha_texts = [
                "captcha", "prove you're human", "اثبات انسان بودن", 
                "verify you are human", "تأیید انسان بودن",
                "security check", "بررسی امنیتی"
            ]
            
            for text in common_captcha_texts:
                if text in page_source:
                    logger.info(f"متن مرتبط با CAPTCHA یافت شد: '{text}'")
                    return True, "text_captcha", {"trigger_text": text}
            
            # بررسی تصاویر رایج CAPTCHA
            captcha_images = driver.find_elements(By.XPATH, "//img[contains(@src, 'captcha')]")
            if captcha_images:
                logger.info("تصویر CAPTCHA در صفحه یافت شد.")
                return True, "image_captcha", {"images": len(captcha_images)}
                
            return False, "no_captcha", {}
            
        except Exception as e:
            logger.error(f"خطا در تشخیص CAPTCHA: {e}")
            return False, "error", {"error": str(e)}
    
    def solve_captcha_via_telegram(self, driver: webdriver.Chrome, chat_id: str = None, timeout: int = 120) -> Tuple[bool, str]:
        """حل CAPTCHA با ارسال اسکرین‌شات به کاربر تلگرام
        
        Args:
            driver: نمونه درایور سلنیوم
            chat_id: شناسه چت تلگرام برای ارسال اسکرین‌شات
            timeout: زمان انتظار به ثانیه برای دریافت پاسخ
            
        Returns:
            Tuple[bool, str]: وضعیت موفقیت و پیام
        """
        if not self.telegram_bot_token:
            logger.error("توکن تلگرام تنظیم نشده است.")
            return False, "Telegram token not provided"
            
        chat_id = chat_id or self.default_chat_id
        if not chat_id:
            logger.error("شناسه چت تلگرام مشخص نشده است.")
            return False, "Telegram chat ID not provided"
            
        try:
            # گرفتن اسکرین‌شات از صفحه
            screenshot_path = os.path.join(self.temp_dir, f"captcha_{uuid.uuid4()}.png")
            driver.save_screenshot(screenshot_path)
            
            # ارسال پیام به کاربر
            message = "لطفاً CAPTCHA در تصویر زیر را حل کنید و پاسخ را ارسال نمایید:"
            self._send_telegram_message(chat_id, message)
            
            # ارسال تصویر به کاربر
            with open(screenshot_path, "rb") as photo:
                self._send_telegram_photo(chat_id, photo)
                
            # انتظار برای دریافت پاسخ
            start_time = time.time()
            last_update_id = 0
            
            while time.time() - start_time < timeout:
                updates = self._get_telegram_updates()
                if not updates.get("ok", False):
                    logger.error("خطا در دریافت آپدیت‌های تلگرام.")
                    time.sleep(5)
                    continue
                    
                for update in updates.get("result", []):
                    update_id = update.get("update_id", 0)
                    if update_id <= last_update_id:
                        continue
                        
                    last_update_id = update_id
                    message = update.get("message", {})
                    if message.get("chat", {}).get("id") == int(chat_id) and "text" in message:
                        captcha_text = message.get("text", "").strip()
                        if captcha_text:
                            logger.info(f"پاسخ CAPTCHA از کاربر دریافت شد: {captcha_text}")
                            
                            # تلاش برای پیدا کردن فیلد ورودی CAPTCHA و وارد کردن پاسخ
                            try:
                                # جستجوی فیلدهای ورودی معمول با حداکثر تلاش
                                input_found = False
                                
                                # استراتژی‌های مختلف برای پیدا کردن فیلد ورودی
                                strategies = [
                                    (By.XPATH, "//input[@name='captcha']"),
                                    (By.XPATH, "//input[contains(@placeholder, 'captcha')]"),
                                    (By.XPATH, "//input[contains(@id, 'captcha')]"),
                                    (By.XPATH, "//input[@type='text']"),
                                    (By.XPATH, "//textarea")
                                ]
                                
                                for strategy in strategies:
                                    try:
                                        inputs = driver.find_elements(*strategy)
                                        for input_field in inputs:
                                            if input_field.is_displayed():
                                                input_field.clear()
                                                input_field.send_keys(captcha_text)
                                                time.sleep(1)
                                                
                                                # تلاش برای ارسال فرم
                                                try:
                                                    input_field.send_keys(Keys.ENTER)
                                                except:
                                                    pass
                                                    
                                                # جستجوی دکمه ارسال
                                                submit_strategies = [
                                                    (By.XPATH, "//button[@type='submit']"),
                                                    (By.XPATH, "//input[@type='submit']"),
                                                    (By.XPATH, "//button[contains(text(), 'Submit')]"),
                                                    (By.XPATH, "//button[contains(text(), 'Verify')]"),
                                                    (By.XPATH, "//button[contains(text(), 'تأیید')]"),
                                                    (By.XPATH, "//button")
                                                ]
                                                
                                                for submit_strategy in submit_strategies:
                                                    try:
                                                        submit_buttons = driver.find_elements(*submit_strategy)
                                                        for button in submit_buttons:
                                                            if button.is_displayed():
                                                                button.click()
                                                                break
                                                    except:
                                                        continue
                                                
                                                input_found = True
                                                break
                                            
                                        if input_found:
                                            break
                                    except:
                                        continue
                                
                                if not input_found:
                                    logger.warning("فیلد ورودی برای CAPTCHA یافت نشد. کاربر باید خودش وارد کند.")
                                    self._send_telegram_message(chat_id, "فیلد ورودی برای CAPTCHA پیدا نشد. لطفاً خودتان پاسخ را وارد کنید.")
                                
                                # انتظار کوتاه برای اعمال تغییرات
                                time.sleep(5)
                                return True, "پاسخ CAPTCHA با موفقیت ارسال شد."
                                
                            except Exception as input_error:
                                logger.error(f"خطا در وارد کردن پاسخ CAPTCHA: {input_error}")
                                self._send_telegram_message(chat_id, f"خطا در وارد کردن پاسخ: {input_error}")
                                return False, f"Error entering CAPTCHA response: {input_error}"
                
                # انتظار کوتاه قبل از بررسی مجدد
                time.sleep(2)
            
            return False, "زمان انتظار برای پاسخ CAPTCHA به پایان رسید."
            
        except Exception as e:
            logger.error(f"خطا در حل CAPTCHA از طریق تلگرام: {e}")
            return False, f"Error solving CAPTCHA via Telegram: {e}"
    
    def solve_recaptcha_audio(self, driver: webdriver.Chrome, max_attempts: int = 3) -> Tuple[bool, str]:
        """حل reCAPTCHA با استفاده از روش صوتی (شبیه‌سازی عملکرد افزونه Buster)
        
        Args:
            driver: نمونه درایور سلنیوم
            max_attempts: حداکثر تعداد تلاش
            
        Returns:
            Tuple[bool, str]: وضعیت موفقیت و پیام
        """
        if not SELENIUM_AVAILABLE:
            return False, "selenium_not_available"
            
        if not self.ffmpeg_available or not self.sr_available:
            logger.error("ffmpeg یا SpeechRecognition در دسترس نیست. حل CAPTCHA صوتی امکان‌پذیر نیست.")
            return False, "ffmpeg or SpeechRecognition not available"
            
        logger.info("تلاش برای حل reCAPTCHA با روش صوتی...")
        
        try:
            # یافتن فریم reCAPTCHA
            recaptcha_frames = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha')]")
            if not recaptcha_frames:
                logger.error("فریم reCAPTCHA یافت نشد.")
                return False, "reCAPTCHA frame not found"
            
            # برگشت به فریم اصلی
            driver.switch_to.default_content()
            
            # سوئیچ به فریم reCAPTCHA
            driver.switch_to.frame(recaptcha_frames[0])
            
            # کلیک روی Checkbox
            try:
                checkbox = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "recaptcha-anchor"))
                )
                checkbox.click()
                logger.info("Checkbox reCAPTCHA کلیک شد.")
            except:
                logger.warning("Checkbox reCAPTCHA یافت نشد یا قبلاً کلیک شده است.")
            
            # برگشت به فریم اصلی
            driver.switch_to.default_content()
            
            # کمی صبر کنید تا چالش reCAPTCHA ظاهر شود
            time.sleep(2)
            
            # یافتن فریم چالش reCAPTCHA
            challenge_frames = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha/api2/bframe')]")
            if not challenge_frames:
                logger.warning("فریم چالش reCAPTCHA یافت نشد. ممکن است reCAPTCHA قبلاً حل شده باشد.")
                return True, "reCAPTCHA might be already solved"
            
            # سوئیچ به فریم چالش
            driver.switch_to.frame(challenge_frames[0])
            
            for attempt in range(max_attempts):
                logger.info(f"تلاش {attempt + 1} از {max_attempts} برای حل reCAPTCHA صوتی...")
                
                # کلیک روی دکمه صوتی
                try:
                    audio_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "recaptcha-audio-button"))
                    )
                    audio_button.click()
                    logger.info("دکمه صوتی reCAPTCHA کلیک شد.")
                except Exception as audio_button_error:
                    logger.error(f"خطا در کلیک دکمه صوتی: {audio_button_error}")
                    continue
                
                # کمی صبر کنید تا صدا بارگذاری شود
                time.sleep(3)
                
                # بررسی اینکه آیا به خاطر تعداد زیاد درخواست بلاک شده‌ایم
                if "try again later" in driver.page_source.lower() or "too many requests" in driver.page_source.lower():
                    logger.warning("تعداد زیادی درخواست تشخیص داده شد. باید بعداً دوباره تلاش کنید.")
                    
                    # برگشت به فریم اصلی و تلاش برای تازه کردن چالش
                    driver.switch_to.default_content()
                    try:
                        refresh_button = driver.find_element(By.ID, "recaptcha-reload-button")
                        refresh_button.click()
                        time.sleep(2)
                    except:
                        pass
                    
                    # سوئیچ دوباره به فریم چالش
                    driver.switch_to.frame(challenge_frames[0])
                    continue
                
                # دانلود فایل صوتی
                try:
                    # یافتن لینک دانلود صدا
                    audio_source = driver.find_element(By.ID, "audio-source")
                    audio_url = audio_source.get_attribute("src")
                    
                    if not audio_url:
                        logger.error("URL فایل صوتی یافت نشد.")
                        continue
                    
                    logger.info(f"URL فایل صوتی: {audio_url}")
                    
                    # دانلود فایل صوتی
                    audio_file_path = os.path.join(self.temp_dir, f"recaptcha_audio_{uuid.uuid4()}.mp3")
                    
                    # دانلود با استفاده از requests
                    response = requests.get(audio_url, stream=True)
                    with open(audio_file_path, "wb") as audio_file:
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:
                                audio_file.write(chunk)
                    
                    logger.info(f"فایل صوتی با موفقیت دانلود شد: {audio_file_path}")
                    
                    # استخراج متن از فایل صوتی
                    audio_text = self._extract_text_from_audio(audio_file_path)
                    
                    if not audio_text:
                        logger.error("متنی از فایل صوتی استخراج نشد.")
                        continue
                    
                    logger.info(f"متن استخراج شده از فایل صوتی: {audio_text}")
                    
                    # وارد کردن متن استخراج شده در فیلد ورودی
                    audio_response = driver.find_element(By.ID, "audio-response")
                    audio_response.clear()
                    audio_response.send_keys(audio_text)
                    
                    # کلیک روی دکمه Verify
                    verify_button = driver.find_element(By.ID, "recaptcha-verify-button")
                    verify_button.click()
                    
                    # انتظار برای نتیجه
                    time.sleep(5)
                    
                    # بررسی نتیجه
                    if "incorrect" in driver.page_source.lower():
                        logger.warning("پاسخ نادرست است. تلاش دوباره...")
                        continue
                    
                    # برگشت به فریم اصلی
                    driver.switch_to.default_content()
                    
                    logger.info("reCAPTCHA با موفقیت حل شد!")
                    return True, "reCAPTCHA successfully solved"
                    
                except Exception as download_error:
                    logger.error(f"خطا در دانلود یا پردازش فایل صوتی: {download_error}")
                    
                    # برگشت به فریم اصلی و سپس دوباره به فریم چالش
                    driver.switch_to.default_content()
                    time.sleep(1)
                    driver.switch_to.frame(challenge_frames[0])
                    continue
            
            # اگر به اینجا رسیدیم، یعنی همه تلاش‌ها ناموفق بوده‌اند
            logger.error(f"پس از {max_attempts} تلاش، reCAPTCHA حل نشد.")
            
            # برگشت به فریم اصلی
            driver.switch_to.default_content()
            
            return False, f"Failed to solve reCAPTCHA after {max_attempts} attempts"
            
        except Exception as e:
            logger.error(f"خطا در حل reCAPTCHA صوتی: {e}")
            
            # برگشت به فریم اصلی
            try:
                driver.switch_to.default_content()
            except:
                pass
                
            return False, f"Error solving reCAPTCHA audio: {e}"
            
    def _extract_text_from_audio(self, audio_file_path: str) -> str:
        """استخراج متن از فایل صوتی با استفاده از روش‌های رایگان
        
        Args:
            audio_file_path: مسیر فایل صوتی
            
        Returns:
            str: متن استخراج شده
        """
        if not self.sr_available or not self.ffmpeg_available:
            logger.error("SpeechRecognition یا ffmpeg در دسترس نیست.")
            return ""
            
        try:
            import speech_recognition as sr
            
            # تبدیل فایل به WAV برای پردازش بهتر
            wav_file_path = os.path.join(self.temp_dir, f"audio_converted_{uuid.uuid4()}.wav")
            
            # استفاده از ffmpeg برای تبدیل به WAV
            convert_command = [
                "ffmpeg", "-i", audio_file_path, "-ar", "16000", "-ac", "1", 
                "-f", "wav", wav_file_path
            ]
            
            subprocess.run(convert_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            logger.info(f"فایل صوتی با موفقیت به WAV تبدیل شد: {wav_file_path}")
            
            # استفاده از SpeechRecognition برای تبدیل صدا به متن
            with sr.AudioFile(wav_file_path) as source:
                audio_data = self.recognizer.record(source)
                
                # استفاده از سرویس رایگان Google برای تشخیص گفتار
                text = self.recognizer.recognize_google(audio_data)
                
                logger.info(f"متن استخراج شده: {text}")
                return text.strip()
                
        except Exception as e:
            logger.error(f"خطا در استخراج متن از فایل صوتی: {e}")
            return ""
            
    def bypass_captcha(self, driver: webdriver.Chrome) -> Tuple[bool, str]:
        """تلاش برای دور زدن CAPTCHA با روش‌های مختلف
        
        Args:
            driver: نمونه درایور سلنیوم
            
        Returns:
            Tuple[bool, str]: وضعیت موفقیت و پیام
        """
        if not SELENIUM_AVAILABLE:
            return False, "selenium_not_available"
            
        logger.info("تلاش برای دور زدن CAPTCHA...")
        
        try:
            # روش 1: شبیه‌سازی حرکات طبیعی موس
            try:
                actions = ActionChains(driver)
                
                # حرکت‌های تصادفی موس در صفحه
                for _ in range(5):
                    x = random.randint(100, 700)
                    y = random.randint(100, 500)
                    actions.move_by_offset(x, y)
                    time.sleep(random.uniform(0.2, 0.5))
                
                # اجرای حرکات
                actions.perform()
                logger.info("حرکات طبیعی موس شبیه‌سازی شد.")
            except Exception as mouse_error:
                logger.warning(f"خطا در شبیه‌سازی حرکات موس: {mouse_error}")
            
            # روش 2: تغییر user-agent
            try:
                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
                ]
                random_user_agent = random.choice(user_agents)
                
                driver.execute_script(f"Object.defineProperty(navigator, 'userAgent', {{get: function() {{return '{random_user_agent}';}}}});")
                logger.info(f"User-Agent تغییر داده شد به: {random_user_agent}")
            except Exception as ua_error:
                logger.warning(f"خطا در تغییر User-Agent: {ua_error}")
            
            # روش 3: اسکرول در صفحه
            try:
                for _ in range(3):
                    driver.execute_script(f"window.scrollBy(0, {random.randint(100, 300)});")
                    time.sleep(random.uniform(0.3, 0.7))
                    driver.execute_script(f"window.scrollBy(0, {random.randint(-200, -50)});")
                    time.sleep(random.uniform(0.3, 0.7))
                
                logger.info("اسکرول در صفحه انجام شد.")
            except Exception as scroll_error:
                logger.warning(f"خطا در اسکرول صفحه: {scroll_error}")
            
            # روش 4: تغییر ویژگی‌های navigator
            try:
                # تغییر navigator.webdriver به false
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: function() {return false;}});")
                
                # تغییر سایر ویژگی‌ها برای مخفی کردن اتوماسیون
                driver.execute_script("""
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({state: Notification.permission}) :
                            originalQuery(parameters)
                    );
                """)
                
                logger.info("ویژگی‌های navigator تغییر داده شد.")
            except Exception as nav_error:
                logger.warning(f"خطا در تغییر ویژگی‌های navigator: {nav_error}")
            
            # روش 5: اضافه کردن تأخیرهای تصادفی بین اقدامات
            time.sleep(random.uniform(1.0, 2.5))
            
            # بررسی مجدد وجود CAPTCHA پس از اعمال روش‌های bypass
            has_captcha, captcha_type, _ = self.detect_captcha(driver)
            
            if not has_captcha:
                logger.info("CAPTCHA با موفقیت دور زده شد!")
                return True, "CAPTCHA successfully bypassed"
            else:
                logger.warning(f"تلاش برای دور زدن CAPTCHA ناموفق بود. نوع CAPTCHA: {captcha_type}")
                return False, f"Failed to bypass {captcha_type}"
            
        except Exception as e:
            logger.error(f"خطا در دور زدن CAPTCHA: {e}")
            return False, f"Error bypassing CAPTCHA: {e}"
    
    def _send_telegram_message(self, chat_id: str, text: str) -> bool:
        """ارسال پیام متنی به تلگرام
        
        Args:
            chat_id: شناسه چت تلگرام
            text: متن پیام
            
        Returns:
            bool: وضعیت موفقیت
        """
        if not self.telegram_bot_token:
            logger.error("توکن تلگرام تنظیم نشده است.")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, data=data)
            result = response.json()
            
            if result.get("ok", False):
                return True
            else:
                logger.error(f"خطا در ارسال پیام تلگرام: {result}")
                return False
                
        except Exception as e:
            logger.error(f"خطا در ارسال پیام تلگرام: {e}")
            return False
    
    def _send_telegram_photo(self, chat_id: str, photo) -> bool:
        """ارسال تصویر به تلگرام
        
        Args:
            chat_id: شناسه چت تلگرام
            photo: فایل تصویر (فایل باز شده یا مسیر)
            
        Returns:
            bool: وضعیت موفقیت
        """
        if not self.telegram_bot_token:
            logger.error("توکن تلگرام تنظیم نشده است.")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendPhoto"
            
            files = None
            data = {"chat_id": chat_id}
            
            if isinstance(photo, str):
                # اگر photo یک مسیر فایل باشد
                files = {"photo": open(photo, "rb")}
            else:
                # اگر photo یک فایل باز شده باشد
                files = {"photo": photo}
            
            response = requests.post(url, data=data, files=files)
            result = response.json()
            
            if result.get("ok", False):
                return True
            else:
                logger.error(f"خطا در ارسال تصویر تلگرام: {result}")
                return False
                
        except Exception as e:
            logger.error(f"خطا در ارسال تصویر تلگرام: {e}")
            return False
    
    def _get_telegram_updates(self) -> Dict[str, Any]:
        """دریافت آپدیت‌های تلگرام
        
        Returns:
            Dict[str, Any]: آپدیت‌های دریافت شده
        """
        if not self.telegram_bot_token:
            logger.error("توکن تلگرام تنظیم نشده است.")
            return {"ok": False, "error": "Telegram token not provided"}
            
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/getUpdates"
            response = requests.get(url)
            return response.json()
            
        except Exception as e:
            logger.error(f"خطا در دریافت آپدیت‌های تلگرام: {e}")
            return {"ok": False, "error": str(e)}
    
    def clean_up(self):
        """پاکسازی فایل‌های موقت"""
        try:
            # پاکسازی دایرکتوری موقت
            if os.path.exists(self.temp_dir):
                for file_name in os.listdir(self.temp_dir):
                    file_path = os.path.join(self.temp_dir, file_name)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception as e:
                        logger.error(f"خطا در حذف فایل {file_path}: {e}")
                
                try:
                    os.rmdir(self.temp_dir)
                    logger.info(f"دایرکتوری موقت {self.temp_dir} با موفقیت حذف شد.")
                except:
                    logger.warning(f"نمی‌توان دایرکتوری موقت {self.temp_dir} را حذف کرد.")
        except Exception as e:
            logger.error(f"خطا در پاکسازی فایل‌های موقت: {e}")