#!/usr/bin/env python3
"""
Main entry point for the application.
This file directly runs the Telegram bot with no web application.
"""

import os
import logging
import sys
from telegram_api import TelegramBot

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Run the Telegram bot"""
    # Check if token is available
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
        logger.error("Please set your Telegram bot token and restart the application.")
        sys.exit(1)
    
    try:
        logger.info("Starting Telegram bot...")
        bot = TelegramBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")
        sys.exit(1)

# This is what Gunicorn expects - a wsgi app
def application(environ, start_response):
    """WSGI application function to keep Gunicorn happy"""
    # Start the bot in a separate thread
    import threading
    bot_thread = threading.Thread(target=main)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Return a simple response to keep Gunicorn happy
    status = '200 OK'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)
    return [b"Telegram bot is running in the background."]

# This variable is what Gunicorn looks for
app = application

if __name__ == "__main__":
    main()
