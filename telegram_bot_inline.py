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
    def __init__(self, token=None):
        """Initialize the bot with Telegram Bot API token."""
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("No bot token provided")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.user_data = {}  # Cache for user data during runtime
        
        # Try to import database models
        try:
            # Import Flask app context
            try:
                from flask import current_app
                from main import db
                from models import User, Account
                
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
                    elif data.startswith('batch_'):
                        # پردازش گزینه‌های تعداد اکانت برای ساخت
                        try:
                            batch_count = int(data.split('_')[1])
                            self.handle_batch_creation(chat_id, user_id, batch_count)
                        except (ValueError, IndexError) as e:
                            logger.error(f"Error processing batch count: {e}")
                
                # اگر پیام متنی است
                elif 'message' in update and 'text' in update['message']:
                    message = update['message']
                    chat_id = message['chat']['id']
                    user_id = message['from']['id']
                    text = message['text']
                    
                    # اطلاعات کاربر را ذخیره می‌کنیم اگر موجود نیست
                    if user_id not in self.user_data:
                        self.user_data[user_id] = {'chat_id': chat_id}
                    
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
                
            except Exception as e:
                logger.error(f"Error handling update: {e}")
    
    def show_main_menu(self, chat_id, user_id):
        """نمایش منوی اصلی با دکمه‌های شیشه‌ای."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔑 ساخت حساب و دریافت API Key", "callback_data": "create_account"}],
                [{"text": "📊 وضعیت حساب‌ها", "callback_data": "status"}, 
                 {"text": "❓ راهنما", "callback_data": "help"}],
                [{"text": "ℹ️ درباره ربات", "callback_data": "about"}]
            ]
        }
        
        welcome_text = (
            "👋 <b>به ربات ساخت حساب Gmail و دریافت کلید API Gemini خوش آمدید!</b>\n\n"
            "🌟 <b>امکانات ربات:</b>\n"
            "• 📧 ساخت خودکار حساب جیمیل\n"
            "• 🔑 دریافت کلید API گوگل جمینی\n"
            "• 🌐 پشتیبانی از پروکسی\n"
            "• 📊 مدیریت حساب‌ها\n\n"
            "👇 از منوی زیر گزینه مورد نظر خود را انتخاب کنید:"
        )
        
        self.send_message(chat_id, welcome_text, reply_markup=keyboard)
    
    def handle_start(self, chat_id, user_id):
        """پردازش دستور /start."""
        # ذخیره اطلاعات کاربر در دیتابیس اگر موجود نیست
        if self.use_db:
            try:
                from flask import current_app
                with current_app.app_context():
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
            "📚 <b>راهنمای استفاده از ربات</b>\n\n"
            "🔹 <b>دستورات اصلی:</b>\n"
            "/start - شروع کار با ربات و نمایش منوی اصلی\n"
            "/create - شروع فرآیند ساخت حساب Gmail و کلید API\n"
            "/status - بررسی وضعیت حساب‌های ساخته شده\n"
            "/help - نمایش این راهنما\n"
            "/about - اطلاعات درباره ربات\n\n"
            
            "🔹 <b>دستورات مرتبط با پروکسی:</b>\n"
            "/noproxy - ساخت حساب بدون استفاده از پروکسی\n"
            "/useproxy - ساخت حساب با پروکسی\n"
            "مثال: /useproxy socks5://user:pass@1.2.3.4:1080\n\n"
            
            "🔹 <b>نکات مهم:</b>\n"
            "• برای ساخت موفق حساب، استفاده از پروکسی توصیه می‌شود.\n"
            "• اطلاعات حساب‌های ساخته شده را در جای امنی ذخیره کنید.\n"
            "• در صورت بروز خطا، مجدداً تلاش کنید یا از پروکسی دیگری استفاده نمایید."
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
            "ℹ️ <b>درباره ربات</b>\n\n"
            "🤖 <b>نام:</b> ربات ساخت حساب Gmail و کلید API Gemini\n"
            "🔄 <b>نسخه:</b> 1.0.0\n\n"
            
            "🌟 <b>قابلیت‌ها:</b>\n"
            "• ساخت خودکار حساب Gmail\n"
            "• دریافت خودکار کلید API از Google AI Studio\n"
            "• پشتیبانی از پروکسی\n"
            "• مدیریت حساب‌ها و کلیدهای API\n\n"
            
            "⚙️ <b>فناوری‌ها:</b>\n"
            "• زبان برنامه‌نویسی Python\n"
            "• API تلگرام\n"
            "• شبیه‌سازی خودکار وب\n\n"
            
            "📝 <b>توضیحات:</b>\n"
            "این ربات به شما کمک می‌کند تا به‌صورت خودکار حساب‌های Gmail و کلیدهای API Gemini ایجاد کنید و از محدودیت‌های استفاده از یک حساب عبور کنید. برای عملکرد بهتر، استفاده از پروکسی توصیه می‌شود."
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
        if self.use_db:
            try:
                from flask import current_app
                with current_app.app_context():
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
        
        # اگر اطلاعاتی در دیتابیس نبود یا دیتابیس غیرفعال بود، از حافظه موقت استفاده کنیم
        if not accounts:
            accounts = self.user_data.get(user_id, {}).get('accounts', [])
        
        if not accounts:
            status_text = (
                "📭 <b>حسابی یافت نشد</b>\n\n"
                "شما تاکنون هیچ حسابی ایجاد نکرده‌اید.\n"
                "برای ساخت حساب جدید، از گزینه «ساخت حساب و دریافت API Key» استفاده کنید."
            )
            
            self.send_message(chat_id, status_text, reply_markup=keyboard)
            return
        
        status_text = "📊 <b>وضعیت حساب‌های شما</b>\n\n"
        
        for i, account in enumerate(accounts):
            status_icon = "✅" if account.get('status') == 'complete' else "❌"
            status_text += f"{i+1}. {status_icon} <b>{account.get('gmail')}</b>\n"
            status_text += f"   📅 تاریخ: {account.get('created_at', 'نامشخص')}\n"
            
            if account.get('api_key'):
                # نمایش بخشی از کلید API
                api_key = account.get('api_key')
                masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
                status_text += f"   🔑 API Key: <code>{masked_key}</code>\n"
            else:
                status_text += f"   ⚠️ کلید API: دریافت نشد\n"
            
            status_text += "\n"
        
        status_text += "برای دریافت کلید API کامل، با ربات تماس بگیرید."
        
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
        """پردازش URL API پروکسی وارد شده توسط کاربر."""
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
            
            # ارسال پیام وضعیت
            self.send_message(
                chat_id,
                f"⏳ <b>در حال دریافت و تست پروکسی‌ها از API...</b>\n\n"
                f"URL: <code>{api_url}</code>"
            )
            
            # دریافت پروکسی از API
            import proxy_manager
            proxy = proxy_manager.get_proxy_from_api_url(api_url)
            
            if proxy:
                self.user_data[user_id]['proxy'] = proxy
                
                # نمایش پیام موفقیت و گزینه‌های تعداد حساب
                self.send_message(
                    chat_id, 
                    f"✅ <b>پروکسی کارآمد از API دریافت شد</b>\n\n"
                    f"نوع: {proxy.get('type')}\n"
                    f"آدرس: {proxy.get('host')}:{proxy.get('port')}"
                )
                
                # نمایش گزینه‌های تعداد حساب
                self.show_batch_options(chat_id, proxy)
                
                # پاک کردن وضعیت
                self.user_data[user_id]['state'] = None
            else:
                self.send_message(
                    chat_id,
                    f"❌ <b>هیچ پروکسی کارآمدی از API دریافت نشد</b>\n\n"
                    f"لطفاً URL دیگری وارد کنید یا از گزینه «استفاده از پروکسی خودکار» استفاده کنید."
                )
        except Exception as e:
            logger.error(f"Error processing proxy API URL: {e}")
            self.send_message(
                chat_id,
                f"❌ <b>خطا در دریافت پروکسی از API</b>\n\n"
                f"پیام خطا: {str(e)}\n\n"
                f"لطفاً مجدداً تلاش کنید یا از گزینه «بدون پروکسی» استفاده کنید."
            )
    
    def show_proxy_resources(self, chat_id, user_id):
        """نمایش منابع پیشنهادی پروکسی."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به تنظیم پروکسی", "callback_data": "use_proxy"}]
            ]
        }
        
        # استفاده از اطلاعات منابع پروکسی از ماژول proxy_manager
        import proxy_manager
        
        # فرمت بندی متن برای تلگرام
        resources_text = proxy_manager.PROXY_RESOURCES_INFO.replace('## ', '<b>').replace('#', '</b>')
        resources_text = resources_text.replace('```', '<code>').replace('```', '</code>')
        # اصلاح نشانه‌گذاری HTML
        resources_text = resources_text.replace('<code>', '<code>').replace('</code>', '</code>')
        
        # ارسال پیام با منابع پروکسی
        self.send_message(
            chat_id,
            f"📚 <b>منابع پیشنهادی پروکسی</b>\n\n{resources_text}",
            reply_markup=keyboard
        )
    
    def handle_no_proxy(self, chat_id, user_id):
        """شروع فرایند ساخت حساب بدون پروکسی."""
        # نمایش گزینه‌های تعداد حساب
        self.show_batch_options(chat_id, None)
    
    def handle_custom_proxy(self, chat_id, user_id, proxy_string):
        """پردازش پروکسی وارد شده توسط کاربر."""
        try:
            # بررسی اینکه آیا لیستی از پروکسی‌ها است یا یک پروکسی تکی
            if '\n' in proxy_string:
                # ارسال پیام وضعیت
                self.send_message(
                    chat_id,
                    f"⏳ <b>در حال پردازش و تست لیست پروکسی‌ها...</b>"
                )
                
                # استفاده از ماژول proxy_manager برای پردازش لیست پروکسی
                proxy_list = proxy_manager.parse_proxy_list(proxy_string)
                
                if not proxy_list:
                    self.send_message(
                        chat_id,
                        f"❌ <b>هیچ پروکسی معتبری در لیست شما یافت نشد</b>\n\n"
                        f"لطفاً پروکسی‌ها را با فرمت صحیح وارد کنید.\n"
                        f"هر پروکسی باید در یک خط جداگانه باشد.\n"
                        f"مثال‌ها:\n"
                        f"<code>socks5://username:password@host:port</code>\n"
                        f"<code>host:port</code>\n\n"
                        f"برای تلاش مجدد، لطفاً لیست دیگری وارد کنید یا به منوی اصلی بازگردید."
                    )
                    return
                
                # اطلاع رسانی تعداد پروکسی‌ها
                self.send_message(
                    chat_id,
                    f"🔍 <b>تعداد {len(proxy_list)} پروکسی شناسایی شد.</b>\n"
                    f"در حال تست پروکسی‌ها یکی یکی..."
                )
                
                # یافتن اولین پروکسی کارآمد
                working_proxy = proxy_manager.find_working_proxy_from_list(proxy_list)
                
                if working_proxy:
                    self.user_data[user_id]['proxy'] = working_proxy
                    
                    # نمایش پیام موفقیت و گزینه‌های تعداد حساب
                    self.send_message(
                        chat_id, 
                        f"✅ <b>پروکسی کارآمد پیدا شد و با موفقیت تنظیم شد</b>\n\n"
                        f"نوع: {working_proxy.get('type')}\n"
                        f"آدرس: {working_proxy.get('host')}:{working_proxy.get('port')}"
                    )
                    
                    # نمایش گزینه‌های تعداد حساب
                    self.show_batch_options(chat_id, working_proxy)
                    
                    # پاک کردن وضعیت
                    self.user_data[user_id]['state'] = None
                else:
                    self.send_message(
                        chat_id,
                        f"❌ <b>هیچ پروکسی کارآمدی در لیست شما پیدا نشد</b>\n\n"
                        f"تمام {len(proxy_list)} پروکسی تست شد، اما هیچ کدام کارآمد نبودند.\n"
                        f"لطفاً لیست دیگری وارد کنید یا از گزینه «استفاده از پروکسی خودکار» استفاده کنید."
                    )
            else:
                # پردازش یک پروکسی تکی
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
                    f"⏳ <b>در حال تست پروکسی...</b>"
                )
                
                # تست پروکسی
                if proxy_manager.test_proxy(proxy):
                    self.user_data[user_id]['proxy'] = proxy
                    
                    # نمایش پیام موفقیت و گزینه‌های تعداد حساب
                    self.send_message(
                        chat_id, 
                        f"✅ <b>پروکسی با موفقیت تنظیم شد</b>\n\n"
                        f"نوع: {proxy.get('type')}\n"
                        f"آدرس: {proxy.get('host')}:{proxy.get('port')}"
                    )
                    
                    # نمایش گزینه‌های تعداد حساب
                    self.show_batch_options(chat_id, proxy)
                    
                    # پاک کردن وضعیت
                    self.user_data[user_id]['state'] = None
                else:
                    self.send_message(
                        chat_id,
                        f"❌ <b>پروکسی قابل استفاده نیست</b>\n\n"
                        f"لطفاً پروکسی دیگری وارد کنید یا از گزینه «استفاده از پروکسی خودکار» استفاده کنید."
                    )
            
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
        
        proxy_status = "با استفاده از پروکسی" if proxy else "بدون استفاده از پروکسی"
        
        batch_text = (
            f"🔢 <b>تعداد حساب</b>\n\n"
            f"حالت فعلی: <b>{proxy_status}</b>\n\n"
            f"چند حساب می‌خواهید ایجاد کنید؟"
        )
        
        self.send_message(chat_id, batch_text, reply_markup=keyboard)
    
    def handle_batch_creation(self, chat_id, user_id, batch_count):
        """شروع فرایند ساخت چند حساب."""
        # فعلاً فقط یک حساب می‌سازیم (پیاده‌سازی ساخت گروهی در نسخه‌های بعدی)
        proxy = self.user_data.get(user_id, {}).get('proxy')
        
        # نمایش پیام اولیه
        self.send_message(
            chat_id,
            f"🚀 <b>شروع فرایند ساخت حساب</b>\n\n"
            f"تعداد درخواستی: {batch_count} حساب\n"
            f"در حال آماده‌سازی..."
        )
        
        # شروع فرایند ساخت حساب
        self.process_account_creation(chat_id, user_id, proxy)
    
    def process_account_creation(self, chat_id, user_id, proxy=None):
        """پردازش ساخت حساب و دریافت کلید API."""
        # تولید اطلاعات تصادفی برای حساب
        user_info = generate_random_user_info()
        
        # ارسال پیام وضعیت اولیه
        self.send_message(chat_id, "⏳ <b>در حال ساخت حساب Gmail...</b>")
        
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
                proxy=proxy
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
                proxy=proxy
            )
            
            # دریافت تاریخ و زمان فعلی
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # ایجاد لیست حساب‌ها اگر موجود نیست
            if 'accounts' not in self.user_data[user_id]:
                self.user_data[user_id]['accounts'] = []
            
            # بررسی نتیجه دریافت کلید API
            if not api_result['success']:
                # دریافت کلید API ناموفق بود اما حساب جیمیل ساخته شد
                self.send_message(
                    chat_id,
                    f"⚠️ <b>ساخت حساب ناقص</b>\n\n"
                    f"✅ <b>حساب Gmail:</b> <code>{gmail}</code>\n"
                    f"🔒 <b>رمز عبور:</b> <code>{user_info['password']}</code>\n\n"
                    f"❌ <b>خطا در دریافت کلید API:</b>\n"
                    f"{api_result.get('error', 'خطای نامشخص')}\n\n"
                    f"می‌توانید بعداً به صورت دستی کلید API را دریافت کنید."
                )
                
                # ذخیره اطلاعات حساب بدون کلید API در کش
                self.user_data[user_id]['accounts'].append({
                    'gmail': gmail,
                    'password': user_info['password'],
                    'api_key': None,
                    'status': 'api_failed',
                    'created_at': current_time
                })
                
                # ذخیره اطلاعات در دیتابیس اگر فعال است
                if self.use_db:
                    try:
                        from flask import current_app
                        with current_app.app_context():
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
            
            # ذخیره اطلاعات کامل حساب در کش
            self.user_data[user_id]['accounts'].append({
                'gmail': gmail,
                'password': user_info['password'],
                'api_key': api_key,
                'status': 'complete',
                'created_at': current_time
            })
            
            # ذخیره اطلاعات در دیتابیس اگر فعال است
            if self.use_db:
                try:
                    from flask import current_app
                    with current_app.app_context():
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
            
            # ارسال پیام موفقیت
            self.send_message(
                chat_id,
                f"✅ <b>عملیات با موفقیت انجام شد!</b>\n\n"
                f"📧 <b>Gmail:</b> <code>{gmail}</code>\n"
                f"🔐 <b>Password:</b> <code>{user_info['password']}</code>\n"
                f"🔑 <b>API Key:</b> <code>{api_key}</code>\n\n"
                f"⚠️ این اطلاعات را در جایی امن ذخیره کنید."
            )
            
            # ثبت موفقیت در لاگ
            logger.info(f"Successfully created account and API key for user {user_id}: {gmail}")
            
            # بازگشت به منوی اصلی
            self.show_main_menu(chat_id, user_id)
            
        except Exception as e:
            logger.error(f"Error in account creation process: {str(e)}")
            
            self.send_message(
                chat_id,
                f"❌ <b>خطای غیرمنتظره در فرآیند ساخت حساب</b>\n\n"
                f"پیام خطا: {str(e)}\n\n"
                f"لطفاً دوباره تلاش کنید یا از پروکسی دیگری استفاده کنید."
            )
            
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
        except Exception as e:
            logger.error(f"Error connecting to Telegram API: {e}")
        
        # حلقه اصلی برای دریافت پیام‌ها
        while True:
            try:
                updates = self.get_updates()
                if updates:
                    logger.info(f"Received {len(updates)} updates")
                    self.handle_updates(updates)
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
        bot = InlineTelegramBot(token)
        bot.run()
    except Exception as e:
        logger.error(f"Error running bot: {e}")

if __name__ == "__main__":
    run_bot()