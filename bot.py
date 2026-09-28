import os
import logging
import asyncio
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from urllib.parse import quote
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter, TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ChatMemberHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN") 

ADMIN_IDS = [5785924075, 8210667307]
MONGO_URI = os.environ.get("MONGO_URI")

SOURCE_CHAT_ID = 5785924075

# Step 1 Message IDs
WELCOME_MSG_16_ID = 16
WELCOME_MSG_14_ID = 14

# Step 2 Message ID
STEP2_MSG_18_ID = 18

# Emojis for Buttons
EMOJI_MSG16_BUTTON = "4956222745814762495"
EMOJI_TELEGRAM_WORK = "6170163662544707658"
EMOJI_WHATSAPP = "5935973359480213803"
EMOJI_FEEDBACK = "5332554596403404883"

# Analytics Emojis
EMOJI_STATS_HEADER = "5244837092042750681"
EMOJI_TOTAL_USERS = "4938653911507534983"
EMOJI_JOIN_REQS = "5156719794946311065"
EMOJI_LEFT_MEMBERS = "5201913231836199981"

# Broadcast performance settings
NUM_WORKERS = 10  # Number of parallel sender workers
# =======================================================

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["telegram_bot_db"]
users_collection = db["users"]
events_collection = db["chat_events"]

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
        logging.error(f"MongoDB User Save Error: {e}")

def log_event(user_id, event_type):
    try:
        events_collection.insert_one({
            "user_id": user_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc)
        })
    except Exception as e:
        logging.error(f"MongoDB Event Tracking Error: {e}")

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("<html><body><h1>Bot is Live!</h1></body></html>", "utf-8"))

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

def styled_button(text, *, style, icon_custom_emoji_id=None, url=None, callback_data=None):
    action = {"url": url} if url else {"callback_data": callback_data or "noop"}
    modern = {"text": text, **action, "style": style}
    if icon_custom_emoji_id:
        modern["icon_custom_emoji_id"] = icon_custom_emoji_id

    try:
        return InlineKeyboardButton(**modern)
    except TypeError:
        api_kwargs = {"style": style}
        if icon_custom_emoji_id:
            api_kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id
        try:
            return InlineKeyboardButton(text=text, api_kwargs=api_kwargs, **action)
        except TypeError:
            return InlineKeyboardButton(text=text, **action)

# --- STEP 1: WELCOME (MSG ID 16 & MSG ID 14 WITH BUTTONS) ---
async def send_initial_welcome(context: ContextTypes.DEFAULT_TYPE, user_id: int, first_name: str):
    try:
        welcome_text = f"👋🏻 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 {first_name} ❤️‍🔥TO OUR PRIVATE SERVER 🔥\n\n"
        await context.bot.send_message(chat_id=user_id, text=welcome_text)

        bot_info = await context.bot.get_me()
        start_link = f"https://t.me/{bot_info.username}?start=bonus"

        # Message 16 - Red Danger Button (triggers /start bonus)
        msg16_keyboard = [
            [styled_button("Get Started", style="danger", icon_custom_emoji_id=EMOJI_MSG16_BUTTON, url=start_link)]
        ]
        msg16_reply_markup = InlineKeyboardMarkup(msg16_keyboard)

        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=WELCOME_MSG_16_ID,
            reply_markup=msg16_reply_markup
        )

        # Message 14 Buttons Setup
        # 1. Blue Primary Button -> Direct DM with autofill text
        autofill_msg = quote("Vijay bhai mujhe work shuru karna hai")
        tg_work_url = f"https://t.me/vijaykiroriwal?text={autofill_msg}"

        # 2. Green WhatsApp Button
        wa_url = "https://alvo.chat/8aJ7"

        # 3. Red Feedback Button
        feedback_url = "https://t.me/vijaykiroriwal"

        msg14_keyboard = [
            [styled_button("Start Work", style="primary", icon_custom_emoji_id=EMOJI_TELEGRAM_WORK, url=tg_work_url)],
            [styled_button("WhatsApp Chat", style="success", icon_custom_emoji_id=EMOJI_WHATSAPP, url=wa_url)],
            [styled_button("Feedback", style="danger", icon_custom_emoji_id=EMOJI_FEEDBACK, url=feedback_url)]
        ]
        msg14_reply_markup = InlineKeyboardMarkup(msg14_keyboard)

        # Sending Msg ID 14
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=WELCOME_MSG_14_ID,
            reply_markup=msg14_reply_markup
        )
    except Exception as e:
        logging.error(f"Could not send initial welcome content to user {user_id}: {e}")

