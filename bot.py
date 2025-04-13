import os
import logging
import re
import html
import sys
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from youtube_transcript_api import YouTubeTranscriptApi
from model_manager import GoogleAIModelManager
try:
    from iso639 import languages
except ImportError:
    # Define a simple fallback if iso639 is not installed
    class LanguageFallback:
        def get(self, part1=None):
            class LangObj:
                def __init__(self, code):
                    self.name = code.upper()
            return LangObj(part1)
    languages = LanguageFallback()

# Enhanced logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables with error handling
try:
    # Try to load from .env file if it exists, but don't require it
    try:
        load_dotenv()
        logger.info("Loaded environment variables from .env file")
    except Exception as e:
        logger.info("No .env file found, using system environment variables")
    
    # Get environment variables directly
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Log the first few characters of each token for debugging
    if TELEGRAM_BOT_TOKEN:
        logger.info(f"TELEGRAM_BOT_TOKEN found (starts with: {TELEGRAM_BOT_TOKEN[:4]}...)")
    else:
        logger.error("TELEGRAM_BOT_TOKEN not found")
        
    if GEMINI_API_KEY:
        logger.info(f"GEMINI_API_KEY found (starts with: {GEMINI_API_KEY[:4]}...)")
    else:
        logger.error("GEMINI_API_KEY not found")
    
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
        raise ValueError("Missing required environment variables")
    
    logger.info("Environment variables loaded successfully")
except Exception as e:
    logger.error(f"Failed to load environment variables: {str(e)}")
    raise

# Initialize model manager with error handling
try:
    model_manager = GoogleAIModelManager(GEMINI_API_KEY)
    logger.info("Model manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize model manager: {str(e)}")
    raise

# Bot settings (can be customized per user in the future)
SUMMARY_SETTINGS = {
    'mode': 'detailed',  # 'short', 'detailed', or 'bullet'
    'tone': 'simple',    # 'simple', 'technical', or 'beginner-friendly'
    'chunk_size': 180,   # seconds (3 minutes)
    'confidence_threshold': 0.7
}

# Define conversation states
WAITING_FOR_URL = 1

