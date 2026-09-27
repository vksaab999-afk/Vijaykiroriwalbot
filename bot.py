import os
import logging
import asyncio
from urllib.parse import quote
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ChatJoinRequestHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Logging Setup
logging.basicConfig(level=logging.INFO)

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN") 

# Multiple Admins Support
ADMIN_IDS = [5785924075, 8802096404]

# MongoDB Atlas URI
MONGO_URI = os.environ.get("MONGO_URI")

# Source Chat & Message IDs
SOURCE_CHAT_ID = 5785924075

# Message IDs
MSG_ID_16 = 16  # Initial Welcome Message
MSG_ID_14 = 14  # WhatsApp & Telegram Contact Message
MSG_ID_18 = 18  # Payment Message

# Contact Info & Pre-filled Messages
TG_USERNAME = "vijaykiroriwal"
WHATSAPP_NUMBER = "8233476434"

TG_PAYMENT_TEXT = "Vijay sir mene payment kar diya hai niche screenshot bhej raha hu"
WA_BUSINESS_TEXT = "Vijay sir mene telegram pe aapse baat ki thii mujhe business shuru karna hai ✅"
TG_READY_TEXT = "I'm ready"

# Deep-link URLs with pre-filled text
URL_TG_PAYMENT = f"https://t.me/{TG_USERNAME}?text={quote(TG_PAYMENT_TEXT)}"
URL_WA_BUSINESS = f"https://wa.me/{WHATSAPP_NUMBER}?text={quote(WA_BUSINESS_TEXT)}"
URL_TG_READY = f"https://t.me/{TG_USERNAME}?text={quote(TG_READY_TEXT)}"

# Custom Emoji IDs for Inline Buttons
EMOJI_INTERESTED = "4956222745814762495"  # Red / Danger Icon Emoji
EMOJI_PAYMENT = "5447183459602669338"     # Blue / Primary Emoji
EMOJI_WHATSAPP = "5935973359480213803"    # Green / WhatsApp Emoji
# =======================================================

# --- MONGODB SETUP ---
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["telegram_bot_db"]
users_collection = db["users"]

def save_user_to_mongo(user_id, first_name, username):
    try:
        users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "first_name": first_name,
                    "username": username
                }
            },
            upsert=True
        )
    except Exception as e:
        logging.error(f"MongoDB Error: {e}")

# --- KEEP-ALIVE WEB SERVER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("<html><body><h1>Bot is Live and MongoDB Connected!</h1></body></html>", "utf-8"))

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
    
    def log_message(self, format, *args):
        return

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# --- STYLED INLINE BUTTON HELPER ---
def styled_button(text, *, style=None, icon_custom_emoji_id=None, url=None, callback_data=None):
    action = {}
    if url:
        action["url"] = url
    else:
        action["callback_data"] = callback_data or "noop"

    modern = {"text": text, **action}
    if style:
        modern["style"] = style
    if icon_custom_emoji_id:
        modern["icon_custom_emoji_id"] = icon_custom_emoji_id

    try:
        return InlineKeyboardButton(**modern)
    except TypeError:
        api_kwargs = {}
        if style:
            api_kwargs["style"] = style
        if icon_custom_emoji_id:
            api_kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id

        if api_kwargs:
            try:
                return InlineKeyboardButton(text=text, api_kwargs=api_kwargs, **action)
            except TypeError:
                return InlineKeyboardButton(text=text, **action)
        return InlineKeyboardButton(text=text, **action)

# --- WORKFLOW FUNCTIONS ---

async def send_initial_flow(context: ContextTypes.DEFAULT_TYPE, user_id: int, first_name: str):
    """
    Step 1:
    - Message ID 16 Bheja jayega akela RED Inline Button ke saath.
    - Message ID 14 (WhatsApp & Telegram links) Bheja jayega.
    """
    # MSG 16: Akela Red Inline Button
    keyboard_16 = [
        [
            styled_button(
                "I'm Interested 🔴",
                style="danger",  # RED COLOR BUTTON
                icon_custom_emoji_id=EMOJI_INTERESTED,
                callback_data="btn_interested"
            )
        ]
    ]
    markup_16 = InlineKeyboardMarkup(keyboard_16)

    # MSG 14: WhatsApp & Telegram Buttons
    keyboard_14 = [
        [
            styled_button(
                "Start Business on WhatsApp",
                style="success",
                icon_custom_emoji_id=EMOJI_WHATSAPP,
                url=URL_WA_BUSINESS
            )
        ],
        [
            styled_button(
                "I'm Ready (Telegram)",
                style="primary",
                url=URL_TG_READY
            )
        ]
    ]
    markup_14 = InlineKeyboardMarkup(keyboard_14)

    try:
        # Send MSG 16
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_ID_16,
            reply_markup=markup_16
        )Lagta hai code poora nahi aaya ya aadhha hi cut gaya! 

Aap apna poora code, problem, ya aap kya banane ki koshish kar rahe hain yahan paste kar dijiye—main dekhta hoon ki usme kya bacha hai ya kya galti hai.
