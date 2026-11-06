from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

import database as db
import keyboards as kb
from states import Registration
from config import TERMS_TEXT
from ui import edit_screen

router = Router()


async def show_main_menu(message: Message):
    text = "🏠 <b>Главное меню</b>\n\nВыберите, что вас интересует:"
    await message.answer(text, reply_markup=kb.main_menu_kb(message.chat.id), parse_mode="HTML")


@router.message(CommandStart())
async def cmd_start(message: Message, state=None):
    if state:
        await state.clear()
    user = db.get_user(message.from_user.id)
    if user:
        await show_main_menu(message)
    else:
        await message.answer(
            "👋 Добро пожаловать в бот парикмахерской!\n\n"
            "Для начала работы необходимо зарегистрироваться.",
            reply_markup=kb.register_kb()
        )


@router.callback_query(F.data == "register_start")
async def register_start(callback: CallbackQuery, state):
    await state.set_state(Registration.waiting_name)
    await edit_screen(callback, "Введите ваше имя:")
    await callback.answer()


@router.message(Registration.waiting_name)
async def register_name(message: Message, state):
    name = (message.text or "").strip()
    if not name or len(name) > 100:
        await message.answer("Пожалуйста, введите корректное имя:")
        return
    await state.update_data(name=name)
    await state.set_state(Registration.waiting_terms)
    await message.answer(
        TERMS_TEXT + "\n\n<b>Для использования бота необходимо принять условия пользовательского соглашения.</b>",
        reply_markup=kb.terms_agreement_kb(), parse_mode="HTML"
    )


@router.callback_query(Registration.waiting_terms, F.data == "terms_agree")
async def terms_agree(callback: CallbackQuery, state):
    data = await state.get_data()
    name = data.get("name", callback.from_user.full_name)
    db.create_user(callback.from_user.id, name)
    await state.clear()
    await callback.answer()
    await edit_screen(
        callback,
        "🏠 <b>Главное меню</b>\n\nВыберите, что вас интересует:",
        reply_markup=kb.main_menu_kb(callback.message.chat.id),
        parse_mode="HTML",
    )


@router.callback_query(Registration.waiting_terms, F.data == "terms_decline")
async def terms_decline(callback: CallbackQuery):
    await edit_screen(callback,
        "Чтобы пользоваться ботом, необходимо принять условия пользовательского соглашения.\n"
        "Если передумаете — нажмите «Я согласен(на)» ниже.",
        reply_markup=kb.terms_agreement_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "menu_main")
async def back_to_main(callback: CallbackQuery, state):
    await state.clear()
    await callback.answer()
    await edit_screen(
        callback,
        "🏠 <b>Главное меню</b>\n\nВыберите, что вас интересует:",
        reply_markup=kb.main_menu_kb(callback.message.chat.id),
        parse_mode="HTML",
    )
