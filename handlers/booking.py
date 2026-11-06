from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery

import database as db
import keyboards as kb
from ui import edit_screen
from states import Booking
from config import CATEGORIES, WORK_START_HOUR, WORK_END_HOUR, SLOT_MINUTES, DAYS_AHEAD, ADMIN_IDS, MAX_ACTIVE_BOOKINGS

router = Router()

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def build_dates():
    dates = []
    today = datetime.now().date()
    for i in range(DAYS_AHEAD):
        d = today + timedelta(days=i)
        label = f"{d.day} {MONTHS_RU[d.month - 1]} ({WEEKDAYS_RU[d.weekday()]})"
        dates.append((label, d.isoformat()))
    return dates


def build_slots():
    slots = []
    h = WORK_START_HOUR
    while h < WORK_END_HOUR:
        slots.append(f"{h:02d}:00")
        h += SLOT_MINUTES // 60
    return slots


def build_dates_with_status(master_id):
    """Returns list of (label, date_iso, is_free) using real availability
    (bookings + vacation days) for the given master."""
    result = []
    for label, date_iso in build_dates():
        is_free = db.master_day_has_free_slot(master_id, date_iso)
        result.append((label, date_iso, is_free))
    return result


@router.callback_query(F.data == "menu_book")
async def start_booking(callback: CallbackQuery, state):
    user = db.get_user(callback.from_user.id)
    active_count = db.count_active_bookings(user["id"])
    if active_count >= MAX_ACTIVE_BOOKINGS:
        await edit_screen(callback,
            f"⚠️ У вас уже {active_count} активных записей — это максимум.\n"
            f"Отмените одну из существующих записей («Профиль» → «Мои записи»), "
            f"прежде чем создавать новую.",
            reply_markup=kb.back_kb()
        )
        await callback.answer()
        return

    await state.set_state(Booking.choosing_master)
    masters = db.get_masters()
    if not masters:
        await edit_screen(callback, "Пока нет доступных мастеров для записи.", reply_markup=kb.back_kb())
        await callback.answer()
        return
    await edit_screen(callback,
        "👤 Выберите мастера:", reply_markup=kb.masters_kb(masters)
    )
    await callback.answer()


