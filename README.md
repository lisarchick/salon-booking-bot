# Salon Booking Bot (Telegram)

A production Telegram bot for salons, barbershops and studios: online booking with a live availability calendar, a loyalty program, support tickets and a full admin panel. Built with **aiogram 3** and SQLite, ~3,200 lines of clean, maintained Python.

*(Документация на русском: [README.ru.md](README.ru.md))*

## Features

**Booking**
- Master → service → date → time slot flow
- Availability calendar (🟩 free / 🟩 busy) so clients instantly see open windows
- Per-client limit on active bookings; no double-booking the same slot
- Masters' days off / vacations with active-booking protection

**Loyalty & engagement**
- Loyalty program bound to internal user IDs
- Promocodes and discounts (first-visit, per-master, per-service)
- Push reminders 3h and 1h before the appointment (per-user notification toggle)

**Support & moderation**
- Ticket system with admin correspondence inside the bot
- Ban system with reasons and a built-in appeal flow (approve/decline right in the ticket)

**Admin panel** (visible to configured admin IDs only)
- Tickets and appeals inbox
- Cancel bookings; manage masters (photo, description, services, vacations)
- Promocodes and discounts management
- Excel export of users and bookings (openpyxl)

## Tech stack

Python 3.10+ · aiogram 3 · SQLite · APScheduler · openpyxl

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # put your BOT_TOKEN and ADMIN_IDS in
python main.py
```

Put a `photo.jpg` next to `main.py` for the main menu image. Services, working hours, slot length and booking horizon are configured in `config.py`. The bot is meant to run 24/7 (systemd / Docker / pm2).

## Structure

```
main.py            entry point
config.py          services, prices, texts (secrets live in .env)
database.py        all SQLite access
middleware.py      registration + ban gate for every update
scheduler.py       3h/1h push reminders
handlers/          registration, booking, profile, support, masters, banning, admin
```
