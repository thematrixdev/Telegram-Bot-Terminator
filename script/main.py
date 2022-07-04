import datetime
import logging
import os
import random

import pymongo
from sqlalchemy import create_engine
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
captcha_symbols = [
    "♠",
    "♣",
    "♥",
    "♦",
]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


engine = create_engine(
    'mysql+pymysql://telegram-bot-terminator:1qaz2wsx@telegram-bot-terminator-database:3306/telegram-bot-terminator',
    echo=False,
)

mongodb_client = pymongo.MongoClient(
    host=os.environ['MONGODB_HOST'],
    port=int(os.environ['MONGODB_PORT']),
    username=os.environ['MONGODB_USER'],
    password=os.environ['MONGODB_PASS'],
)
mongodb_database = mongodb_client['terminator']
mongodb_collection = mongodb_database['record']


async def captcha_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    if query.from_user.id != query.message.reply_to_message.from_user.id:
        await query.answer('Not for you 🤡', show_alert=True)
    else:
        await query.delete_message()

        current_jobs = context.job_queue.get_jobs_by_name(str(update.callback_query.message.chat_id) + '_' + str(update.callback_query.from_user.id))
        if current_jobs:
            for job in current_jobs:
                job.schedule_removal()

        bot_check_passed = True
        if query.data == '0':
            bot_check_passed = False

        if bot_check_passed:
            await context.bot.restrict_chat_member(
                chat_id=update.callback_query.message.chat_id,
                user_id=update.callback_query.from_user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_change_info=True,
                    can_invite_users=True,
                ),
            )
        else:
            await update.callback_query.message.chat.ban_member(
                user_id=update.callback_query.from_user.id,
                revoke_messages=True,
            )

        record = mongodb_collection.find_one({
            "chat_id": update.callback_query.message.chat_id,
            "user_id": update.callback_query.from_user.id,
            "bot_check_passed": {"$exists": False},
        })
        if record:
            if not bot_check_passed:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=record["welcome_message_id"],
                )

            mongodb_collection.update_one({
                "_id": record["_id"],
            }, {"$set": {
                "bot_check_passed": bot_check_passed,
                "bot_check_time": update.callback_query.message.date,
            }})


async def captcha_timeout(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job

    await context.bot.delete_message(
        chat_id=job.chat_id,
        message_id=job.data,
    )

    await context.bot.ban_chat_member(
        chat_id=job.chat_id,
        user_id=job.user_id,
        revoke_messages=True,
    )

    record = mongodb_collection.find_one({
        "chat_id": job.chat_id,
        "user_id": job.user_id,
        "bot_check_passed": {"$exists": False},
    })
    if record:
        await context.bot.delete_message(
            chat_id=job.chat_id,
            message_id=record["welcome_message_id"],
        )

        mongodb_collection.update_one({
            "_id": record["_id"],
        }, {"$set": {
            "bot_check_passed": False,
            "bot_check_time": datetime.datetime.now(),
        }})


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(update)

    if not update.message:
        return

    if update.message.new_chat_members:
        for new_member in update.message.new_chat_members:
            if (new_member.id != update.message.from_user.id) or new_member.is_premium:
                mongodb_collection.insert_one({
                    "chat_id": update.message.chat.id,
                    "chat_name": update.message.chat.title,
                    "user_id": new_member.id,
                    "user_name": new_member.name,
                    "premium": new_member.is_premium,
                    "cause_id": update.message.from_user.id,
                    "cause_name": update.message.from_user.name,
                    "welcome_message_id": update.message.id,
                    "joined_time": update.message.date,
                    "bot_check_passed": True,
                    "spam_check_passed": True,
                })
            else:
                await context.bot.restrict_chat_member(
                    chat_id=update.message.chat.id,
                    user_id=new_member.id,
                    permissions=ChatPermissions(
                        can_send_messages=False,
                        can_send_media_messages=False,
                        can_send_polls=False,
                        can_send_other_messages=False,
                        can_add_web_page_previews=False,
                        can_change_info=False,
                        can_invite_users=False,
                        can_pin_messages=False,
                    ),
                )

                random.shuffle(captcha_symbols)
                i = random.randint(1, len(captcha_symbols)) - 1
                keyboard_row = []
                for k in range(len(captcha_symbols)):
                    d = '0'
                    if k == i:
                        d = '1'
                    keyboard_row.append(InlineKeyboardButton(captcha_symbols[k], callback_data=d))
                reply_markup = InlineKeyboardMarkup([keyboard_row])
                result = await update.message.reply_text(
                    "Hello " + new_member.name + "\nPlease select " + captcha_symbols[i] + " in 60 seconds",
                    reply_markup=reply_markup)

                context.job_queue.run_once(
                    captcha_timeout,
                    60,
                    data=result.id,
                    name=str(update.message.chat.id) + '_' + str(new_member.id),
                    chat_id=update.message.chat.id,
                    user_id=new_member.id,
                )

                mongodb_collection.insert_one({
                    "chat_id": update.message.chat.id,
                    "chat_name": update.message.chat.title,
                    "user_id": new_member.id,
                    "user_name": new_member.name,
                    "premium": new_member.is_premium,
                    "welcome_message_id": update.message.id,
                    "joined_time": update.message.date,
                })
    elif update.message.left_chat_member:
        mongodb_collection.update_one({
            "chat_id": update.message.chat.id,
            "user_id": update.message.left_chat_member.id,
        }, {"$set": {
            "left": True,
            "left_time": update.message.date,
        }})

        await update.message.delete()
    else:
        record = mongodb_collection.find_one({
            "chat_id": update.message.chat.id,
            "user_id": update.message.from_user.id,
            "spam_check_passed": {"$exists": False},
        })
        if record:
            spam_check_passed = None

            if spam_check_passed is None and update.message.entities:
                for entity in update.message.entities:
                    if entity.URL:
                        spam_check_passed = False
                        break
                    elif entity.MENTION:
                        spam_check_passed = False
                        break

            if spam_check_passed is None and update.message.text:
                spam_check_passed = not ('://' in update.message.text)

            if spam_check_passed is False:
                await update.message.delete()

                await context.bot.delete_message(
                    chat_id=update.message.chat.id,
                    message_id=record["welcome_message_id"],
                )

                await update.message.chat.ban_member(
                    user_id=update.message.from_user.id,
                    revoke_messages=True,
                )

            if spam_check_passed is not None:
                mongodb_collection.update_one({
                    "_id": record["_id"],
                }, {'$set': {
                    "first_message_id": update.message.id,
                    "first_message": update.message.text,
                    "first_message_time": update.message.date,
                    "spam_check_passed": spam_check_passed,
                    "spam_check_time": update.message.date,
                }})

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CallbackQueryHandler(captcha_handler))
    application.add_handler(MessageHandler(filters.ALL, message_handler))

    application.run_webhook(
        listen='0.0.0.0',
        port=int(os.environ['TELEGRAM_BOT_LISTEN_PORT']),
        url_path=TELEGRAM_TOKEN,
        webhook_url=os.environ['TELEGRAM_WEBHOOK_URL'],
    )
