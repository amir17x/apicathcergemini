#!/usr/bin/env python3
"""
Telegram bot for Gmail account creation and Google Gemini API key generation.
This file implements a simplified version using direct commands instead of callback queries.
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

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SimpleTelegramBot:
    def __init__(self, token=None):
        """Initialize the bot with Telegram Bot API token."""
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("No bot token provided")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.user_data = {}  # Simple in-memory store for user data
        
    def get_updates(self, timeout=30):
        """Poll for updates from Telegram API."""
        params = {
            'offset': self.offset,
            'timeout': timeout,
            'allowed_updates': json.dumps(['message'])  # We only care about messages, no callbacks
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
    
    def send_message(self, chat_id, text, parse_mode='HTML'):
        """Send a message to a chat."""
        params = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
            
        try:
            response = requests.post(f"{self.base_url}/sendMessage", data=params)
            result = response.json()
            if not result.get('ok'):
                logger.warning(f"Failed to send message: {result.get('description')}")
            return result
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    def handle_updates(self, updates):
        """Process updates and dispatch to handlers."""
        for update in updates:
            try:
                if 'message' in update and 'text' in update['message']:
                    message = update['message']
                    chat_id = message['chat']['id']
                    user_id = message['from']['id']
                    text = message['text']
                    
                    # Initialize user data if not exists
                    if user_id not in self.user_data:
                        self.user_data[user_id] = {'chat_id': chat_id}
                    
                    # Handle commands
                    if text.startswith('/'):
                        command_parts = text.split()
                        command = command_parts[0][1:].lower()  # Remove the / prefix and make lowercase
                        args = command_parts[1:] if len(command_parts) > 1 else []
                        
                        # Dispatch to appropriate handler
                        if command == 'start':
                            self.handle_start(chat_id, user_id)
                        elif command == 'help':
                            self.handle_help(chat_id)
                        elif command == 'create':
                            self.handle_create(chat_id, user_id)
                        elif command == 'status':
                            self.handle_status(chat_id, user_id)
                        elif command == 'noproxy':
                            self.handle_no_proxy(chat_id, user_id)
                        elif command == 'useproxy':
                            # If the command has a proxy parameter
                            if len(args) > 0:
                                proxy = args[0]
                                self.handle_custom_proxy(chat_id, user_id, proxy)
                            else:
                                self.send_message(chat_id, 
                                    "🌐 <b>تنظیم پروکسی</b>\n\n"
                                    "لطفاً پروکسی خود را با فرمت زیر وارد کنید:\n"
                                    "/useproxy protocol://username:password@host:port\n\n"
                                    "مثال:\n"
                                    "/useproxy socks5://user:pass@1.2.3.4:1080")
                        else:
                            self.send_message(chat_id, "دستور نامعتبر است. برای راهنمایی، /help را وارد کنید.")
                    
                    # Handle custom proxy input (for older messages before command implementation)
                    elif self.user_data.get(user_id, {}).get('state') == 'waiting_for_proxy':
                        self.handle_custom_proxy(chat_id, user_id, text)
                
            except Exception as e:
                logger.error(f"Error handling update: {e}")
    
    def handle_start(self, chat_id, user_id):
        """Handle /start command."""
        self.send_message(
            chat_id,
            "👋 سلام! به ربات ساخت حساب Gmail و کلید API Gemini خوش آمدید.\n\n"
            "🔸 با این ربات می‌توانید به صورت خودکار:\n"
            "  • حساب Gmail ایجاد کنید\n"
            "  • کلید API Gemini دریافت کنید\n\n"
            "دستورات اصلی:\n"
            "/create - شروع ساخت حساب جدید\n"
            "/status - مشاهده وضعیت حساب‌ها\n"
            "/help - راهنمای استفاده از ربات"
        )
    
    def handle_help(self, chat_id):
        """Handle /help command."""
        self.send_message(
            chat_id,
            "📚 <b>راهنمای استفاده از ربات</b>\n\n"
            "🔸 <b>دستورات اصلی:</b>\n"
            "/start - شروع کار با ربات و نمایش منوی اصلی\n"
            "/create - شروع فرآیند ساخت حساب Gmail و کلید API\n"
            "/status - بررسی وضعیت درخواست‌های شما\n"
            "/help - نمایش این راهنما\n\n"
            "🔸 <b>دستورات مرتبط با پروکسی:</b>\n"
            "/noproxy - ساخت حساب بدون استفاده از پروکسی\n"
            "/useproxy - ساخت حساب با پروکسی (مثال: /useproxy socks5://user:pass@host:port)\n\n"
            "🔸 <b>نکات مهم:</b>\n"
            "• ممکن است برای ساخت موفق حساب به پروکسی یا VPN نیاز داشته باشید.\n"
            "• تمام اطلاعات حساب‌های ساخته شده را در جای امنی ذخیره کنید.\n"
            "• در صورت بروز مشکل، می‌توانید مجدداً تلاش کنید."
        )
    
    def handle_create(self, chat_id, user_id):
        """Handle /create command."""
        # Set the user's state to waiting for proxy choice
        self.user_data[user_id]['state'] = 'waiting_for_proxy'
        
        self.send_message(
            chat_id,
            "🌐 <b>انتخاب پروکسی</b>\n\n"
            "برای ساخت حساب Gmail، یکی از گزینه‌های زیر را انتخاب کنید:\n\n"
            "1️⃣ برای ساخت بدون پروکسی: /noproxy\n\n"
            "2️⃣ برای ساخت با پروکسی: /useproxy\n"
            "    نحوه استفاده: /useproxy protocol://username:password@host:port\n"
            "    مثال: /useproxy socks5://user:pass@1.2.3.4:1080"
        )
    
    def handle_status(self, chat_id, user_id):
        """Handle /status command."""
        accounts = self.user_data.get(user_id, {}).get('accounts', [])
        
        if not accounts:
            self.send_message(
                chat_id, 
                "📭 <b>حسابی یافت نشد</b>\n\n"
                "شما تاکنون هیچ حسابی ایجاد نکرده‌اید.\n"
                "برای ساخت حساب جدید، از دستور /create استفاده کنید."
            )
            return
        
        message = "📊 <b>وضعیت حساب‌های شما</b>\n\n"
        
        for i, account in enumerate(accounts):
            status_icon = "✅" if account.get('status') == 'complete' else "❌"
            message += f"{i+1}. {status_icon} <b>{account.get('gmail')}</b>\n"
            message += f"   📅 تاریخ: {account.get('created_at', 'نامشخص')}\n"
            
            if account.get('api_key'):
                # فقط بخشی از کلید را نمایش می‌دهیم
                api_key = account.get('api_key')
                masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
                message += f"   🔑 API Key: <code>{masked_key}</code>\n"
            else:
                message += f"   ⚠️ کلید API: دریافت نشد\n"
            
            message += "\n"
        
        message += "برای مشاهده اطلاعات کامل یا کپی کردن کلیدها، با ربات تماس بگیرید."
        
        self.send_message(chat_id, message)
    
    def handle_no_proxy(self, chat_id, user_id):
        """Handle /noproxy command."""
        self.send_message(chat_id, "⏳ <b>در حال آماده‌سازی برای ساخت حساب جدید بدون پروکسی...</b>")
        # Start account creation without proxy
        self.process_account_creation(chat_id, user_id)
        # Clear the state
        self.user_data[user_id]['state'] = None
    
    def handle_custom_proxy(self, chat_id, user_id, proxy_string):
        """Handle custom proxy from /useproxy command."""
        try:
            from utils import setup_proxy
            proxy = setup_proxy(proxy_string)
            
            if proxy is None:
                self.send_message(
                    chat_id,
                    f"❌ <b>فرمت پروکسی نامعتبر است</b>\n\n"
                    f"لطفاً پروکسی را با فرمت صحیح وارد کنید.\n"
                    f"مثال: socks5://username:password@host:port\n\n"
                    f"برای تلاش مجدد از دستور /create استفاده کنید."
                )
                return
            
            self.user_data[user_id]['proxy'] = proxy_string
            
            self.send_message(chat_id, f"🌐 <b>پروکسی با موفقیت تنظیم شد</b>\n\n⏳ در حال شروع فرآیند ساخت حساب...")
            self.process_account_creation(chat_id, user_id, proxy)
            # Clear the state
            self.user_data[user_id]['state'] = None
            
        except Exception as e:
            self.send_message(
                chat_id,
                f"❌ <b>خطا در تنظیم پروکسی</b>\n\n"
                f"پیام خطا: {str(e)}\n\n"
                f"لطفاً مجدداً تلاش کنید یا از دستور /noproxy برای ساخت بدون پروکسی استفاده کنید."
            )
    
    def process_account_creation(self, chat_id, user_id, proxy=None):
        """Process the account creation and API key generation."""
        # Generate random user info for the account
        user_info = generate_random_user_info()
        
        # Send initial status message
        self.send_message(chat_id, "⏳ <b>در حال ساخت حساب Gmail...</b>")
        
        try:
            # Step 1: Create Gmail account using the gmail_creator module
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
            
            # Check Gmail creation result
            if not gmail_result['success']:
                self.send_message(
                    chat_id, 
                    f"❌ <b>خطا در ساخت حساب Gmail</b>\n\n"
                    f"پیام خطا: {gmail_result.get('error', 'خطای نامشخص')}\n\n"
                    f"لطفاً دوباره تلاش کنید یا از پروکسی استفاده کنید.",
                )
                return
            
            # Gmail creation successful
            gmail = gmail_result['gmail']
            
            # Update status message
            self.send_message(
                chat_id,
                f"✅ <b>حساب Gmail با موفقیت ساخته شد:</b>\n"
                f"📧 {gmail}\n\n"
                f"⏳ <b>در حال دریافت کلید API Gemini...</b>"
            )
            
            # Step 2: Generate API key using the api_key_generator module
            logger.info(f"Starting API key generation for {gmail}")
            
            api_result = api_key_generator.generate_api_key(
                gmail=gmail,
                password=user_info['password'],
                proxy=proxy
            )
            
            # Get current date and time for record
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Initialize accounts list if not exists
            if 'accounts' not in self.user_data[user_id]:
                self.user_data[user_id]['accounts'] = []
            
            # Check API key generation result
            if not api_result['success']:
                # API key generation failed, but Gmail account was created
                self.send_message(
                    chat_id,
                    f"⚠️ <b>ساخت حساب ناقص</b>\n\n"
                    f"✅ <b>حساب Gmail:</b> <code>{gmail}</code>\n"
                    f"🔒 <b>رمز عبور:</b> <code>{user_info['password']}</code>\n\n"
                    f"❌ <b>خطا در دریافت کلید API:</b>\n"
                    f"{api_result.get('error', 'خطای نامشخص')}\n\n"
                    f"می‌توانید بعداً به صورت دستی کلید API را دریافت کنید."
                )
                
                # Save account info without API key
                self.user_data[user_id]['accounts'].append({
                    'gmail': gmail,
                    'password': user_info['password'],
                    'api_key': None,
                    'status': 'api_failed',
                    'created_at': current_time
                })
                return
            
            # Both Gmail and API key creation successful
            api_key = api_result['api_key']
            
            # Save complete account info
            self.user_data[user_id]['accounts'].append({
                'gmail': gmail,
                'password': user_info['password'],
                'api_key': api_key,
                'status': 'complete',
                'created_at': current_time
            })
            
            # Send complete success message
            self.send_message(
                chat_id,
                f"✅ <b>عملیات با موفقیت انجام شد!</b>\n\n"
                f"📧 <b>Gmail:</b> <code>{gmail}</code>\n"
                f"🔐 <b>Password:</b> <code>{user_info['password']}</code>\n"
                f"🔑 <b>API Key:</b> <code>{api_key}</code>\n\n"
                f"⚠️ این اطلاعات را در جایی امن ذخیره کنید."
            )
            
            # Log success
            logger.info(f"Successfully created account and API key for user {user_id}: {gmail}")
            
        except Exception as e:
            logger.error(f"Error in account creation process: {str(e)}")
            
            self.send_message(
                chat_id,
                f"❌ <b>خطای غیرمنتظره در فرآیند ساخت حساب</b>\n\n"
                f"پیام خطا: {str(e)}\n\n"
                f"لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
            )
    
    def run(self):
        """Main loop to continuously poll for updates."""
        logger.info("Starting bot polling...")
        logger.info(f"Bot token available and valid: {bool(self.token)}")
        logger.info(f"Base URL: {self.base_url.replace(self.token, 'TOKEN_HIDDEN')}")
        
        # Test API connection to verify token is working
        try:
            test_response = requests.get(f"{self.base_url}/getMe", timeout=10)
            test_data = test_response.json()
            if test_data.get('ok'):
                bot_info = test_data.get('result', {})
                logger.info(f"Connected successfully to Telegram API as @{bot_info.get('username')} (ID: {bot_info.get('id')})")
            else:
                logger.error(f"Failed to connect to Telegram API: {test_data.get('description', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Error testing Telegram API connection: {e}")
        
        logger.info("Starting main polling loop now...")
        
        try:
            poll_count = 0
            while True:
                poll_count += 1
                if poll_count % 10 == 0:  # Log every 10 polls to avoid too much noise
                    logger.info(f"Polling for updates (count: {poll_count})...")
                
                try:
                    updates = self.get_updates()
                    if updates:
                        logger.info(f"Received {len(updates)} new update(s)!")
                        self.handle_updates(updates)
                except Exception as e:
                    logger.error(f"Error during polling cycle: {e}")
                
                time.sleep(1)  # Sleep to avoid flooding Telegram API
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot stopped due to error: {e}")

def run_bot():
    """Run the Telegram bot."""
    bot = SimpleTelegramBot()
    bot.run()

if __name__ == "__main__":
    run_bot()