@router.callback_query(Booking.choosing_master, F.data.startswith("master_"))
async def choose_master(callback: CallbackQuery, state):
    master_id = int(callback.data.split("_")[1])
    master = db.get_master(master_id)
    if not master:
        await callback.answer("Мастер не найден", show_alert=True)
        return
    await state.update_data(master_id=master_id, master_name=master["name"])
    await state.set_state(Booking.choosing_category)
    allowed = [k for k in (master["services"] or "").split(",") if k]

    user = db.get_user(callback.from_user.id)
    discount = db.best_available_discount(user["id"], master_id=master_id)["percent"]
    discount_note = f"\n🔥 Для вас сейчас действует скидка {discount}%!" if discount else ""

    await edit_screen(callback,
        f"Мастер: <b>{master['name']}</b>\n\nВыберите услугу:{discount_note}",
        reply_markup=kb.categories_kb(allowed, discount), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(Booking.choosing_category, F.data.startswith("cat_"))
async def choose_category(callback: CallbackQuery, state):
    key = callback.data[len("cat_"):]
    if key not in CATEGORIES:
        await callback.answer("Неизвестная услуга", show_alert=True)
        return
    data = await state.get_data()
    master = db.get_master(data["master_id"])
    allowed = [k for k in (master["services"] or "").split(",") if k]
    if allowed and key not in allowed:
        await callback.answer("Этот мастер не предоставляет такую услугу", show_alert=True)
        return

    name, base_price = CATEGORIES[key]
    user = db.get_user(callback.from_user.id)
    best = db.best_available_discount(user["id"], master_id=data["master_id"], category_key=key)
    discount = best["percent"]
    final_price = round(base_price * (100 - discount) / 100) if discount else base_price

    await state.update_data(
        category_key=key, category_name=name,
        price=final_price, original_price=base_price, discount_percent=discount,
        discount_source=best["source"], discount_redemption_id=best["redemption_id"],
    )
    await state.set_state(Booking.choosing_date)
    dates = build_dates_with_status(data["master_id"])
    price_line = f"{final_price}₽ (было {base_price}₽, -{discount}%)" if discount else f"{base_price}₽"
    await edit_screen(callback,
        f"Услуга: <b>{name}</b> — {price_line}\n\n📅 Выберите дату (🟩 — есть окна, 🟥 — свободных мест нет):",
        reply_markup=kb.dates_kb(dates), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(Booking.choosing_date, F.data == "date_full")
async def date_full(callback: CallbackQuery):
    await callback.answer("На эту дату нет свободных окон, выберите другую.", show_alert=True)


@router.callback_query(Booking.choosing_date, F.data.startswith("date_"))
async def choose_date(callback: CallbackQuery, state):
    date_str = callback.data[len("date_"):]
    data = await state.get_data()
    master_id = data["master_id"]

    if db.is_master_day_off(master_id, date_str):
        await callback.answer("Мастер не работает в этот день (отпуск). Выберите другую дату.", show_alert=True)
        return

    taken = db.get_taken_slots(master_id, date_str)
    all_slots = build_slots()

    # if the chosen date is today, hide past time slots
    today = datetime.now().date().isoformat()
    if date_str == today:
        now = datetime.now()
        all_slots = [s for s in all_slots if datetime.strptime(s, "%H:%M").time() > now.time()]

    await state.update_data(date=date_str)
    await state.set_state(Booking.choosing_time)

    if not all_slots:
        await edit_screen(callback,
            "На выбранную дату свободных слотов не осталось. Выберите другую дату.",
            reply_markup=kb.back_kb("menu_book")
        )
        await callback.answer()
        return

    await edit_screen(callback,
        "🕐 Выберите время (🚫 — уже занято):",
        reply_markup=kb.times_kb(all_slots, taken)
    )
    await callback.answer()


@router.callback_query(Booking.choosing_time, F.data == "time_taken")
async def time_taken(callback: CallbackQuery):
    await callback.answer("Это время уже занято, выберите другое.", show_alert=True)


@router.callback_query(Booking.choosing_time, F.data.startswith("time_"))
async def choose_time(callback: CallbackQuery, state):
    time_str = callback.data[len("time_"):]
    data = await state.get_data()
    master_id = data["master_id"]
    date_str = data["date"]

    user = db.get_user(callback.from_user.id)

    if db.is_master_day_off(master_id, date_str):
        await callback.answer("Мастер только что ушёл в отпуск на эту дату. Выберите другую дату.", show_alert=True)
        return

    # limit re-checked here too, in case user opened two booking flows in parallel
    if db.count_active_bookings(user["id"]) >= MAX_ACTIVE_BOOKINGS:
        await callback.answer("У вас уже максимум активных записей.", show_alert=True)
        await state.clear()
        return

    # re-check slot wasn't taken meanwhile (race condition safety)
    taken = db.get_taken_slots(master_id, date_str)
    if time_str in taken:
        await callback.answer("Это время только что заняли, выберите другое.", show_alert=True)
        return

    # prevent the same user from double-booking themselves at the same date & time
    if db.find_active_booking_at(user["id"], date_str, time_str):
        await callback.answer("У вас уже есть запись на это время у другого мастера.", show_alert=True)
        return

    # recompute the best discount right before creating the booking (race-condition
    # safety: a promo/discount may have expired or been used up while choosing date/time)
    base_price = CATEGORIES[data["category_key"]][1]
    best = db.best_available_discount(user["id"], master_id=master_id, category_key=data["category_key"])
    discount = best["percent"]
    final_price = round(base_price * (100 - discount) / 100) if discount else base_price

    booking_id = db.create_booking(
        user_id=user["id"], master_id=master_id,
        category_key=data["category_key"], category_name=data["category_name"],
        price=final_price, date=date_str, time=time_str,
        original_price=base_price,
        discount_percent=discount,
    )
    if best["source"] == "promo" and best["redemption_id"]:
        db.mark_user_promocode_used(best["redemption_id"], booking_id)
    await state.clear()

    price_line = f"{final_price}₽ (скидка {discount}%)" if discount else f"{final_price}₽"
    summary = (
        f"✅ <b>Запись подтверждена!</b>\n\n"
        f"Мастер: {data['master_name']}\n"
        f"Услуга: {data['category_name']} — {price_line}\n"
        f"Дата: {date_str}\n"
        f"Время: {time_str}\n\n"
        f"Напомним вам за 3 часа и за 1 час до визита 🙂"
    )
    await edit_screen(callback, summary, reply_markup=kb.back_kb(), parse_mode="HTML")
    await callback.answer()

    # notify admins
    admin_text = (
        f"📥 <b>Новая запись</b> #{booking_id}\n"
        f"Клиент: {user['name']} (ID {user['id']})\n"
        f"Мастер: {data['master_name']}\n"
        f"Услуга: {data['category_name']} — {price_line}\n"
        f"Дата: {date_str} {time_str}"
    )
    bot = callback.bot
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, parse_mode="HTML")
        except Exception:
            pass
