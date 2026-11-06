import random
import string
import sqlite3
from datetime import datetime, date as date_cls
from contextlib import contextmanager

from config import DB_PATH, WORK_START_HOUR, WORK_END_HOUR, SLOT_MINUTES


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                name TEXT,
                discount INTEGER DEFAULT 0,
                notifications_enabled INTEGER DEFAULT 1,
                banned INTEGER DEFAULT 0,
                ban_reason TEXT DEFAULT '',
                appeal_status TEXT DEFAULT '',
                appeal_ticket_id INTEGER,
                registered_at TEXT
            );

            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                photo_file_id TEXT,
                services TEXT DEFAULT '',
                active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS master_days_off (
                master_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                reason TEXT DEFAULT '',
                PRIMARY KEY (master_id, date),
                FOREIGN KEY(master_id) REFERENCES masters(id)
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                master_id INTEGER NOT NULL,
                category_key TEXT NOT NULL,
                category_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                original_price INTEGER,
                discount_percent INTEGER DEFAULT 0,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                reminder_3h_sent INTEGER DEFAULT 0,
                reminder_1h_sent INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(master_id) REFERENCES masters(id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS discounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,          -- 'all' | 'master' | 'service'
                master_id INTEGER,
                category_key TEXT,
                percent INTEGER NOT NULL,
                expires_at TEXT,              -- ISO date, NULL = бессрочно
                active INTEGER DEFAULT 1,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                discount INTEGER NOT NULL,
                type TEXT DEFAULT 'total',    -- 'first_order' | 'master' | 'service' | 'total'
                name TEXT DEFAULT '',
                master_id INTEGER,
                category_key TEXT,
                max_activations INTEGER,
                activations_used INTEGER DEFAULT 0,
                expires_at TEXT,              -- ISO date, NULL = бессрочно
                auto_apply INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS user_promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                applied_at TEXT,
                used INTEGER DEFAULT 0,
                used_at TEXT,
                booking_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                is_appeal INTEGER DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender TEXT NOT NULL, -- 'user' or 'admin'
                text TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY(ticket_id) REFERENCES tickets(id)
            );
            """
        )
        # Backward-compatible migrations for DBs created before these columns existed
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(masters)").fetchall()]
        if "services" not in cols:
            conn.execute("ALTER TABLE masters ADD COLUMN services TEXT DEFAULT ''")
        if "active" not in cols:
            conn.execute("ALTER TABLE masters ADD COLUMN active INTEGER DEFAULT 1")

        ucols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "notifications_enabled" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN notifications_enabled INTEGER DEFAULT 1")
        if "banned" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0")
        if "ban_reason" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN ban_reason TEXT DEFAULT ''")
        if "appeal_status" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN appeal_status TEXT DEFAULT ''")
        if "appeal_ticket_id" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN appeal_ticket_id INTEGER")

        bcols = [r["name"] for r in conn.execute("PRAGMA table_info(bookings)").fetchall()]
        if "original_price" not in bcols:
            conn.execute("ALTER TABLE bookings ADD COLUMN original_price INTEGER")
        if "discount_percent" not in bcols:
            conn.execute("ALTER TABLE bookings ADD COLUMN discount_percent INTEGER DEFAULT 0")

        tcols = [r["name"] for r in conn.execute("PRAGMA table_info(tickets)").fetchall()]
        if "is_appeal" not in tcols:
            conn.execute("ALTER TABLE tickets ADD COLUMN is_appeal INTEGER DEFAULT 0")

        pcols = [r["name"] for r in conn.execute("PRAGMA table_info(promocodes)").fetchall()]
        if "type" not in pcols:
            conn.execute("ALTER TABLE promocodes ADD COLUMN type TEXT DEFAULT 'total'")
        if "name" not in pcols:
            conn.execute("ALTER TABLE promocodes ADD COLUMN name TEXT DEFAULT ''")
        if "master_id" not in pcols:
            conn.execute("ALTER TABLE promocodes ADD COLUMN master_id INTEGER")
        if "category_key" not in pcols:
            conn.execute("ALTER TABLE promocodes ADD COLUMN category_key TEXT")
        if "max_activations" not in pcols:
            conn.execute("ALTER TABLE promocodes ADD COLUMN max_activations INTEGER")
        if "activations_used" not in pcols:
            conn.execute("ALTER TABLE promocodes ADD COLUMN activations_used INTEGER DEFAULT 0")
        if "expires_at" not in pcols:
            conn.execute("ALTER TABLE promocodes ADD COLUMN expires_at TEXT")
        if "auto_apply" not in pcols:
            conn.execute("ALTER TABLE promocodes ADD COLUMN auto_apply INTEGER DEFAULT 0")
        if "created_at" not in pcols:
            conn.execute("ALTER TABLE promocodes ADD COLUMN created_at TEXT")

        upcols = [r["name"] for r in conn.execute("PRAGMA table_info(user_promocodes)").fetchall()]
        if "used" not in upcols:
            conn.execute("ALTER TABLE user_promocodes ADD COLUMN used INTEGER DEFAULT 0")
        if "used_at" not in upcols:
            conn.execute("ALTER TABLE user_promocodes ADD COLUMN used_at TEXT")
        if "booking_id" not in upcols:
            conn.execute("ALTER TABLE user_promocodes ADD COLUMN booking_id INTEGER")

        # Seed a couple of example masters if table is empty
        row = conn.execute("SELECT COUNT(*) c FROM masters").fetchone()
        if row["c"] == 0:
            conn.executemany(
                "INSERT INTO masters (name, description, services) VALUES (?, ?, ?)",
                [
                    ("Алексей", "Топ-мастер, стаж 8 лет. Чёткие мужские стрижки и оформление бороды.",
                     "haircut_male"),
                    ("Марина", "Специалист по детским стрижкам, умеет найти подход даже к самым непоседливым клиентам.",
                     "haircut_child,haircut_both"),
                ],
            )


# ---------- USERS ----------

def get_user(telegram_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()


def create_user(telegram_id: int, name: str):
    """Creates a user. The internal loyalty ID is simply the auto-incrementing
    primary key `id` — invisible to the user in the bot UI, but shown to the
    admin in ticket views and the exported spreadsheet."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (telegram_id, name, registered_at) VALUES (?, ?, ?)",
            (telegram_id, name, datetime.now().isoformat(timespec="seconds")),
        )


