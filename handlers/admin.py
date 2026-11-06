import os
import tempfile
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
import keyboards as kb
from ui import edit_screen
from states import AdminAddMaster, AdminDiscount, AdminPromo
from config import ADMIN_IDS, CATEGORIES

router = Router()


# ---------- Add master (step-by-step, with photo and services) ----------

@router.callback_query(F.data == "admin_add_master")
async def add_master_start(callback: CallbackQuery, state):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    await state.set_state(AdminAddMaster.waiting_name)
    await edit_screen(callback, "Введите имя нового мастера:")
    await callback.answer()


@router.message(AdminAddMaster.waiting_name)
async def add_master_name(message: Message, state):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Введите корректное имя мастера:")
        return
    await state.update_data(name=name)
    await state.set_state(AdminAddMaster.waiting_description)
    await message.answer("Введите короткое описание мастера (специализация, опыт и т.п.):")


@router.message(AdminAddMaster.waiting_description)
async def add_master_description(message: Message, state):
    description = (message.text or "").strip()
    await state.update_data(description=description)
    await state.set_state(AdminAddMaster.waiting_photo)
    await message.answer(
        "Отправьте фото мастера (просто отправьте картинку в чат):",
        reply_markup=kb.skip_photo_kb()
    )


@router.message(AdminAddMaster.waiting_photo, F.photo)
async def add_master_photo(message: Message, state):
    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=file_id, selected_services=[])
    await message.answer(
        "Выберите услуги, которые оказывает мастер, и нажмите «Готово»:",
        reply_markup=kb.services_select_kb(set())
    )
    await state.set_state(AdminAddMaster.waiting_services)


@router.callback_query(AdminAddMaster.waiting_photo, F.data == "master_photo_skip")
async def add_master_photo_skip(callback: CallbackQuery, state):
    await state.update_data(photo_file_id=None, selected_services=[])
    await edit_screen(callback,
        "Выберите услуги, которые оказывает мастер, и нажмите «Готово»:",
        reply_markup=kb.services_select_kb(set())
    )
    await state.set_state(AdminAddMaster.waiting_services)
    await callback.answer()


@router.message(AdminAddMaster.waiting_photo)
async def add_master_photo_wrong(message: Message):
    await message.answer("Отправьте фото картинкой, или нажмите «Без фото» под предыдущим сообщением.")


@router.callback_query(AdminAddMaster.waiting_services, F.data.startswith("svc_toggle_"))
async def add_master_toggle_service(callback: CallbackQuery, state):
    key = callback.data[len("svc_toggle_"):]
    if key not in CATEGORIES:
        await callback.answer()
        return
    data = await state.get_data()
    selected = set(data.get("selected_services", []))
    if key in selected:
        selected.discard(key)
    else:
        selected.add(key)
    await state.update_data(selected_services=list(selected))
    await callback.message.edit_reply_markup(reply_markup=kb.services_select_kb(selected))
    await callback.answer()


@router.callback_query(AdminAddMaster.waiting_services, F.data == "svc_done")
async def add_master_finish(callback: CallbackQuery, state):
    data = await state.get_data()
    selected = data.get("selected_services", [])
    if not selected:
        await callback.answer("Выберите хотя бы одну услугу", show_alert=True)
        return
    db.add_master(
        name=data["name"],
        description=data.get("description", ""),
        photo_file_id=data.get("photo_file_id"),
        services=",".join(selected),
    )
    await state.clear()
    services_names = ", ".join(CATEGORIES[k][0] for k in selected)
    await edit_screen(callback,
        f"✅ Мастер «{data['name']}» добавлен!\nУслуги: {services_names}",
        reply_markup=kb.back_kb("admin_panel")
    )
    await callback.answer()


