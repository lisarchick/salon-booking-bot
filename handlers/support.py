from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from ui import edit_screen
from states import Support, TicketChat, AdminTicketChat
from config import ADMIN_IDS

router = Router()


@router.callback_query(F.data == "menu_support")
async def support_menu(callback: CallbackQuery):
    await edit_screen(callback,
        "🛠 <b>Поддержка</b>\n\nЕсли у вас есть вопрос или проблема — напишите нам, "
        "и мы ответим в тикете.",
        reply_markup=kb.support_start_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "support_write")
async def support_write(callback: CallbackQuery, state):
    await state.set_state(Support.waiting_reason)
    await edit_screen(callback,
        "Опишите причину обращения одним сообщением:",
        reply_markup=kb.support_cancel_kb()
    )
    await callback.answer()


@router.message(Support.waiting_reason)
async def support_save_reason(message: Message, state):
    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Пожалуйста, опишите проблему текстом, или нажмите «Вернуться».", reply_markup=kb.support_cancel_kb())
        return
    user = db.get_user(message.from_user.id)
    ticket_id = db.create_ticket(user["id"], reason)
    await state.clear()
    await message.answer(
        f"✅ Тикет #{ticket_id} создан! Мы ответим вам в ближайшее время.\n"
        f"Посмотреть его можно в «Профиль» → «Мои тикеты».",
        reply_markup=kb.back_kb()
    )
    text = f"🆕 <b>Новый тикет #{ticket_id}</b>\nОт: {user['name']} (ID {user['id']})\n\n{reason}"
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass


def _render_ticket(ticket, messages):
    lines = [f"🎫 <b>Тикет #{ticket['id']}</b> ({'открыт' if ticket['status']=='open' else 'закрыт'})\n"]
    for m in messages:
        who = "👤 Клиент" if m["sender"] == "user" else "🛡 Поддержка"
        lines.append(f"<b>{who}:</b> {m['text']}")
    return "\n\n".join(lines)


@router.callback_query(F.data.startswith("ticket_view_"))
async def view_ticket(callback: CallbackQuery):
    ticket_id = int(callback.data.split("_")[-1])
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден", show_alert=True)
        return
    is_admin = callback.from_user.id in ADMIN_IDS
    # security: non-admins may only view their own tickets
    user = db.get_user(callback.from_user.id)
    if not is_admin and ticket["user_id"] != user["id"]:
        await callback.answer("Недоступно", show_alert=True)
        return
    messages = db.get_ticket_messages(ticket_id)
    text = _render_ticket(ticket, messages)
    await edit_screen(callback,
        text,
        reply_markup=kb.ticket_view_kb(ticket_id, ticket["status"], is_admin=is_admin, is_appeal=bool(ticket["is_appeal"])),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ticket_reply_"))
async def reply_ticket_start(callback: CallbackQuery, state):
    ticket_id = int(callback.data.split("_")[-1])
    ticket = db.get_ticket(ticket_id)
    if not ticket or ticket["status"] != "open":
        await callback.answer("Тикет закрыт или не найден", show_alert=True)
        return
    is_admin = callback.from_user.id in ADMIN_IDS
    if is_admin:
        await state.set_state(AdminTicketChat.waiting_reply)
    else:
        await state.set_state(TicketChat.waiting_message)
    await state.update_data(ticket_id=ticket_id)
    await edit_screen(callback, "Введите сообщение:")
    await callback.answer()


@router.message(TicketChat.waiting_message)
async def user_ticket_message(message: Message, state):
    data = await state.get_data()
    ticket_id = data["ticket_id"]
    ticket = db.get_ticket(ticket_id)
    if not ticket or ticket["status"] != "open":
        await message.answer("Тикет уже закрыт.")
        await state.clear()
        return
    db.add_ticket_message(ticket_id, "user", message.text or "")
    await state.clear()
    await message.answer("Сообщение отправлено в поддержку.", reply_markup=kb.back_kb())
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"✉️ Новое сообщение в тикете #{ticket_id} от клиента:\n{message.text}",
            )
        except Exception:
            pass


@router.message(AdminTicketChat.waiting_reply)
async def admin_ticket_message(message: Message, state):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    data = await state.get_data()
    ticket_id = data["ticket_id"]
    ticket = db.get_ticket(ticket_id)
    if not ticket or ticket["status"] != "open":
        await message.answer("Тикет уже закрыт.")
        await state.clear()
        return
    db.add_ticket_message(ticket_id, "admin", message.text or "")
    await state.clear()
    await message.answer("Ответ отправлен клиенту.", reply_markup=kb.back_kb())
    try:
        await message.bot.send_message(
            ticket["tg_id"],
            f"💬 Ответ поддержки по тикету #{ticket_id}:\n{message.text}",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("ticket_close_"))
async def close_ticket(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    ticket_id = int(callback.data.split("_")[-1])
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден", show_alert=True)
        return
    db.close_ticket(ticket_id)
    await edit_screen(callback, f"✅ Тикет #{ticket_id} закрыт.", reply_markup=kb.back_kb("admin_tickets"))
    await callback.answer()
    try:
        await callback.bot.send_message(ticket["tg_id"], f"ℹ️ Ваш тикет #{ticket_id} был закрыт поддержкой.")
    except Exception:
        pass
