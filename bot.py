import os
import logging
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler
from gmail_creator import create_gmail_account
from api_key_generator import generate_api_key
from utils import generate_random_user_info
from app import db, Account

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# States for conversation
WAITING_FOR_PROXY = 1

# Get bot token from environment
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "your_bot_token_here")

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I can help you create Gmail accounts and generate Google Gemini API keys.\n\n"
        f"Use /create to start the process.\n"
        f"Use /status to check the status of your requests.\n"
        f"Use /help to see all available commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message with available commands."""
    help_text = (
        "Available commands:\n"
        "/start - Start the bot\n"
        "/create - Create a new Gmail account and generate API key\n"
        "/status - Check status of your requests\n"
        "/help - Show this help message\n\n"
        "Note: You may need to provide a proxy/VPN for successful account creation."
    )
    await update.message.reply_text(help_text)

async def create_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiate the account creation process."""
    keyboard = [
        [
            InlineKeyboardButton("Use default proxy", callback_data="proxy_default"),
            InlineKeyboardButton("Provide proxy", callback_data="proxy_custom"),
        ],
        [InlineKeyboardButton("No proxy (direct connection)", callback_data="proxy_none")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "To create a Gmail account and generate a Gemini API key, I need to know how to connect to Google:\n\n"
        "• Use default proxy: I'll use the system's default proxy settings\n"
        "• Provide proxy: You can specify your own proxy server\n"
        "• No proxy: I'll attempt a direct connection (may not work in restricted regions)",
        reply_markup=reply_markup
    )
    
    return WAITING_FOR_PROXY

async def proxy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle proxy selection."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data.split("_")[1]
    
    if choice == "custom":
        await query.edit_message_text(
            "Please send your proxy in the format: protocol://username:password@host:port\n"
            "For example: http://user:pass@127.0.0.1:8080\n\n"
            "Supported protocols: http, https, socks5"
        )
        return WAITING_FOR_PROXY
    
    # For default or none options, proceed with account creation
    proxy = None
    if choice == "default":
        proxy = "default"
    
    await query.edit_message_text("Starting Gmail account creation process. This may take several minutes...")
    
    # Start the account creation process
    await process_account_creation(update, context, proxy)
    return ConversationHandler.END

async def process_custom_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process custom proxy input from user."""
    proxy = update.message.text.strip()
    
    # Validate proxy format (simple validation)
    if not (proxy.startswith("http://") or proxy.startswith("https://") or proxy.startswith("socks5://")):
        await update.message.reply_text(
            "Invalid proxy format. Please provide in format: protocol://username:password@host:port\n"
            "Try again or use /cancel to abort."
        )
        return WAITING_FOR_PROXY
    
    await update.message.reply_text("Starting Gmail account creation process. This may take several minutes...")
    
    # Start the account creation process with custom proxy
    await process_account_creation(update, context, proxy)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

async def process_account_creation(update, context, proxy=None):
    """Process the account creation and API key generation."""
    # Get the chat for sending updates
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
    else:
        chat_id = update.message.chat_id
    
    # Generate random user info
    user_info = generate_random_user_info()
    
    # Create a new account entry in pending state
    new_account = Account(
        gmail=f"{user_info['username']}@gmail.com",
        password=user_info['password'],
        status="creating_gmail"
    )
    
    # Add to database
    db.session.add(new_account)
    db.session.commit()
    
    try:
        # Send progress update
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Creating Gmail account: {new_account.gmail}...\nThis may take 3-5 minutes."
        )
        
        # Create Gmail account
        result = create_gmail_account(
            user_info['first_name'],
            user_info['last_name'],
            user_info['username'],
            user_info['password'],
            user_info['birth_day'],
            user_info['birth_month'],
            user_info['birth_year'],
            user_info['gender'],
            proxy
        )
        
        if not result['success']:
            # Update account status and notify user of failure
            new_account.status = "gmail_creation_failed"
            db.session.commit()
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Failed to create Gmail account: {result['error']}"
            )
            return
        
        # Update account status
        new_account.status = "generating_api_key"
        db.session.commit()
        
        # Send progress update
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Gmail account created successfully!\nNow generating Gemini API key..."
        )
        
        # Generate API key
        api_result = generate_api_key(new_account.gmail, new_account.password, proxy)
        
        if not api_result['success']:
            # Update account status and notify user of failure
            new_account.status = "api_key_generation_failed"
            db.session.commit()
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Failed to generate API key: {api_result['error']}\n\n"
                     f"Gmail account was created successfully:\n"
                     f"Email: {new_account.gmail}\n"
                     f"Password: {new_account.password}"
            )
            return
        
        # Update account with API key and status
        new_account.api_key = api_result['api_key']
        new_account.status = "completed"
        db.session.commit()
        
        # Send success message with credentials
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Process completed successfully!\n\n"
                 f"📧 Gmail Account:\n"
                 f"Email: {new_account.gmail}\n"
                 f"Password: {new_account.password}\n\n"
                 f"🔑 Gemini API Key:\n"
                 f"{new_account.api_key}\n\n"
                 f"Remember to keep these credentials secure!"
        )
        
    except Exception as e:
        logger.error(f"Error in account creation process: {str(e)}")
        
        # Update account status
        new_account.status = "error"
        db.session.commit()
        
        # Notify user of error
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ An error occurred during the process: {str(e)}"
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show status of recent account creation requests."""
    # Get the 5 most recent accounts
    recent_accounts = Account.query.order_by(Account.created_at.desc()).limit(5).all()
    
    if not recent_accounts:
        await update.message.reply_text("No account creation requests found.")
        return
    
    status_text = "Recent account creation requests:\n\n"
    
    for account in recent_accounts:
        status_emoji = "⏳"
        if account.status == "completed":
            status_emoji = "✅"
        elif "failed" in account.status or account.status == "error":
            status_emoji = "❌"
            
        status_text += f"{status_emoji} {account.gmail}: {account.status}\n"
        
        if account.status == "completed":
            status_text += f"   API Key: {account.api_key}\n"
            
        status_text += "\n"
    
    await update.message.reply_text(status_text)

def start_polling():
    """Start the bot."""
    # Create application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add conversation handler for account creation process
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create", create_command)],
        states={
            WAITING_FOR_PROXY: [
                CallbackQueryHandler(proxy_callback, pattern=r"^proxy_"),
                CommandHandler("cancel", cancel),
                # Default handler for custom proxy input
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_custom_proxy)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(conv_handler)
    
    # Start the Bot
    application.run_polling()

# The following import needs to be at the end to avoid circular imports
from telegram.ext import MessageHandler, filters
