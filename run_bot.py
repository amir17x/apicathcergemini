#!/usr/bin/env python3
"""
This script runs the Telegram bot directly.
"""

import logging
import os
import sys
from telegram_bot_simple import SimpleTelegramBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("telegram_bot.log"),
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main function to run the telegram bot"""
    logger.info("=" * 50)
    logger.info("TELEGRAM BOT STANDALONE SCRIPT STARTING")
    logger.info("=" * 50)
    
    # Check if token is available
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
        logger.error("Please set your Telegram bot token and restart the script.")
        sys.exit(1)
    else:
        logger.info("TELEGRAM_BOT_TOKEN is available")
    
    try:
        logger.info("Starting Telegram bot...")
        bot = SimpleTelegramBot()
        logger.info("Bot instance created, starting to run")
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()