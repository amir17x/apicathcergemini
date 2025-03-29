import os
import logging
import requests
import json
import time

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token=None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("No bot token provided")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.user_data = {}  # Simple store for user data
        
    def get_updates(self, timeout=30):
        """Poll for updates from Telegram"""
        params = {
            'offset': self.offset,
            'timeout': timeout,
            'allowed_updates': json.dumps(['message', 'callback_query'])
        }
        try:
            response = requests.get(f"{self.base_url}/getUpdates", params=params)
            data = response.json()
            
            if data.get('ok') and data.get('result'):
                if data['result']:
                    self.offset = data['result'][-1]['update_id'] + 1
                return data['result']
            return []
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []
    
    def send_message(self, chat_id, text, reply_markup=None):
        """Send a message to a chat"""
        params = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        if reply_markup:
            params['reply_markup'] = json.dumps(reply_markup)
            
        try:
            response = requests.post(f"{self.base_url}/sendMessage", json=params)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    def update_message(self, chat_id, message_id, text, reply_markup=None):
        """Edit a message"""
        params = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        if reply_markup:
            params['reply_markup'] = json.dumps(reply_markup)
            
        try:
            response = requests.post(f"{self.base_url}/editMessageText", json=params)
            return response.json()
        except Exception as e:
            logger.error(f"Error updating message: {e}")
            return None

    def handle_updates(self, updates):
        """Process updates and dispatch to handlers"""
        for update in updates:
            try:
                if 'message' in update:
                    message = update['message']
                    chat_id = message['chat']['id']
                    
                    # Store user_id in context for later use
                    user_id = message['from']['id']
                    if user_id not in self.user_data:
                        self.user_data[user_id] = {'chat_id': chat_id}
                    
                    # Handle commands
                    if 'text' in message:
                        text = message['text']
                        if text.startswith('/'):
                            # Extract command and args
                            command_parts = text.split()
                            command = command_parts[0][1:]  # Remove the / prefix
                            args = command_parts[1:] if len(command_parts) > 1 else []
                            
                            handler_method = f"handle_{command}"
                            if hasattr(self, handler_method):
                                getattr(self, handler_method)(update, args)
                        else:
                            # Regular text message
                            self.handle_text_message(update)
                            
            except Exception as e:
                logger.error(f"Error handling update: {e}")
    
    def handle_start(self, update, args):
        """Handle /start command"""
        chat_id = update['message']['chat']['id']
        self.send_message(
            chat_id,
            "سلام! من ربات ساخت حساب Gmail و کلید API Gemini هستم.\n"
            "از دستورات زیر می‌توانید استفاده کنید:\n"
            "/help - راهنمای دستورات\n"
            "/create - ساخت حساب جدید\n"
            "/status - بررسی وضعیت درخواست‌ها"
        )
    
    def handle_help(self, update, args):
        """Handle /help command"""
        chat_id = update['message']['chat']['id']
        self.send_message(
            chat_id,
            "دستورات موجود:\n"
            "/start - شروع کار با ربات\n"
            "/create - شروع فرآیند ساخت حساب Gmail و کلید API\n"
            "/status - بررسی وضعیت درخواست‌های شما\n"
            "/help - نمایش این راهنما\n\n"
            "توجه: ممکن است برای ساخت موفق حساب به پروکسی/VPN نیاز داشته باشید."
        )
    
    def handle_create(self, update, args):
        """Handle /create command"""
        chat_id = update['message']['chat']['id']
        user_id = update['message']['from']['id']
        
        # Set the user's state to waiting for proxy choice
        self.user_data[user_id]['state'] = 'proxy_choice'
        
        keyboard = {
            "keyboard": [
                ["بدون پروکسی"],
                ["استفاده از پروکسی دلخواه"]
            ],
            "one_time_keyboard": True,
            "resize_keyboard": True
        }
        
        self.send_message(
            chat_id,
            "آیا می‌خواهید از پروکسی استفاده کنید؟",
            reply_markup=keyboard
        )
    
    def handle_status(self, update, args):
        """Handle /status command"""
        chat_id = update['message']['chat']['id']
        user_id = update['message']['from']['id']
        accounts = self.user_data.get(user_id, {}).get('accounts', [])
        
        if not accounts:
            self.send_message(chat_id, "تاکنون هیچ حسابی ایجاد نکرده‌اید.")
            return
        
        message = "📊 وضعیت حساب‌های شما:\n\n"
        
        for i, account in enumerate(accounts):
            status_icon = "✅" if account.get('status') == 'complete' else "❌"
            message += f"{i+1}. {status_icon} {account.get('gmail')}\n"
            
            if account.get('api_key'):
                message += f"   🔑 API Key: {account.get('api_key')}\n"
            else:
                message += f"   ⚠️ کلید API: دریافت نشد\n"
            
            message += "\n"
        
        self.send_message(chat_id, message)
    
    def handle_text_message(self, update):
        """Handle regular text messages based on user state"""
        chat_id = update['message']['chat']['id']
        user_id = update['message']['from']['id']
        text = update['message']['text']
        
        # Get the current user state
        state = self.user_data.get(user_id, {}).get('state')
        
        if state == 'proxy_choice':
            if text == "بدون پروکسی":
                self.send_message(chat_id, "در حال شروع فرآیند ساخت حساب بدون پروکسی...")
                self.process_account_creation(chat_id, user_id)
                self.user_data[user_id]['state'] = None
            
            elif text == "استفاده از پروکسی دلخواه":
                self.send_message(
                    chat_id,
                    "لطفاً پروکسی خود را در قالب زیر وارد کنید:\n"
                    "protocol://username:password@host:port\n"
                    "مثال: socks5://user:pass@1.2.3.4:1080"
                )
                self.user_data[user_id]['state'] = 'custom_proxy'
            
            else:
                self.send_message(chat_id, "انتخاب نامعتبر. لطفاً یکی از گزینه‌های موجود را انتخاب کنید.")
        
        elif state == 'custom_proxy':
            proxy_string = text
            
            try:
                from utils import setup_proxy
                proxy = setup_proxy(proxy_string)
                self.user_data[user_id]['proxy'] = proxy_string
                
                self.send_message(chat_id, f"پروکسی با موفقیت تنظیم شد. در حال شروع فرآیند ساخت حساب...")
                self.process_account_creation(chat_id, user_id, proxy)
                self.user_data[user_id]['state'] = None
                
            except Exception as e:
                self.send_message(
                    chat_id,
                    f"خطا در پروکسی: {str(e)}\nلطفاً مجدداً تلاش کنید یا از گزینه بدون پروکسی استفاده کنید."
                )
    
    def process_account_creation(self, chat_id, user_id, proxy=None):
        """Process the account creation and API key generation"""
        from utils import generate_random_user_info
        import gmail_creator
        import api_key_generator
        
        user_info = generate_random_user_info()
        
        # Send initial status message
        response = self.send_message(chat_id, "⏳ در حال ساخت حساب Gmail...")
        if not response or not response.get('ok'):
            logger.error("Failed to send initial status message")
            return
        
        status_message_id = response['result']['message_id']
        
        try:
            # Create Gmail account
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
            
            if not gmail_result['success']:
                self.update_message(
                    chat_id, 
                    status_message_id,
                    f"❌ خطا در ساخت حساب Gmail: {gmail_result['error']}"
                )
                return
            
            gmail = f"{user_info['username']}@gmail.com"
            self.update_message(
                chat_id,
                status_message_id,
                f"✅ حساب Gmail با موفقیت ساخته شد: {gmail}\n"
                f"⏳ در حال دریافت کلید API Gemini..."
            )
            
            # Generate API key
            api_result = api_key_generator.generate_api_key(
                gmail=gmail,
                password=user_info['password'],
                proxy=proxy
            )
            
            if not api_result['success']:
                self.update_message(
                    chat_id,
                    status_message_id,
                    f"✅ حساب Gmail: {gmail}\n"
                    f"❌ خطا در دریافت کلید API: {api_result['error']}"
                )
                # Save account info without API key
                if 'accounts' not in self.user_data[user_id]:
                    self.user_data[user_id]['accounts'] = []
                
                self.user_data[user_id]['accounts'].append({
                    'gmail': gmail,
                    'password': user_info['password'],
                    'api_key': None,
                    'status': 'api_failed'
                })
                return
            
            # Success - save complete account info
            api_key = api_result['api_key']
            if 'accounts' not in self.user_data[user_id]:
                self.user_data[user_id]['accounts'] = []
            
            self.user_data[user_id]['accounts'].append({
                'gmail': gmail,
                'password': user_info['password'],
                'api_key': api_key,
                'status': 'complete'
            })
            
            # Send complete success message
            self.update_message(
                chat_id,
                status_message_id,
                f"✅ عملیات با موفقیت انجام شد!\n\n"
                f"📧 Gmail: {gmail}\n"
                f"🔑 Password: {user_info['password']}\n"
                f"🔑 API Key: {api_key}\n\n"
                f"این اطلاعات را در جایی امن ذخیره کنید."
            )
            
        except Exception as e:
            logger.error(f"Error in account creation process: {str(e)}")
            self.update_message(
                chat_id,
                status_message_id,
                f"❌ خطای غیرمنتظره: {str(e)}"
            )
    
    def run(self):
        """Main loop to continuously poll for updates"""
        logger.info("Starting bot polling...")
        
        try:
            while True:
                updates = self.get_updates()
                if updates:
                    self.handle_updates(updates)
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot stopped due to error: {e}")

def run_bot():
    """Run the Telegram bot"""
    bot = TelegramBot()
    bot.run()

if __name__ == "__main__":
    run_bot()