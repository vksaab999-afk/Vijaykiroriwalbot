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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("BOT_TOKEN") 

ADMIN_IDS = [5785924075, 8210667307]
MONGO_URI = os.environ.get("MONGO_URI")

SOURCE_CHAT_ID = 5785924075

MSG_WELCOME_16 = 16
MSG_INFO_14 = 14
MSG_STEP2_18 = 18

EMOJI_RED_START = "4956222745814762495"
EMOJI_TG_CHAT = "6170163662544707658"
EMOJI_WA_CHAT = "5935973359480213803"
EMOJI_FEEDBACK = "5332554596403404883"
EMOJI_SCREENSHOT = "5388971216629412467"

EMOJI_STATS_HEADER = "5244837092042750681"
EMOJI_TOTAL_USERS = "4938653911507534983"
EMOJI_JOIN_REQS = "5156719794946311065"
EMOJI_LEFT_MEMBERS = "5201913231836199981"

NUM_WORKERS = 10

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

async def send_initial_welcome(context: ContextTypes.DEFAULT_TYPE, user_id: int, first_name: str):
    try:
        welcome_text = f"👋🏻 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 {first_name} ❤️‍🔥TO OUR PRIVATE SERVER 🔥\n\n"
        await context.bot.send_message(chat_id=user_id, text=welcome_text)

        bot_info = await context.bot.get_me()
        start_link = f"https://t.me/{bot_info.username}?start=bonus"

        msg16_keyboard = [
            [styled_button("Get Started", style="danger", icon_custom_emoji_id=EMOJI_RED_START, url=start_link)]
        ]
        msg16_reply_markup = InlineKeyboardMarkup(msg16_keyboard)

        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_WELCOME_16,
            reply_markup=msg16_reply_markup
        )

        autofill_text_14 = urllib.parse.quote("Vijay bhai mujhe work shuru karna hai")
        tg_autofill_url_14 = f"https://t.me/vijaykiroriwal?text={autofill_text_14}"

        msg14_keyboard = [
            [styled_button("Contact Vijay Bhai", style="primary", icon_custom_emoji_id=EMOJI_TG_CHAT, url=tg_autofill_url_14)],
            [styled_button("WhatsApp Chat", style="success", icon_custom_emoji_id=EMOJI_WA_CHAT, url="https://alvo.chat/8aJ7")],
            [styled_button("Feedback", style="danger", icon_custom_emoji_id=EMOJI_FEEDBACK, url="https://t.me/vijaykiroriwal")]
        ]
        msg14_reply_markup = InlineKeyboardMarkup(msg14_keyboard)

        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_INFO_14,
            reply_markup=msg14_reply_markup
        )

    except Exception as e:
        logging.error(f"Could not send initial welcome content to user {user_id}: {e}")

async def send_full_original_flow(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        autofill_text_18 = urllib.parse.quote("Vijay sir mene payment kar diya hai niche screenshot bhej raha hu dekh lijiye")
        tg_autofill_url_18 = f"https://t.me/vijaykiroriwal?text={autofill_text_18}"

        msg18_keyboard = [
            [styled_button("SEND SCREENSHOT", style="primary", icon_custom_emoji_id=EMOJI_SCREENSHOT, url=tg_autofill_url_18)]
        ]
        msg18_reply_markup = InlineKeyboardMarkup(msg18_keyboard)

        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=MSG_STEP2_18,
            reply_markup=msg18_reply_markup
        )
    except Exception as e:
        logging.error(f"Could not send step 2 content to user {user_id}: {e}")

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    user = request.from_user
    
    save_user_to_mongo(user.id, user.first_name, user.username)
    log_event(user.id, "join_request")
    
    asyncio.create_task(send_initial_welcome(context, user.id, user.first_name))

async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return

    user = result.from_user
    save_user_to_mongo(user.id, user.first_name, user.username)

    new_status = result.new_chat_member.status
    if new_status == "left":
        log_event(user.id, "left")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user_to_mongo(user.id, user.first_name, user.username)

    if context.args and context.args[0] == "bonus":
        asyncio.create_task(send_full_original_flow(context, user.id))
    else:
        asyncio.create_task(send_initial_welcome(context, user.id, user.first_name))

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    try:
        total_users = users_collection.count_documents({})
        total_join_requests = events_collection.count_documents({"event_type": "join_request"})
        total_left = events_collection.count_documents({"event_type": "left"})

        stats_message = (
            f"<b>BOT ANALYTICS DASHBOARD</b>\n\n"
            f" Total Users in Database: {total_users}\n"
            f" Total Join Requests Received: {total_join_requests}\n"
            f" Users Left / Unsubscribed: {total_left}"
        )
        await update.message.reply_text(stats_message, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error fetching stats: {e}")

async def broadcast_worker(queue, context, source_chat_id, message_id, reply_markup, stats):
    while True:
        user_id = await queue.get()
        try:
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=source_chat_id,
                message_id=message_id,
                reply_markup=reply_markup
            )
            stats["success"] += 1
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await context.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=source_chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup
                )
                stats["success"] += 1
            except Exception:
                stats["failed"] += 1
        except Exception as e:
            stats["failed"] += 1
            logging.error(f"Broadcast error for user {user_id}: {e}")
        finally:
            queue.task_done()

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("<b>Usage:</b> /broadcast &lt;message_id&gt;", parse_mode="HTML")
        return

    message_id = int(context.args[0])
    all_users = list(users_collection.find({}, {"user_id": 1}))
    total_targets = len(all_users)

    if total_targets == 0:
        await update.message.reply_text("No users found in database to broadcast.")
        return

    status_msg = await update.message.reply_text(f"<b>Starting Broadcast to {total_targets} users...</b>", parse_mode="HTML")

    queue = asyncio.Queue()
    for u in all_users:
        queue.put_nowait(u["user_id"])

    stats = {"success": 0, "failed": 0}
    workers = [
        asyncio.create_task(broadcast_worker(queue, context, SOURCE_CHAT_ID, message_id, None, stats))
        for _ in range(NUM_WORKERS)
    ]

    await queue.join()

    for w in workers:
        w.cancel()

    await status_msg.edit_text(
        f"<b>Broadcast Completed!</b>\n\n"
        f" Success: {stats['success']}\n"
        f" Failed: {stats['failed']}",
        parse_mode="HTML"
    )

def main():
    Thread(target=run_web_server, daemon=True).start()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
