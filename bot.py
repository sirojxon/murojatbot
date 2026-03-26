import os
import logging
import asyncio
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from google import genai

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.environ.get("PORT", 10000))

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

# Dictionary to store chat history
chat_history = {}

# --- Health Check Server ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive and healthy!")

def run_health_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthCheckHandler)
        logger.info(f"Health check server started on port {PORT}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start health server: {e}")

# --- Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from user {update.effective_user.id}")
    welcome_text = (
        f"Salom {update.effective_user.first_name}! 👋\n\n"
        "Men Gemini 1.5 Flash AI botman. Savolingizni yuboring!"
    )
    await update.message.reply_text(welcome_text)

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_history[user_id] = []
    await update.message.reply_text("Suhbat tarixi tozalandi! 🧹")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    logger.info(f"Received message from {user_id}: {user_text}")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    if user_id not in chat_history:
        chat_history[user_id] = []

    try:
        history = chat_history[user_id]
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=history + [user_text]
        )
        ai_response = response.text
        
        chat_history[user_id].append(f"User: {user_text}")
        chat_history[user_id].append(f"AI: {ai_response}")
        if len(chat_history[user_id]) > 20:
            chat_history[user_id] = chat_history[user_id][-20:]

        await update.message.reply_text(ai_response, parse_mode='Markdown')
        logger.info(f"Sent AI response to {user_id}")
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        await update.message.reply_text("Xatolik yuz berdi. Iltimos qayta urinib ko'ring.")

if __name__ == '__main__':
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
        logger.error("Missing tokens in environment!")
        exit(1)

    # Delay to avoid Conflict error from previous instances
    logger.info("Waiting 10 seconds for old sessions to clear...")
    time.sleep(10)

    # Start health server
    threading.Thread(target=run_health_server, daemon=True).start()

    # Start Telegram Bot
    logger.info("Starting Telegram Bot...")
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('clear', clear))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat))
    
    application.run_polling()
