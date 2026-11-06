from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_name = State()
    waiting_terms = State()


class Booking(StatesGroup):
    choosing_master = State()
    choosing_category = State()
    choosing_date = State()
    choosing_time = State()


class Support(StatesGroup):
    waiting_reason = State()


class TicketChat(StatesGroup):
    waiting_message = State()  # user typing a reply inside an open ticket


class Loyalty(StatesGroup):
    waiting_promocode = State()


class AdminTicketChat(StatesGroup):
    waiting_reply = State()


class AdminAddMaster(StatesGroup):
    waiting_name = State()
    waiting_description = State()
    waiting_photo = State()
    waiting_services = State()


class AdminDiscount(StatesGroup):
    choosing_scope = State()
    choosing_master = State()
    choosing_service = State()
    waiting_percent = State()
    waiting_expiry = State()


class AdminPromo(StatesGroup):
    choosing_type = State()
    choosing_master = State()
    choosing_service = State()
    waiting_name = State()
    waiting_percent = State()
    waiting_activations = State()
    waiting_expiry = State()
    waiting_confirm = State()


class AdminBan(StatesGroup):
    waiting_reason = State()
