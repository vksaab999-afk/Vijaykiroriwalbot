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
MSG_ID_16 = 16  # Welcome Message
MSG_ID_14 = 14  # WhatsApp & Telegram Contact Message
MSG_ID_18 = 18  # Payment Message (Sent on clicking "I'm Interested")

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

# Custom Emoji IDs
EMOJI_INTERESTED = "4956222745814762495"
EMOJI_PAYMENT = "5447183459602669338"
EMOJI_WHATSAPP = "5935973359480213803"
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

# --- BUTTON CREATOR WITH CUSTOM EMOJI SUPPORT ---
def create_button(text, url=None, callback_data=None, custom_emoji_id=None):
    api_kwargs = {}
    if custom_emoji_id:
        api_kwargs["icon_custom_emoji_id"] = custom_emoji_id

    if url:
        if api_kwargs:
            return InlineKeyboardButton(text=text, url=url, api_kwargs=api_kwargs)
        return InlineKeyboardButton(text=text, url=url)
    elif callback_data:
        if api_kwargs:
            return InlineKeyboardButton(text=text, callback_data=callback_data, api_kwargs=api_kwargs)
        return InlineKeyboardButton(text=text, callback_data=callback_data)
    
    return InlineKeyboardButton(text=text, callback_data="noop")

# --- WORKFLOW FUNCTIONS ---

async def send_initial_flow(context: ContextTypes.DEFAULT_TYPE, user_id: int, first_name: str):
    """
    Step 1: Pehle Message ID 16 bhejega (I'm Interested button ke sath), 
    aur TURANT baad Message ID 14 bhejega (WhatsApp & Telegram buttons ke sath).
    """
    # Button for Message 16
    keyboard_16 = [
        [
            create_button(
                "I'm Interested",
                callback_data="btn_interested",
                custom_emoji_id=EMOJI_INTERESTED
            )
        ]
    ]
    markup_16 = InlineKeyboardMarkup(keyboard_16)

    # Buttons for Message 14
    keyboard_14 = [
        [
            create_button(
                "Start Business on WhatsApp",
                url=URL_WA_BUSINESS,
                custom_emoji_id=EMOJI_WHATSAPP
            )
        ],
        [
            create_button(
                "I'm Ready (Telegram)",
                url=URL_TG_READY
            )
        ]
    ]
    markup_14 = InlineKeyboardMarkup(keyboard_14)

    try:
        # Message ID 16 bhej raha hai
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_ID_16,
            reply_markup=markup_16
        )
        
        # Turant Message ID 14 bhej raha hai
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_ID_14,
            reply_markup=markup_14
        )
    except Exception as e:
        logging.error(f"Error sending MSG_ID_16 or 14 to user {user_id}: {e}")

async def handle_interested_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 2: Jab user 'I'm Interested' par click karega, tab SIRF Message ID 18 jayega.
    """
    query = update.callback_query
    await query.answer()

    user = query.from_user
    save_user_to_mongo(user.id, user.first_name, user.username)

    # Button for Message 18
    keyboard_18 = [
        [
            create_button(
                "Send Payment Screenshot",
                url=URL_TG_PAYMENT,
                custom_emoji_id=EMOJI_PAYMENT
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

# --- HANDLERS ---

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    user = request.from_user
    save_user_to_mongo(user.id, user.first_name, user.username)
    await send_initial_flow(context, user.id, user.first_name)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user_to_mongo(user.id, user.first_name, user.username)
    await send_initial_flow(context, user.id, user.first_name)

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
                await context.bot.send_video(chat_id=u_id, video=message_to_broadcast.video.file_id, caption=message_to_broadcast.caption, caption_entities=message_to_broadcast.caption_entities)
            elif message_to_broadcast.audio:
                await context.bot.send_audio(chat_id=u_id, audio=message_to_broadcast.audio.file_id, caption=message_to_broadcast.caption, caption_entities=message_to_broadcast.caption_entities)
            elif message_to_broadcast.voice:
                await context.bot.send_voice(chat_id=u_id, voice=message_to_broadcast.voice.file_id, caption=message_to_broadcast.caption, caption_entities=message_to_broadcast.caption_entities)
            elif message_to_broadcast.document:
                await context.bot.send_document(chat_id=u_id, document=message_to_broadcast.document.file_id, caption=message_to_broadcast.caption, caption_entities=message_to_broadcast.caption_entities)
            
            await asyncio.sleep(0.04)
        except Exception as e:
            logging.error(f"Error sending to {u_id}: {e}")

    await context.bot.send_message(
        chat_id=admin_chat_id, 
        text="✅ Broadcast Completed!", 
        parse_mode="Markdown"
    )

async def auto_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if update.effective_user.id not in ADMIN_IDS:
        return
    if msg.text and msg.text.startswith("/"):
        return
    await execute_broadcast(msg, context, update.effective_user.id)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if update.effective_user.id not in ADMIN_IDS:
        return

    if msg.reply_to_message:
        await execute_broadcast(msg.reply_to_message, context, update.effective_user.id)
    else:
        text_after_command = msg.text.replace("/broadcast", "").strip()
        if text_after_command:
            users = list(users_collection.find({"user_id": {"$nin": ADMIN_IDS}}, {"user_id": 1}))
            for u in users:
                try:
                    await context.bot.send_message(chat_id=u["user_id"], text=text_after_command)
                    await asyncio.sleep(0.04)
                except:
                    pass
            await msg.reply_text("✅ Broadcast Completed!")
        else:
            await msg.reply_text("⚠️ Kripya message ke sath /broadcast likhein ya kisi message par reply karke /broadcast bhejein.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        total_users = users_collection.count_documents({})
        await update.message.reply_text(f"📊 **Total Users:** `{total_users}`", parse_mode="Markdown")

def main():
    Thread(target=run_web_server, daemon=True).start()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands & Join Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))

    # Callback Query Handler for "I'm Interested" button
    app.add_handler(CallbackQueryHandler(handle_interested_click, pattern="^btn_interested$"))

    # Admin Auto Broadcast Handler
    app.add_handler(MessageHandler(filters.User(ADMIN_IDS) & ~filters.COMMAND, auto_broadcast))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