def get_user_by_id(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def all_users():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users ORDER BY id").fetchall()


# ---------- MASTERS ----------

def get_masters():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM masters WHERE active=1 ORDER BY id").fetchall()


def get_master(master_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM masters WHERE id = ?", (master_id,)).fetchone()


def add_master(name: str, description: str = "", photo_file_id: str = None, services: str = ""):
    """services: comma-separated CATEGORIES keys the master provides, e.g. 'haircut_male,haircut_both'"""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO masters (name, description, photo_file_id, services) VALUES (?, ?, ?, ?)",
            (name, description, photo_file_id, services),
        )


def count_active_bookings_for_master(master_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM bookings WHERE master_id=? AND status='active'", (master_id,)
        ).fetchone()
        return row["c"]


def delete_master(master_id: int) -> bool:
    """'Deletes' a master (hides them everywhere), unless they still have active
    bookings (safety check — cancel/complete those first). Bookings history is kept
    intact (soft-delete, not a hard DELETE) so past records and exports stay correct.
    Returns True if hidden, False if blocked by active bookings."""
    if count_active_bookings_for_master(master_id) > 0:
        return False
    with get_conn() as conn:
        conn.execute("UPDATE masters SET active=0 WHERE id=?", (master_id,))
    return True


# ---------- MASTER DAYS OFF (vacation) ----------

def add_master_day_off(master_id: int, date: str, reason: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO master_days_off (master_id, date, reason) VALUES (?, ?, ?)",
            (master_id, date, reason),
        )


def remove_master_day_off(master_id: int, date: str):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM master_days_off WHERE master_id=? AND date=?", (master_id, date)
        )


def is_master_day_off(master_id: int, date: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM master_days_off WHERE master_id=? AND date=?", (master_id, date)
        ).fetchone()
        return row is not None


def get_master_days_off(master_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM master_days_off WHERE master_id=? ORDER BY date", (master_id,)
        ).fetchall()


def _build_work_slots():
    slots = []
    h = WORK_START_HOUR
    while h < WORK_END_HOUR:
        slots.append(f"{h:02d}:00")
        h += SLOT_MINUTES // 60
    return slots


