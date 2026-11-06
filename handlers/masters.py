from aiogram import Router, F
from aiogram.types import CallbackQuery

import database as db
import keyboards as kb
from ui import edit_screen
from config import FAQ_TEXT, TERMS_TEXT, CATEGORIES

router = Router()


def _services_text(master):
    keys = [k for k in (master["services"] or "").split(",") if k]
    if not keys:
        return "оказывает все виды услуг"
    names = [CATEGORIES[k][0] for k in keys if k in CATEGORIES]
    return ", ".join(names)


@router.callback_query(F.data == "menu_masters")
async def show_masters(callback: CallbackQuery):
    masters = db.get_masters()
    if not masters:
        await edit_screen(callback, "Пока нет добавленных мастеров.", reply_markup=kb.back_kb())
        await callback.answer()
        return
    await edit_screen(
        callback, "💇 <b>Наши мастера</b>\n\nВыберите мастера, чтобы посмотреть фото, описание и услуги:",
        reply_markup=kb.masters_pick_kb(masters, "viewmaster", "menu_main"), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("viewmaster_"))
async def view_master(callback: CallbackQuery):
    master_id = int(callback.data.split("_")[-1])
    master = db.get_master(master_id)
    if not master:
        await callback.answer("Мастер не найден", show_alert=True)
        return
    caption = f"<b>{master['name']}</b>\n{master['description']}\n\nУслуги: {_services_text(master)}"
    await edit_screen(
        callback, caption, reply_markup=kb.back_kb("menu_masters"), parse_mode="HTML",
        photo=master["photo_file_id"],
    )
    await callback.answer()


@router.callback_query(F.data == "menu_faq")
async def show_faq(callback: CallbackQuery):
    text = FAQ_TEXT + "\n\n" + TERMS_TEXT
    await edit_screen(callback, text, reply_markup=kb.back_kb(), parse_mode="HTML")
    await callback.answer()
