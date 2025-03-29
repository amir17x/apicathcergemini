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
                updates = data['result']
                
                # Filter out the problematic callback query that's causing errors
                filtered_updates = []
                for update in updates:
                    if 'callback_query' in update and update['callback_query']['id'] == "7877987201":
                        logger.info(f"Skipping problematic callback query: {update['callback_query']['id']}")
                    else:
                        filtered_updates.append(update)
                
                if filtered_updates:
                    self.offset = filtered_updates[-1]['update_id'] + 1
                elif updates:  # If we filtered everything but had updates
                    self.offset = updates[-1]['update_id'] + 1
                
                return filtered_updates
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
            response = requests.post(f"{self.base_url}/sendMessage", data=params)
            result = response.json()
            if not result.get('ok'):
                logger.warning(f"Failed to send message: {result.get('description')}")
            return result
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
            response = requests.post(f"{self.base_url}/editMessageText", data=params)
            result = response.json()
            if not result.get('ok'):
                # If update fails, try to send a new message with the same content instead
                if "message to edit not found" in str(result.get('description', '')).lower():
                    logger.warning("Message to edit not found, sending as new message instead")
                    return self.send_message(chat_id, text, reply_markup=reply_markup)
                else:
                    logger.warning(f"Failed to update message: {result.get('description')}")
            return result
        except Exception as e:
            logger.error(f"Error updating message: {e}")
            # Try to send a new message if updating fails
            try:
                return self.send_message(chat_id, text, reply_markup=reply_markup)
            except:
                return None

    def handle_updates(self, updates):
        """Process updates and dispatch to handlers"""
        for update in updates:
            try:
                # Handle regular messages
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
                
                # Handle callback queries (from inline keyboard buttons)
                elif 'callback_query' in update:
                    self.handle_callback_query(update)
                            
            except Exception as e:
                logger.error(f"Error handling update: {e}")
                
    def handle_callback_query(self, update):
        """Handle callback queries from inline keyboard buttons"""
        # Define chat_id at the start in case we need it in the exception handler
        chat_id = None
        try:
            query = update['callback_query']
            message = query['message']
            chat_id = message['chat']['id']
            user_id = query['from']['id']
            callback_data = query.get('data', '')
            callback_id = query['id']
            
            # Initialize user data if not exists
            if user_id not in self.user_data:
                self.user_data[user_id] = {'chat_id': chat_id}
            
            # Try to silently acknowledge the callback query without showing an alert
            # But ignore any errors (just log them)
            try:
                self.answer_callback_query(callback_id)
            except Exception as e:
                # If there's an error answering the callback query, just log and continue
                # This is usually due to the query being too old, which is non-critical
                logger.warning(f"Non-critical error acknowledging callback: {str(e)}")
            
            logger.info(f"Processing callback data: {callback_data}")
            
            # Process different callback data
            if callback_data == 'start':
                # Show main menu
                self.handle_start({'message': message}, [])
            
            elif callback_data == 'help':
                # Show help message
                self.handle_help({'message': message}, [])
            
            elif callback_data == 'create':
                # Start account creation process
                self.handle_create({'message': message}, [])
            
            elif callback_data == 'status':
                # Show account status
                self._show_status(chat_id, user_id)
            
            elif callback_data == 'no_proxy':
                # Send a message before starting account creation
                self.send_message(chat_id, "⏳ <b>در حال آماده‌سازی برای ساخت حساب جدید...</b>")
                # Start account creation without proxy
                self.process_account_creation(chat_id, user_id)
            
            elif callback_data == 'custom_proxy':
                # Ask for custom proxy
                proxy_msg = "🌐 <b>تنظیم پروکسی دلخواه</b>\n\n"
                proxy_msg += "لطفاً پروکسی خود را در قالب زیر وارد کنید:\n"
                proxy_msg += "<code>protocol://username:password@host:port</code>\n\n"
                proxy_msg += "مثال:\n"
                proxy_msg += "<code>socks5://user:pass@1.2.3.4:1080</code>"
                
                # Create cancel button
                inline_keyboard = {
                    "inline_keyboard": [
                        [{"text": "🔙 بازگشت", "callback_data": "create"}]
                    ]
                }
                
                self.send_message(chat_id, proxy_msg, reply_markup=inline_keyboard)
                self.user_data[user_id]['state'] = 'custom_proxy'
            
            else:
                logger.warning(f"Unknown callback data: '{callback_data}'")
                self.send_message(chat_id, "⚠️ گزینه نامعتبر. لطفاً از منوی اصلی انتخاب کنید.", 
                    reply_markup={"inline_keyboard": [[{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "start"}]]})
                
        except KeyError as ke:
            logger.error(f"KeyError in handle_callback_query: {str(ke)}")
            # Don't try to send an error message, as we might not have chat_id
        except Exception as e:
            logger.error(f"Error handling callback query: {str(e)}")
            try:
                # Try to send an error message, but don't let this fail the whole handler
                # Make sure chat_id is defined before using it
                if chat_id:  # Now this won't cause an error since chat_id is defined at the top
                    self.send_message(chat_id, f"خطا در پردازش درخواست. لطفاً دوباره تلاش کنید.")
            except Exception as send_error:
                logger.error(f"Error sending error message: {str(send_error)}")
                pass
    
    def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        """Answer a callback query to stop the loading animation"""
        params = {
            'callback_query_id': callback_query_id
        }
        
        if text:
            params['text'] = text
            
        if show_alert:
            params['show_alert'] = True
            
        try:
            # Using URLencoded parameters instead of JSON
            response = requests.post(f"{self.base_url}/answerCallbackQuery", data=params)
            result = response.json()
            if not result.get('ok'):
                logger.warning(f"Failed to answer callback query: {result.get('description')}")
            return result
        except Exception as e:
            logger.error(f"Error answering callback query: {e}")
            return None
    
    def handle_start(self, update, args):
        """Handle /start command"""
        chat_id = update['message']['chat']['id']
        
        # Create inline keyboard buttons
        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "🔧 ساخت حساب جدید", "callback_data": "create"}],
                [{"text": "📊 وضعیت درخواست‌ها", "callback_data": "status"}],
                [{"text": "❓ راهنما", "callback_data": "help"}]
            ]
        }
        
        self.send_message(
            chat_id,
            "👋 سلام! به ربات ساخت حساب Gmail و کلید API Gemini خوش آمدید.\n\n"
            "🔸 با این ربات می‌توانید به صورت خودکار:\n"
            "  • حساب Gmail ایجاد کنید\n"
            "  • کلید API Gemini دریافت کنید\n\n"
            "از منوی زیر گزینه مورد نظر خود را انتخاب کنید:",
            reply_markup=inline_keyboard
        )
    
    def handle_help(self, update, args):
        """Handle /help command"""
        chat_id = update['message']['chat']['id']
        
        # Create inline keyboard buttons for navigation
        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "start"}]
            ]
        }
        
        self.send_message(
            chat_id,
            "📚 <b>راهنمای استفاده از ربات</b>\n\n"
            "🔸 <b>دستورات اصلی:</b>\n"
            "/start - شروع کار با ربات و نمایش منوی اصلی\n"
            "/create - شروع فرآیند ساخت حساب Gmail و کلید API\n"
            "/status - بررسی وضعیت درخواست‌های شما\n"
            "/help - نمایش این راهنما\n\n"
            "🔸 <b>نکات مهم:</b>\n"
            "• ممکن است برای ساخت موفق حساب به پروکسی یا VPN نیاز داشته باشید.\n"
            "• تمام اطلاعات حساب‌های ساخته شده را در جای امنی ذخیره کنید.\n"
            "• در صورت بروز مشکل، می‌توانید مجدداً تلاش کنید.",
            reply_markup=inline_keyboard
        )
    
    def handle_create(self, update, args):
        """Handle /create command"""
        chat_id = update['message']['chat']['id']
        user_id = update['message']['from']['id']
        
        # Set the user's state to waiting for proxy choice
        self.user_data[user_id]['state'] = 'proxy_choice'
        
        # Create inline keyboard buttons
        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "🔄 بدون پروکسی", "callback_data": "no_proxy"}],
                [{"text": "🌐 استفاده از پروکسی", "callback_data": "custom_proxy"}],
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "start"}]
            ]
        }
        
        self.send_message(
            chat_id,
            "🌐 <b>انتخاب پروکسی</b>\n\n"
            "برای ساخت حساب Gmail، آیا می‌خواهید از پروکسی استفاده کنید؟",
            reply_markup=inline_keyboard
        )
    
    def handle_status(self, update, args):
        """Handle /status command"""
        chat_id = update['message']['chat']['id']
        user_id = update['message']['from']['id']
        
        # اجرای متد مشترک برای نمایش وضعیت
        self._show_status(chat_id, user_id)
        
    def _show_status(self, chat_id, user_id):
        """Show status of accounts (shared method for command and callback)"""
        accounts = self.user_data.get(user_id, {}).get('accounts', [])
        
        # Create return to menu button
        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "start"}]
            ]
        }
        
        if not accounts:
            self.send_message(
                chat_id, 
                "📭 <b>حسابی یافت نشد</b>\n\n"
                "شما تاکنون هیچ حسابی ایجاد نکرده‌اید.\n"
                "برای ساخت حساب جدید، از دکمه «ساخت حساب جدید» در منوی اصلی استفاده کنید.",
                reply_markup=inline_keyboard
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
        
        self.send_message(chat_id, message, reply_markup=inline_keyboard)
    
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
                # Create inline keyboard for return button
                inline_keyboard = {
                    "inline_keyboard": [
                        [{"text": "🔄 تلاش مجدد", "callback_data": "create"}]
                    ]
                }
                
                self.send_message(
                    chat_id,
                    f"❌ <b>خطا در تنظیم پروکسی</b>\n\n"
                    f"پیام خطا: {str(e)}\n\n"
                    f"لطفاً مجدداً تلاش کنید یا از گزینه بدون پروکسی استفاده کنید.",
                    reply_markup=inline_keyboard
                )
    
    def process_account_creation(self, chat_id, user_id, proxy=None):
        """Process the account creation and API key generation"""
        from utils import generate_random_user_info
        import gmail_creator
        import api_key_generator
        import datetime
        
        # Generate random user info for the account
        user_info = generate_random_user_info()
        
        # Create inline keyboard for return to menu
        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "start"}]
            ]
        }
        
        # Send initial status message
        response = self.send_message(chat_id, "⏳ <b>در حال ساخت حساب Gmail...</b>")
        if not response or not response.get('ok'):
            logger.error("Failed to send initial status message")
            return
        
        status_message_id = response['result']['message_id']
        
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
                self.update_message(
                    chat_id, 
                    status_message_id,
                    f"❌ <b>خطا در ساخت حساب Gmail</b>\n\n"
                    f"پیام خطا: {gmail_result.get('error', 'خطای نامشخص')}\n\n"
                    f"لطفاً دوباره تلاش کنید یا از پروکسی استفاده کنید.",
                    reply_markup=inline_keyboard
                )
                return
            
            # Gmail creation successful
            gmail = gmail_result['gmail']
            
            # Update status message
            self.update_message(
                chat_id,
                status_message_id,
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
                self.update_message(
                    chat_id,
                    status_message_id,
                    f"⚠️ <b>ساخت حساب ناقص</b>\n\n"
                    f"✅ <b>حساب Gmail:</b> <code>{gmail}</code>\n"
                    f"🔒 <b>رمز عبور:</b> <code>{user_info['password']}</code>\n\n"
                    f"❌ <b>خطا در دریافت کلید API:</b>\n"
                    f"{api_result.get('error', 'خطای نامشخص')}\n\n"
                    f"می‌توانید بعداً به صورت دستی کلید API را دریافت کنید.",
                    reply_markup=inline_keyboard
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
            
            # Send complete success message with return button
            self.update_message(
                chat_id,
                status_message_id,
                f"✅ <b>عملیات با موفقیت انجام شد!</b>\n\n"
                f"📧 <b>Gmail:</b> <code>{gmail}</code>\n"
                f"🔐 <b>Password:</b> <code>{user_info['password']}</code>\n"
                f"🔑 <b>API Key:</b> <code>{api_key}</code>\n\n"
                f"⚠️ این اطلاعات را در جایی امن ذخیره کنید.",
                reply_markup=inline_keyboard
            )
            
            # Log success
            logger.info(f"Successfully created account and API key for user {user_id}: {gmail}")
            
        except Exception as e:
            logger.error(f"Error in account creation process: {str(e)}")
            
            self.update_message(
                chat_id,
                status_message_id,
                f"❌ <b>خطای غیرمنتظره در فرآیند ساخت حساب</b>\n\n"
                f"پیام خطا: {str(e)}\n\n"
                f"لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
                reply_markup=inline_keyboard
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