from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InputMediaPhoto


async def edit_screen(callback: CallbackQuery, text: str, reply_markup=None, parse_mode=None, photo=None):
    """Updates the bot's message in place so navigating between screens stays in
    the same chat window instead of spamming new messages.

    `photo`: optional file_id to show as a photo screen. Telegram's Bot API can't
    convert a text message into a photo message (or vice versa) via an edit, so
    when the target screen type differs from the current message this quietly
    deletes the old message and sends a replacement instead.
    """
    message = callback.message
    kwargs = {"reply_markup": reply_markup}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode

    async def _resend():
        try:
            await message.delete()
        except Exception:
            pass
        if photo:
            await callback.bot.send_photo(message.chat.id, photo, caption=text, **kwargs)
        else:
            await callback.bot.send_message(message.chat.id, text, **kwargs)

    try:
        if photo:
            if message.photo:
                media = InputMediaPhoto(media=photo, caption=text, parse_mode=parse_mode)
                await message.edit_media(media=media, reply_markup=reply_markup)
            else:
                await _resend()
        else:
            if message.photo:
                await _resend()
            else:
                await message.edit_text(text, **kwargs)
    except TelegramBadRequest as error:
        if "message is not modified" in str(error).lower():
            return
        await _resend()