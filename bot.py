import os
import logging
import asyncio
import re
from urllib.parse import quote, quote_plus
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

# MongoDB Atlas URI Fix for Special Characters
MONGO_URI = os.environ.get("MONGO_URI", "")

def format_mongo_uri(uri: str) -> str:
    """Escapes special characters in password if present in standard mongodb/mongodb+srv URI"""
    if not uri:
        return uri
    pattern = r"^(mongodb(?:\+srv)?://)([^:]+):([^@]+)@(.+)$"
    match = re.match(pattern, uri)
    if match:
        prefix, user, password, rest = match.groups()
        # Clean unencoded special characters in username & password
        encoded_user = quote_plus(user)
        encoded_pass = quote_plus(password)
        return f"{prefix}{encoded_user}:{encoded_pass}@{rest}"
    return uri

FINAL_MONGO_URI = format_mongo_uri(MONGO_URI)

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
mongo_client = MongoClient(FINAL_MONGO_URI)
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
    exceptSamajh gaya! Ho sakta hai pichhle code me koi bug ya logic mistake reh gayi ho. 

Galti pakadne aur usko sahi karne ke liye mujhe thoda context chahiye hoga:

1. **Aap kaun sa code try kar rahe the?** (Kis programming language/framework me hai?)
2. **Exactly kya dikkat ya error aa raha hai?** (Output galat aa raha hai, code crash ho raha hai, ya koi error message mil raha hai?)

Aap bas apna purana code (ya problem ka description) aur error yahan paste kar do. Main ise thoroughly re-check karke bilkul sahi aur working code dobara bhej deta hoon.
