import sys
import io
import logging
import base64
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

    user_input = []

    # Handle callback queries
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data if query.data else ""
        user_input.append({"type": "text", "text": data})

        if isinstance(query.message, Message):
            original_text = query.message.text
            reply_text = f"{original_text}\n\n✅ {data}"
            await query.edit_message_text(text=reply_text, reply_markup=None)

    # Handle regular messages
    elif update.message:
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

        if update.message.text:
            user_input.append({"type": "text", "text": update.message.text})

        if update.message.photo:
            photo = max(update.message.photo, key=lambda p: p.width * p.height)
            file = await photo.get_file()

            bytearray = io.BytesIO()
            await file.download_to_memory(bytearray)
            bytearray.seek(0)

            image_base64 = base64.b64encode(bytearray.read()).decode("utf-8")

            user_input.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}})

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
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO & user_filter, update_handler))
    app.add_handler(CallbackQueryHandler(update_handler, block=False))

    app.run_webhook(
        listen="0.0.0.0",
        port=env.PORT,
        webhook_url=env.WEBHOOK_URL,
        secret_token=env.SECRET_TOKEN,
    )
