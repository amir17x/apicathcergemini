#!/usr/bin/env python3
"""
Main entry point for the application.
This file directly runs the Telegram bot with no web application.
"""

import os
import logging
import sys
import time
from telegram_bot_simple import SimpleTelegramBot

# Configure logging to file for better debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler("/tmp/telegram_bot.log"),  # Log to file for persistence
    ]
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("=" * 50)
logger.info("TELEGRAM BOT APPLICATION STARTING")
logger.info("=" * 50)

def main():
    """Run the Telegram bot"""
    # Check if token is available
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
        logger.error("Please set your Telegram bot token and restart the application.")
        sys.exit(1)
    else:
        # Only log that we have a token, not the token itself
        logger.info("TELEGRAM_BOT_TOKEN is set and available")
    
    try:
        logger.info("Starting Telegram bot...")
        bot = SimpleTelegramBot()
        logger.info("Bot instance created successfully, about to start polling")
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")
        sys.exit(1)

# This is what Gunicorn expects - a wsgi app
def application(environ, start_response):
    """WSGI application function to keep Gunicorn happy"""
    # Log WSGI application startup
    logger.info("WSGI application function called")
    
    # Start the bot in a separate thread
    import threading
    logger.info("Starting bot in a separate thread")
    bot_thread = threading.Thread(target=main)
    bot_thread.daemon = True
    bot_thread.start()
    logger.info(f"Bot thread started with ID: {bot_thread.ident}")
    
    # Return a simple response to keep Gunicorn happy
    status = '200 OK'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)
    return [b"Telegram bot is running in the background."]

# This variable is what Gunicorn looks for
app = application

if __name__ == "__main__":
    logger.info("Running as standalone Python script")
    main()
