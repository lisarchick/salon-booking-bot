from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db

ALLOWED_WITHOUT_REGISTRATION = {"register_start", "terms_agree", "terms_decline"}

# What a banned user is still allowed to do: appeal, and continue the
# conversation inside their own appeal ticket.
BAN_ALLOWED_CALLBACKS = {"appeal_ban", "profile_tickets", "menu_main"}
BAN_ALLOWED_CALLBACK_PREFIXES = ("ticket_view_", "ticket_reply_")


def _ban_message_and_kb(user):
    reason = user["ban_reason"] or "не указана"
    status = user["appeal_status"]
    if status == "pending":
        text = (
            f"🚫 <b>Вы заблокированы.</b>\nПричина: {reason}\n\n"
            f"Ваша апелляция на рассмотрении, ожидайте ответа администратора в разделе "
            f"«Профиль» → «Мои тикеты»."
        )
        return text, None
    if status == "declined":
        text = (
            f"🚫 <b>Вы заблокированы навсегда.</b>\nПричина: {reason}\n\n"
            f"Ваша апелляция была рассмотрена и отклонена администрацией."
        )
        return text, None
    text = (
        f"🚫 <b>Вы заблокированы.</b>\nПричина: {reason}\n\n"
        f"Если считаете это ошибкой, вы можете подать апелляцию."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📮 Обжаловать блокировку", callback_data="appeal_ban")]
    ])
    return text, kb


class RegistrationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        state = data.get("state")
        current_state = await state.get_state() if state else None

        # Let registration flow (name entry, terms agreement) and /start pass through freely
        if current_state and current_state.startswith("Registration"):
            return await handler(event, data)

        if isinstance(event, Message):
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
            user = db.get_user(event.from_user.id)
            if not user:
                await event.answer("Пожалуйста, сначала зарегистрируйтесь: отправьте /start")
                return
            if user["banned"]:
                # allow continuing a conversation inside the appeal ticket
                if current_state == "TicketChat:waiting_message":
                    return await handler(event, data)
                text, kb = _ban_message_and_kb(user)
                await event.answer(text, reply_markup=kb, parse_mode="HTML")
                return
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            if event.data in ALLOWED_WITHOUT_REGISTRATION:
                return await handler(event, data)
            user = db.get_user(event.from_user.id)
            if not user:
                await event.answer("Сначала зарегистрируйтесь, отправьте /start", show_alert=True)
                return
            if user["banned"]:
                allowed = (
                    event.data in BAN_ALLOWED_CALLBACKS
                    or any(event.data.startswith(p) for p in BAN_ALLOWED_CALLBACK_PREFIXES)
                )
                if allowed:
                    return await handler(event, data)
                text, kb = _ban_message_and_kb(user)
                await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
                await event.answer()
                return
            return await handler(event, data)

        return await handler(event, data)