@router.message(Command("addmaster"))
async def cmd_add_master(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    name = message.text.replace("/addmaster", "", 1).strip()
    if not name:
        await message.answer("Использование: /addmaster Имя мастера")
        return
    db.add_master(name)
    await message.answer(f"✅ Мастер «{name}» добавлен.")


@router.message(Command("addpromo"))
async def cmd_add_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[2].isdigit():
        await message.answer("Использование: /addpromo КОД СКИДКА_В_ПРОЦЕНТАХ\nНапример: /addpromo SALE10 10")
        return
    code, discount = parts[1].upper(), int(parts[2])
    db.create_promocode(code, ptype="total", percent=discount, name="Ручной промокод")
    await message.answer(f"✅ Промокод {code} на {discount}% создан (тип: скидка на всю покупку, без ограничений).")


def admin_only(callback: CallbackQuery) -> bool:
    return callback.from_user.id in ADMIN_IDS


@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if not admin_only(callback):
        await callback.answer("Недоступно", show_alert=True)
        return
    await edit_screen(callback, "🛡 <b>Панель администратора</b>", reply_markup=kb.admin_panel_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_tickets")
async def admin_tickets(callback: CallbackQuery):
    if not admin_only(callback):
        await callback.answer("Недоступно", show_alert=True)
        return
    tickets = db.get_open_tickets()
    if not tickets:
        await edit_screen(callback, "Открытых тикетов нет.", reply_markup=kb.back_kb("admin_panel"))
        await callback.answer()
        return
    rows = []
    for t in tickets:
        appeal_mark = "🆘 " if t["is_appeal"] else ""
        rows.append([InlineKeyboardButton(
            text=f"{appeal_mark}#{t['id']} — {t['user_name']} — {t['reason'][:25]}",
            callback_data=f"ticket_view_{t['id']}"
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")])
    await edit_screen(callback,
        "🎫 <b>Открытые тикеты</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_export_users")
async def admin_export_users(callback: CallbackQuery):
    if not admin_only(callback):
        await callback.answer("Недоступно", show_alert=True)
        return
    await callback.answer("Формирую файл...")
    try:
        from openpyxl import Workbook
    except ImportError:
        await edit_screen(callback, "Библиотека openpyxl не установлена на сервере.")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Пользователи"
    ws.append(["ID (программа лояльности)", "Telegram ID", "Имя", "Скидка %", "Заблокирован", "Причина блокировки", "Дата регистрации"])
    for u in db.all_users():
        ws.append([u["id"], u["telegram_id"], u["name"], u["discount"],
                   "да" if u["banned"] else "нет", u["ban_reason"], u["registered_at"]])

    ws2 = wb.create_sheet("Записи")
    ws2.append(["ID", "Клиент", "Мастер", "Услуга", "Цена", "Дата", "Время", "Статус"])
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT b.*, m.name as master_name, u.name as user_name FROM bookings b "
            "JOIN masters m ON b.master_id=m.id JOIN users u ON b.user_id=u.id ORDER BY b.date, b.time"
        ).fetchall()
    for b in rows:
        ws2.append([b["id"], b["user_name"], b["master_name"], b["category_name"], b["price"], b["date"], b["time"], b["status"]])

    tmp_path = os.path.join(tempfile.gettempdir(), "users_export.xlsx")
    wb.save(tmp_path)
    await callback.message.answer_document(
        FSInputFile(tmp_path, filename="salon_users_export.xlsx"),
        caption="📊 Данные пользователей и записей"
    )
    await edit_screen(callback, "Готово.", reply_markup=kb.back_kb("admin_panel"))


# ---------- Bookings management (admin can cancel/delete a booking) ----------

@router.callback_query(F.data == "admin_bookings")
async def admin_bookings_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    bookings = db.get_upcoming_active_bookings()
    if not bookings:
        await edit_screen(callback, "Активных записей нет.", reply_markup=kb.back_kb("admin_panel"))
        await callback.answer()
        return
    rows = []
    for b in bookings:
        rows.append([InlineKeyboardButton(
            text=f"{b['date']} {b['time']} — {b['user_name']} у {b['master_name']}",
            callback_data=f"admin_view_booking_{b['id']}"
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")])
    await edit_screen(callback,
        "📅 <b>Активные записи</b>\nНажмите на запись, чтобы посмотреть детали и отменить её:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_view_booking_"))
async def admin_view_booking(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    booking_id = int(callback.data.split("_")[-1])
    b = db.get_booking(booking_id)
    if not b or b["status"] != "active":
        await callback.answer("Запись не найдена или уже отменена", show_alert=True)
        return
    price_line = f"{b['price']}₽"
    if b["discount_percent"]:
        price_line += f" (скидка {b['discount_percent']}%, было {b['original_price']}₽)"
    text = (
        f"📅 <b>Запись #{b['id']}</b>\n\n"
        f"Клиент: {b['user_name']}\n"
        f"Мастер: {b['master_name']}\n"
        f"Услуга: {b['category_name']} — {price_line}\n"
        f"Дата: {b['date']} в {b['time']}"
    )
    await edit_screen(callback, text, reply_markup=kb.booking_view_kb(booking_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_cancel_booking_"))
async def admin_cancel_booking(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    booking_id = int(callback.data.split("_")[-1])
    b = db.get_booking(booking_id)
    if not b or b["status"] != "active":
        await callback.answer("Запись не найдена или уже отменена", show_alert=True)
        return
    db.cancel_booking(booking_id)
    db.create_cancellation_promo(b["user_id"])
    await edit_screen(callback, f"✅ Запись #{booking_id} отменена.", reply_markup=kb.back_kb("admin_bookings"))
    await callback.answer()
    try:
        await callback.bot.send_message(
            b["tg_id"],
            f"ℹ️ Ваша запись на {b['date']} в {b['time']} ({b['category_name']}, "
            f"мастер {b['master_name']}) была отменена администратором.\n"
            f"Если у вас есть вопросы — напишите в поддержку.\n\n"
            f"🎁 В качестве компенсации мы начислили вам купон на <b>10% скидку</b> на следующий заказ "
            f"(бессрочный, посмотреть можно в «Профиль» → «Программа лояльности»).",
            parse_mode="HTML",
        )
    except Exception:
        pass


# ---------- Discounts & promocodes (scoped discounts + generated promo codes) ----------

def _discount_desc(d) -> str:
    if d["scope"] == "all":
        target = "на все услуги"
    elif d["scope"] == "master":
        target = f"у мастера «{d['master_name']}»" if d["master_name"] else "у мастера (удалён)"
    else:
        name = CATEGORIES.get(d["category_key"], (d["category_key"],))[0]
        target = f"на услугу «{name}»"
    expiry = f"до {d['expires_at']}" if d["expires_at"] else "бессрочно"
    return f"#{d['id']}: -{d['percent']}% {target}, {expiry}"


def _promo_desc(p) -> str:
    label = db.PROMO_TYPE_LABELS.get(p["type"], p["type"])
    target = ""
    if p["type"] == "master" and p["master_id"]:
        master = db.get_master(p["master_id"])
        target = f" (мастер «{master['name']}»)" if master else " (мастер удалён)"
    elif p["type"] == "service" and p["category_key"]:
        name = CATEGORIES.get(p["category_key"], (p["category_key"],))[0]
        target = f" (услуга «{name}»)"
    expiry = f"до {p['expires_at']}" if p["expires_at"] else "бессрочно"
    activations = f"{p['activations_used']}/{p['max_activations']}" if p["max_activations"] else f"{p['activations_used']}/∞"
    status = "✅ активен" if p["active"] else "🚫 выключен"
    name_line = f" «{p['name']}»" if p["name"] else ""
    return f"<b>{p['code']}</b>{name_line} — {label}{target}, -{p['discount']}%, активаций {activations}, {expiry}, {status}"


@router.callback_query(F.data == "admin_sale")
async def admin_sale_panel(callback: CallbackQuery):
    if not admin_only(callback):
        await callback.answer("Недоступно", show_alert=True)
        return
    discounts = db.get_active_discounts()
    promos = [p for p in db.get_all_promocodes() if p["active"]]
    text = (
        f"🔥 <b>Скидки и промокоды</b>\n\n"
        f"Активных скидок: {len(discounts)}\n"
        f"Активных промокодов: {len(promos)}\n\n"
        f"Скидки применяются автоматически при записи. Промокоды клиент вводит сам "
        f"(кроме компенсационных купонов за отменённые записи — они начисляются "
        f"автоматически). Если применимо несколько скидок — используется наибольшая, "
        f"они не суммируются."
    )
    await edit_screen(callback, text, reply_markup=kb.discount_promo_panel_kb(), parse_mode="HTML")
    await callback.answer()


# ----- Add discount -----

@router.callback_query(F.data == "discount_add")
async def discount_add_start(callback: CallbackQuery, state):
    if not admin_only(callback):
        await callback.answer("Недоступно", show_alert=True)
        return
    await state.set_state(AdminDiscount.choosing_scope)
    await edit_screen(callback, "На что действует скидка?", reply_markup=kb.discount_scope_kb())
    await callback.answer()


@router.callback_query(AdminDiscount.choosing_scope, F.data == "discount_scope_all")
async def discount_scope_all(callback: CallbackQuery, state):
    await state.update_data(scope="all", master_id=None, category_key=None)
    await state.set_state(AdminDiscount.waiting_percent)
    await edit_screen(callback, "Введите процент скидки (число от 1 до 90), например: 15")
    await callback.answer()


@router.callback_query(AdminDiscount.choosing_scope, F.data == "discount_scope_master")
async def discount_scope_master(callback: CallbackQuery, state):
    masters = db.get_masters()
    if not masters:
        await callback.answer("Мастеров пока нет", show_alert=True)
        return
    await state.set_state(AdminDiscount.choosing_master)
    await edit_screen(callback, "Выберите мастера:", reply_markup=kb.masters_pick_kb(masters, "discmaster", "discount_add"))
    await callback.answer()


@router.callback_query(AdminDiscount.choosing_scope, F.data == "discount_scope_service")
async def discount_scope_service(callback: CallbackQuery, state):
    await state.set_state(AdminDiscount.choosing_service)
    await edit_screen(callback, "Выберите услугу:", reply_markup=kb.services_pick_kb("discsvc", "discount_add"))
    await callback.answer()


@router.callback_query(AdminDiscount.choosing_master, F.data.startswith("discmaster_"))
async def discount_pick_master(callback: CallbackQuery, state):
    master_id = int(callback.data.split("_")[-1])
    await state.update_data(scope="master", master_id=master_id, category_key=None)
    await state.set_state(AdminDiscount.waiting_percent)
    await edit_screen(callback, "Введите процент скидки (число от 1 до 90), например: 15")
    await callback.answer()


@router.callback_query(AdminDiscount.choosing_service, F.data.startswith("discsvc_"))
async def discount_pick_service(callback: CallbackQuery, state):
    key = callback.data[len("discsvc_"):]
    if key not in CATEGORIES:
        await callback.answer("Неизвестная услуга", show_alert=True)
        return
    await state.update_data(scope="service", master_id=None, category_key=key)
    await state.set_state(AdminDiscount.waiting_percent)
    await edit_screen(callback, "Введите процент скидки (число от 1 до 90), например: 15")
    await callback.answer()


@router.message(AdminDiscount.waiting_percent)
async def discount_waiting_percent(message: Message, state):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text.isdigit() or not (1 <= int(text) <= 90):
        await message.answer("Введите целое число от 1 до 90:")
        return
    await state.update_data(percent=int(text))
    await state.set_state(AdminDiscount.waiting_expiry)
    await message.answer("До какого числа действует скидка? Формат: ДД.ММ.ГГГГ, либо «-» — бессрочно.")


@router.message(AdminDiscount.waiting_expiry)
async def discount_waiting_expiry(message: Message, state):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    text = (message.text or "").strip()
    expires_at = None
    if text != "-":
        try:
            expires_at = datetime.strptime(text, "%d.%m.%Y").date().isoformat()
        except ValueError:
            await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ, либо «-» — бессрочно.")
            return
    data = await state.get_data()
    db.add_discount(
        scope=data["scope"], percent=data["percent"], expires_at=expires_at,
        master_id=data.get("master_id"), category_key=data.get("category_key"),
    )
    await state.clear()
    await message.answer(
        f"✅ Скидка {data['percent']}% добавлена ({'бессрочно' if not expires_at else 'до ' + expires_at}).",
        reply_markup=kb.back_kb("admin_sale")
    )


@router.callback_query(F.data == "discount_list")
async def discount_list(callback: CallbackQuery):
    if not admin_only(callback):
        await callback.answer("Недоступно", show_alert=True)
        return
    discounts = db.get_active_discounts()
    if not discounts:
        await edit_screen(callback, "Активных скидок нет.", reply_markup=kb.back_kb("admin_sale"))
        await callback.answer()
        return
    text = "📋 <b>Активные скидки</b>\n\n" + "\n".join(_discount_desc(d) for d in discounts)
    await edit_screen(callback, text, reply_markup=kb.discount_list_kb(discounts), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("discount_del_"))
async def discount_delete(callback: CallbackQuery):
    if not admin_only(callback):
        await callback.answer("Недоступно", show_alert=True)
        return
    discount_id = int(callback.data.split("_")[-1])
    db.deactivate_discount(discount_id)
    await callback.answer("Скидка деактивирована")
    discounts = db.get_active_discounts()
    if not discounts:
        await edit_screen(callback, "Активных скидок нет.", reply_markup=kb.back_kb("admin_sale"))
        return
    text = "📋 <b>Активные скидки</b>\n\n" + "\n".join(_discount_desc(d) for d in discounts)
    await edit_screen(callback, text, reply_markup=kb.discount_list_kb(discounts), parse_mode="HTML")


# ----- Add promocode -----

@router.callback_query(F.data == "promo_add")
async def promo_add_start(callback: CallbackQuery, state):
    if not admin_only(callback):
        await callback.answer("Недоступно", show_alert=True)
        return
    await state.set_state(AdminPromo.choosing_type)
    await edit_screen(callback, "Для чего этот промокод?", reply_markup=kb.promo_type_kb())
    await callback.answer()


@router.callback_query(AdminPromo.choosing_type, F.data == "promo_type_first_order")
async def promo_type_first_order(callback: CallbackQuery, state):
    await state.update_data(ptype="first_order", master_id=None, category_key=None)
    await state.set_state(AdminPromo.waiting_name)
    await edit_screen(callback, "Введите название промокода (для внутреннего учёта):")
    await callback.answer()


@router.callback_query(AdminPromo.choosing_type, F.data == "promo_type_total")
async def promo_type_total(callback: CallbackQuery, state):
    await state.update_data(ptype="total", master_id=None, category_key=None)
    await state.set_state(AdminPromo.waiting_name)
    await edit_screen(callback, "Введите название промокода (для внутреннего учёта):")
    await callback.answer()


@router.callback_query(AdminPromo.choosing_type, F.data == "promo_type_master")
async def promo_type_master(callback: CallbackQuery, state):
    masters = db.get_masters()
    if not masters:
        await callback.answer("Мастеров пока нет", show_alert=True)
        return
    await state.set_state(AdminPromo.choosing_master)
    await edit_screen(callback, "Выберите мастера:", reply_markup=kb.masters_pick_kb(masters, "promomaster", "promo_add"))
    await callback.answer()


@router.callback_query(AdminPromo.choosing_type, F.data == "promo_type_service")
async def promo_type_service(callback: CallbackQuery, state):
    await state.set_state(AdminPromo.choosing_service)
    await edit_screen(callback, "Выберите услугу:", reply_markup=kb.services_pick_kb("promosvc", "promo_add"))
    await callback.answer()


@router.callback_query(AdminPromo.choosing_master, F.data.startswith("promomaster_"))
async def promo_pick_master(callback: CallbackQuery, state):
    master_id = int(callback.data.split("_")[-1])
    await state.update_data(ptype="master", master_id=master_id, category_key=None)
    await state.set_state(AdminPromo.waiting_name)
    await edit_screen(callback, "Введите название промокода (для внутреннего учёта):")
    await callback.answer()


@router.callback_query(AdminPromo.choosing_service, F.data.startswith("promosvc_"))
async def promo_pick_service(callback: CallbackQuery, state):
    key = callback.data[len("promosvc_"):]
    if key not in CATEGORIES:
        await callback.answer("Неизвестная услуга", show_alert=True)
        return
    await state.update_data(ptype="service", master_id=None, category_key=key)
    await state.set_state(AdminPromo.waiting_name)
    await edit_screen(callback, "Введите название промокода (для внутреннего учёта):")
    await callback.answer()


@router.message(AdminPromo.waiting_name)
async def promo_waiting_name(message: Message, state):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("Введите название промокода текстом:")
        return
    await state.update_data(name=name)
    await state.set_state(AdminPromo.waiting_percent)
    await message.answer("Введите процент скидки по промокоду (число от 1 до 90):")


@router.message(AdminPromo.waiting_percent)
async def promo_waiting_percent(message: Message, state):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text.isdigit() or not (1 <= int(text) <= 90):
        await message.answer("Введите целое число от 1 до 90:")
        return
    await state.update_data(percent=int(text))
    await state.set_state(AdminPromo.waiting_activations)
    await message.answer("Сколько раз можно активировать этот промокод? Введите целое число:")


@router.message(AdminPromo.waiting_activations)
async def promo_waiting_activations(message: Message, state):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) < 1:
        await message.answer("Введите целое положительное число:")
        return
    await state.update_data(max_activations=int(text))
    await state.set_state(AdminPromo.waiting_expiry)
    await message.answer("До какого числа действует промокод? Формат: ДД.ММ.ГГГГ, либо «-» — бессрочно.")


@router.message(AdminPromo.waiting_expiry)
async def promo_waiting_expiry(message: Message, state):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    text = (message.text or "").strip()
    expires_at = None
    if text != "-":
        try:
            expires_at = datetime.strptime(text, "%d.%m.%Y").date().isoformat()
        except ValueError:
            await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ, либо «-» — бессрочно.")
            return
    code = db.generate_promo_code()
    await state.update_data(expires_at=expires_at, generated_code=code)
    await state.set_state(AdminPromo.waiting_confirm)
    await message.answer(
        f"Сгенерирован код: <code>{code}</code>\n\n"
        f"Чтобы подтвердить создание промокода, введите этот код ещё раз:",
        parse_mode="HTML"
    )


@router.message(AdminPromo.waiting_confirm)
async def promo_waiting_confirm(message: Message, state):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    data = await state.get_data()
    entered = (message.text or "").strip().upper()
    if entered != data.get("generated_code"):
        await message.answer(
            f"❌ Код не совпадает. Введите код ещё раз:\n<code>{data.get('generated_code')}</code>",
            parse_mode="HTML"
        )
        return
    db.create_promocode(
        code=data["generated_code"], ptype=data["ptype"], percent=data["percent"], name=data.get("name", ""),
        master_id=data.get("master_id"), category_key=data.get("category_key"),
        max_activations=data.get("max_activations"), expires_at=data.get("expires_at"),
    )
    await state.clear()
    await message.answer(
        f"✅ Промокод <code>{data['generated_code']}</code> создан!\n"
        f"Передайте этот код клиенту — он вводит его в «Профиль» → «Программа лояльности» → «Применить промокод».",
        reply_markup=kb.back_kb("admin_sale"), parse_mode="HTML"
    )


@router.callback_query(F.data == "promo_list")
async def promo_list(callback: CallbackQuery):
    if not admin_only(callback):
        await callback.answer("Недоступно", show_alert=True)
        return
    promos = db.get_all_promocodes()
    if not promos:
        await edit_screen(callback, "Промокодов пока нет.", reply_markup=kb.back_kb("admin_sale"))
        await callback.answer()
        return
    text = "📋 <b>Промокоды</b>\n\n" + "\n".join(_promo_desc(p) for p in promos)
    await edit_screen(callback, text, reply_markup=kb.promo_list_kb(promos), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("promo_del_"))
async def promo_delete(callback: CallbackQuery):
    if not admin_only(callback):
        await callback.answer("Недоступно", show_alert=True)
        return
    code = callback.data[len("promo_del_"):]
    db.deactivate_promocode(code)
    await callback.answer("Промокод деактивирован")
    promos = db.get_all_promocodes()
    text = "📋 <b>Промокоды</b>\n\n" + "\n".join(_promo_desc(p) for p in promos)
    await edit_screen(callback, text, reply_markup=kb.promo_list_kb(promos), parse_mode="HTML")


# ================= MASTER MANAGEMENT (vacation calendar + delete) =================

from handlers.booking import build_dates  # reuse date-range helper


def _vacation_day_statuses(master_id):
    return [(label, date_iso, db.master_day_has_free_slot(master_id, date_iso))
            for label, date_iso in build_dates()]


@router.callback_query(F.data == "admin_manage_masters")
async def admin_manage_masters(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    masters = db.get_masters()
    if not masters:
        await edit_screen(callback, "Мастеров пока нет.", reply_markup=kb.back_kb("admin_panel"))
        await callback.answer()
        return
    await edit_screen(callback,
        "🗂 <b>Управление мастерами</b>\nВыберите мастера:",
        reply_markup=kb.manage_masters_kb(masters), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manage_master_"))
async def manage_master(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    master_id = int(callback.data.split("_")[-1])
    master = db.get_master(master_id)
    if not master:
        await callback.answer("Мастер не найден", show_alert=True)
        return
    text = f"👤 <b>{master['name']}</b>\n{master['description']}"
    await edit_screen(callback, text, reply_markup=kb.master_manage_actions_kb(master_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("vacation_"))
async def vacation_calendar(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    master_id = int(callback.data.split("_")[-1])
    statuses = _vacation_day_statuses(master_id)
    await edit_screen(callback,
        "🏖 <b>Управление отпуском</b>\n\n"
        "🟩 — есть свободные окна, 🟥 — окон нет или день выходной.\n"
        "Нажмите на дату, чтобы поставить/снять «выходной» для мастера "
        "(если на день уже есть активные записи — сначала отмените их).",
        reply_markup=kb.vacation_calendar_kb(master_id, statuses), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("vacday_"))
async def vacation_toggle_day(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    _, master_id_str, date_str = callback.data.split("_", 2)
    master_id = int(master_id_str)

    if db.is_master_day_off(master_id, date_str):
        db.remove_master_day_off(master_id, date_str)
        await callback.answer("Выходной снят, день снова рабочий.")
    else:
        taken = db.get_taken_slots(master_id, date_str)
        if taken:
            await callback.answer(
                "На этот день уже есть активные записи — сначала отмените их в разделе "
                "«Записи (удалить)», потом можно поставить выходной.", show_alert=True
            )
            return
        db.add_master_day_off(master_id, date_str, reason="отпуск")
        await callback.answer("День отмечен как выходной (отпуск).")

    statuses = _vacation_day_statuses(master_id)
    await callback.message.edit_reply_markup(reply_markup=kb.vacation_calendar_kb(master_id, statuses))


@router.callback_query(F.data.startswith("delete_master_confirm_"))
async def delete_master_confirm(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    master_id = int(callback.data.split("_")[-1])
    master = db.get_master(master_id)
    ok = db.delete_master(master_id)
    if ok:
        await edit_screen(callback, f"🗑 Мастер «{master['name']}» удалён.", reply_markup=kb.back_kb("admin_manage_masters"))
    else:
        await edit_screen(callback,
            f"⚠️ У мастера «{master['name']}» есть активные записи — сначала отмените их "
            f"в разделе «Записи (удалить)», потом можно будет удалить мастера.",
            reply_markup=kb.back_kb("admin_manage_masters")
        )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_master_") & ~F.data.startswith("delete_master_confirm_"))
async def delete_master_ask(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    master_id = int(callback.data.split("_")[-1])
    master = db.get_master(master_id)
    if not master:
        await callback.answer("Мастер не найден", show_alert=True)
        return
    await edit_screen(callback,
        f"Удалить мастера «{master['name']}»? Это скроет его из всех списков "
        f"(история его записей сохранится).",
        reply_markup=kb.confirm_delete_master_kb(master_id)
    )
    await callback.answer()
