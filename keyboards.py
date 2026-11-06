from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from config import CATEGORIES, ADMIN_IDS


def register_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Зарегистрироваться", callback_data="register_start")]
    ])


def terms_agreement_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я согласен(на) с условиями", callback_data="terms_agree")],
        [InlineKeyboardButton(text="❌ Не согласен(на)", callback_data="terms_decline")],
    ])


def main_menu_kb(telegram_id: int = None):
    rows = [
        [InlineKeyboardButton(text="📅 Записаться", callback_data="menu_book")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton(text="💇 Мастера", callback_data="menu_masters")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="menu_faq")],
        [InlineKeyboardButton(text="🛠 Связаться с поддержкой", callback_data="menu_support")],
    ]
    if telegram_id in ADMIN_IDS:
        rows.append([InlineKeyboardButton(text="🛡 Панель администратора", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb(target="menu_main"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=target)]
    ])


def masters_kb(masters, prefix="master"):
    rows = [[InlineKeyboardButton(text=m["name"], callback_data=f"{prefix}_{m['id']}")] for m in masters]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_kb(allowed_keys=None, discount: int = 0):
    """allowed_keys: iterable of CATEGORIES keys to show; None/empty means show all (legacy masters).
    discount: percent to apply to displayed prices (0 = no discount)."""
    rows = []
    keys = allowed_keys if allowed_keys else CATEGORIES.keys()
    for key in keys:
        if key not in CATEGORIES:
            continue
        name, price = CATEGORIES[key]
        if discount:
            final_price = round(price * (100 - discount) / 100)
            label = f"{name} — {final_price}₽ (было {price}₽, -{discount}%)"
        else:
            label = f"{name} — {price}₽"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"cat_{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_book")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_select_kb(selected: set):
    """Multi-select keyboard used by admin when adding a new master."""
    rows = []
    for key, (name, price) in CATEGORIES.items():
        mark = "✅ " if key in selected else "▫️ "
        rows.append([InlineKeyboardButton(text=f"{mark}{name} — {price}₽", callback_data=f"svc_toggle_{key}")])
    rows.append([InlineKeyboardButton(text="✔️ Готово", callback_data="svc_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dates_kb(dates):
    """dates: list of (label, date_iso, is_free: bool)."""
    rows = []
    line = []
    for label, value, is_free in dates:
        emoji = "🟩" if is_free else "🟥"
        cb = f"date_{value}" if is_free else "date_full"
        line.append(InlineKeyboardButton(text=f"{emoji} {label}", callback_data=cb))
        if len(line) == 3:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_book")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def times_kb(all_slots, taken_slots):
    rows = []
    line = []
    for slot in all_slots:
        text = f"✅ {slot}" if slot not in taken_slots else f"🚫 {slot}"
        cb = f"time_{slot}" if slot not in taken_slots else "time_taken"
        line.append(InlineKeyboardButton(text=text, callback_data=cb))
        if len(line) == 4:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_book")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Мои записи", callback_data="profile_bookings")],
        [InlineKeyboardButton(text="🎁 Программа лояльности", callback_data="profile_loyalty")],
        [InlineKeyboardButton(text="🎫 Мои тикеты", callback_data="profile_tickets")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="profile_notifications")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")],
    ])


def notifications_kb(enabled: bool):
    toggle_text = "🔕 Выключить уведомления" if enabled else "🔔 Включить уведомления"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data="notifications_toggle")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")],
    ])


def loyalty_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Применить промокод", callback_data="loyalty_enter_code")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_profile")],
    ])


def support_start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать в поддержку", callback_data="support_write")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")],
    ])


def support_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Вернуться", callback_data="menu_main")],
    ])


