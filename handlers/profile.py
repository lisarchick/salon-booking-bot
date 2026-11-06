from aiogram import Router, F
from aiogram.types import CallbackQuery

import database as db
import keyboards as kb
from ui import edit_screen
from states import Loyalty
from config import CATEGORIES

router = Router()


def _discount_line(d) -> str:
    if d["scope"] == "all":
        target = "на все услуги"
    elif d["scope"] == "master":
        target = f"у мастера «{d['master_name']}»" if d["master_name"] else "у мастера"
    else:
        name = CATEGORIES.get(d["category_key"], (d["category_key"],))[0]
        target = f"на услугу «{name}»"
    expiry = f"до {d['expires_at']}" if d["expires_at"] else "бессрочно"
    return f"🔥 -{d['percent']}% {target} ({expiry})"


def _promo_line(p) -> str:
    label = db.PROMO_TYPE_LABELS.get(p["type"], p["type"])
    target = ""
    if p["type"] == "master" and p["master_id"]:
        master = db.get_master(p["master_id"])
        target = f" (мастер «{master['name']}»)" if master else ""
    elif p["type"] == "service" and p["category_key"]:
        name = CATEGORIES.get(p["category_key"], (p["category_key"],))[0]
        target = f" (услуга «{name}»)"
    expiry = f"до {p['expires_at']}" if p["expires_at"] else "бессрочно"
    return f"🎟 <b>{p['code']}</b> — {label}{target}, -{p['discount']}% ({expiry})"


@router.callback_query(F.data == "menu_profile")
async def show_profile(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    available = db.get_user_available_promocodes(user["id"])
    best = db.best_available_discount(user["id"])
    text = (
        f"👤 <b>Мой профиль</b>\n\n"
        f"Имя: {user['name']}\n"
        f"Доступных промокодов: {len(available)}\n"
        f"Максимальная скидка сейчас: {best['percent']}%"
    )
    await edit_screen(callback, text, reply_markup=kb.profile_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "profile_bookings")
async def my_bookings(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    bookings = db.get_user_bookings(user["id"])
    if not bookings:
        text = "У вас пока нет активных записей."
    else:
        lines = ["📖 <b>Мои записи</b>\n"]
        for b in bookings:
            price_line = f"{b['price']}₽"
            if b["discount_percent"]:
                price_line += f" (скидка {b['discount_percent']}%, было {b['original_price']}₽)"
            lines.append(
                f"• {b['date']} в {b['time']} — {b['category_name']} ({price_line})\n"
                f"  Мастер: {b['master_name']}"
            )
        text = "\n".join(lines)
    await edit_screen(callback, text, reply_markup=kb.back_kb("menu_profile"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "profile_loyalty")
async def loyalty_menu(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    discounts = db.get_active_discounts()
    promos = db.get_user_available_promocodes(user["id"])

    lines = ["🎁 <b>Программа лояльности</b>\n"]
    if not discounts and not promos:
        lines.append("Сейчас для вас нет доступных скидок или промокодов.")
    else:
        if discounts:
            lines.append("<b>Действующие скидки:</b>")
            lines.extend(_discount_line(d) for d in discounts)
        if promos:
            if discounts:
                lines.append("")
            lines.append("<b>Ваши промокоды:</b>")
            lines.extend(_promo_line(p) for p in promos)
    lines.append("\nСкидки не суммируются — при записи применяется наибольшая из доступных.")
    lines.append("Есть промокод от администратора? Введите его кнопкой ниже.")
    text = "\n".join(lines)
    await edit_screen(callback, text, reply_markup=kb.loyalty_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "loyalty_enter_code")
async def loyalty_enter_code(callback: CallbackQuery, state):
    await state.set_state(Loyalty.waiting_promocode)
    await edit_screen(callback, "Введите промокод:", reply_markup=kb.back_kb("menu_profile"))
    await callback.answer()


@router.message(Loyalty.waiting_promocode)
async def loyalty_process_code(message, state):
    code = message.text.strip().upper()
    user = db.get_user(message.from_user.id)
    result = db.redeem_promocode_for_user(user["id"], code)
    await state.clear()
    if result == "not_found":
        await message.answer("❌ Такой промокод не найден или отключён. Попробуйте ещё раз, или нажмите «Назад».", reply_markup=kb.back_kb("menu_profile"))
        return
    if result == "already":
        await message.answer("Вы уже активировали этот промокод.", reply_markup=kb.back_kb("menu_profile"))
        return
    if result == "expired":
        await message.answer("❌ Срок действия промокода истёк, либо закончились активации.", reply_markup=kb.back_kb("menu_profile"))
        return
    promo = db.get_promocode(code)
    label = db.PROMO_TYPE_LABELS.get(promo["type"], promo["type"])
    await message.answer(
        f"✅ Промокод применён! {label}: -{promo['discount']}%.\n"
        f"Он появится в списке доступных скидок в «Программа лояльности» и применится "
        f"автоматически при подходящей записи.",
        reply_markup=kb.back_kb("menu_profile")
    )


@router.callback_query(F.data == "profile_tickets")
async def my_tickets(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    tickets = db.get_user_tickets(user["id"])
    if not tickets:
        text = "У вас нет тикетов."
        await edit_screen(callback, text, reply_markup=kb.back_kb("menu_profile"))
        await callback.answer()
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for t in tickets:
        status_emoji = "🟢" if t["status"] == "open" else "⚪️"
        appeal_mark = "🆘 " if t["is_appeal"] else ""
        rows.append([InlineKeyboardButton(
            text=f"{status_emoji} {appeal_mark}Тикет #{t['id']} — {t['reason'][:25]}",
            callback_data=f"ticket_view_{t['id']}"
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")])
    await edit_screen(callback, "🎫 <b>Мои тикеты</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "profile_notifications")
async def notifications_menu(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    enabled = bool(user["notifications_enabled"])
    status = "включены ✅" if enabled else "выключены ❌"
    text = (
        f"🔔 <b>Уведомления</b>\n\n"
        f"Сейчас уведомления {status}.\n"
        f"Сюда входят напоминания о записи (за 3 часа и за 1 час) и сообщения об акциях/скидках."
    )
    await edit_screen(callback, text, reply_markup=kb.notifications_kb(enabled), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "notifications_toggle")
async def notifications_toggle(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    new_state = not bool(user["notifications_enabled"])
    db.set_notifications(user["id"], new_state)
    status = "включены ✅" if new_state else "выключены ❌"
    await edit_screen(callback, f"Готово, уведомления теперь {status}.", reply_markup=kb.notifications_kb(new_state))
    await callback.answer()