def master_day_has_free_slot(master_id: int, date: str) -> bool:
    """True if this master has at least one bookable slot left on this date
    (False if the master is off that day, or every slot is already taken,
    or — for today — every remaining slot has already passed)."""
    if is_master_day_off(master_id, date):
        return False
    slots = _build_work_slots()
    today = date_cls.today().isoformat()
    if date == today:
        now_time = datetime.now().time()
        slots = [s for s in slots if datetime.strptime(s, "%H:%M").time() > now_time]
    if not slots:
        return False
    taken = get_taken_slots(master_id, date)
    return any(s not in taken for s in slots)


# ---------- BOOKINGS ----------

def get_taken_slots(master_id: int, date: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT time FROM bookings WHERE master_id=? AND date=? AND status='active'",
            (master_id, date),
        ).fetchall()
        return {r["time"] for r in rows}


def create_booking(user_id, master_id, category_key, category_name, price, date, time,
                    original_price=None, discount_percent=0):
    if original_price is None:
        original_price = price
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO bookings
               (user_id, master_id, category_key, category_name, price, original_price,
                discount_percent, date, time, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, master_id, category_key, category_name, price, original_price,
             discount_percent, date, time, datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def get_user_bookings(user_id: int, only_active=True):
    with get_conn() as conn:
        q = "SELECT b.*, m.name as master_name FROM bookings b JOIN masters m ON b.master_id=m.id WHERE b.user_id=?"
        if only_active:
            q += " AND b.status='active'"
        q += " ORDER BY b.date, b.time"
        return conn.execute(q, (user_id,)).fetchall()


def get_booking(booking_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT b.*, m.name as master_name, u.name as user_name, u.telegram_id as tg_id "
            "FROM bookings b JOIN masters m ON b.master_id=m.id JOIN users u ON b.user_id=u.id "
            "WHERE b.id=?",
            (booking_id,),
        ).fetchone()


def cancel_booking(booking_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))


def count_active_bookings(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM bookings WHERE user_id=? AND status='active'", (user_id,)
        ).fetchone()
        return row["c"]


def find_active_booking_at(user_id: int, date: str, time: str):
    """Checks if the user already has an active booking at this exact date/time (any master)."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM bookings WHERE user_id=? AND date=? AND time=? AND status='active'",
            (user_id, date, time),
        ).fetchone()


def get_upcoming_active_bookings(limit=40):
    """For the admin panel: upcoming active bookings, soonest first."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT b.*, m.name as master_name, u.name as user_name, u.telegram_id as tg_id
               FROM bookings b
               JOIN masters m ON b.master_id = m.id
               JOIN users u ON b.user_id = u.id
               WHERE b.status='active'
               ORDER BY b.date, b.time
               LIMIT ?""",
            (limit,),
        ).fetchall()


def bookings_needing_reminder(field: str, window_start, window_end):
    """field: 'reminder_3h_sent' or 'reminder_1h_sent'. Returns active bookings whose
    datetime falls within [window_start, window_end) and that reminder not sent yet.
    Skips users who turned notifications off."""
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT b.*, m.name as master_name, u.telegram_id as tg_id
                FROM bookings b
                JOIN masters m ON b.master_id = m.id
                JOIN users u ON b.user_id = u.id
                WHERE b.status='active' AND b.{field}=0 AND u.notifications_enabled=1""",
        ).fetchall()
        result = []
        for r in rows:
            dt = datetime.strptime(f"{r['date']} {r['time']}", "%Y-%m-%d %H:%M")
            if window_start <= dt < window_end:
                result.append(r)
        return result


def mark_reminder_sent(booking_id: int, field: str):
    with get_conn() as conn:
        conn.execute(f"UPDATE bookings SET {field}=1 WHERE id=?", (booking_id,))


# ---------- LOYALTY / DISCOUNTS / PROMOCODES ----------

PROMO_TYPE_LABELS = {
    "first_order": "Скидка на первый заказ",
    "master": "Скидка у мастера",
    "service": "Скидка на стрижку",
    "total": "Скидка на всю покупку",
}


def generate_promo_code(length: int = 15) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=length))


