import os
import logging
import asyncio
from urllib.parse import quote
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from pymongo import MongoClient
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    InlineQueryResultArticle, 
    InputTextMessageContent
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ChatJoinRequestHandler,
    CallbackQueryHandler,
    MessageHandler,
    InlineQueryHandler,
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
def styled_button(text, *, style=None, icon_custom_emoji_id=None, url=None, callback_data=None, switch_inline_query_current_chat=None):
    action = {}
    if url:
        action["url"] = url
    elif switch_inline_query_current_chat is not None:
        action["switch_inline_query_current_chat"] = switch_inline_query_current_chat
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
    - Message ID 16 Bheja jayega RED Inline Button ke saath (Auto /start send karne ke liye).
    - Message ID 14 (WhatsApp & Telegram links) Bheja jayega.
    """
    # MSG 16: Red Inline Button with Auto-send /start functionality
    keyboard_16 = [
        [
            styled_button(
                "I'm Interested 🔴",
                style="danger",  # RED COLOR BUTTON
                icon_custom_emoji_id=EMOJI_INTERESTED,
                switch_inline_query_current_chat="interested"
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
        )
        
        # Send MSG 14
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_ID_14,
            reply_markup=markup_14
        )

    except Exception as e:
        logging.error(f"Error sending initial flow to user {user_id}: {e}")

async def send_payment_flow(context: ContextTypes.DEFAULT_TYPE, user):
    """
    Step 2:
    - User details save in MongoDB.
    - Send Message ID 18 (Payment Message).
    """
    save_user_to_mongo(user.id, user.first_name, user.username)

    keyboard_18 = [
        [
            styled_button(
                "Send Payment Screenshot",
                style="primary",
                icon_custom_emoji_id=EMOJI_PAYMENT,
                url=URL_TG_PAYMENT
            )
        ]
    ]
    markup_18 = InlineKeyboardMarkup(keyboard_18)

    try:
        await context.bot.copy_message(
            chat_id=user.id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_ID_18,
            reply_markup=markup_18
        )
    except Exception as e:
        logging.error(f"Error sending MSG_ID_18 to user {user.id}: {e}")

# --- INLINE QUERY HANDLER (Button click par user ki taraf se auto /start bhejega) ---
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = [
        InlineQueryResultArticle(
            id="1",
            title="🔴 Click to Send /start",
            description="Is par click karke /start bhein",
            input_message_content=InputTextMessageContent("/start")
        )
    ]
    await update.inline_query.answer(results, cache_time=1)

# --- HANDLERS ---

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    user = request.from_user
    save_user_to_mongo(user.id, user.first_name, user.username)
    await send_initial_flow(context, user.id, user.first_name)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user_to_mongo(user.id, user.first_name, user.username)
    
    # Jab user pehli baar join karta hai ya /start bhejta hai:
    # Agar usne button daba kar /start bheja hai toh payment flow (MSG 18) chala jayega.
    await send_payment_flow(context, user)

# --- BROADCAST LOGIC ---
async def execute_broadcast(message_to_broadcast, context, admin_chat_id):
    users = list(users_collection.find({"user_id": {"$nin": ADMIN_IDS}}, {"user_id": 1}))
    total_users = len(users)

    if total_users == 0:
        await context.bot.send_message(chat_id=admin_chat_id, text="⚠️ Database me aur koi user nahi hai!")
        return

    for u in users:
        u_id = u["user_id"]
        try:
            if message_to_broadcast.text:
                await context.bot.send_message(chat_id=u_id, text=message_to_broadcast.text, entities=message_to_broadcast.entities)
            elif message_to_broadcast.photo:
                await context.bot.send_photo(chat_id=u_id, photo=message_to_broadcast.photo[-1].file_id, caption=message_to_broadcast.caption, caption_entities=message_to_broadcast.caption_entities)
            elif message_to_broadcast.video:
                await context.bot.send_video(chat_id=u_id, video=message_to_broadcastSure, code dene ke liye mujhe thoda context chahiye hoga:

1. **Kis cheez ka code chahiye?** (e.g., website, mobile app, game, python script, etc.)
2. **Kis programming language ya framework mein?** (e.g., Python, JavaScript, React, C++, HTML/CSS, etc.)
3. **Pura functionality/feature kya hona chahiye?**

Thoda detail batao, main aapko pura aur ready-to-run code likh kar deta hoon!
