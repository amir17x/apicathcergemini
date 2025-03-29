#!/usr/bin/env python3
"""
This file now only imports and runs the Telegram bot.
It exists only for compatibility with the existing workflow.
"""

import logging
import os
import sys
from telegram_api import TelegramBot

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create a Flask app stub for compatibility
class FlaskAppStub:
    def run(self, host, port, debug):
        logger.info(f"Flask app stub called with host={host}, port={port}, debug={debug}")
        logger.info("Starting Telegram bot instead...")
        
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
            logger.error("Please set your Telegram bot token and restart the application.")
            sys.exit(1)
        
        try:
            bot = TelegramBot()
            bot.run()
        except Exception as e:
            logger.error(f"Bot stopped due to error: {e}")
            sys.exit(1)

# Create the flask app stub
app = FlaskAppStub()
