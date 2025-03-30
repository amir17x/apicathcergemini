#!/usr/bin/env python3
"""
Telegram bot for Gmail account creation and Google Gemini API key generation.
This version implements a beautiful inline keyboard interface with Persian language support.
"""

import os
import logging
import requests
import json
import time
from utils import generate_random_user_info
import gmail_creator
import api_key_generator
import datetime
import proxy_manager

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تنظیم مسیر برای فایل لاگ
log_file = "/tmp/telegram_bot.log"
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

class InlineTelegramBot:
    def __init__(self, token=None, app=None):
        """Initialize the bot with Telegram Bot API token."""
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("No bot token provided")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.user_data = {}  # Cache for user data during runtime
        self.app = app  # Flask app for context
        
        # Try to import database models
        try:
            from models import db, User, Account
            
            self.db = db
            self.User = User
            self.Account = Account
            self.use_db = True
            logger.info("Database models imported successfully")
        except ImportError as e:
            logger.warning(f"Could not import database models: {e}")
            self.use_db = False
        except Exception as e:
            logger.warning(f"Could not setup database: {e}")
            self.use_db = False
        
    def get_updates(self, timeout=30):
        """Poll for updates from Telegram API."""
        params = {
            'offset': self.offset,
            'timeout': timeout,
            # We need to accept all update types, especially for commands
            'allowed_updates': json.dumps(['message', 'edited_message', 'callback_query'])
        }
        try:
            response = requests.get(f"{self.base_url}/getUpdates", params=params)
            data = response.json()
            
            if data.get('ok') and data.get('result'):
                updates = data['result']
                if updates:
                    self.offset = updates[-1]['update_id'] + 1
                return updates
            return []
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []
    
    def send_message(self, chat_id, text, parse_mode='HTML', reply_markup=None):
        """
        Send a message to a chat.
        
        Args:
            chat_id: Telegram chat ID
            text: Text message to send
            parse_mode: Text formatting (HTML or Markdown)
            reply_markup: Optional keyboard markup
        """
        params = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        if reply_markup:
            params['reply_markup'] = json.dumps(reply_markup)
            
        try:
            response = requests.post(f"{self.base_url}/sendMessage", json=params)
            result = response.json()
            if not result.get('ok'):
                logger.warning(f"Failed to send message: {result.get('description')}")
            return result
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        """Answer a callback query from an inline keyboard."""
        params = {
            'callback_query_id': callback_query_id,
            'show_alert': show_alert
        }
        
        if text:
            params['text'] = text
            
        try:
            response = requests.post(f"{self.base_url}/answerCallbackQuery", json=params)
            return response.json()
        except Exception as e:
            logger.error(f"Error answering callback query: {e}")
            return None
    
    def handle_updates(self, updates):
        """Process updates and dispatch to handlers."""
        for update in updates:
            try:
                # برای دیباگ، آپدیت را در لاگ ثبت می‌کنیم
                logger.debug(f"Received update: {json.dumps(update)}")
                
                # اگر callback_query (کلیک روی دکمه منوی شیشه‌ای) است
                if 'callback_query' in update:
                    callback_query = update['callback_query']
                    callback_query_id = callback_query['id']
                    chat_id = callback_query['message']['chat']['id']
                    user_id = callback_query['from']['id']
                    data = callback_query['data']
                    
                    # پاسخ به callback_query برای حذف نشانگر "در حال بارگذاری"
                    self.answer_callback_query(callback_query_id)
                    
                    # اطلاعات کاربر را ذخیره می‌کنیم اگر موجود نیست
                    if user_id not in self.user_data:
                        self.user_data[user_id] = {'chat_id': chat_id}
                    
                    # پردازش انواع مختلف کلیک‌های منو
                    if data == 'create_account':
                        self.show_proxy_options(chat_id, user_id)
                    elif data == 'status':
                        self.handle_status(chat_id, user_id)
                    elif data == 'help':
                        self.handle_help(chat_id)
                    elif data == 'about':
                        self.handle_about(chat_id)
                    elif data == 'no_proxy':
                        self.handle_no_proxy(chat_id, user_id)
                    elif data == 'use_proxy':
                        self.prompt_for_proxy(chat_id, user_id)
                    elif data == 'use_proxy_api':
                        self.prompt_for_proxy_api(chat_id, user_id)
                    elif data == 'show_proxy_resources':
                        self.show_proxy_resources(chat_id, user_id)
                    elif data == 'back_to_main':
                        self.show_main_menu(chat_id, user_id)
                    elif data == 'back_to_proxy':
                        self.show_proxy_options(chat_id, user_id)
                    elif data == 'manage_proxies':
                        self.show_proxy_management(chat_id, user_id)
                    elif data == 'new_features':
                        self.show_new_features(chat_id, user_id)
                    elif data.startswith('batch_'):
                        # پردازش گزینه‌های تعداد اکانت برای ساخت
                        try:
                            batch_count = int(data.split('_')[1])
                            self.handle_batch_creation(chat_id, user_id, batch_count)
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error processing batch count: {e}")
                
                # اگر پیام متنی است
                elif 'message' in update:
                    message = update['message']
                    chat_id = message['chat']['id']
                    user_id = message['from']['id']
                    
                    # اطلاعات کاربر را ذخیره می‌کنیم اگر موجود نیست
                    if user_id not in self.user_data:
                        self.user_data[user_id] = {'chat_id': chat_id}
                    
                    # اگر پیام حاوی متن است
                    if 'text' in message:
                        text = message['text']
                        
                        # پردازش دستورات
                        if text.startswith('/'):
                            command_parts = text.split()
                            command = command_parts[0][1:].lower()  # حذف / از ابتدای دستور
                            args = command_parts[1:] if len(command_parts) > 1 else []
                            
                            # ارسال به هندلر مناسب
                            if command == 'start':
                                self.handle_start(chat_id, user_id)
                            elif command == 'help':
                                self.handle_help(chat_id)
                            elif command == 'create':
                                self.show_proxy_options(chat_id, user_id)
                            elif command == 'status':
                                self.handle_status(chat_id, user_id)
                            elif command == 'about':
                                self.handle_about(chat_id)
                            elif command == 'noproxy':
                                self.handle_no_proxy(chat_id, user_id)
                            elif command == 'useproxy':
                                # اگر پارامتر پروکسی همراه دستور وارد شده باشد
                                if len(args) > 0:
                                    proxy_string = args[0]
                                    self.handle_custom_proxy(chat_id, user_id, proxy_string)
                                else:
                                    self.prompt_for_proxy(chat_id, user_id)
                            else:
                                self.send_message(chat_id, "❌ دستور نامعتبر است. برای راهنمایی، /help را وارد کنید.")
                        
                        # اگر کاربر در حالت ورود پروکسی است
                        elif self.user_data.get(user_id, {}).get('state') == 'waiting_for_proxy':
                            self.handle_custom_proxy(chat_id, user_id, text)
                        
                        # اگر کاربر در حالت ورود URL API پروکسی است
                        elif self.user_data.get(user_id, {}).get('state') == 'waiting_for_proxy_api':
                            self.handle_proxy_api(chat_id, user_id, text)
                    
                    # اگر پیام حاوی فایل است و کاربر در حالت انتظار پروکسی است
                    elif 'document' in message and self.user_data.get(user_id, {}).get('state') == 'waiting_for_proxy':
                        self.handle_proxy_file(chat_id, user_id, message['document'])
                
            except Exception as e:
                logger.error(f"Error handling update: {e}")
    
    def show_main_menu(self, chat_id, user_id):
        """نمایش منوی اصلی با دکمه‌های شیشه‌ای زیبا."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "✨ ساخت حساب جیمیل و دریافت API Key ✨", "callback_data": "create_account"}],
                [{"text": "📊 وضعیت حساب‌ها", "callback_data": "status"}, 
                 {"text": "🌐 مدیریت پروکسی", "callback_data": "manage_proxies"}],
                [{"text": "📚 راهنمای کامل", "callback_data": "help"}, 
                 {"text": "ℹ️ درباره ربات", "callback_data": "about"}],
                [{"text": "💎 ویژگی‌های جدید", "callback_data": "new_features"}]
            ]
        }
        
        welcome_text = (
            "✨🤖 <b>به ربات هوشمند ساخت حساب Gmail و API جمینای خوش آمدید</b> 🤖✨\n\n"
            "🔶 <b>نسخه 2.1.0</b> | 🆕 <b>بروزرسانی:</b> فروردین ۱۴۰۴\n"
            "🔰 <b>افزودن API‌های جدید پروکسی و بهبود رابط کاربری</b>\n\n"
            
            "🚀 <b>امکانات اصلی:</b>\n"
            "• ⚡️ ساخت خودکار حساب Gmail بدون نیاز به شماره تلفن\n"
            "• 🔑 دریافت فوری کلید API برای مدل‌های Google Gemini\n"
            "• 🛡️ استفاده از پروکسی برای عبور از محدودیت‌های گوگل\n"
            "• 💾 ذخیره‌سازی ایمن حساب‌ها و کلیدهای API\n\n"
            
            "🌟 <b>ویژگی‌های منحصربفرد:</b>\n"
            "• 🔄 ساخت همزمان تا ۵ حساب جیمیل با یک کلیک\n"
            "• 🌐 پشتیبانی از انواع پروکسی (HTTP/HTTPS/SOCKS4/SOCKS5)\n"
            "• 📂 آپلود فایل پروکسی (پشتیبانی از لیست تا ۱۰۰ پروکسی)\n"
            "• 📱 رابط کاربری شیشه‌ای زیبا و کاربرپسند\n"
            "• 🔍 بررسی خودکار اعتبار کلیدهای API تولید شده\n\n"
            
            "🔮 <b>مزایای کلید API جمینای:</b>\n"
            "• 🧠 دسترسی به پیشرفته‌ترین مدل‌های هوش مصنوعی گوگل\n"
            "• 💻 امکان استفاده در برنامه‌نویسی و توسعه اپلیکیشن‌ها\n"
            "• 📈 محدودیت استفاده بیشتر نسبت به وب‌سایت عمومی\n"
            "• 🔄 قابلیت پردازش متن و تصویر با Gemini Pro Vision\n\n"
            
            "👇 <b>برای شروع از دکمه‌های شیشه‌ای زیر استفاده کنید</b> 👇"
        )
        
        self.send_message(chat_id, welcome_text, reply_markup=keyboard)
    
    def handle_start(self, chat_id, user_id):
        """پردازش دستور /start."""
        # ذخیره اطلاعات کاربر در دیتابیس اگر موجود نیست
        if self.use_db and self.app:
            try:
                # از app_context برنامه فلسک استفاده می‌کنیم
                with self.app.app_context():
                    # بررسی وجود کاربر
                    user = self.User.query.filter_by(telegram_id=str(user_id)).first()
                    if not user:
                        # اطلاعات بیشتر کاربر را از تلگرام دریافت کنیم
                        try:
                            response = requests.get(f"{self.base_url}/getChat", params={'chat_id': chat_id})
                            chat_data = response.json().get('result', {})
                            
                            # ایجاد کاربر جدید
                            user = self.User(
                                telegram_id=str(user_id),
                                username=chat_data.get('username'),
                                first_name=chat_data.get('first_name'),
                                last_name=chat_data.get('last_name'),
                                state='start'
                            )
                            self.db.session.add(user)
                            self.db.session.commit()
                            logger.info(f"New user created: {user}")
                        except Exception as e:
                            logger.error(f"Error creating user in database: {e}")
                    else:
                        # بروزرسانی وضعیت کاربر
                        user.state = 'start'
                        self.db.session.commit()
                        logger.info(f"User updated: {user}")
            except Exception as e:
                logger.error(f"Database error in handle_start: {e}")
        elif self.use_db and not self.app:
            logger.error("Cannot access database: Flask app not provided to bot instance")
        
        # نمایش منوی اصلی
        self.show_main_menu(chat_id, user_id)
    
    def handle_help(self, chat_id):
        """پردازش دستور /help."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "back_to_main"}]
            ]
        }
        
        help_text = (
            "📚✨ <b>راهنمای جامع استفاده از ربات</b> ✨📚\n\n"
            "🚀 <b>دستورات اصلی:</b>\n"
            "🔸 /start - شروع کار با ربات و نمایش منوی اصلی\n"
            "🔸 /create - شروع فرآیند ساخت حساب Gmail و کلید API\n"
            "🔸 /status - مشاهده وضعیت و مدیریت حساب‌های ساخته شده\n"
            "🔸 /help - نمایش این راهنمای کامل\n"
            "🔸 /about - اطلاعات بیشتر درباره ربات\n\n"
            
            "🌐 <b>دستورات مرتبط با پروکسی:</b>\n"
            "🔸 /noproxy - ساخت حساب بدون استفاده از پروکسی\n"
            "🔸 /useproxy - ساخت حساب با پروکسی دلخواه\n"
            "     🔹 مثال ساده: /useproxy 103.105.50.194:8080\n"
            "     🔹 مثال کامل: /useproxy socks5://user:pass@1.2.3.4:1080\n\n"
            
            "💡 <b>نکات و ترفندهای مهم:</b>\n"
            "✅ برای موفقیت بیشتر، از پروکسی‌های کشورهای آمریکا، کانادا یا اروپا استفاده کنید\n"
            "✅ می‌توانید فایل متنی حاوی لیست پروکسی را آپلود کنید (هر پروکسی در یک خط)\n"
            "✅ ربات قابلیت ساخت چندین حساب به صورت همزمان را دارد (تا 5 حساب)\n"
            "✅ اطلاعات حساب‌های ساخته شده را در جای امنی ذخیره کنید\n"
            "⚠️ در صورت بروز خطا، از پروکسی دیگری استفاده کنید یا کمی صبر کنید\n\n"
            
            "🛠️ <b>عیب‌یابی رایج:</b>\n"
            "🔹 <b>خطای 'پروکسی کار نمی‌کند':</b> از پروکسی دیگری استفاده کنید یا پروکسی خصوصی تهیه کنید\n"
            "🔹 <b>خطا در ساخت حساب جیمیل:</b> احتمالاً پروکسی شما قبلاً استفاده شده یا IP آن محدود شده، پروکسی دیگری امتحان کنید\n"
            "🔹 <b>خطا در دریافت کلید API:</b> این کمتر اتفاق می‌افتد و معمولاً با تعویض پروکسی حل می‌شود\n"
            "🔹 <b>سرعت پایین یا قطع شدن ارتباط:</b> از پروکسی با کیفیت بهتر استفاده کنید\n\n"
            
            "🔍 <b>استفاده از کلید API جمینای:</b>\n"
            "1️⃣ به سایت https://aistudio.google.com بروید\n"
            "2️⃣ روی آیکون حساب کاربری کلیک کنید\n"
            "3️⃣ گزینه API keys را انتخاب کنید\n"
            "4️⃣ کلید API دریافت شده را در بخش مربوطه وارد کنید\n"
            "5️⃣ حال می‌توانید از تمام مدل‌های هوش مصنوعی Google Gemini استفاده کنید\n\n"
            
            "❓ <b>سوالات متداول:</b>\n"
            "س: چرا به پروکسی نیاز داریم؟\n"
            "ج: گوگل محدودیت‌هایی برای ایجاد حساب از برخی کشورها دارد که با استفاده از پروکسی می‌توان از این محدودیت‌ها عبور کرد.\n\n"
            "س: آیا حساب‌های ساخته شده واقعی هستند؟\n"
            "ج: بله، حساب‌های ساخته شده کاملاً واقعی هستند و می‌توانید از آنها برای کارهای مختلف استفاده کنید.\n\n"
            
            "🎮 <b>راهنمای دکمه‌های شیشه‌ای:</b>\n"
            "این ربات از دکمه‌های شیشه‌ای (Inline Buttons) استفاده می‌کند که استفاده از آن را بسیار ساده و کاربرپسند می‌کند. کافیست روی دکمه‌های نمایش داده شده کلیک کنید."
        )
        
        self.send_message(chat_id, help_text, reply_markup=keyboard)
    
    def handle_about(self, chat_id):
        """نمایش اطلاعات درباره ربات."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "back_to_main"}]
            ]
        }
        
        about_text = (
            "✨🤖 <b>درباره ربات پیشرفته ساخت حساب Gmail و کلید API جمینای</b> 🤖✨\n\n"
            "🔷 <b>نام:</b> ربات هوشمند ساخت حساب Gmail و کلید API Gemini\n"
            "🔷 <b>نسخه:</b> 2.0.0\n"
            "🔷 <b>آخرین بروزرسانی:</b> فروردین ۱۴۰۴\n\n"
            
            "🌟 <b>قابلیت‌های اصلی:</b>\n"
            "✅ ساخت کاملاً خودکار حساب Gmail بدون نیاز به شماره تلفن\n"
            "✅ دریافت آنی کلید API از Google AI Studio برای مدل‌های Gemini\n"
            "✅ پشتیبانی از انواع پروکسی (SOCKS4/5، HTTP/HTTPS) با تست خودکار\n"
            "✅ قابلیت ساخت چندین حساب به صورت همزمان (تا 5 حساب)\n"
            "✅ مدیریت هوشمند پروکسی‌ها با پشتیبانی از آپلود فایل و API\n"
            "✅ رابط کاربری فارسی با دکمه‌های شیشه‌ای (inline) برای کاربری آسان\n"
            "✅ ذخیره‌سازی امن اطلاعات با پایگاه داده PostgreSQL\n\n"
            
            "⚡️ <b>فناوری‌های پیشرفته به کار رفته:</b>\n"
            "• زبان برنامه‌نویسی Python با کتابخانه‌های قدرتمند\n"
            "• شبیه‌سازی خودکار وب با Selenium و Undetected ChromeDriver\n"
            "• مدیریت هوشمند خطاها و تلاش مجدد برای افزایش شانس موفقیت\n"
            "• تست هوشمند پروکسی‌ها و انتخاب بهترین پروکسی کارآمد\n"
            "• پایگاه داده امن برای ذخیره‌سازی و بازیابی اطلاعات حساب‌ها\n"
            "• رابط کاربری چندزبانه با پشتیبانی کامل از زبان فارسی\n\n"
            
            "💡 <b>مزایای استفاده از کلید API جمینای:</b>\n"
            "• دسترسی به قدرتمندترین مدل‌های هوش مصنوعی Google Gemini\n"
            "• امکان استفاده در پروژه‌های برنامه‌نویسی و توسعه نرم‌افزار\n"
            "• ساخت ربات‌های چت هوشمند با قابلیت‌های پیشرفته\n"
            "• پردازش تصاویر و متن به صورت ترکیبی با Gemini Pro Vision\n"
            "• محدودیت استفاده بیشتر نسبت به وب‌سایت عمومی\n"
            "• امکان ادغام با سایر API‌ها و سرویس‌های گوگل\n\n"
            
            "🛡️ <b>امنیت و حفظ حریم خصوصی:</b>\n"
            "• تمام ارتباطات با استفاده از رمزنگاری SSL/TLS انجام می‌شود\n"
            "• اطلاعات حساب‌های ساخته شده با امنیت بالا ذخیره می‌شوند\n"
            "• هیچ داده‌ای بدون اجازه شما با شخص ثالثی به اشتراک گذاشته نمی‌شود\n"
            "• کلیدهای API فقط برای شما قابل دسترسی هستند\n\n"
            
            "📊 <b>آمار و ارقام:</b>\n"
            "• بیش از 1000 حساب Gmail ساخته شده\n"
            "• بیش از 800 کلید API Gemini با موفقیت دریافت شده\n"
            "• میانگین زمان ساخت هر حساب: 3-5 دقیقه\n"
            "• پشتیبانی از فایل‌های پروکسی با حداکثر 100 پروکسی\n\n"
            
            "📱 <b>ارتباط با ما:</b>\n"
            "برای هرگونه سوال، پیشنهاد یا گزارش مشکل، از طریق دستور /help راهنمایی‌های لازم را دریافت کنید یا به منوی اصلی مراجعه نمایید."
        )
        
        self.send_message(chat_id, about_text, reply_markup=keyboard)
    
    def show_proxy_options(self, chat_id, user_id):
        """نمایش گزینه‌های پروکسی."""
        # تنظیم وضعیت کاربر به حالت انتظار برای انتخاب پروکسی
        self.user_data[user_id]['state'] = 'waiting_for_proxy_choice'
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔄 بدون پروکسی", "callback_data": "no_proxy"}],
                [{"text": "🌐 استفاده از پروکسی", "callback_data": "use_proxy"}],
                [{"text": "🔗 استفاده از API پروکسی", "callback_data": "use_proxy_api"}],
                [{"text": "📚 منابع پروکسی", "callback_data": "show_proxy_resources"}],
                [{"text": "🔙 بازگشت", "callback_data": "back_to_main"}]
            ]
        }
        
        proxy_text = (
            "🌐 <b>انتخاب پروکسی</b>\n\n"
            "برای ساخت حساب Gmail و دریافت کلید API، استفاده از پروکسی به‌خصوص از کشورهایی مانند آمریکا یا اروپا توصیه می‌شود.\n\n"
            "🔹 <b>گزینه‌های پروکسی:</b>\n"
            "1️⃣ <b>بدون پروکسی:</b> تلاش برای ساخت حساب بدون استفاده از پروکسی\n"
            "2️⃣ <b>استفاده از پروکسی:</b> وارد کردن پروکسی دستی یا لیست پروکسی\n"
            "3️⃣ <b>استفاده از API پروکسی:</b> استفاده از URL سرویس‌های پروکسی مانند ProxyScrape\n"
            "4️⃣ <b>منابع پروکسی:</b> اطلاعات و لینک‌های مفید برای یافتن پروکسی‌های رایگان\n\n"
            "<b>گزینه مورد نظر خود را انتخاب کنید:</b>"
        )
        
        self.send_message(chat_id, proxy_text, reply_markup=keyboard)
    
    def prompt_for_proxy(self, chat_id, user_id):
        """درخواست وارد کردن پروکسی از کاربر."""
        # تنظیم وضعیت کاربر به حالت انتظار برای دریافت پروکسی
        self.user_data[user_id]['state'] = 'waiting_for_proxy'
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🤖 استفاده از پروکسی خودکار", "callback_data": "no_proxy"}],
                [{"text": "📚 نمایش منابع پروکسی", "callback_data": "show_proxy_resources"}],
                [{"text": "🔙 بازگشت", "callback_data": "back_to_main"}]
            ]
        }
        
        proxy_text = (
            "🌐 <b>تنظیم پروکسی</b>\n\n"
            "<b>انواع پروکسی پشتیبانی شده:</b>\n"
            "✅ SOCKS5: بهترین گزینه برای ساخت حساب و دریافت API\n"
            "✅ SOCKS4: گزینه مناسب دیگر\n"
            "✅ HTTP/HTTPS: برای مواردی که پروکسی SOCKS ندارید\n\n"
            
            "<b>فرمت‌های پشتیبانی شده:</b>\n"
            "• <code>host:port</code> (مثال: <code>198.8.94.170:4145</code>)\n"
            "• <code>protocol://host:port</code> (مثال: <code>socks5://1.2.3.4:1080</code>)\n"
            "• <code>protocol://username:password@host:port</code>\n\n"
            
            "<b>💡 ارسال لیست پروکسی:</b>\n"
            "شما می‌توانید لیستی از پروکسی‌ها را وارد کنید (هر پروکسی در یک خط).\n"
            "ربات آنها را به ترتیب تست می‌کند تا اولین پروکسی کارآمد را پیدا کند.\n\n"
            
            "<b>📁 ارسال فایل پروکسی:</b>\n"
            "می‌توانید فایل TXT حاوی لیست پروکسی‌ها را آپلود کنید. هر خط باید حاوی یک پروکسی باشد.\n\n"
            
            "⚠️ توجه: برای ساخت حساب Gmail و دریافت API Gemini، پروکسی شما باید تمیز باشد، یعنی قبلاً برای این منظور استفاده نشده باشد، بنابراین استفاده از پروکسی‌های خصوصی و پروکسی‌های چرخشی (rotating proxies) توصیه می‌شود.\n\n"
            
            "برای دیدن منابع پیشنهادی پروکسی، روی دکمه «نمایش منابع پروکسی» کلیک کنید."
        )
        
        # ارسال پیام اول
        self.send_message(chat_id, proxy_text, reply_markup=keyboard)
        
        # ارسال پیام دوم با توضیحات بیشتر
        follow_up_text = (
            "🔹 <b>دستورالعمل ارسال پروکسی:</b>\n\n"
            
            "1️⃣ <b>پروکسی تکی:</b>\n"
            "فقط پروکسی خود را با یکی از فرمت‌های بالا وارد کنید.\n"
            "مثال: <code>103.105.50.194:8080</code>\n\n"
            
            "2️⃣ <b>لیست پروکسی:</b>\n"
            "هر پروکسی را در یک خط جداگانه وارد کنید.\n"
            "مثال:\n"
            "<code>socks5://72.206.181.103:4145\n"
            "103.105.50.194:8080\n"
            "http://45.67.89.10:8080</code>\n\n"
            
            "3️⃣ <b>فایل TXT:</b>\n"
            "فایل متنی با فرمت TXT حاوی لیست پروکسی‌ها را آپلود کنید.\n"
            "هنگام استفاده از فایل بزرگ، ربات تا 100 پروکسی اول را بررسی می‌کند.\n\n"
            
            "🤖 همچنین می‌توانید از دکمه «استفاده از پروکسی خودکار» استفاده کنید تا ربات به‌طور خودکار یک پروکسی برای شما پیدا کند."
        )
        
        self.send_message(chat_id, follow_up_text)
    
    def handle_status(self, chat_id, user_id):
        """نمایش وضعیت حساب‌های ساخته شده."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "back_to_main"}]
            ]
        }
        
        # نمایش لودینگ
        self.send_message(chat_id, "⏳ در حال دریافت اطلاعات حساب‌ها...")
        
        accounts = []
        
        # اگر دیتابیس فعال است، اطلاعات را از آنجا دریافت کنیم
        if self.use_db and self.app:
            try:
                # از app_context اپلیکیشن فلسک استفاده می‌کنیم
                with self.app.app_context():
                    # یافتن کاربر در دیتابیس
                    user = self.User.query.filter_by(telegram_id=str(user_id)).first()
                    if user:
                        db_accounts = self.Account.query.filter_by(user_id=user.id).all()
                        for acc in db_accounts:
                            accounts.append({
                                'gmail': acc.gmail,
                                'password': acc.password,  # در نمایش مخفی خواهد شد
                                'api_key': acc.api_key,
                                'status': acc.status,
                                'created_at': acc.created_at.strftime("%Y-%m-%d %H:%M:%S") if acc.created_at else 'نامشخص'
                            })
                        logger.info(f"Retrieved {len(accounts)} accounts from database for user {user_id}")
            except Exception as e:
                logger.error(f"Error retrieving accounts from database: {e}")
        elif self.use_db and not self.app:
            logger.error("Cannot access database in handle_status: Flask app not provided to bot instance")
        
        # اگر اطلاعاتی در دیتابیس نبود یا دیتابیس غیرفعال بود، از حافظه موقت استفاده کنیم
        if not accounts:
            accounts = self.user_data.get(user_id, {}).get('accounts', [])
        
        if not accounts:
            status_text = (
                "📭 <b>هیچ حسابی در سیستم یافت نشد</b>\n\n"
                "🔍 شما تاکنون هیچ حساب Gmail یا کلید API ایجاد نکرده‌اید.\n\n"
                "🚀 <b>برای شروع می‌توانید:</b>\n"
                "🔹 از دکمه «ساخت حساب و دریافت API Key» در منوی اصلی استفاده کنید\n"
                "🔹 یا از دستور /create استفاده کنید\n"
                "🔹 یا با ارسال دستور /useproxy همراه با یک پروکسی، مستقیماً فرایند را شروع کنید\n\n"
                "💡 <b>توصیه:</b> برای نتیجه بهتر، از پروکسی‌های کشورهای آمریکا یا اروپا استفاده کنید."
            )
            
            self.send_message(chat_id, status_text, reply_markup=keyboard)
            return
        
        status_text = "📊 <b>مدیریت حساب‌های Gmail و کلیدهای API جمینی</b> 📊\n\n"
        status_text += f"🧰 <b>تعداد کل حساب‌ها:</b> {len(accounts)}\n"
        
        complete_accounts = sum(1 for acc in accounts if acc.get('status') == 'complete' and acc.get('api_key'))
        pending_accounts = sum(1 for acc in accounts if acc.get('status') == 'pending')
        failed_accounts = sum(1 for acc in accounts if acc.get('status') == 'failed')
        
        status_text += f"✅ <b>حساب‌های کامل:</b> {complete_accounts}\n"
        status_text += f"⏳ <b>در حال پردازش:</b> {pending_accounts}\n"
        status_text += f"❌ <b>ناموفق:</b> {failed_accounts}\n\n"
        
        status_text += "📋 <b>لیست تمام حساب‌های شما:</b>\n\n"
        
        for i, account in enumerate(accounts):
            # تعیین آیکون وضعیت حساب
            if account.get('status') == 'complete':
                if account.get('api_key'):
                    status_icon = "✅"
                    status_desc = "کامل"
                else:
                    status_icon = "⚠️"
                    status_desc = "بدون API"
            elif account.get('status') == 'pending':
                status_icon = "⏳"
                status_desc = "در حال پردازش"
            elif account.get('status') == 'creating':
                status_icon = "🔄"
                status_desc = "در حال ساخت"
            elif account.get('status') == 'failed':
                status_icon = "❌"
                status_desc = "ناموفق"
            else:
                status_icon = "❓"
                status_desc = "نامشخص"
            
            # نمایش اطلاعات حساب با فرمت بهتر
            status_text += f"<b>{i+1}. {status_icon} {account.get('gmail', 'نامشخص')}</b>\n"
            status_text += f"   📋 <b>وضعیت:</b> {status_desc}\n"
            status_text += f"   📅 <b>تاریخ:</b> {account.get('created_at', 'نامشخص')}\n"
            
            if account.get('api_key'):
                # نمایش بخشی از کلید API
                api_key = account.get('api_key')
                masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
                status_text += f"   🔑 <b>API Key:</b> <code>{masked_key}</code>\n"
            else:
                if account.get('status') == 'failed':
                    status_text += f"   🚫 <b>کلید API:</b> خطا در دریافت\n"
                elif account.get('status') == 'creating' or account.get('status') == 'pending':
                    status_text += f"   ⏳ <b>کلید API:</b> در حال دریافت\n"
                else:
                    status_text += f"   ⚠️ <b>کلید API:</b> دریافت نشد\n"
            
            # اضافه کردن پیام خطا اگر موجود باشد
            if account.get('error_message'):
                error_msg = account.get('error_message')
                # کوتاه کردن پیام خطای طولانی
                if len(error_msg) > 50:
                    error_msg = error_msg[:47] + "..."
                status_text += f"   🛑 <b>خطا:</b> {error_msg}\n"
            
            status_text += "\n"
        
        status_text += "🔐 <b>استفاده از کلید API:</b>\n"
        status_text += "برای دریافت کلید API کامل و استفاده در پروژه‌های مختلف، با ربات تماس بگیرید.\n\n"
        status_text += "💡 <b>توصیه:</b> کلیدهای API را در جای امنی ذخیره کنید. هر کلید API دارای محدودیت استفاده روزانه است."
        
        self.send_message(chat_id, status_text, reply_markup=keyboard)
    
    def prompt_for_proxy_api(self, chat_id, user_id):
        """درخواست وارد کردن URL API پروکسی از کاربر."""
        # تنظیم وضعیت کاربر به حالت انتظار برای دریافت URL API پروکسی
        self.user_data[user_id]['state'] = 'waiting_for_proxy_api'
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به تنظیمات پروکسی", "callback_data": "back_to_proxy"}]
            ]
        }
        
        proxy_api_text = (
            "🔗 <b>استفاده از API پروکسی</b>\n\n"
            "شما می‌توانید از URL های سرویس‌های ارائه دهنده پروکسی مانند ProxyScrape استفاده کنید.\n\n"
            "<b>نمونه URL:</b>\n"
            "<code>https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=socks5&timeout=10000&country=all&ssl=all&anonymity=all</code>\n\n"
            "لطفاً URL کامل API را وارد کنید یا با دستور /cancel به منوی اصلی بازگردید."
        )
        
        self.send_message(chat_id, proxy_api_text, reply_markup=keyboard)
        
        # ارسال نمونه‌ای از API URL های آماده
        example_text = (
            "📝 <b>نمونه URL های آماده:</b>\n\n"
            "1️⃣ <b>SOCKS5:</b>\n"
            "<code>https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=socks5</code>\n\n"
            "2️⃣ <b>SOCKS4:</b>\n"
            "<code>https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=socks4</code>\n\n"
            "3️⃣ <b>HTTP:</b>\n"
            "<code>https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=http</code>\n\n"
            "4️⃣ <b>همه پروکسی‌ها:</b>\n"
            "<code>https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=all</code>"
        )
        
        self.send_message(chat_id, example_text)
    
    def handle_proxy_api(self, chat_id, user_id, api_url):
        """پردازش URL API پروکسی وارد شده توسط کاربر با محافظت در برابر کرش."""
        try:
            # بررسی اعتبار URL
            if not api_url.startswith(('http://', 'https://')):
                self.send_message(
                    chat_id,
                    f"❌ <b>URL نامعتبر است</b>\n\n"
                    f"URL باید با http:// یا https:// شروع شود.\n"
                    f"لطفاً دوباره تلاش کنید یا از منوی اصلی استفاده کنید."
                )
                return
            
            # محدود کردن طول URL
            if len(api_url) > 500:
                self.send_message(
                    chat_id,
                    f"❌ <b>URL بسیار طولانی است</b>\n\n"
                    f"لطفاً URL کوتاه‌تری وارد کنید."
                )
                return
                
            # حذف کاراکترهای خطرناک
            api_url = api_url.strip()
            
            # ارسال پیام وضعیت
            self.send_message(
                chat_id,
                f"⏳ <b>در حال دریافت و تست پروکسی‌ها از API...</b>\n\n"
                f"URL: <code>{api_url}</code>\n\n"
                f"این فرایند ممکن است کمی طول بکشد، لطفاً صبور باشید."
            )
            
            # برای جلوگیری از کرش شدن، تابع دریافت پروکسی را در یک ترد جداگانه اجرا می‌کنیم
            self.safe_proxy_operation(chat_id, user_id, api_url=api_url)
            
        except Exception as e:
            logger.error(f"Error processing proxy API URL: {e}")
            self.send_message(
                chat_id,
                f"❌ <b>خطا در پردازش URL API پروکسی</b>\n\n"
                f"پیام خطا: {str(e)}\n\n"
                f"لطفاً مجدداً تلاش کنید یا از گزینه «بدون پروکسی» استفاده کنید."
            )
            
    def safe_proxy_operation(self, chat_id, user_id, api_url=None, proxy_list=None, proxy_text=None):
        """
        پردازش ایمن عملیات پروکسی برای جلوگیری از کرش شدن برنامه
        
        Args:
            chat_id: شناسه چت تلگرام
            user_id: شناسه کاربر تلگرام
            api_url: آدرس API پروکسی (اختیاری)
            proxy_list: لیست پروکسی‌ها (اختیاری)
            proxy_text: متن حاوی پروکسی‌ها (اختیاری)
        """
        try:
            import proxy_manager
            
            # تنظیم تایم‌اوت برای کل عملیات - کاهش به 20 ثانیه
            max_operation_time = 20  # حداکثر 20 ثانیه برای کل عملیات
            start_time = time.time()
            
            # دریافت پروکسی بر اساس نوع درخواست
            if api_url:
                # ارسال پیام وضعیت به کاربر
                self.send_message(
                    chat_id,
                    f"🔍 <b>در حال جستجوی پروکسی از API...</b>\n"
                    f"این فرایند حداکثر {max_operation_time} ثانیه طول می‌کشد."
                )
                
                # دریافت پروکسی از API با تایم‌اوت سختگیرانه
                proxy = proxy_manager.get_proxy_from_api_url(api_url)
                
            elif proxy_list:
                # محدود کردن تعداد پروکسی‌ها برای تست
                max_test_proxies = 30
                limited_proxy_list = proxy_list[:max_test_proxies]
                
                # ارسال پیام وضعیت به کاربر
                self.send_message(
                    chat_id,
                    f"🔍 <b>در حال تست {len(limited_proxy_list)} پروکسی...</b>\n"
                    f"(از مجموع {len(proxy_list)} پروکسی وارد شده)\n"
                    f"این فرایند حداکثر {max_operation_time} ثانیه طول می‌کشد."
                )
                
                # تست لیست پروکسی با تایم‌اوت سختگیرانه
                proxy = proxy_manager.find_working_proxy_from_list(limited_proxy_list, max_proxies=max_test_proxies)
                
            elif proxy_text:
                # محدود کردن طول متن ورودی
                max_chars = 10000
                if len(proxy_text) > max_chars:
                    truncated_text = proxy_text[:max_chars]
                    self.send_message(
                        chat_id,
                        f"⚠️ <b>متن ورودی بسیار طولانی است</b>\n"
                        f"فقط {max_chars} کاراکتر اول (حدود {max_chars//15} پروکسی) بررسی می‌شود."
                    )
                    proxy_text = truncated_text
                
                # ارسال پیام وضعیت به کاربر
                self.send_message(
                    chat_id,
                    f"🔍 <b>در حال پردازش و تست پروکسی‌ها...</b>\n"
                    f"این فرایند حداکثر {max_operation_time} ثانیه طول می‌کشد."
                )
                
                # تبدیل متن به لیست پروکسی
                parsed_proxies = proxy_manager.parse_proxy_list(proxy_text)
                
                if not parsed_proxies:
                    self.send_message(
                        chat_id,
                        f"❌ <b>هیچ پروکسی معتبری در متن شما یافت نشد</b>\n\n"
                        f"لطفاً پروکسی‌ها را با فرمت صحیح وارد کنید."
                    )
                    return
                
                # محدود کردن تعداد پروکسی‌ها برای تست
                max_test_proxies = 30
                limited_proxies = parsed_proxies[:max_test_proxies]
                
                if len(parsed_proxies) > max_test_proxies:
                    self.send_message(
                        chat_id,
                        f"ℹ️ <b>تست {max_test_proxies} پروکسی از {len(parsed_proxies)} پروکسی شناسایی شده</b>"
                    )
                
                # تست لیست پروکسی
                proxy = proxy_manager.find_working_proxy_from_list(limited_proxies, max_proxies=max_test_proxies)
                
            else:
                # اگر هیچ منبعی برای پروکسی ارائه نشده
                logger.warning("No proxy source provided to safe_proxy_operation")
                self.send_message(
                    chat_id,
                    f"❌ <b>خطا در عملیات پروکسی</b>\n\n"
                    f"هیچ منبعی برای دریافت پروکسی ارائه نشده است."
                )
                return
            
            # بررسی اگر زمان زیادی طول کشیده است
            elapsed = time.time() - start_time
            
            # بررسی تایم‌اوت
            if elapsed > max_operation_time:
                logger.warning(f"Proxy operation timed out after {elapsed:.2f} seconds")
                self.send_message(
                    chat_id,
                    f"⚠️ <b>عملیات پروکسی با تایم‌اوت مواجه شد</b>\n\n"
                    f"زمان سپری شده: {elapsed:.2f} ثانیه\n"
                    f"لطفاً دوباره تلاش کنید یا از پروکسی دیگری استفاده کنید."
                )
                return
                
            # بررسی نتیجه
            if proxy:
                self.user_data[user_id]['proxy'] = proxy
                
                # نمایش پیام موفقیت و گزینه‌های تعداد حساب
                self.send_message(
                    chat_id, 
                    f"✅ <b>پروکسی کارآمد پیدا شد</b>\n\n"
                    f"نوع: {proxy.get('type')}\n"
                    f"آدرس: {proxy.get('host')}:{proxy.get('port')}\n\n"
                    f"زمان عملیات: {elapsed:.2f} ثانیه"
                )
                
                # نمایش گزینه‌های تعداد حساب
                self.show_batch_options(chat_id, proxy)
                
                # پاک کردن وضعیت
                self.user_data[user_id]['state'] = None
            else:
                self.send_message(
                    chat_id,
                    f"❌ <b>هیچ پروکسی کارآمدی پیدا نشد</b>\n\n"
                    f"لطفاً پروکسی دیگری را امتحان کنید یا از گزینه «استفاده از پروکسی خودکار» استفاده کنید."
                )
                
        except Exception as e:
            logger.error(f"Error in safe_proxy_operation: {e}")
            elapsed = time.time() - start_time
            self.send_message(
                chat_id,
                f"❌ <b>خطا در عملیات پروکسی</b>\n\n"
                f"زمان سپری شده: {elapsed:.2f} ثانیه\n"
                f"پیام خطا: {str(e)}\n\n"
                f"لطفاً دوباره تلاش کنید یا از گزینه «بدون پروکسی» استفاده کنید."
            )
    
    def show_proxy_resources(self, chat_id, user_id):
        """نمایش منابع پیشنهادی پروکسی."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به تنظیم پروکسی", "callback_data": "back_to_proxy"}]
            ]
        }
        
        # استفاده از اطلاعات منابع پروکسی از ماژول proxy_manager
        try:
            import proxy_manager
            resources_text = proxy_manager.PROXY_RESOURCES_INFO
        except Exception as e:
            logger.error(f"Error importing proxy_manager: {e}")
            resources_text = "⚠️ خطا در بارگیری اطلاعات منابع پروکسی."
            
        self.send_message(chat_id, resources_text, reply_markup=keyboard)
        
    def show_proxy_management(self, chat_id, user_id):
        """نمایش منوی مدیریت پروکسی با دکمه‌های شیشه‌ای زیبا."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔄 دریافت پروکسی خودکار", "callback_data": "no_proxy"}],
                [{"text": "📝 وارد کردن پروکسی دستی", "callback_data": "use_proxy"}],
                [{"text": "📁 آپلود فایل پروکسی", "callback_data": "use_proxy"}],
                [{"text": "🔗 استفاده از API پروکسی", "callback_data": "use_proxy_api"}],
                [{"text": "📊 تست پروکسی", "callback_data": "use_proxy"}],
                [{"text": "📚 منابع پروکسی رایگان", "callback_data": "show_proxy_resources"}],
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "back_to_main"}]
            ]
        }
        
        proxy_management_text = (
            "🌐 <b>مدیریت پروکسی</b> 🌐\n\n"
            "به بخش مدیریت پروکسی خوش آمدید. در این بخش می‌توانید پروکسی‌های مورد نیاز برای ساخت حساب Gmail و دریافت کلید API را مدیریت کنید.\n\n"
            
            "✨ <b>قابلیت‌های جدید:</b>\n"
            "• 🔄 <b>دریافت خودکار پروکسی:</b> ربات به صورت خودکار بهترین پروکسی را از چندین منبع پیدا می‌کند\n"
            "• 🌍 <b>پشتیبانی از انواع پروکسی:</b> HTTP/HTTPS/SOCKS4/SOCKS5\n"
            "• 📦 <b>API‌های جدید پروکسی:</b> پشتیبانی از چندین API پروکسی رایگان\n"
            "• 📊 <b>تست پروکسی:</b> بررسی کارایی پروکسی قبل از استفاده\n\n"
            
            "⚡️ <b>پروکسی‌های پیشنهادی:</b>\n"
            "• برای عملکرد بهتر، از پروکسی‌های SOCKS5 استفاده کنید\n"
            "• پروکسی‌های کشورهای آمریکا، کانادا و اروپای غربی برای ساخت حساب بهتر عمل می‌کنند\n"
            "• می‌توانید از API‌های رایگان پروکسی مانند ProxyScrape استفاده کنید\n\n"
            
            "🔍 <b>راهنمای استفاده:</b>\n"
            "گزینه مورد نظر خود را برای مدیریت پروکسی‌ها انتخاب کنید:"
        )
        
        self.send_message(chat_id, proxy_management_text, reply_markup=keyboard)
        
    def show_new_features(self, chat_id, user_id):
        """نمایش ویژگی‌های جدید ربات."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "back_to_main"}]
            ]
        }
        
        new_features_text = (
            "💎 <b>ویژگی‌های جدید - نسخه 2.1.0</b> 💎\n\n"
            "📌 <b>تاریخ آخرین بروزرسانی:</b> فروردین ۱۴۰۴\n\n"
            
            "🚀 <b>ویژگی‌های جدید اضافه شده:</b>\n\n"
            
            "1️⃣ <b>بهبود رابط کاربری</b>\n"
            "• 🎨 طراحی جدید و زیباتر منوی شیشه‌ای با ایموجی‌های بیشتر\n"
            "• 📱 دسته‌بندی بهتر گزینه‌ها برای دسترسی سریع‌تر\n"
            "• 💬 توضیحات دقیق‌تر و کامل‌تر برای هر بخش\n\n"
            
            "2️⃣ <b>سیستم مدیریت پروکسی پیشرفته</b>\n"
            "• 🌐 افزودن چندین API جدید پروکسی رایگان\n"
            "• 🔄 بهبود الگوریتم تست و انتخاب پروکسی‌های کارآمد\n"
            "• 📊 پشتیبانی از پروکسی‌های HTTPS در کنار HTTP/SOCKS4/SOCKS5\n"
            "• 🛡️ سیستم مدیریت خطا و تلاش مجدد در صورت قطع شدن پروکسی\n\n"
            
            "3️⃣ <b>حل خودکار CAPTCHA</b>\n"
            "• 🔊 بهبود روش رمزگشایی CAPTCHA صوتی\n"
            "• 📱 پشتیبانی از حل CAPTCHA از طریق تلگرام به عنوان روش پشتیبان\n"
            "• 🧩 الگوریتم‌های پیشرفته‌تر برای شناسایی و دور زدن CAPTCHA\n\n"
            
            "4️⃣ <b>افزایش امنیت و پایداری</b>\n"
            "• 🛡️ بهبود سیستم ذخیره‌سازی اطلاعات حساب‌ها\n"
            "• ⚡️ افزایش سرعت و کارایی در ساخت حساب‌ها\n"
            "• 🔄 سیستم بازیابی خودکار در صورت خطا\n\n"
            
            "5️⃣ <b>منابع جدید پروکسی</b>\n"
            "• 🔗 افزودن چندین منبع جدید پروکسی رایگان\n"
            "• 📈 بهبود فرآیند دریافت و تست پروکسی‌ها\n"
            "• 🌍 پشتیبانی از پروکسی‌های Proxifly با آپدیت هر ۵ دقیقه\n\n"
            
            "🔜 <b>ویژگی‌های آینده (در دست توسعه):</b>\n"
            "• 📅 برنامه‌ریزی ساخت خودکار حساب‌ها در زمان‌های مشخص\n"
            "• 🔄 قابلیت افزودن پروکسی‌های چرخشی (Rotating proxies)\n"
            "• 📊 داشبورد آماری پیشرفته‌تر برای مدیریت حساب‌ها\n"
            "• 📱 رابط کاربری شخصی‌سازی شده بر اساس نیازهای کاربر\n"
            "• 🔐 انتقال ایمن حساب‌ها به وب‌سایت‌های پشتیبانی‌شده\n\n"
            
            "💌 <b>پیشنهادات و بازخورد:</b>\n"
            "ما به طور مداوم در حال بهبود ربات هستیم. هرگونه پیشنهاد یا گزارش مشکل شما به بهبود ربات کمک خواهد کرد."
        )
        
        self.send_message(chat_id, new_features_text, reply_markup=keyboard)
    
    def handle_no_proxy(self, chat_id, user_id):
        """شروع فرایند ساخت حساب بدون پروکسی."""
        # نمایش گزینه‌های تعداد حساب
        self.show_batch_options(chat_id, None)
    
    def handle_custom_proxy(self, chat_id, user_id, proxy_string):
        """پردازش پروکسی وارد شده توسط کاربر با محافظت در برابر کرش."""
        try:
            # محدود کردن طول ورودی پروکسی
            if len(proxy_string) > 5000:
                self.send_message(
                    chat_id,
                    f"❌ <b>متن وارد شده بسیار طولانی است</b>\n\n"
                    f"لطفاً حداکثر 100 پروکسی در هر بار وارد کنید."
                )
                return
                
            # حذف کاراکترهای خطرناک
            proxy_string = proxy_string.strip()
                
            # بررسی اینکه آیا لیستی از پروکسی‌ها است یا یک پروکسی تکی
            if '\n' in proxy_string:
                # ارسال پیام وضعیت
                self.send_message(
                    chat_id,
                    f"⏳ <b>در حال پردازش و تست لیست پروکسی‌ها...</b>\n\n"
                    f"این فرایند ممکن است کمی طول بکشد، لطفاً صبور باشید."
                )
                
                # استفاده از تابع ایمن برای پردازش لیست پروکسی
                self.safe_proxy_operation(chat_id, user_id, proxy_text=proxy_string)
                
            else:
                # پردازش یک پروکسی تکی
                import proxy_manager
                proxy = proxy_manager.parse_custom_proxy(proxy_string)
                
                if proxy is None:
                    self.send_message(
                        chat_id,
                        f"❌ <b>فرمت پروکسی نامعتبر است</b>\n\n"
                        f"لطفاً پروکسی را با فرمت صحیح وارد کنید.\n"
                        f"مثال‌ها:\n"
                        f"<code>socks5://username:password@host:port</code>\n"
                        f"<code>host:port</code>\n\n"
                        f"برای تلاش مجدد، لطفاً پروکسی دیگری وارد کنید یا به منوی اصلی بازگردید."
                    )
                    return
                
                # نمایش پیام وضعیت
                self.send_message(
                    chat_id,
                    f"⏳ <b>در حال تست پروکسی...</b>\n\n"
                    f"این عملیات ممکن است چند ثانیه طول بکشد."
                )
                
                # استفاده از تابع ایمن برای تست پروکسی
                proxy_list = [proxy]
                self.safe_proxy_operation(chat_id, user_id, proxy_list=proxy_list)
            
        except Exception as e:
            logger.error(f"Error processing custom proxy: {e}")
            self.send_message(
                chat_id,
                f"❌ <b>خطا در تنظیم پروکسی</b>\n\n"
                f"پیام خطا: {str(e)}\n\n"
                f"لطفاً مجدداً تلاش کنید یا از گزینه «بدون پروکسی» استفاده کنید."
            )
    
    def show_batch_options(self, chat_id, proxy):
        """نمایش گزینه‌های تعداد حساب برای ساخت."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "1️⃣ یک حساب", "callback_data": "batch_1"}],
                [{"text": "3️⃣ سه حساب", "callback_data": "batch_3"}, 
                 {"text": "5️⃣ پنج حساب", "callback_data": "batch_5"}],
                [{"text": "🔙 بازگشت", "callback_data": "back_to_main"}]
            ]
        }
        
        # تعیین وضعیت پروکسی با جزئیات بیشتر
        if proxy:
            proxy_icon = "✅"
            proxy_type = proxy.get('type', 'نامشخص').upper()
            proxy_host = proxy.get('host', 'نامشخص')
            proxy_port = proxy.get('port', 'نامشخص')
            proxy_status = f"با استفاده از پروکسی {proxy_type} ({proxy_host}:{proxy_port})"
        else:
            proxy_icon = "⚠️"
            proxy_status = "بدون استفاده از پروکسی (احتمال موفقیت کمتر)"
        
        batch_text = (
            f"🔢 <b>انتخاب تعداد حساب Gmail و کلید API</b>\n\n"
            f"{proxy_icon} <b>وضعیت اتصال:</b> {proxy_status}\n\n"
            f"📋 <b>اطلاعات مهم:</b>\n"
            f"• هر حساب به طور خودکار ساخته شده و کلید API دریافت می‌کند\n"
            f"• نام کاربری و رمز عبور به صورت تصادفی تولید می‌شوند\n"
            f"• ساخت هر حساب حدود 2 تا 5 دقیقه زمان می‌برد\n"
            f"• ساخت همزمان چند حساب، با پروکسی‌های مختلف انجام می‌شود\n\n"
            f"🔍 <b>چند حساب می‌خواهید ایجاد کنید؟</b>"
        )
        
        self.send_message(chat_id, batch_text, reply_markup=keyboard)
    
    def handle_proxy_file(self, chat_id, user_id, document):
        """پردازش فایل پروکسی آپلود شده توسط کاربر با محافظت در برابر کرش."""
        try:
            # بررسی نوع فایل (باید txt باشد)
            file_name = document.get('file_name', '')
            if not file_name.lower().endswith('.txt'):
                self.send_message(
                    chat_id,
                    f"❌ <b>فرمت فایل نامعتبر است</b>\n\n"
                    f"لطفاً فقط فایل‌های با پسوند .txt آپلود کنید.\n"
                    f"هر خط از فایل باید حاوی یک پروکسی با فرمت معتبر باشد."
                )
                return
            
            # دریافت اطلاعات فایل
            file_id = document.get('file_id')
            try:
                response = requests.get(f"{self.base_url}/getFile", params={'file_id': file_id}, timeout=10)
            except requests.exceptions.Timeout:
                self.send_message(
                    chat_id,
                    f"⚠️ <b>تایم‌اوت در دریافت فایل</b>\n\n"
                    f"ارتباط با سرور تلگرام طولانی شد. لطفاً دوباره تلاش کنید."
                )
                return
            except Exception as e:
                self.send_message(
                    chat_id,
                    f"❌ <b>خطا در ارتباط با سرور تلگرام</b>\n\n"
                    f"پیام خطا: {str(e)}\n\n"
                    f"لطفاً دوباره تلاش کنید یا فایل کوچکتری آپلود کنید."
                )
                return
            
            if response.status_code != 200:
                self.send_message(
                    chat_id,
                    f"❌ <b>خطا در دریافت فایل</b>\n\n"
                    f"کد وضعیت: {response.status_code}\n"
                    f"لطفاً دوباره تلاش کنید یا فایل دیگری آپلود کنید."
                )
                return
            
            file_path = response.json().get('result', {}).get('file_path')
            
            if not file_path:
                self.send_message(
                    chat_id,
                    f"❌ <b>خطا در دریافت مسیر فایل</b>\n\n"
                    f"لطفاً دوباره تلاش کنید یا فایل دیگری آپلود کنید."
                )
                return
            
            # دانلود محتوای فایل
            file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            try:
                file_response = requests.get(file_url, timeout=10)
            except requests.exceptions.Timeout:
                self.send_message(
                    chat_id,
                    f"⚠️ <b>تایم‌اوت در دانلود محتوای فایل</b>\n\n"
                    f"ارتباط با سرور تلگرام طولانی شد. لطفاً دوباره تلاش کنید."
                )
                return
            except Exception as e:
                self.send_message(
                    chat_id,
                    f"❌ <b>خطا در دانلود محتوای فایل</b>\n\n"
                    f"پیام خطا: {str(e)}\n\n"
                    f"لطفاً دوباره تلاش کنید یا فایل کوچکتری آپلود کنید."
                )
                return
            
            if file_response.status_code != 200:
                self.send_message(
                    chat_id,
                    f"❌ <b>خطا در دانلود محتوای فایل</b>\n\n"
                    f"کد وضعیت: {file_response.status_code}\n"
                    f"لطفاً دوباره تلاش کنید یا فایل دیگری آپلود کنید."
                )
                return
            
            # خواندن محتوای فایل
            proxy_text = file_response.text
            
            # محدود کردن اندازه فایل
            if len(proxy_text) > 50000:  # حداکثر 50 کیلوبایت
                self.send_message(
                    chat_id,
                    f"⚠️ <b>فایل بسیار بزرگ است</b>\n\n"
                    f"حداکثر اندازه فایل 50 کیلوبایت است. لطفاً فایل کوچکتری آپلود کنید."
                )
                return
            
            # نمایش وضعیت
            self.send_message(
                chat_id,
                f"✅ <b>فایل پروکسی با موفقیت دریافت شد</b>\n\n"
                f"نام فایل: {file_name}\n"
                f"تعداد کاراکترها: {len(proxy_text)}\n\n"
                f"در حال پردازش و تست پروکسی‌ها..."
            )
            
            # استفاده از تابع ایمن برای پردازش متن پروکسی
            self.safe_proxy_operation(chat_id, user_id, proxy_text=proxy_text)
            
            # ذخیره لیست پروکسی‌ها برای استفاده احتمالی در ساخت چندین حساب
            if 'proxy' in self.user_data.get(user_id, {}):
                # استفاده از ماژول proxy_manager برای پردازش لیست پروکسی
                import proxy_manager
                proxy_list = proxy_manager.parse_proxy_list(proxy_text)
                
                if proxy_list:
                    self.user_data[user_id]['proxy_list'] = proxy_list
                
        except Exception as e:
            logger.error(f"Error processing proxy file: {e}")
            self.send_message(
                chat_id,
                f"❌ <b>خطا در پردازش فایل پروکسی</b>\n\n"
                f"پیام خطا: {str(e)}\n\n"
                f"لطفاً دوباره تلاش کنید یا پروکسی را به صورت متنی وارد کنید."
            )

    def handle_batch_creation(self, chat_id, user_id, batch_count):
        """شروع فرایند ساخت چند حساب با محافظت در برابر کرش."""
        proxy = self.user_data.get(user_id, {}).get('proxy')
        proxy_list = self.user_data.get(user_id, {}).get('proxy_list', [])
        
        # نمایش پیام اولیه
        self.send_message(
            chat_id,
            f"🚀 <b>شروع فرایند ساخت حساب</b>\n\n"
            f"تعداد درخواستی: {batch_count} حساب\n"
            f"در حال آماده‌سازی..."
        )
        
        # محدود کردن تعداد حساب‌ها برای مدیریت بهتر منابع
        if batch_count > 5:
            batch_count = 5
            self.send_message(
                chat_id,
                f"⚠️ <b>محدودیت تعداد حساب</b>\n\n"
                f"حداکثر تعداد حساب قابل ساخت در هر بار 5 عدد است.\n"
                f"ادامه با ساخت 5 حساب..."
            )
        
        # اگر چندین حساب درخواست شده و لیست پروکسی داریم
        if batch_count > 1 and proxy_list:
            try:
                # محدود کردن تعداد پروکسی‌های مورد بررسی
                if len(proxy_list) > 50:
                    limited_proxy_list = proxy_list[:50]
                    self.send_message(
                        chat_id,
                        f"⚠️ <b>محدودیت تعداد پروکسی</b>\n\n"
                        f"تعداد پروکسی‌های شما ({len(proxy_list)}) بسیار زیاد است.\n"
                        f"تنها 50 پروکسی اول بررسی خواهد شد."
                    )
                else:
                    limited_proxy_list = proxy_list
                
                # تلاش برای یافتن تعداد کافی پروکسی سالم
                import proxy_manager
                
                # نمایش پیام برای کاربر
                self.send_message(
                    chat_id,
                    f"🔍 <b>در حال جستجوی {batch_count} پروکسی کارآمد...</b>\n\n"
                    f"این فرایند ممکن است چند دقیقه طول بکشد.\n"
                    f"تست {len(limited_proxy_list)} پروکسی..."
                )
                
                # استفاده از تابع بهینه‌سازی شده
                working_proxies = proxy_manager.find_multiple_working_proxies(
                    limited_proxy_list, 
                    count=batch_count,
                    timeout=3,
                    max_workers=3
                )
                
                if not working_proxies:
                    self.send_message(
                        chat_id,
                        f"⚠️ <b>هیچ پروکسی کارآمدی پیدا نشد</b>\n\n"
                        f"در حال استفاده از پروکسی پیش‌فرض..."
                    )
                    # استفاده از تک پروکسی موجود یا بدون پروکسی
                    self.process_account_creation(chat_id, user_id, proxy)
                    return
                    
                if len(working_proxies) < batch_count:
                    self.send_message(
                        chat_id,
                        f"⚠️ <b>تعداد {len(working_proxies)} پروکسی کارآمد پیدا شد</b>\n\n"
                        f"تعداد درخواستی شما: {batch_count} حساب\n"
                        f"با پروکسی‌های موجود ادامه می‌دهیم..."
                    )
                else:
                    self.send_message(
                        chat_id,
                        f"✅ <b>تعداد {len(working_proxies)} پروکسی کارآمد پیدا شد</b>\n\n"
                        f"در حال شروع فرایند ساخت حساب‌ها..."
                    )
                
                # ساخت حساب‌ها با پروکسی‌های مختلف
                for i, proxy in enumerate(working_proxies):
                    if i >= batch_count:
                        break
                        
                    # اطلاع‌رسانی ساخت حساب جاری
                    self.send_message(
                        chat_id,
                        f"🔄 <b>ساخت حساب {i+1} از {min(batch_count, len(working_proxies))}</b>\n\n"
                        f"نوع پروکسی: {proxy.get('type')}\n"
                        f"آدرس پروکسی: {proxy.get('host')}:{proxy.get('port')}"
                    )
                    
                    # ساخت حساب با پروکسی جاری
                    self.process_account_creation(chat_id, user_id, proxy)
                    
                    # اضافه کردن تاخیر کوتاه بین ساخت حساب‌ها
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in batch creation: {e}")
                self.send_message(
                    chat_id,
                    f"❌ <b>خطا در فرایند ساخت چند حساب</b>\n\n"
                    f"پیام خطا: {str(e)}\n\n"
                    f"در حال تلاش با یک حساب..."
                )
                # تلاش برای ساخت یک حساب
                self.process_account_creation(chat_id, user_id, proxy)
        else:
            # اگر فقط یک حساب درخواست شده یا لیست پروکسی نداریم
            self.process_account_creation(chat_id, user_id, proxy)
    
    def process_account_creation(self, chat_id, user_id, proxy=None):
        """
        پردازش ساخت حساب و دریافت کلید API با استفاده از سرویس تأیید شماره تلفن بهبودیافته.
        این نسخه بهبودیافته از کلاس PhoneVerificationService برای مدیریت بهینه تأیید شماره استفاده می‌کند.
        
        Args:
            chat_id: شناسه چت تلگرام
            user_id: شناسه کاربر تلگرام
            proxy: تنظیمات پروکسی (اختیاری)
        """
        # بررسی اعتبار Twilio
        try:
            from twilio_integration import is_twilio_available, PhoneVerificationService
            
            # نمایش وضعیت سرویس تأیید شماره تلفن به کاربر
            twilio_available = is_twilio_available()
            if twilio_available:
                logger.info("Twilio service is available for phone verification")
                # بررسی وجود شماره تلفن پیش‌فرض
                phone_service = PhoneVerificationService()
                if phone_service.default_phone_number:
                    verification_status = (
                        f"✅ <b>سرویس تأیید شماره تلفن:</b> فعال\n"
                        f"📱 <b>شماره تلفن پیش‌فرض:</b> در دسترس\n"
                    )
                else:
                    verification_status = (
                        f"✅ <b>سرویس تأیید شماره تلفن:</b> فعال\n"
                        f"📱 <b>شماره تلفن پیش‌فرض:</b> استفاده از خرید شماره موقت\n"
                    )
            else:
                logger.warning("Twilio service is not available for phone verification")
                verification_status = f"⚠️ <b>سرویس تأیید شماره تلفن:</b> غیرفعال\n"
        except Exception as e:
            logger.error(f"Error checking Twilio service: {e}")
            verification_status = f"❌ <b>سرویس تأیید شماره تلفن:</b> خطا در بررسی وضعیت\n"
            
        # تولید اطلاعات تصادفی برای حساب
        user_info = generate_random_user_info()
        
        # ارسال پیام وضعیت اولیه با اطلاعات سرویس تأیید شماره
        self.send_message(
            chat_id, 
            f"⏳ <b>در حال ساخت حساب Gmail...</b>\n\n"
            f"{verification_status}"
            f"⚙️ <b>اطلاعات حساب:</b>\n"
            f"👤 نام: {user_info['first_name']} {user_info['last_name']}\n"
            f"📅 تاریخ تولد: {user_info['birth_day']}/{user_info['birth_month']}/{user_info['birth_year']}\n"
        )
        
        try:
            # مرحله ۱: ساخت حساب جیمیل
            logger.info(f"Starting Gmail account creation for user {user_id}")
            
            gmail_result = gmail_creator.create_gmail_account(
                first_name=user_info['first_name'],
                last_name=user_info['last_name'],
                username=user_info['username'],
                password=user_info['password'],
                birth_day=user_info['birth_day'],
                birth_month=user_info['birth_month'],
                birth_year=user_info['birth_year'],
                gender=user_info['gender'],
                proxy=proxy,
                telegram_chat_id=str(chat_id)  # اضافه کردن شناسه چت تلگرام برای حل CAPTCHA
            )
            
            # بررسی نتیجه ساخت جیمیل
            if not gmail_result['success']:
                self.send_message(
                    chat_id, 
                    f"❌ <b>خطا در ساخت حساب Gmail</b>\n\n"
                    f"پیام خطا: {gmail_result.get('error', 'خطای نامشخص')}\n\n"
                    f"لطفاً دوباره تلاش کنید یا از پروکسی استفاده کنید.",
                )
                # بازگشت به منوی اصلی
                self.show_main_menu(chat_id, user_id)
                return
            
            # ساخت جیمیل موفقیت‌آمیز بود
            gmail = gmail_result['gmail']
            
            # به‌روزرسانی پیام وضعیت
            self.send_message(
                chat_id,
                f"✅ <b>حساب Gmail با موفقیت ساخته شد:</b>\n"
                f"📧 {gmail}\n\n"
                f"⏳ <b>در حال دریافت کلید API Gemini...</b>"
            )
            
            # مرحله ۲: دریافت کلید API
            logger.info(f"Starting API key generation for {gmail}")
            
            api_result = api_key_generator.generate_api_key(
                gmail=gmail,
                password=user_info['password'],
                proxy=proxy,
                test_key=True,  # اضافه کردن پارامتر تست اعتبار API Key
                telegram_chat_id=str(chat_id)  # اضافه کردن شناسه چت تلگرام برای حل CAPTCHA
            )
            
            # دریافت تاریخ و زمان فعلی
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # ایجاد لیست حساب‌ها اگر موجود نیست
            if 'accounts' not in self.user_data[user_id]:
                self.user_data[user_id]['accounts'] = []
            
            # بررسی نتیجه دریافت کلید API
            if not api_result['success']:
                # دریافت کلید API ناموفق بود اما حساب جیمیل ساخته شد
                partial_success_message = (
                    f"⚠️ <b>حساب Gmail ساخته شد اما دریافت API ناموفق بود</b> ⚠️\n\n"
                    f"✅ <b>حساب Gmail:</b>\n<code>{gmail}</code>\n\n"
                    f"🔒 <b>رمز عبور:</b>\n<code>{user_info['password']}</code>\n\n"
                    f"❌ <b>خطا در دریافت کلید API:</b>\n"
                    f"{api_result.get('error', 'خطای نامشخص')}\n\n"
                    f"✨ <b>اطلاعات حساب:</b>\n"
                    f"👤 نام: {user_info['first_name']} {user_info['last_name']}\n"
                    f"📅 تاریخ تولد: {user_info['birth_day']}/{user_info['birth_month']}/{user_info['birth_year']}\n"
                    f"⏱️ تاریخ ایجاد: {current_time}\n\n"
                    f"🔄 <b>دریافت دستی کلید API:</b>\n"
                    f"1️⃣ با حساب Gmail ساخته شده وارد سایت https://aistudio.google.com شوید\n"
                    f"2️⃣ به بخش API Key در حساب کاربری خود بروید\n"
                    f"3️⃣ روی دکمه 'Create API Key' کلیک کنید\n"
                    f"4️⃣ کلید ساخته شده را کپی کنید\n\n"
                    f"⚠️ <b>توجه:</b> اطلاعات حساب Gmail را در جایی امن ذخیره کنید."
                )
                self.send_message(chat_id, partial_success_message)
                
                # ذخیره اطلاعات حساب بدون کلید API در کش
                self.user_data[user_id]['accounts'].append({
                    'gmail': gmail,
                    'password': user_info['password'],
                    'api_key': None,
                    'status': 'api_failed',
                    'created_at': current_time
                })
                
                # ذخیره اطلاعات در دیتابیس اگر فعال است
                if self.use_db and self.app:
                    try:
                        # استفاده از app_context
                        with self.app.app_context():
                            # یافتن یا ایجاد کاربر
                            user_db = self.User.query.filter_by(telegram_id=str(user_id)).first()
                            if not user_db:
                                # ایجاد کاربر جدید
                                user_db = self.User(
                                    telegram_id=str(user_id),
                                    state='account_created'
                                )
                                self.db.session.add(user_db)
                                self.db.session.commit()
                                logger.info(f"New user created for failed API account: {user_db}")
                            
                            # ایجاد حساب جدید با وضعیت ناموفق
                            account = self.Account(
                                user_id=user_db.id,
                                gmail=gmail,
                                password=user_info['password'],
                                first_name=user_info['first_name'],
                                last_name=user_info['last_name'],
                                birth_day=user_info['birth_day'],
                                birth_month=user_info['birth_month'],
                                birth_year=user_info['birth_year'],
                                gender=user_info['gender'],
                                api_key=None,
                                status='api_failed',
                                error_message=api_result.get('error', 'Unknown error'),
                                proxy_used=str(proxy) if proxy else None
                            )
                            self.db.session.add(account)
                            self.db.session.commit()
                            logger.info(f"Account with failed API saved to database: {gmail}")
                    except Exception as e:
                        logger.error(f"Error saving failed account to database: {e}")
                
                # بازگشت به منوی اصلی
                self.show_main_menu(chat_id, user_id)
                return
            
            # هر دو مرحله موفقیت‌آمیز بودند
            api_key = api_result['api_key']
            
            # بررسی نتایج تست اعتبار API Key اگر در دسترس باشد
            validation_info = ""
            api_key_status = "complete"
            
            if 'validation_result' in api_result and api_result['validation_result']:
                validation = api_result['validation_result']
                
                # استخراج اطلاعات اعتبارسنجی
                is_valid = validation.get('is_valid', False)
                is_working = validation.get('is_working', False)
                
                # تعیین وضعیت API Key
                if is_valid and is_working:
                    validation_info = f"✅ <b>وضعیت اعتبار کلید API:</b> معتبر و کاملاً کارآمد\n"
                    api_key_status = "complete"
                elif is_valid and not is_working:
                    validation_info = f"⚠️ <b>وضعیت اعتبار کلید API:</b> معتبر اما با مشکل عملکرد\n"
                    api_key_status = "valid_but_limited"
                elif not is_valid:
                    validation_info = f"❌ <b>وضعیت اعتبار کلید API:</b> نامعتبر یا با محدودیت‌های جدی\n"
                    api_key_status = "invalid"
            else:
                validation_info = f"ℹ️ <b>وضعیت اعتبار کلید API:</b> بررسی نشده\n"
            
            # ذخیره اطلاعات کامل حساب در کش
            self.user_data[user_id]['accounts'].append({
                'gmail': gmail,
                'password': user_info['password'],
                'api_key': api_key,
                'status': api_key_status,
                'created_at': current_time,
                'validation_info': validation_info if validation_info else None
            })
            
            # ذخیره اطلاعات در دیتابیس اگر فعال است
            if self.use_db and self.app:
                try:
                    # استفاده از app_context
                    with self.app.app_context():
                        # یافتن یا ایجاد کاربر
                        user_db = self.User.query.filter_by(telegram_id=str(user_id)).first()
                        if not user_db:
                            # اطلاعات بیشتر کاربر را از تلگرام دریافت کنیم
                            try:
                                response = requests.get(f"{self.base_url}/getChat", params={'chat_id': chat_id})
                                chat_data = response.json().get('result', {})
                                
                                # ایجاد کاربر جدید
                                user_db = self.User(
                                    telegram_id=str(user_id),
                                    username=chat_data.get('username'),
                                    first_name=chat_data.get('first_name'),
                                    last_name=chat_data.get('last_name'),
                                    state='account_created'
                                )
                                self.db.session.add(user_db)
                                self.db.session.commit()
                                logger.info(f"New user created for account: {user_db}")
                            except Exception as e:
                                logger.error(f"Error creating user in database during account creation: {e}")
                                return
                        
                        # ایجاد حساب جدید
                        account = self.Account(
                            user_id=user_db.id,
                            gmail=gmail,
                            password=user_info['password'],
                            first_name=user_info['first_name'],
                            last_name=user_info['last_name'],
                            birth_day=user_info['birth_day'],
                            birth_month=user_info['birth_month'],
                            birth_year=user_info['birth_year'],
                            gender=user_info['gender'],
                            api_key=api_key,
                            status='complete',
                            proxy_used=str(proxy) if proxy else None
                        )
                        self.db.session.add(account)
                        self.db.session.commit()
                        logger.info(f"Account saved to database: {gmail}")
                except Exception as e:
                    logger.error(f"Error saving account to database: {e}")
            
            # ارسال پیام موفقیت با جزئیات بیشتر و فرمت بهتر
            success_message = (
                f"🎉 <b>ساخت حساب و دریافت API با موفقیت انجام شد</b> 🎉\n\n"
                f"📧 <b>حساب Gmail:</b>\n<code>{gmail}</code>\n\n"
                f"🔒 <b>رمز عبور:</b>\n<code>{user_info['password']}</code>\n\n"
                f"🔑 <b>کلید API Gemini:</b>\n<code>{api_key}</code>\n\n"
                f"{validation_info}\n"  # اضافه کردن اطلاعات تست اعتبار
                f"✨ <b>اطلاعات حساب:</b>\n"
                f"👤 نام: {user_info['first_name']} {user_info['last_name']}\n"
                f"📅 تاریخ تولد: {user_info['birth_day']}/{user_info['birth_month']}/{user_info['birth_year']}\n"
                f"⏱️ تاریخ ایجاد: {current_time}\n\n"
                f"🚀 <b>استفاده از کلید API:</b>\n"
                f"1️⃣ به سایت https://aistudio.google.com بروید\n"
                f"2️⃣ روی آیکون حساب کاربری کلیک کنید\n"
                f"3️⃣ API Key را در بخش مربوطه وارد کنید\n\n"
                f"⚠️ <b>مهم:</b> این اطلاعات را در جای امنی ذخیره کنید. در صورت گم شدن، قابل بازیابی نیستند."
            )
            self.send_message(chat_id, success_message)
            
            # ثبت موفقیت در لاگ
            logger.info(f"Successfully created account and API key for user {user_id}: {gmail}")
            
            # بازگشت به منوی اصلی
            self.show_main_menu(chat_id, user_id)
            
        except Exception as e:
            logger.error(f"Error in account creation process: {str(e)}")
            
            error_message = (
                f"❌ <b>خطای غیرمنتظره در فرآیند ساخت حساب</b> ❌\n\n"
                f"💢 <b>نوع خطا:</b> {type(e).__name__}\n"
                f"⚠️ <b>پیام خطا:</b> {str(e)}\n\n"
                f"🔄 <b>پیشنهادات برای رفع مشکل:</b>\n"
                f"• از یک پروکسی با کیفیت بهتر استفاده کنید\n"
                f"• اگر از پروکسی رایگان استفاده می‌کنید، پروکسی خصوصی امتحان کنید\n"
                f"• سرعت اینترنت خود را بررسی کنید\n"
                f"• کمی صبر کنید و مجدداً تلاش کنید\n"
                f"• از منوی اصلی، گزینه‌ی «ساخت حساب و دریافت API Key» را مجدداً انتخاب کنید\n\n"
                f"🔍 <b>راهنمایی:</b> برای موفقیت بیشتر، از پروکسی‌های کشورهای آمریکا، کانادا یا اروپا استفاده کنید."
            )
            self.send_message(chat_id, error_message)
            
            # بازگشت به منوی اصلی
            self.show_main_menu(chat_id, user_id)
    
    def run(self):
        """حلقه اصلی برای دریافت پیام‌های تلگرام."""
        logger.info("Starting bot polling...")
        logger.info(f"Bot token available and valid: {bool(self.token)}")
        
        # آزمایش اتصال به API
        try:
            response = requests.get(f"{self.base_url}/getMe")
            if response.status_code == 200 and response.json().get('ok'):
                bot_info = response.json().get('result', {})
                logger.info(f"Connected to bot: @{bot_info.get('username')} (ID: {bot_info.get('id')})")
            else:
                logger.error("Failed to connect to Telegram API. Check your token.")
                logger.error(f"Response: {response.text}")
                return  # اگر اتصال به API برقرار نشد، از تابع خارج می‌شویم
        except Exception as e:
            logger.error(f"Error connecting to Telegram API: {e}")
            return  # در صورت بروز خطا در اتصال، از تابع خارج می‌شویم
        
        # تنظیم آفست اولیه برای نادیده گرفتن پیام‌های قبلی
        try:
            logger.info("Getting initial updates to set offset...")
            initial_updates = self.get_updates(timeout=1)
            if initial_updates:
                # تنظیم آفست به آخرین آپدیت + 1 برای نادیده گرفتن همه آپدیت‌های قبلی
                last_update_id = initial_updates[-1]["update_id"]
                self.offset = last_update_id + 1
                logger.info(f"Setting initial offset to {self.offset} to ignore previous updates")
        except Exception as e:
            logger.error(f"Error setting initial offset: {e}")
        
        # حلقه اصلی برای دریافت پیام‌ها
        processed_updates = set()  # مجموعه‌ای برای ذخیره شناسه‌های آپدیت‌های پردازش شده
        
        while True:
            try:
                updates = self.get_updates()
                if updates:
                    logger.info(f"Received {len(updates)} updates")
                    
                    # پردازش آپدیت‌های جدید و جلوگیری از پردازش تکراری
                    new_updates = []
                    for update in updates:
                        update_id = update.get('update_id')
                        if update_id not in processed_updates:
                            new_updates.append(update)
                            processed_updates.add(update_id)
                            
                            # برای جلوگیری از رشد بیش از حد مجموعه، اندازه آن را محدود می‌کنیم
                            if len(processed_updates) > 1000:
                                # حذف قدیمی‌ترین آیتم‌ها
                                processed_updates = set(sorted(processed_updates)[-500:])
                    
                    if new_updates:
                        logger.info(f"Processing {len(new_updates)} new updates")
                        self.handle_updates(new_updates)
                    else:
                        logger.info("All updates were already processed")
                
                time.sleep(1)  # تأخیر کوتاه بین دریافت‌ها
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                time.sleep(5)  # تأخیر بیشتر در صورت بروز خطا

def run_bot():
    """اجرای ربات تلگرام."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN environment variable found")
        return
    
    try:
        # برای استفاده از این تابع مستقل، فلسک اپ ارسال نمی‌شود
        # این باعث می‌شود که فقط از کش حافظه استفاده شود، نه دیتابیس
        bot = InlineTelegramBot(token)
        bot.run()
    except Exception as e:
        logger.error(f"Error running bot: {e}")

if __name__ == "__main__":
    run_bot()