def add_discount(scope: str, percent: int, expires_at: str = None, master_id: int = None, category_key: str = None):
    """scope: 'all' | 'master' | 'service'. expires_at: ISO date or None (бессрочно)."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO discounts (scope, master_id, category_key, percent, expires_at, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (scope, master_id, category_key, percent, expires_at, datetime.now().isoformat(timespec="seconds")),
        )


def get_active_discounts():
    today = date_cls.today().isoformat()
    with get_conn() as conn:
        return conn.execute(
            "SELECT d.*, m.name as master_name FROM discounts d LEFT JOIN masters m ON d.master_id = m.id "
            "WHERE d.active=1 AND (d.expires_at IS NULL OR d.expires_at='' OR d.expires_at >= ?) "
            "ORDER BY d.id DESC",
            (today,),
        ).fetchall()


def get_all_discounts():
    with get_conn() as conn:
        return conn.execute(
            "SELECT d.*, m.name as master_name FROM discounts d LEFT JOIN masters m ON d.master_id = m.id "
            "ORDER BY d.active DESC, d.id DESC"
        ).fetchall()


def get_discount(discount_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM discounts WHERE id=?", (discount_id,)).fetchone()


def deactivate_discount(discount_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE discounts SET active=0 WHERE id=?", (discount_id,))


def best_scoped_discount_percent(master_id: int = None, category_key: str = None) -> int:
    """Highest active admin-set discount percent applicable to this master/category
    (or overall, if master_id/category_key are None)."""
    best = 0
    for d in get_active_discounts():
        if d["scope"] == "all":
            best = max(best, d["percent"])
        elif d["scope"] == "master" and master_id is not None and d["master_id"] == master_id:
            best = max(best, d["percent"])
        elif d["scope"] == "service" and category_key is not None and d["category_key"] == category_key:
            best = max(best, d["percent"])
    return best


def create_promocode(code: str, ptype: str, percent: int, name: str = "", master_id: int = None,
                      category_key: str = None, max_activations: int = None, expires_at: str = None,
                      auto_apply: bool = False):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO promocodes
               (code, discount, type, name, master_id, category_key, max_activations,
                activations_used, expires_at, auto_apply, active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 1, ?)""",
            (code, percent, ptype, name, master_id, category_key, max_activations,
             expires_at, 1 if auto_apply else 0, datetime.now().isoformat(timespec="seconds")),
        )


def get_promocode(code: str):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM promocodes WHERE code=?", (code,)).fetchone()


def get_all_promocodes():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM promocodes ORDER BY active DESC, rowid DESC").fetchall()


def deactivate_promocode(code: str):
    with get_conn() as conn:
        conn.execute("UPDATE promocodes SET active=0 WHERE code=?", (code,))


def promocode_is_valid(promo) -> bool:
    if not promo or not promo["active"]:
        return False
    if promo["max_activations"] is not None and promo["activations_used"] >= promo["max_activations"]:
        return False
    if promo["expires_at"] and promo["expires_at"] < date_cls.today().isoformat():
        return False
    return True


def user_used_promocode(user_id: int, code: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM user_promocodes WHERE user_id=? AND code=?", (user_id, code)
        ).fetchone()


def redeem_promocode_for_user(user_id: int, code: str) -> str:
    """Manual code entry by a client. Returns 'ok' | 'not_found' | 'expired' | 'already'."""
    promo = get_promocode(code)
    if not promo:
        return "not_found"
    if user_used_promocode(user_id, code):
        return "already"
    if not promocode_is_valid(promo):
        return "expired"
    _claim_promocode_for_user(user_id, code)
    return "ok"


def _claim_promocode_for_user(user_id: int, code: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_promocodes (user_id, code, applied_at, used) VALUES (?, ?, ?, 0)",
            (user_id, code, datetime.now().isoformat(timespec="seconds")),
        )
        conn.execute("UPDATE promocodes SET activations_used = activations_used + 1 WHERE code=?", (code,))


def create_cancellation_promo(user_id: int) -> str:
    """Auto-issues a one-time 10% "next order" voucher to a client whose booking
    the admin cancelled. Immediately claimed for that user (no manual entry needed)."""
    code = generate_promo_code()
    create_promocode(
        code, ptype="total", percent=10, name="Компенсация за отменённую запись",
        max_activations=1, expires_at=None, auto_apply=True,
    )
    _claim_promocode_for_user(user_id, code)
    return code


def get_user_available_promocodes(user_id: int):
    """Unused, still-valid promocodes claimed by this user (manually entered or auto-issued)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT up.id as redemption_id, p.* FROM user_promocodes up
               JOIN promocodes p ON up.code = p.code
               WHERE up.user_id=? AND up.used=0 AND p.active=1
               ORDER BY up.id DESC""",
            (user_id,),
        ).fetchall()
    today = date_cls.today().isoformat()
    result = []
    for r in rows:
        if r["expires_at"] and r["expires_at"] < today:
            continue
        result.append(r)
    return result


