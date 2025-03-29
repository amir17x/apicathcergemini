import os
import logging
import signal
import sys
import threading
from telegram_api import TelegramBot

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

def run_bot_thread():
    """Run the Telegram bot in a separate thread"""
    try:
        bot = TelegramBot()
        bot.run()
    except Exception as e:
        logger.error(f"Bot thread error: {e}")

def handle_signals(signum, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

def main():
    """Main entry point"""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signals)
    signal.signal(signal.SIGTERM, handle_signals)
    
    # Check if TELEGRAM_BOT_TOKEN is set
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN environment variable is not set!")
        logger.warning("Please set your Telegram bot token using: export TELEGRAM_BOT_TOKEN=your_token")
        
    # Start bot in a separate thread
    bot_thread = threading.Thread(target=run_bot_thread)
    bot_thread.daemon = True
    bot_thread.start()
    
    logger.info("Bot started in background thread. Press CTRL+C to exit.")
    
    # Keep the main thread alive
    try:
        while True:
            bot_thread.join(1)
            if not bot_thread.is_alive():
                logger.error("Bot thread died unexpectedly, restarting...")
                bot_thread = threading.Thread(target=run_bot_thread)
                bot_thread.daemon = True
                bot_thread.start()
    except KeyboardInterrupt:
        logger.info("Main thread received keyboard interrupt, exiting.")
        sys.exit(0)

if __name__ == "__main__":
    main()