def ticket_view_kb(ticket_id, status, is_admin=False, is_appeal=False):
    rows = []
    if status == "open":
        rows.append([InlineKeyboardButton(text="✍️ Ответить", callback_data=f"ticket_reply_{ticket_id}")])
        if is_admin and is_appeal:
            rows.append([
                InlineKeyboardButton(text="✅ Одобрить апелляцию", callback_data=f"appeal_approve_{ticket_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"appeal_decline_{ticket_id}"),
            ])
        if is_admin:
            rows.append([InlineKeyboardButton(text="✅ Закрыть тикет", callback_data=f"ticket_close_{ticket_id}")])
    back_target = "admin_tickets" if is_admin else "profile_tickets"
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Тикеты", callback_data="admin_tickets")],
        [InlineKeyboardButton(text="📅 Записи (удалить)", callback_data="admin_bookings")],
        [InlineKeyboardButton(text="🗂 Управление мастерами", callback_data="admin_manage_masters")],
        [InlineKeyboardButton(text="➕ Добавить мастера", callback_data="admin_add_master")],
        [InlineKeyboardButton(text="🚫 Баны", callback_data="admin_bans")],
        [InlineKeyboardButton(text="🔥 Скидки и промокоды", callback_data="admin_sale")],
        [InlineKeyboardButton(text="📊 Данные пользователей", callback_data="admin_export_users")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")],
    ])


def skip_photo_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Без фото", callback_data="master_photo_skip")]
    ])


def booking_view_kb(booking_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить эту запись", callback_data=f"admin_cancel_booking_{booking_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_bookings")],
    ])


def discount_promo_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить скидку", callback_data="discount_add")],
        [InlineKeyboardButton(text="➕ Добавить промокод", callback_data="promo_add")],
        [InlineKeyboardButton(text="📋 Активные скидки", callback_data="discount_list")],
        [InlineKeyboardButton(text="📋 Промокоды", callback_data="promo_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")],
    ])


def discount_scope_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 На все услуги", callback_data="discount_scope_all")],
        [InlineKeyboardButton(text="💇 На конкретного мастера", callback_data="discount_scope_master")],
        [InlineKeyboardButton(text="✂️ На конкретную услугу", callback_data="discount_scope_service")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_sale")],
    ])


def promo_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆕 Скидка на первый заказ", callback_data="promo_type_first_order")],
        [InlineKeyboardButton(text="💇 Скидка у мастера", callback_data="promo_type_master")],
        [InlineKeyboardButton(text="✂️ Скидка на стрижку", callback_data="promo_type_service")],
        [InlineKeyboardButton(text="🛍 Скидка на всю покупку", callback_data="promo_type_total")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_sale")],
    ])


def masters_pick_kb(masters, prefix, back_target):
    rows = [[InlineKeyboardButton(text=m["name"], callback_data=f"{prefix}_{m['id']}")] for m in masters]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_pick_kb(prefix, back_target):
    rows = []
    for key, (name, price) in CATEGORIES.items():
        rows.append([InlineKeyboardButton(text=f"{name} — {price}₽", callback_data=f"{prefix}_{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def discount_list_kb(discounts):
    rows = [
        [InlineKeyboardButton(text=f"🗑 Деактивировать #{d['id']}", callback_data=f"discount_del_{d['id']}")]
        for d in discounts
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_sale")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promo_list_kb(promos):
    rows = [
        [InlineKeyboardButton(text=f"🗑 Деактивировать {p['code']}", callback_data=f"promo_del_{p['code']}")]
        for p in promos if p["active"]
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_sale")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- BANS ----------

def bans_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи (забанить)", callback_data="admin_users_for_ban")],
        [InlineKeyboardButton(text="🔓 Забаненные (разбанить)", callback_data="admin_banned_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")],
    ])


def user_ban_action_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Забанить", callback_data=f"admin_ban_select_{user_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_users_for_ban")],
    ])


def banned_user_action_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Разбанить", callback_data=f"admin_unban_{user_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_banned_list")],
    ])


# ---------- MASTER MANAGEMENT (vacation calendar, delete) ----------

def manage_masters_kb(masters):
    rows = [[InlineKeyboardButton(text=m["name"], callback_data=f"manage_master_{m['id']}")] for m in masters]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def master_manage_actions_kb(master_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏖 Управление отпуском", callback_data=f"vacation_{master_id}")],
        [InlineKeyboardButton(text="🗑 Удалить мастера", callback_data=f"delete_master_{master_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_manage_masters")],
    ])


def vacation_calendar_kb(master_id, day_statuses):
    """day_statuses: list of (label, date_iso, is_free: bool)."""
    rows = []
    line = []
    for label, date_iso, is_free in day_statuses:
        emoji = "🟩" if is_free else "🟥"
        line.append(InlineKeyboardButton(text=f"{emoji} {label}", callback_data=f"vacday_{master_id}_{date_iso}"))
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_master_{master_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete_master_kb(master_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_master_confirm_{master_id}")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"manage_master_{master_id}")],
    ])