# User states dictionary
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    keyboard = [
        [
            InlineKeyboardButton("🎥 Summarize Video", callback_data='summarize'),
            InlineKeyboardButton("⚙️ Settings", callback_data='settings')
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data='help'),
            InlineKeyboardButton("ℹ️ About", callback_data='about')
        ],
        [
            InlineKeyboardButton("🔗 URL Formats", callback_data='format')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        "👋 Welcome to YouTube Summarizer Bot!\n\n"
        "I can help you get quick summaries of YouTube videos.\n\n"
        "Click '🎥 Summarize Video' to start, or choose another option:"
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "<b>🤖 Available Commands:</b>\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/about - About this bot\n"
        "/format - Show supported URL formats\n"
        "/settings - Show current settings\n\n"
        "<b>📝 How to use:</b>\n"
        "1. Simply send a YouTube URL\n"
        "2. Wait for the summary\n"
        "3. Enjoy the concise version!\n\n"
        "⚠️ Note: Video must have English captions/subtitles available"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /about is issued."""
    about_text = (
        "<b>🤖 YouTube Summarizer Bot</b>\n\n"
        "This bot uses Google's Gemini 2.5 Pro AI to create concise summaries "
        "of YouTube videos. Simply send a video URL and get a quick summary!\n\n"
        "<b>🛠 Technologies Used:</b>\n"
        "• Google Gemini 2.5 Pro AI\n"
        "• YouTube Transcript API\n"
        "• Python Telegram Bot\n\n"
        "Created with ❤️ to save your time!"
    )
    await update.message.reply_text(about_text, parse_mode='HTML')

async def format_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show supported URL formats."""
    format_text = (
        "<b>🔗 Supported YouTube URL Formats:</b>\n\n"
        "• Regular Videos:\n"
        "  <code>https://www.youtube.com/watch?v=VIDEO_ID</code>\n\n"
        "• Short URLs:\n"
        "  <code>https://youtu.be/VIDEO_ID</code>\n\n"
        "• Embedded Videos:\n"
        "  <code>https://www.youtube.com/embed/VIDEO_ID</code>\n\n"
        "• YouTube Shorts:\n"
        "  <code>https://youtube.com/shorts/VIDEO_ID</code>"
    )
    await update.message.reply_text(format_text, parse_mode='HTML')

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current settings and model status."""
    keyboard = [
        [
            InlineKeyboardButton("📝 Summary Mode", callback_data='set_mode'),
            InlineKeyboardButton("🎯 Tone", callback_data='set_tone')
        ],
        [
            InlineKeyboardButton("⚡ Chunk Size", callback_data='set_chunk'),
            InlineKeyboardButton("📊 Model Status", callback_data='model_status')
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data='cancel')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    settings_text = (
        "<b>⚙️ Current Settings:</b>\n\n"
        f"📝 Mode: {SUMMARY_SETTINGS['mode'].capitalize()}\n"
        f"🎯 Tone: {SUMMARY_SETTINGS['tone'].capitalize()}\n"
        f"⚡ Chunk Size: {SUMMARY_SETTINGS['chunk_size']} seconds\n\n"
        f"🤖 Current Model: {model_manager.current_model_name}\n\n"
        "Select a setting to change:"
    )
    await update.message.reply_text(settings_text, reply_markup=reply_markup, parse_mode='HTML')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data == 'summarize':
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎥 <b>Please send me the YouTube video URL you want to summarize.</b>\n\n"
            "You can send:\n"
            "• Regular video links\n"
            "• Short links (youtu.be)\n"
            "• YouTube Shorts\n\n"
            "⚠️ The video must have English captions available.",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        user_states[update.effective_user.id] = WAITING_FOR_URL
    
    elif query.data == 'cancel':
        if update.effective_user.id in user_states:
            del user_states[update.effective_user.id]
        await query.edit_message_text(
            "❌ Operation cancelled. Send /start to begin again.",
            parse_mode='HTML'
        )
    elif query.data == 'help':
        await help_command(query, context)
    elif query.data == 'about':
        await about_command(query, context)
    elif query.data == 'format':
        await format_command(query, context)
    elif query.data == 'settings':
        await settings_command(query, context)
    elif query.data == 'set_mode':
        keyboard = [
            [
                InlineKeyboardButton("📄 Detailed", callback_data='mode_detailed'),
                InlineKeyboardButton("📌 Bullet", callback_data='mode_bullet')
            ],
            [
                InlineKeyboardButton("⚡ Short", callback_data='mode_short'),
                InlineKeyboardButton("❌ Cancel", callback_data='cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "<b>📝 Select Summary Mode:</b>\n\n"
            "📄 Detailed: Full paragraphs with sections\n"
            "📌 Bullet: Clean bullet points\n"
            "⚡ Short: Quick 3-line summary",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    elif query.data == 'set_tone':
        keyboard = [
            [
                InlineKeyboardButton("👥 Simple", callback_data='tone_simple'),
                InlineKeyboardButton("🔬 Technical", callback_data='tone_technical')
            ],
            [
                InlineKeyboardButton("🎓 Beginner", callback_data='tone_beginner-friendly'),
                InlineKeyboardButton("❌ Cancel", callback_data='cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "<b>🎯 Select Summary Tone:</b>\n\n"
            "👥 Simple: Everyday language\n"
            "🔬 Technical: Precise terminology\n"
            "🎓 Beginner: Explanatory style",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    elif query.data == 'set_chunk':
        keyboard = [
            [
                InlineKeyboardButton("3 min", callback_data='chunk_180'),
                InlineKeyboardButton("5 min", callback_data='chunk_300')
            ],
            [
                InlineKeyboardButton("10 min", callback_data='chunk_600'),
                InlineKeyboardButton("❌ Cancel", callback_data='cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "<b>⚡ Select Chunk Size:</b>\n\n"
            "Choose how to split long videos:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    elif query.data.startswith('mode_'):
        SUMMARY_SETTINGS['mode'] = query.data.split('_')[1]
        await show_settings_updated(query, "Summary mode")
    elif query.data.startswith('tone_'):
        SUMMARY_SETTINGS['tone'] = query.data.split('_')[1]
        await show_settings_updated(query, "Summary tone")
    elif query.data.startswith('chunk_'):
        SUMMARY_SETTINGS['chunk_size'] = int(query.data.split('_')[1])
        await show_settings_updated(query, "Chunk size")
    elif query.data == 'model_status':
        await show_model_status(query)

async def show_settings_updated(query: CallbackQuery, setting_type: str):
    """Show updated settings message."""
    await query.edit_message_text(
        f"✅ {setting_type} updated!\n\n"
        "<b>⚙️ Current Settings:</b>\n\n"
        f"📝 Mode: {SUMMARY_SETTINGS['mode'].capitalize()}\n"
        f"🎯 Tone: {SUMMARY_SETTINGS['tone'].capitalize()}\n"
        f"⚡ Chunk Size: {SUMMARY_SETTINGS['chunk_size']} seconds\n\n"
        "Use /settings to make more changes.",
        parse_mode='HTML'
    )

async def show_model_status(query: CallbackQuery):
    """Show the current status of all AI models."""
    status = model_manager.get_model_status()
    
    status_text = "<b>🤖 AI Model Status:</b>\n\n"
    for model_name, info in status.items():
        status_text += f"<b>{model_name}</b>\n"
        status_text += f"• Available: {'✅' if info['available'] else '❌'}\n"
        status_text += f"• Quota Remaining: {'✅' if info['quota_remaining'] else '❌'}\n"
        if info['cooldown_remaining']:
            status_text += f"• Cooldown: {info['cooldown_remaining']}\n"
        if info['last_success']:
            status_text += f"• Last Success: {info['last_success']}\n"
        status_text += "\n"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data='model_status'),
                InlineKeyboardButton("⬅️ Back", callback_data='settings')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(status_text, reply_markup=reply_markup, parse_mode='HTML')

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/|/embed/)([^&?/]+)',
        r'youtube.com/shorts/([^&?/]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_transcript(video_id: str) -> str:
    """Fetch and combine video transcript (English only)."""
    try:
        # Get English transcript
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        logger.info("Found English transcript")
        
        # Combine all transcript pieces into one text
        return " ".join([entry['text'] for entry in transcript_list])
    except Exception as e:
        logger.error(f"Error fetching transcript: {str(e)}")
        raise Exception("No English transcript available for this video")

def chunk_transcript(transcript: str, chunk_size_seconds: int = 180) -> list:
    """Split transcript into smaller chunks based on estimated duration."""
    # Rough estimation: average speaking rate is about 150 words per minute
    words = transcript.split()
    words_per_chunk = (chunk_size_seconds / 60) * 150
    chunks = []
    
    for i in range(0, len(words), int(words_per_chunk)):
        chunk = ' '.join(words[i:i + int(words_per_chunk)])
        chunks.append(chunk)
    
    return chunks

def format_summary_by_mode(summary: str, mode: str) -> str:
    """Format the summary based on the selected mode."""
    if mode == 'short':
        # Extract or generate a 3-line summary
        lines = summary.split('\n')
        key_points = [line for line in lines if line.strip() and not line.startswith(('📝', '🎯', '💡', '🔑'))][:3]
        return "📝 Quick Summary:\n\n" + '\n'.join(key_points)
    
    elif mode == 'bullet':
        # Keep the bullet point format but make it more concise
        return summary
    
    else:  # detailed mode
        # Convert bullet points into coherent paragraphs
        sections = summary.split('\n\n')
        formatted_sections = []
        
        for section in sections:
            if any(section.startswith(emoji) for emoji in ['📝', '🎯', '💡', '🔑']):
                # Keep section headers
                formatted_sections.append(section)
            else:
                # Convert bullets to paragraph
                points = [p.strip('• ').strip() for p in section.split('\n') if p.strip()]
                paragraph = ' '.join(points)
                formatted_sections.append(paragraph)
        
        return '\n\n'.join(formatted_sections)

async def generate_summary(transcript: str, is_english: bool = True) -> str:
    """Generate summary using Google AI models with fallback support."""
    try:
        # Split transcript into chunks
        chunks = chunk_transcript(transcript, SUMMARY_SETTINGS['chunk_size'])
        all_summaries = []
        
        for chunk in chunks:
            tone_instruction = {
                'simple': "Use simple, everyday language",
                'technical': "Use technical, precise language",
                'beginner-friendly': "Explain concepts as if to a beginner"
            }[SUMMARY_SETTINGS['tone']]
            
            prompt = f"""Analyze this part of the video transcript and create a structured summary.
            {tone_instruction} and focus on clarity and coherence.

            Format the output with these sections:

            📝 Main Points & Key Takeaways
            [Key messages and central ideas]

            🎯 Important Details
            [Specific examples and supporting information]

            💡 Insights & Analysis
            [Deeper understanding and interpretations]

            🔑 Practical Applications
            [Actionable takeaways and real-world applications]

            Guidelines:
            - Start each bullet point with a relevant emoji
            - Be concise and clear
            - Remove any filler content or redundant information
            - Ensure high confidence in the output
            - Make each point meaningful and substantive

            Transcript chunk:
            {chunk}"""
            
            logger.info("Processing transcript chunk...")
            try:
                summary = await model_manager.generate_content(prompt)
                if summary:
                    all_summaries.append(summary)
            except Exception as e:
                logger.error(f"Error processing chunk: {str(e)}")
                continue
        
        if not all_summaries:
            raise Exception("Failed to generate summary for any chunk of the transcript.")
        
        # Combine all chunk summaries
        combined_summary = '\n\n'.join(all_summaries)
        
        # Post-process the summary
        processed_summary = format_summary_by_mode(combined_summary, SUMMARY_SETTINGS['mode'])
        
        return processed_summary
        
    except Exception as e:
        logger.error("Error in generate_summary: %s", str(e))
        raise Exception(f"Summary generation failed: {str(e)}")

def sanitize_html(text):
    """Sanitize text for HTML formatting with improved spacing and structure."""
    # First escape any HTML special characters
    text = html.escape(text)
    
    # Preserve emojis and section headers
    sections = text.split('\n\n')
    formatted_sections = []
    
    for section in sections:
        if section.strip():
            # If it's a header (starts with emoji)
            if any(section.startswith(emoji) for emoji in ['📝', '🎯', '💡', '🔑']):
                # Format header with proper spacing
                header = section.strip()
                header = re.sub(r'[*]', '', header)  # Remove asterisks
                formatted_sections.append(f"\n<b>{header}</b>\n")
            else:
                # Format content based on summary mode
                if SUMMARY_SETTINGS['mode'] == 'detailed':
                    # Format as paragraph
                    formatted_sections.append(f"{section.strip()}\n")
                else:
                    # Format as bullet points with proper spacing
                    lines = [line.strip() for line in section.split('\n') if line.strip()]
                    formatted_lines = []
                    for line in lines:
                        # Clean up the line
                        line = re.sub(r'^\d+\.\s*', '', line)  # Remove numbering
                        line = re.sub(r'[*]', '', line)        # Remove asterisks
                        line = re.sub(r'^[•\-]\s*', '', line.strip())  # Remove existing bullets
                        if line:
                            # Add emoji if line doesn't start with one
                            if not any(line.startswith(emoji) for emoji in ['📝', '🎯', '💡', '🔑', '⚡', '📌', '✨', '💫', '🔍', '💡', '📊', '🎯', '🎨', '💪', '🌟']):
                                line = f"📌 {line}"
                            formatted_lines.append(f"&#8226; {line}\n")
                    formatted_sections.append(''.join(formatted_lines))
    
    # Join sections with proper spacing
    return '\n'.join(formatted_sections)

def split_message(message: str, max_length: int = 4000) -> list:
    """Split a long message into smaller chunks that fit within Telegram's message limit."""
    # If message is short enough, return it as is
    if len(message) <= max_length:
        return [message]
    
    sections = message.split('\n\n')
    chunks = []
    current_chunk = ""
    current_header = ""
    
    for section in sections:
        # If it's a header (starts with emoji)
        if any(section.strip().startswith(emoji) for emoji in ['📝', '🎯', '💡', '🔑']):
            # If we have content in current_chunk, save it
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_header = section
            current_chunk = f"<b>🎥 Video Summary (Continued):</b>\n\n{current_header}\n"
        else:
            # Check if adding this section would exceed the limit
            potential_chunk = current_chunk + "\n" + section if current_chunk else section
            if len(potential_chunk) > max_length:
                # Save current chunk and start new one with same header
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = f"<b>🎥 Video Summary (Continued):</b>\n\n{current_header}\n{section}"
            else:
                current_chunk = potential_chunk
    
    # Add the last chunk if it has content
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    user_id = update.effective_user.id
    
    # Check if we're waiting for a URL from this user
    if user_id in user_states and user_states[user_id] == WAITING_FOR_URL:
        # Clear the state
        del user_states[user_id]
        
        # Process the URL
        await handle_youtube_url(update, context)
    else:
        # If it looks like a YouTube URL, process it
        if any(pattern in update.message.text for pattern in ['youtube.com', 'youtu.be']):
            await handle_youtube_url(update, context)
        else:
            # Show the main menu
            keyboard = [
                [
                    InlineKeyboardButton("🎥 Summarize Video", callback_data='summarize'),
                    InlineKeyboardButton("⚙️ Settings", callback_data='settings')
                ],
                [
                    InlineKeyboardButton("❓ Help", callback_data='help'),
                    InlineKeyboardButton("ℹ️ About", callback_data='about')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "👋 Please click '🎥 Summarize Video' to start, or choose another option:",
                reply_markup=reply_markup
            )

def escape_markdown(text):
    """Escape special characters for Markdown V2 format."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

async def setup_commands(application: Application):
    """Set up the bot commands in Telegram UI."""
    commands = [
        BotCommand("start", "Start the bot and show main menu"),
        BotCommand("summarize", "Summarize a YouTube video"),
        BotCommand("settings", "Adjust summary settings"),
        BotCommand("help", "Show help information"),
        BotCommand("about", "About this bot"),
        BotCommand("format", "Show supported URL formats")
    ]
    await application.bot.set_my_commands(commands)

async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /summarize command."""
    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎥 <b>Please send me the YouTube video URL you want to summarize.</b>\n\n"
        "You can send:\n"
        "• Regular video links\n"
        "• Short links (youtu.be)\n"
        "• YouTube Shorts\n\n"
        "⚠️ The video must have English captions available.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    user_states[update.effective_user.id] = WAITING_FOR_URL

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the telegram bot."""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        if update and hasattr(update, 'effective_message'):
            await update.effective_message.reply_text(
                "❌ An error occurred while processing your request.\n"
                "The error has been logged and we'll look into it.",
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Failed to send error message: {str(e)}")

async def handle_youtube_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube URL messages."""
    try:
        # Send initial processing message
        processing_message = await update.message.reply_text(
            "<b>🔄 Processing your request...</b>\n"
            "This might take a few moments depending on the video length.",
            parse_mode='HTML'
        )
        
        # Extract video ID
        video_id = extract_video_id(update.message.text)
        if not video_id:
            await processing_message.edit_text(
                "❌ <b>Please send a valid YouTube URL</b>\n"
                "Use /format to see supported URL formats",
                parse_mode='HTML'
            )
            return
        
        # Get transcript
        try:
            logger.info("Fetching transcript for video ID: %s", video_id)
            transcript = get_transcript(video_id)
            logger.info("Transcript fetched successfully")
        except Exception as e:
            error_msg = str(e)
            logger.error("Transcript error: %s", error_msg)
            
            if "No transcripts available" in error_msg:
                error_text = (
                    "❌ <b>This video has no English captions available.</b>\n\n"
                    "Please try a video that has English captions enabled."
                )
            elif "not available" in error_msg.lower():
                error_text = (
                    "❌ <b>The English captions for this video are not accessible.</b>\n\n"
                    "This could be because:\n"
                    "&#8226; The video owner has disabled captions\n"
                    "&#8226; The captions are still processing\n"
                    "&#8226; The video has been deleted or is private\n\n"
                    "Please try another video with English captions."
                )
            else:
                error_text = (
                    "❌ <b>Unable to fetch English transcript.</b>\n\n"
                    "This could be because:\n"
                    "&#8226; The video has no English captions\n"
                    "&#8226; The captions are auto-generated and not publicly accessible\n"
                    "&#8226; The video owner has disabled captions\n\n"
                    "Try a different video with English subtitles enabled."
                )
            
            await processing_message.edit_text(error_text, parse_mode='HTML')
            return
        
        # Generate summary
        try:
            logger.info("Generating summary...")
            summary = await generate_summary(transcript, True)
            logger.info("Summary generated successfully")
            
            # Sanitize and format the summary
            safe_summary = sanitize_html(summary)
            
            # Split the message if it's too long
            message_parts = split_message(f"<b>🎥 Video Summary:</b>\n\n{safe_summary}")
            
            # Send the first part by editing the processing message
            await processing_message.edit_text(
                message_parts[0],
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            # Send any additional parts as new messages
            for part in message_parts[1:]:
                await update.message.reply_text(
                    part,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            
        except Exception as e:
            logger.error("Summary error: %s", str(e))
            error_message = (
                "❌ <b>Error generating summary.</b>\n"
                f"Error details: {html.escape(str(e))}\n"
                "Please try again later or contact support."
            )
            await processing_message.edit_text(error_message, parse_mode='HTML')
            return
        
    except Exception as e:
        logger.error("Error processing request: %s", str(e))
        await update.message.reply_text(
            "❌ <b>An error occurred while processing your request.</b>\n"
            f"Error details: {html.escape(str(e))}",
            parse_mode='HTML'
        )

def main():
    """Start the bot with enhanced error handling."""
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
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Setup commands menu
        application.post_init = setup_commands
        
        logger.info("Bot is starting...")
        
        # Start the bot with error handling
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Don't process updates from when the bot was offline
            timeout=30,  # Increase timeout
            read_timeout=30,
            write_timeout=30,
            pool_timeout=30,
            connect_timeout=30
        )
        
    except Exception as e:
        logger.error(f"Critical error starting bot: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1) 