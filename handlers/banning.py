from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
import keyboards as kb
from ui import edit_screen
from states import AdminBan
from config import ADMIN_IDS

router = Router()


# ================= USER SIDE: APPEAL =================

@router.callback_query(F.data == "appeal_ban")
async def appeal_ban(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    if not user or not user["banned"]:
        await callback.answer()
        return
    if user["appeal_status"] in ("pending", "declined"):
        await callback.answer("Апелляция уже подана или была отклонена ранее.", show_alert=True)
        return

    reason_text = f"Апелляция блокировки. Причина блокировки: {user['ban_reason'] or 'не указана'}"
    ticket_id = db.create_ticket(user["id"], reason_text, is_appeal=True)
    db.set_appeal_pending(user["id"], ticket_id)

    await edit_screen(callback,
        f"✅ Апелляция отправлена (тикет #{ticket_id}). Ожидайте ответа администратора — "
        f"следить за статусом можно в «Профиль» → «Мои тикеты» (там же можно написать "
        f"дополнительные пояснения).",
    )
    await callback.answer()

    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🆘 <b>Апелляция блокировки</b> — тикет #{ticket_id}\n"
                f"Пользователь: {user['name']} (ID {user['id']})\n"
                f"Причина блокировки: {user['ban_reason'] or 'не указана'}",
                parse_mode="HTML"
            )
        except Exception:
            pass


# ================= ADMIN SIDE: APPROVE / DECLINE APPEAL =================

@router.callback_query(F.data.startswith("appeal_approve_"))
async def appeal_approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    ticket_id = int(callback.data.split("_")[-1])
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден", show_alert=True)
        return
    db.approve_appeal(ticket["uid"])
    db.close_ticket(ticket_id)
    await edit_screen(callback, "✅ Апелляция одобрена, пользователь разблокирован.", reply_markup=kb.back_kb("admin_tickets"))
    await callback.answer()
    try:
        await callback.bot.send_message(
            ticket["tg_id"],
            "✅ Ваша апелляция одобрена! Блокировка снята, вы снова можете пользоваться ботом. Отправьте /start."
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("appeal_decline_"))
async def appeal_decline(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    ticket_id = int(callback.data.split("_")[-1])
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден", show_alert=True)
        return
    db.decline_appeal(ticket["uid"])
    db.close_ticket(ticket_id)
    await edit_screen(callback, "❌ Апелляция отклонена.", reply_markup=kb.back_kb("admin_tickets"))
    await callback.answer()
    try:
        await callback.bot.send_message(
            ticket["tg_id"],
            "🚫 Ваша апелляция отклонена. Блокировка остаётся в силе окончательно."
        )
    except Exception:
        pass


# ================= ADMIN SIDE: BAN / UNBAN MANAGEMENT =================

@router.callback_query(F.data == "admin_bans")
async def admin_bans_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    await edit_screen(callback, "🚫 <b>Управление банами</b>", reply_markup=kb.bans_panel_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_users_for_ban")
async def admin_users_for_ban(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    users = [u for u in db.all_users() if not u["banned"]]
    if not users:
        await edit_screen(callback, "Нет пользователей для бана.", reply_markup=kb.back_kb("admin_bans"))
        await callback.answer()
        return
    rows = [
        [InlineKeyboardButton(text=f"{u['name']} (ID {u['id']})", callback_data=f"admin_user_card_{u['id']}")]
        for u in users
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_bans")])
    await edit_screen(callback,
        "👥 <b>Все пользователи</b>\nВыберите, кого забанить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_user_card_"))
async def admin_user_card(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    user_id = int(callback.data.split("_")[-1])
    user = db.get_user_by_id(user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    promos = db.get_user_available_promocodes(user_id)
    text = f"👤 {user['name']}\nID (программа лояльности): {user['id']}\nДоступных промокодов: {len(promos)}"
    await edit_screen(callback, text, reply_markup=kb.user_ban_action_kb(user_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ban_select_"))
async def admin_ban_select(callback: CallbackQuery, state):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    user_id = int(callback.data.split("_")[-1])
    await state.update_data(ban_user_id=user_id)
    await state.set_state(AdminBan.waiting_reason)
    await edit_screen(callback, "Введите причину бана:")
    await callback.answer()


@router.message(AdminBan.waiting_reason)
async def admin_ban_reason(message: Message, state):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Введите причину бана текстом:")
        return
    data = await state.get_data()
    user_id = data["ban_user_id"]
    user = db.get_user_by_id(user_id)
    db.ban_user(user_id, reason)
    await state.clear()
    await message.answer(f"🚫 Пользователь «{user['name']}» забанен.\nПричина: {reason}", reply_markup=kb.back_kb("admin_bans"))
    try:
        await message.bot.send_message(
            user["telegram_id"],
            f"🚫 <b>Вы заблокированы.</b>\nПричина: {reason}\n\n"
            f"Если считаете это ошибкой, вы можете подать апелляцию.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📮 Обжаловать блокировку", callback_data="appeal_ban")]
            ]),
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_banned_list")
async def admin_banned_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    users = db.get_banned_users()
    if not users:
        await edit_screen(callback, "Забаненных пользователей нет.", reply_markup=kb.back_kb("admin_bans"))
        await callback.answer()
        return
    rows = [
        [InlineKeyboardButton(text=f"{u['name']} (ID {u['id']}) — {u['ban_reason'][:20]}", callback_data=f"admin_banned_card_{u['id']}")]
        for u in users
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_bans")])
    await edit_screen(callback,
        "🔓 <b>Забаненные пользователи</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_banned_card_"))
async def admin_banned_card(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    user_id = int(callback.data.split("_")[-1])
    user = db.get_user_by_id(user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    appeal_line = {
        "pending": "апелляция на рассмотрении",
        "declined": "апелляция отклонена (блокировка постоянная)",
    }.get(user["appeal_status"], "апелляция не подавалась")
    text = (
        f"👤 {user['name']} (ID {user['id']})\n"
        f"Причина бана: {user['ban_reason']}\n"
        f"Статус апелляции: {appeal_line}\n\n"
        f"Разбанить можно в любой момент, даже если блокировка постоянная."
    )
    await edit_screen(callback, text, reply_markup=kb.banned_user_action_kb(user_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    user_id = int(callback.data.split("_")[-1])
    user = db.get_user_by_id(user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    db.unban_user(user_id)
    await edit_screen(callback, f"✅ Пользователь «{user['name']}» разбанен.", reply_markup=kb.back_kb("admin_bans"))
    await callback.answer()
    try:
        await callback.bot.send_message(
            user["telegram_id"],
            "✅ Администратор снял с вас блокировку. Можете снова пользоваться ботом. Отправьте /start."
        )
    except Exception:
        pass
