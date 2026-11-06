import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db

logger = logging.getLogger(__name__)


def setup_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "interval", minutes=1, args=[bot])
    scheduler.start()
    return scheduler


async def check_reminders(bot):
    now = datetime.now()

    # 3-hour reminders: bookings between now+2h55m and now+3h05m (checked every minute)
    await _send_batch(bot, "reminder_3h_sent", now + timedelta(hours=2, minutes=55), now + timedelta(hours=3, minutes=5),
                       "⏰ Напоминаем: через 3 часа у вас запись")

    # 1-hour reminders
    await _send_batch(bot, "reminder_1h_sent", now + timedelta(minutes=55), now + timedelta(hours=1, minutes=5),
                       "⏰ Напоминаем: через 1 час у вас запись")


async def _send_batch(bot, field, window_start, window_end, prefix):
    bookings = db.bookings_needing_reminder(field, window_start, window_end)
    for b in bookings:
        text = (
            f"{prefix}!\n\n"
            f"Мастер: {b['master_name']}\n"
            f"Услуга: {b['category_name']}\n"
            f"Дата: {b['date']} в {b['time']}"
        )
        try:
            await bot.send_message(b["tg_id"], text)
        except Exception as e:
            logger.warning(f"Failed to send reminder for booking {b['id']}: {e}")
        db.mark_reminder_sent(b["id"], field)
