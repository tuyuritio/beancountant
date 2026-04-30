import sys
import logging
from telegram import (
    Update,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    filters,
    ContextTypes,
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
)

import app.context as env
from app.tools.retrieve import initialize_embeddings
from app.workflow import invoke


if not env.WEBHOOK_URL or not env.BOT_TOKEN:
    raise ValueError("[Launch] Lack of necessary environment variables for Telegram bot.")


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s](%(name)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)


async def start_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Welcome to Beancountant!\nSend me your financial queries or transactions.")


async def update_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if (
        not update.effective_user
        or not update.effective_message
        or not update.effective_chat
        or context.user_data is None
    ):
        return

    # Handle callback queries
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_input = query.data if query.data else ""

        if isinstance(query.message, Message):
            original_text = query.message.text
            reply_text = f"{original_text}\n\n✅ {user_input}"
            await query.edit_message_text(text=reply_text, reply_markup=None)

    # Handle regular messages
    elif update.message and update.message.text:
        last = context.user_data.get("last")
        if last and isinstance(last, int):
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=update.effective_chat.id,
                    message_id=last,
                    reply_markup=None,
                )
            except Exception as e:
                logging.error(f"Failed to edit message reply markup: {e}")

        user_input = update.message.text

    # Ignore non-text messages
    else:
        return

    await update.effective_message.reply_chat_action("typing")
    response = invoke(user_input, update.effective_user.id)

    reply_markup = None
    if "options" in response:
        options = response["options"]
        if not isinstance(options[0], list):
            options = [[option] for option in options]

        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text=option, callback_data=option) for option in row] for row in options]
        )

    # Send message
    sent = await update.effective_message.reply_text(
        text=response["text"],
        reply_markup=reply_markup,
        parse_mode="HTML",
    )

    # Store the ID of the sent message
    context.user_data["last"] = sent.message_id


async def embed_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
    initialize_embeddings()


if __name__ == "__main__":
    app = ApplicationBuilder().token(env.BOT_TOKEN).build()

    user_filter = filters.User(user_id=env.ALLOWED_USERS)

    app.add_handler(CommandHandler("start", start_handler, filters=user_filter))
    app.add_handler(CommandHandler("embed", embed_handler, filters=user_filter))
    app.add_handler(MessageHandler(filters.TEXT & user_filter, update_handler))
    app.add_handler(CallbackQueryHandler(update_handler, block=False))

    app.run_webhook(
        listen="0.0.0.0",
        port=env.PORT,
        webhook_url=env.WEBHOOK_URL,
        secret_token=env.SECRET_TOKEN,
    )
