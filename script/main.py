import datetime
import logging
import os
import random

from sqlalchemy import BOOLEAN, BIGINT, TEXT, DATETIME
from sqlalchemy import Column
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, \
    ChatPermissions
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

Base = declarative_base()
engine = create_engine('mysql+pymysql://telegram-bot-terminator:1qaz2wsx@telegram-bot-terminator-database:3306/telegram-bot-terminator', echo=False)
captcha_symbols = [
    "♠",
    "♣",
    "♥",
    "♦",
]


class Records(Base):
    __tablename__ = "records"
    id = Column(BIGINT, primary_key=True, autoincrement=True)

    chat_id = Column(BIGINT, nullable=False)
    chat_name = Column(TEXT, nullable=False)

    user_id = Column(BIGINT, nullable=False)
    user_name = Column(TEXT, nullable=False)
    premium = Column(BOOLEAN)

    cause_id = Column(BIGINT)
    cause_name = Column(TEXT)

    welcome_message_id = Column(BIGINT)

    joined_time = Column(DATETIME, nullable=False)

    bot_check_passed = Column(BOOLEAN)
    bot_check_time = Column(DATETIME)

    first_message_id = Column(BIGINT)
    first_message = Column(TEXT)
    first_message_time = Column(DATETIME)

    spam_check_passed = Column(BOOLEAN)
    spam_check_time = Column(DATETIME)

    left = Column(BOOLEAN)
    left_time = Column(DATETIME)


async def captcha_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    if query.from_user.id != query.message.reply_to_message.from_user.id:
        await query.answer('Not for you 🤡', show_alert=True)
    else:
        logger.info(update)

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

        Session = sessionmaker(bind=engine)
        session = Session()
        result = session.query(
            Records
        ).filter(
            Records.chat_id == update.callback_query.message.chat_id
        ).filter(
            Records.user_id == update.callback_query.from_user.id
        ).filter(
            Records.bot_check_passed == None
        ).order_by(Records.id.desc()).first()
        if result:
            if not bot_check_passed:
                await context.bot.delete_message(
                    chat_id=update.callback_query.message.chat_id,
                    message_id=result.welcome_message_id,
                )

            result.bot_check_passed = bot_check_passed
            result.bot_check_time = update.callback_query.message.date
            session.commit()
            session.close()


async def captcha_timeout(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job

    await context.bot.delete_message(
        chat_id=job.chat_id,
        message_id=job.data,
    )

    Session = sessionmaker(bind=engine)
    session = Session()
    result = session.query(Records).filter(
        Records.chat_id == job.chat_id
    ).filter(
        Records.user_id == job.user_id
    ).filter(
        Records.bot_check_passed == None
    ).order_by(Records.id.desc()).first()
    if result:
        await context.bot.delete_message(
            chat_id=job.chat_id,
            message_id=result.welcome_message_id,
        )

        result.bot_check_passed = False
        result.bot_check_time = datetime.datetime.now()
        session.commit()
        session.close()

    await context.bot.ban_chat_member(
        chat_id=job.chat_id,
        user_id=job.user_id,
        revoke_messages=True,
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(update)

    if not update.message:
        return

    if update.message.new_chat_members:
        Session = sessionmaker(bind=engine)
        session = Session()
        for new_member in update.message.new_chat_members:
            if (new_member.id != update.message.from_user.id) or new_member.is_premium:
                session.add(Records(
                    chat_id=update.message.chat.id,
                    chat_name=update.message.chat.title,
                    user_id=new_member.id,
                    user_name=new_member.name,
                    premium=new_member.is_premium,
                    cause_id=update.message.from_user.id,
                    cause_name=update.message.from_user.name,
                    welcome_message_id=update.message.id,
                    joined_time=update.message.date,
                    bot_check_passed=True,
                    spam_check_passed=True,
                ))
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
                result = await update.message.reply_text("Hello " + new_member.name + "\nPlease select " + captcha_symbols[i] + " in 60 seconds", reply_markup=reply_markup)

                context.job_queue.run_once(
                    captcha_timeout,
                    60,
                    data=result.id,
                    name=str(update.message.chat.id) + '_' + str(new_member.id),
                    chat_id=update.message.chat.id,
                    user_id=new_member.id,
                )

                session.add(Records(
                    chat_id=update.message.chat.id,
                    chat_name=update.message.chat.title,
                    user_id=new_member.id,
                    user_name=new_member.name,
                    premium=new_member.is_premium,
                    welcome_message_id=update.message.id,
                    joined_time=update.message.date,
                ))

        session.commit()
        session.close()
    elif update.message.left_chat_member:
        Session = sessionmaker(bind=engine)
        session = Session()
        result = session.query(Records).filter(Records.chat_id == update.message.chat.id).filter(Records.user_id == update.message.left_chat_member.id).order_by(Records.id.desc()).first()
        if result:
            result.left = True
            result.left_time = update.message.date
            session.commit()
        session.close()

        await update.message.delete()
    else:
        Session = sessionmaker(bind=engine)
        session = Session()
        result = session.query(Records).filter(
            Records.chat_id == update.message.chat.id
        ).filter(
            Records.user_id == update.message.from_user.id
        ).filter(
            Records.spam_check_passed == None
        ).order_by(Records.id.desc()).first()
        if result:
            spam_check_passed = None

            if spam_check_passed is None and update.message.entities:
                for entity in update.message.entities:
                    if entity.url:
                        spam_check_passed = False
                        break

            if spam_check_passed is None and update.message.text:
                spam_check_passed = not ('://' in update.message.text)

                if not spam_check_passed:
                    await update.message.delete()

                    await context.bot.delete_message(
                        chat_id=update.message.chat.id,
                        message_id=result.welcome_message_id,
                    )

                    await update.message.chat.ban_member(
                        user_id=update.message.from_user.id,
                        revoke_messages=True,
                    )

            if spam_check_passed is not None:
                result.first_message_id = update.message.id
                result.first_message = update.message.text
                result.first_message_time = update.message.date
                result.spam_check_passed = spam_check_passed
                result.spam_check_time = update.message.date
                session.commit()
        session.close()


if __name__ == "__main__":
    Base.metadata.create_all(engine)

    TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CallbackQueryHandler(captcha_handler))
    application.add_handler(MessageHandler(filters.ALL, message_handler))

    application.run_webhook(
        listen='0.0.0.0',
        port=int(os.environ['TELEGRAM_BOT_LISTEN_PORT']),
        url_path=TELEGRAM_TOKEN,
        webhook_url=os.environ['TELEGRAM_WEBHOOK_URL'],
    )