# --- STEP 2: SECOND FLOW (MSG ID 18) ---
async def send_full_original_flow(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        # Msg ID 18
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=STEP2_MSG_18_ID
        )

    except Exception as e:
        logging.error(f"Could not send full flow content to user {user_id}: {e}")

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    user = request.from_user
    
    save_user_to_mongo(user.id, user.first_name, user.username)
    log_event(user.id, "join_request")
    
    # Send Step 1 Only
    asyncio.create_task(send_initial_welcome(context, user.id, user.first_name))

async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return
    
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user = result.from_user

    if old_status in ["member", "administrator"] and new_status in ["left", "kicked"]:
        log_event(user.id, "left")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user_to_mongo(user.id, user.first_name, user.username)
    
    # Check if user triggered the link via Red button click
    if context.args and context.args[0] == "bonus":
        asyncio.create_task(send_full_original_flow(context, user.id))
    else:
        # Standard welcome trigger
        asyncio.create_task(send_initial_welcome(context, user.id, user.first_name))

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

# --- PARALLEL MULTI-WORKER BROADCAST ENGINE ---
async def broadcast_worker(queue, context, message_to_broadcast, stats_dict):
    reply_markup = message_to_broadcast.reply_markup
    while not queue.empty():
        u_id = await queue.get()
        sent = False
        retries = 3

        while retries > 0 and not sent:
            try:
                if message_to_broadcast.text:
                    await context.bot.send_message(
                        chat_id=u_id, 
                        text=message_to_broadcast.text, 
                        entities=message_to_broadcast.entities,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                elif message_to_broadcast.photo:
                    await context.bot.send_photo(
                        chat_id=u_id, 
                        photo=message_to_broadcast.photo[-1].file_id, 
                        caption=message_to_broadcast.caption, 
                        caption_entities=message_to_broadcast.caption_entities,
                        reply_markup=reply_markup
                    )
                elif message_to_broadcast.video:
                    await context.bot.send_video(
                        chat_id=u_id, 
                        video=message_to_broadcast.video.file_id, 
                        caption=message_to_broadcast.caption, 
                        caption_entities=message_to_broadcast.caption_entities,
                        reply_markup=reply_markup
                    )
                elif message_to_broadcast.audio:
                    await context.bot.send_audio(
                        chat_id=u_id, 
                        audio=message_to_broadcast.audio.file_id, 
                        caption=messageAapke pythondrive (`python-telegram-bot`) script ko update kar diya gaya hai. Isme aapki requirement ke mutabiq sabhi changes apply kar diye gaye hain:

1. **Welcome Message Setup (Msg ID 16)**:
   - Isme ek **Red** button ("Bonus / Start") laga diya gaya hai ($4956222745814762495$). Is par click karne se Telegram client open hoga standard start payload (`?start=bonus`) ke sath, bilkul purane flow ki tarah.
2. **Follow-up Message (Msg ID 14)**:
   - Ye message Step 1 me Welcome message ke sath hi send hota hai.
   - **Blue Button**: Direct Telegram DM (`t.me/vijaykiroriwal?text=...`) autofilled text "*Vijay bhai mujhe work shuru karna hai*" ke saath.
   - **Green Button**: "WhatsApp Chat" button jo `https://alvo.chat/8aJ7` par redirect karta hai.
   - **Red Button**: "Feedback" button (placeholder URL ke sath, jise baad me change kar sakte hain).
3. **Step 2 (Msg ID 18)**:
   - Jab koi user Red button (`?start=bonus`) par click karke `/start bonus` trigger karta hai, toh **Msg ID 18** serve hota hai.

### Updated Complete Code:

```python
import os
import logging
import asyncio
import urllib.parse
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter, TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ChatMemberHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN") 

ADMIN_IDS = [5785924075, 8210667307]
MONGO_URI = os.environ.get("MONGO_URI")

SOURCE_CHAT_ID = 5785924075

# Updated Message IDs according to your requirements
MSG_WELCOME_16 = 16    # Step 1: Welcome Message with Red Start Button
MSG_INFO_14 = 14       # Step 1: Follow-up Message with Telegram, WhatsApp & Feedback Buttons
MSG_STEP2_18 = 18      # Step 2: Main Flow Message (Triggered on Start/Bonus link click)

# Emoji Custom IDs
EMOJI_RED_START = "4956222745814762495"
EMOJI_TG_CHAT = "6170163662544707658"
EMOJI_WA_CHAT = "5935973359480213803"
EMOJI_FEEDBACK = "5332554596403404883"

EMOJI_STATS_HEADER = "5244837092042750681"
EMOJI_TOTAL_USERS = "4938653911507534983"
EMOJI_JOIN_REQS = "5156719794946311065"
EMOJI_LEFT_MEMBERS = "5201913231836199981"

# Broadcast performance settings
NUM_WORKERS = 10  # Number of parallel sender workers
# =======================================================

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["telegram_bot_db"]
users_collection = db["users"]
events_collection = db["chat_events"]

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
        logging.error(f"MongoDB User Save Error: {e}")

def log_event(user_id, event_type):
    try:
        events_collection.insert_one({
            "user_id": user_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc)
        })
    except Exception as e:
        logging.error(f"MongoDB Event Tracking Error: {e}")

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("<html><body><h1>Bot is Live!</h1></body></html>", "utf-8"))

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

def styled_button(text, *, style, icon_custom_emoji_id=None, url=None, callback_data=None):
    action = {"url": url} if url else {"callback_data": callback_data or "noop"}
    modern = {"text": text, **action, "style": style}
    if icon_custom_emoji_id:
        modern["icon_custom_emoji_id"] = icon_custom_emoji_id

    try:
        return InlineKeyboardButton(**modern)
    except TypeError:
        api_kwargs = {"style": style}
        if icon_custom_emoji_id:
            api_kwargs["icon_custom_emoji_id"] = icon_custom_emoji_id
        try:
            return InlineKeyboardButton(text=text, api_kwargs=api_kwargs, **action)
        except TypeError:
            return InlineKeyboardButton(text=text, **action)

# --- STEP 1: INITIAL WELCOME FLOW (MSG 16 & MSG 14) ---
async def send_initial_welcome(context: ContextTypes.DEFAULT_TYPE, user_id: int, first_name: str):
    try:
        welcome_text = f"👋🏻 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 {first_name} ❤️‍🔥TO OUR PRIVATE SERVER 🔥\n\n"
        await context.bot.send_message(chat_id=user_id, text=welcome_text)

        # Deep-Link for Red Button on Msg ID 16
        bot_info = await context.bot.get_me()
        start_link = f"[https://t.me/](https://t.me/){bot_info.username}?start=bonus"

        # Msg ID 16 Button (Red Style)
        msg16_keyboard = [
            [styled_button("Get Started", style="danger", icon_custom_emoji_id=EMOJI_RED_START, url=start_link)]
        ]
        msg16_reply_markup = InlineKeyboardMarkup(msg16_keyboard)

        # Send Msg ID 16
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_WELCOME_16,
            reply_markup=msg16_reply_markup
        )

        # Build autofill URL for Telegram Direct Chat
        autofill_text = urllib.parse.quote("Vijay bhai mujhe work shuru karna hai")
        tg_autofill_url = f"[https://t.me/vijaykiroriwal?text=](https://t.me/vijaykiroriwal?text=){autofill_text}"

        # Msg ID 14 Buttons Setup (Blue, Green, Red)
        msg14_keyboard = [
            [styled_button("Contact Vijay Bhai", style="primary", icon_custom_emoji_id=EMOJI_TG_CHAT, url=tg_autofill_url)],
            [styled_button("WhatsApp Chat", style="success", icon_custom_emoji_id=EMOJI_WA_CHAT, url="[https://alvo.chat/8aJ7](https://alvo.chat/8aJ7)")],
            [styled_button("Feedback", style="danger", icon_custom_emoji_id=EMOJI_FEEDBACK, url="[https://t.me/vijaykiroriwal](https://t.me/vijaykiroriwal)")] # Placeholder link
        ]
        msg14_reply_markup = InlineKeyboardMarkup(msg14_keyboard)

        # Send Msg ID 14
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_INFO_14,
            reply_markup=msg14_reply_markup
        )

    except Exception as e:
        logging.error(f"Could not send initial welcome content to user {user_id}: {e}")

# --- STEP 2: MAIN FLOW (MSG 18) ---
async def send_full_original_flow(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        # Msg ID 18
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_STEP2_18
        )
    except Exception as e:
        logging.error(f"Could not send step 2 content to user {user_id}: {e}")

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    user = request.from_user
    
    save_user_to_mongo(user.id, user.first_name, user.username)
    log_event(user.id, "join_request")
    
    # Send Step 1
    asyncio.create_task(send_initial_welcome(context, user.id, user.first_name))

async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return
    
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user = result.from_user

    if old_status in ["member", "administrator"] and new_status in ["left", "kicked"]:
        log_event(user.id, "left")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user_to_mongo(user.id, user.first_name, user.username)
    
    # Check if user clicked the Red Button on Msg 16
    if context.args and context.args[0] == "bonus":
        asyncio.create_task(send_full_original_flow(context, user.id))
    else:
        # Standard welcome trigger
        asyncio.create_task(send_initial_welcome(context, user.id, user.first_name))

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

# --- PARALLEL MULTI-WORKER BROADCAST ENGINE ---
async def broadcast_worker(queue, context, message_to_broadcast, stats_dict):
    reply_markup = message_to_broadcast.reply_markup
    while not queue.empty():
        u_id = await queue.get()
        sent = False
        retries = 3

        while retries > 0 and not sent:
            try:
                if message_to_broadcast.text:
                    await context.bot.send_message(
                        chat_id=u_id, 
                        text=message_to_broadcast.text, 
                        entities=message_to_broadcast.entities,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                elif message_to_broadcast.photo:
                    await context.bot.send_photo(
                        chat_id=u_id, 
                        photo=message_to_broadcast.photo[-1].file_id, 
                        caption=message_to_broadcast.caption, 
                        caption_entities=message_to_broadcast.caption_entities,
                        reply_markup=reply_markup
                    )
                elif message_to_broadcast.video:
                    await context.bot.send_video(
                        chat_id=u_id, 
                        video=message_to_broadcast.video.file_id, 
                        caption=message_to_broadcast.caption, 
                        caption_entities=message_to_broadcast.caption_entities,
                        reply_markup=reply_markup
                    )
                elif message_to_broadcast.audio:
                    await context.bot.send_audio(
                        chat_id=u_id, 
                        audio=message_to_broadcast.audio.file_id, 
                        caption=message_to_broadcast.caption, 
                        caption_entities=message_to_broadcast.caption_entities,
                        reply_markup=reply_markup
                    )
                elif message_to_broadcast.voice:
                    await context.bot.send_voice(
                        chat_id=u_id, 
                        voice=message_to_broadcast.voice.file_id, 
                        caption=message_to_broadcast.caption, 
                        caption_entities=message_to_broadcast.caption_entities,
                        reply_markup=reply_markup
                    )
                elif message_to_broadcast.document:
                    await context.bot.send_document(
                        chat_id=u_id, 
                        document=message_to_broadcast.document.file_id, 
                        caption=message_to_broadcast.caption, 
                        caption_entities=message_to_broadcast.caption_entities,
                        reply_markup=reply_markup
                    )
                
                stats_dict["success"] += 1
                sent = True
            
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
                retries -= 1
            except TelegramError:
                stats_dict["failed"] += 1
                sent = True
            except Exception as e:
                logging.error(f"Unexpected Broadcast Error for {u_id}: {e}")
                stats_dict["failed"] += 1
                sent = True

        queue.task_done()

async def execute_broadcast(message_to_broadcast, context, admin_chat_id):
    users = list(users_collection.find({"user_id": {"$nin": ADMIN_IDS}}, {"user_id": 1}))
    total_users = len(users)

    if total_users == 0:
        await context.bot.send_message(chat_id=admin_chat_id, text="⚠️ Database me koi user nahi hai!")
        return

    await context.bot.send_message(
        chat_id=admin_chat_id, 
        text=f"🚀 **Parallel Multi-Worker Broadcast Started!**\nTargeting `{total_users}` users with {NUM_WORKERS} workers...",
        parse_mode="Markdown"
    )

    queue = asyncio.Queue()
    for u in users:
        queue.put_nowait(u["user_id"])

    stats_dict = {"success": 0, "failed": 0}

    tasks = []
    for _ in range(NUM_WORKERS):
        task = asyncio.create_task(broadcast_worker(queue, context, message_to_broadcast, stats_dict))
        tasks.append(task)

    await queue.join()

    for task in tasks:
        task.cancel()

    await context.bot.send_message(
        chat_id=admin_chat_id, 
        text=(
            f"✅ **Broadcast Finished!**\n\n"
            f"🟢 Successful: `{stats_dict['success']}`\n"
            f"🔴 Failed/Blocked: `{stats_dict['failed']}`"
        ), 
        parse_mode="Markdown"
    )

async def auto_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if update.effective_user.id not in ADMIN_IDS:
        return
    if msg.text and msg.text.startswith("/"):
        return
    
    asyncio.create_task(execute_broadcast(msg, context, update.effective_user.id))

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if update.effective_user.id not in ADMIN_IDS:
        return

    if msg.reply_to_message:
        asyncio.create_task(execute_broadcast(msg.reply_to_message, context, update.effective_user.id))
    else:
        await msg.reply_text("⚠️ Kripya kisi message par reply karke `/broadcast` likhein ya direct message bhejain.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    total_users = users_collection.count_documents({})

    now = datetime.now(timezone.utc)
    start_of_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    today_joins = events_collection.count_documents({
        "event_type": "join_request",
        "timestamp": {"$gte": start_of_today}
    })

    today_lefts = events_collection.count_documents({
        "event_type": "left",
        "timestamp": {"$gte": start_of_today}
    })

    stats_msg = (
        f'<tg-emoji emoji-id="{EMOJI_STATS_HEADER}">📊</tg-emoji> <b>LIVE BOT ANALYTICS</b>\n'
        "━━━━━━━━━━━━━━━━━━━\n"
        f'<tg-emoji emoji-id="{EMOJI_TOTAL_USERS}">👤</tg-emoji> <b>Total Users:</b> <code>{total_users}</code>\n\n'
        f'<tg-emoji emoji-id="{EMOJI_STATS_HEADER}">📈</tg-emoji> <b>TODAY\'S ACTIVITY</b>\n'
        "━━━━━━━━━━━━━━━━━━━\n"
        f'<tg-emoji emoji-id="{EMOJI_JOIN_REQS}">📥</tg-emoji> <b>Channel Join Requests:</b> <code>{today_joins}</code>\n'
        f'<tg-emoji emoji-id="{EMOJI_LEFT_MEMBERS}">📤</tg-emoji> <b>Channel Left Members:</b> <code>{today_lefts}</code>'
    )

    await update.message.reply_text(stats_msg, parse_mode="HTML")

def main():
    Thread(target=run_web_server, daemon=True).start()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.User(ADMIN_IDS) & ~filters.COMMAND, auto_broadcast))

    print("Bot is running with Multi-Worker Architecture...")
    app.run_polling(allowed_updates=["message", "chat_join_request", "chat_member", "callback_query"])

if __name__ == "__main__":
    main()
