import os
import logging
import sys
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Import all the necessary functions from bot.py
from bot import start, help_command, about_command, format_command, settings_command, summarize_command
from bot import button_callback, handle_message, error_handler, setup_commands

# Enhanced logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("Missing required environment variables")
    sys.exit(1)

def main():
    """Start the bot."""
    try:
        # Create application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("about", about_command))
        application.add_handler(CommandHandler("format", format_command))
        application.add_handler(CommandHandler("settings", settings_command))
        application.add_handler(CommandHandler("summarize", summarize_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Setup commands menu
        application.post_init = setup_commands
        
        logger.info("Bot is starting...")
        
        # Start the bot with proper v20+ syntax
        application.run_polling(allowed_updates=["message", "callback_query", "chat_member"])
        
    except Exception as e:
        logger.error(f"Critical error starting bot: {str(e)}")
        raise

if __name__ == '__main__':
    main() 