def mark_user_promocode_used(redemption_id: int, booking_id: int = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE user_promocodes SET used=1, used_at=?, booking_id=? WHERE id=?",
            (datetime.now().isoformat(timespec="seconds"), booking_id, redemption_id),
        )


def user_has_any_bookings(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) c FROM bookings WHERE user_id=?", (user_id,)).fetchone()
        return row["c"] > 0


def best_available_discount(user_id: int, master_id: int = None, category_key: str = None):
    """Best discount currently applicable to a booking with this master/category —
    considers admin-set scoped discounts and the user's own unused promocodes
    (they don't stack, the higher one wins). Returns a dict with percent/source/redemption_id."""
    best = {"percent": best_scoped_discount_percent(master_id, category_key), "source": "admin_discount", "redemption_id": None}
    is_first_order = not user_has_any_bookings(user_id)
    for promo in get_user_available_promocodes(user_id):
        applicable = (
            promo["type"] == "total"
            or (promo["type"] == "first_order" and is_first_order)
            or (promo["type"] == "master" and master_id is not None and promo["master_id"] == master_id)
            or (promo["type"] == "service" and category_key is not None and promo["category_key"] == category_key)
        )
        if applicable and promo["discount"] > best["percent"]:
            best = {"percent": promo["discount"], "source": "promo", "redemption_id": promo["redemption_id"]}
    return best


# ---------- TICKETS ----------

def create_ticket(user_id: int, reason: str, is_appeal: bool = False):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tickets (user_id, reason, is_appeal, created_at) VALUES (?, ?, ?, ?)",
            (user_id, reason, 1 if is_appeal else 0, datetime.now().isoformat(timespec="seconds")),
        )
        ticket_id = cur.lastrowid
        conn.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, created_at) VALUES (?, 'user', ?, ?)",
            (ticket_id, reason, datetime.now().isoformat(timespec="seconds")),
        )
        return ticket_id


def get_user_tickets(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM tickets WHERE user_id=? ORDER BY id DESC", (user_id,)
        ).fetchall()


def get_open_tickets():
    with get_conn() as conn:
        return conn.execute(
            "SELECT t.*, u.name as user_name, u.telegram_id as tg_id FROM tickets t "
            "JOIN users u ON t.user_id=u.id WHERE t.status='open' ORDER BY t.id DESC"
        ).fetchall()


def get_ticket(ticket_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT t.*, u.name as user_name, u.telegram_id as tg_id, u.id as uid FROM tickets t "
            "JOIN users u ON t.user_id=u.id WHERE t.id=?", (ticket_id,)
        ).fetchone()


def get_ticket_messages(ticket_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY id", (ticket_id,)
        ).fetchall()


def add_ticket_message(ticket_id: int, sender: str, text: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
            (ticket_id, sender, text, datetime.now().isoformat(timespec="seconds")),
        )


def close_ticket(ticket_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE tickets SET status='closed' WHERE id=?", (ticket_id,))


# ---------- NOTIFICATIONS TOGGLE ----------

def set_notifications(user_id: int, enabled: bool):
    with get_conn() as conn:
        conn.execute("UPDATE users SET notifications_enabled=? WHERE id=?", (1 if enabled else 0, user_id))


def users_with_notifications_enabled():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE notifications_enabled=1"
        ).fetchall()


# ---------- SETTINGS (site-wide sale discount, etc.) ----------

def get_setting(key: str, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )


# ---------- BANS / APPEALS ----------

def ban_user(user_id: int, reason: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET banned=1, ban_reason=?, appeal_status='', appeal_ticket_id=NULL WHERE id=?",
            (reason, user_id),
        )


def unban_user(user_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET banned=0, ban_reason='', appeal_status='', appeal_ticket_id=NULL WHERE id=?",
            (user_id,),
        )


def get_banned_users():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE banned=1 ORDER BY id").fetchall()


def set_appeal_pending(user_id: int, ticket_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET appeal_status='pending', appeal_ticket_id=? WHERE id=?",
            (ticket_id, user_id),
        )


def approve_appeal(user_id: int):
    unban_user(user_id)


def decline_appeal(user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET appeal_status='declined' WHERE id=?", (user_id,))
