import sqlite3

# Use check_same_thread=False because discord.py may call DB from different threads
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS permissions (
    guild_id INTEGER PRIMARY KEY,
    admin_role TEXT,
    mod_role TEXT
)
""")
conn.commit()

# Table for storing user XP per guild
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_xp (
    guild_id INTEGER,
    user_id INTEGER,
    xp INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")
conn.commit()

# Table for shop items per guild
cursor.execute("""
CREATE TABLE IF NOT EXISTS shop_items (
    guild_id INTEGER,
    item_name TEXT,
    price INTEGER,
    description TEXT,
    PRIMARY KEY (guild_id, item_name)
)
""")
conn.commit()

# Ensure shop_items has atk and def columns (migrations)
try:
    cursor.execute("ALTER TABLE shop_items ADD COLUMN atk INTEGER DEFAULT 0")
    cursor.execute("ALTER TABLE shop_items ADD COLUMN def INTEGER DEFAULT 0")
    conn.commit()
except Exception:
    # ignore if columns already exist
    pass

# Table for user profiles (HP, ATK, DEF, gold)
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_profile (
    guild_id INTEGER,
    user_id INTEGER,
    max_hp INTEGER DEFAULT 100,
    hp INTEGER DEFAULT 100,
    atk INTEGER DEFAULT 10,
    def INTEGER DEFAULT 5,
    gold INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")
conn.commit()
try:
    cursor.execute("ALTER TABLE user_profile ADD COLUMN selected_badge TEXT DEFAULT NULL")
    cursor.execute("ALTER TABLE user_profile ADD COLUMN onboarded INTEGER DEFAULT 0")
    conn.commit()
except Exception:
    pass
try:
    cursor.execute("ALTER TABLE user_profile ADD COLUMN wins INTEGER DEFAULT 0")
    conn.commit()
except Exception:
    pass

# Table for user inventory (item_name, qty, equipped, slot)
cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    guild_id INTEGER,
    user_id INTEGER,
    item_name TEXT,
    qty INTEGER DEFAULT 1,
    PRIMARY KEY (guild_id, user_id, item_name)
)
""")
conn.commit()

# Add equipped/slot columns if missing
try:
    cursor.execute("ALTER TABLE inventory ADD COLUMN equipped INTEGER DEFAULT 0")
    cursor.execute("ALTER TABLE inventory ADD COLUMN slot TEXT DEFAULT 'none'")
    conn.commit()
except Exception:
    pass

# Table for cooldowns (per command per user)
cursor.execute("""
CREATE TABLE IF NOT EXISTS cooldowns (
    guild_id INTEGER,
    user_id INTEGER,
    command TEXT,
    last_used INTEGER,
    PRIMARY KEY (guild_id, user_id, command)
)
""")
conn.commit()

# Table for daily quests per user (one quest per day)
cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_quests (
    guild_id INTEGER,
    user_id INTEGER,
    date TEXT,
    quest_key TEXT,
    progress INTEGER DEFAULT 0,
    target INTEGER DEFAULT 1,
    completed INTEGER DEFAULT 0,
    reward_gold INTEGER DEFAULT 0,
    reward_xp INTEGER DEFAULT 0,
    reward_item TEXT,
    created_ts INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, date)
)
""")
conn.commit()
try:
    cursor.execute("ALTER TABLE daily_quests ADD COLUMN created_ts INTEGER DEFAULT 0")
    conn.commit()
except Exception:
    pass

# Table for per-guild prefix and other per-guild config
cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id INTEGER PRIMARY KEY,
    prefix TEXT DEFAULT '!'
)
""")
conn.commit()

# Ensure shop_items has atk/def/slot columns (migrations)
def ensure_table_columns(table: str, required: dict):
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [r[1] for r in cursor.fetchall()]
    for col, col_def in required.items():
        if col not in existing:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            except Exception:
                # ignore failures (race conditions or locked DB); best-effort
                pass
    conn.commit()


# Ensure necessary columns exist on startup (safe, idempotent)
ensure_table_columns('shop_items', {
    'atk': 'INTEGER DEFAULT 0',
    'def': 'INTEGER DEFAULT 0',
    "slot": "TEXT DEFAULT 'none'",
})
ensure_table_columns('inventory', {
    'equipped': 'INTEGER DEFAULT 0',
    "slot": "TEXT DEFAULT 'none'",
})
ensure_table_columns('user_profile', {
    'onboarded': 'INTEGER DEFAULT 0',
})


import time


def get_roles_db(guild_id):
    cursor.execute(
        "SELECT admin_role, mod_role FROM permissions WHERE guild_id=?",
        (guild_id,)
    )
    return cursor.fetchone()


def set_roles_db(guild_id, admin, mod):
    cursor.execute("""
    INSERT INTO permissions VALUES (?, ?, ?)
    ON CONFLICT(guild_id)
    DO UPDATE SET admin_role=?, mod_role=?
    """, (guild_id, admin, mod, admin, mod))
    conn.commit()


def get_prefix_db(guild_id):
    cursor.execute("SELECT prefix FROM guild_config WHERE guild_id=?", (guild_id,))
    row = cursor.fetchone()
    return row[0] if row else '!'


def set_prefix_db(guild_id, prefix):
    cursor.execute(
        "INSERT INTO guild_config(guild_id, prefix) VALUES (?, ?)"
        " ON CONFLICT(guild_id) DO UPDATE SET prefix=?",
        (guild_id, prefix, prefix)
    )
    conn.commit()


def get_user_xp(guild_id, user_id):
    cursor.execute("SELECT xp FROM user_xp WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    row = cursor.fetchone()
    return row[0] if row else 0


def set_user_xp(guild_id, user_id, xp):
    cursor.execute(
        "INSERT INTO user_xp(guild_id, user_id, xp) VALUES (?, ?, ?)"
        " ON CONFLICT(guild_id, user_id) DO UPDATE SET xp=?",
        (guild_id, user_id, xp, xp)
    )
    conn.commit()


def add_user_xp(guild_id, user_id, delta):
    cur = get_user_xp(guild_id, user_id) + delta
    set_user_xp(guild_id, user_id, cur)
    return cur


def get_leaderboard(guild_id, limit=10):
    cursor.execute(
        "SELECT user_id, xp FROM user_xp WHERE guild_id=? ORDER BY xp DESC LIMIT ?",
        (guild_id, limit)
    )
    return cursor.fetchall()


def add_shop_item(guild_id, item_name, price, description='', atk=0, defn=0, slot='none'):
    try:
        cursor.execute(
            "INSERT INTO shop_items(guild_id, item_name, price, description, atk, def, slot) VALUES (?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(guild_id, item_name) DO UPDATE SET price=?, description=?, atk=?, def=?, slot=?",
            (guild_id, item_name, price, description, atk, defn, slot, price, description, atk, defn, slot)
        )
        conn.commit()
    except Exception as e:
        # Fallback for older DB schema without atk/def/slot columns
        try:
            cursor.execute(
                "INSERT INTO shop_items(guild_id, item_name, price, description) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(guild_id, item_name) DO UPDATE SET price=?, description=?",
                (guild_id, item_name, price, description, price, description)
            )
            conn.commit()
        except Exception:
            # Re-raise original exception for visibility if fallback fails
            raise e


def remove_shop_item(guild_id, item_name):
    cursor.execute("DELETE FROM shop_items WHERE guild_id=? AND item_name=?", (guild_id, item_name))
    conn.commit()


def list_shop_items(guild_id):
    cursor.execute("SELECT item_name, price, description FROM shop_items WHERE guild_id=?", (guild_id,))
    return cursor.fetchall()


def get_shop_item(guild_id, item_name):
    cursor.execute("SELECT item_name, price, description, atk, def, slot FROM shop_items WHERE guild_id=? AND item_name=?", (guild_id, item_name))
    return cursor.fetchone()


def get_profile(guild_id, user_id):
    cursor.execute("SELECT max_hp, hp, atk, def, gold FROM user_profile WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    row = cursor.fetchone()
    if row:
        return {
            'max_hp': row[0],
            'hp': row[1],
            'atk': row[2],
            'def': row[3],
            'gold': row[4],
        }
    # create default profile
    cursor.execute("INSERT INTO user_profile(guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
    conn.commit()
    return get_profile(guild_id, user_id)


def update_profile(guild_id, user_id, **kwargs):
    # Allowed keys: max_hp, hp, atk, def, gold
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in ('max_hp', 'hp', 'atk', 'def', 'gold'):
            fields.append(f"{k}=?")
            values.append(v)
    if not fields:
        return False
    values.extend([guild_id, user_id])
    sql = f"UPDATE user_profile SET {', '.join(fields)} WHERE guild_id=? AND user_id=?"
    cursor.execute(sql, tuple(values))
    conn.commit()
    return True


def add_gold(guild_id, user_id, amount):
    prof = get_profile(guild_id, user_id)
    new = prof['gold'] + amount
    update_profile(guild_id, user_id, gold=new)
    return new


def spend_gold(guild_id, user_id, amount):
    prof = get_profile(guild_id, user_id)
    if prof['gold'] < amount:
        return False
    update_profile(guild_id, user_id, gold=prof['gold'] - amount)
    return True


def add_item(guild_id, user_id, item_name, qty=1):
    # determine item slot from shop (if exists)
    cursor.execute("SELECT slot FROM shop_items WHERE guild_id=? AND item_name=?", (guild_id, item_name))
    row = cursor.fetchone()
    slot = row[0] if row else 'none'

    cursor.execute("SELECT qty FROM inventory WHERE guild_id=? AND user_id=? AND item_name=?", (guild_id, user_id, item_name))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE inventory SET qty=qty+?, slot=? WHERE guild_id=? AND user_id=? AND item_name=?", (qty, slot, guild_id, user_id, item_name))
    else:
        cursor.execute("INSERT INTO inventory(guild_id, user_id, item_name, qty, equipped, slot) VALUES (?, ?, ?, ?, 0, ?)", (guild_id, user_id, item_name, qty, slot))
    conn.commit()


def get_inventory(guild_id, user_id):
    cursor.execute("SELECT item_name, qty, equipped, slot FROM inventory WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    return cursor.fetchall()


def remove_item(guild_id, user_id, item_name, qty=1):
    """Remove qty of an item from inventory. If qty reaches <=0, delete the row."""
    cursor.execute("SELECT qty FROM inventory WHERE guild_id=? AND user_id=? AND item_name=?", (guild_id, user_id, item_name))
    row = cursor.fetchone()
    if not row:
        return False
    cur_qty = row[0]
    if cur_qty <= qty:
        cursor.execute("DELETE FROM inventory WHERE guild_id=? AND user_id=? AND item_name=?", (guild_id, user_id, item_name))
    else:
        cursor.execute("UPDATE inventory SET qty=qty-? WHERE guild_id=? AND user_id=? AND item_name=?", (qty, guild_id, user_id, item_name))
    conn.commit()
    return True


def set_equipped(guild_id, user_id, item_name, equipped: bool):
    val = 1 if equipped else 0
    cursor.execute("UPDATE inventory SET equipped=? WHERE guild_id=? AND user_id=? AND item_name=?", (val, guild_id, user_id, item_name))
    conn.commit()


def get_equipped_items(guild_id, user_id):
    cursor.execute("SELECT item_name, qty, slot FROM inventory WHERE guild_id=? AND user_id=? AND equipped=1", (guild_id, user_id))
    return cursor.fetchall()


def get_shop_item_with_stats(guild_id, item_name):
    # Try exact match first
    cursor.execute("SELECT item_name, price, description, atk, def, slot FROM shop_items WHERE guild_id=? AND item_name=?", (guild_id, item_name))
    row = cursor.fetchone()
    if row:
        return row
    # Fallback: fetch all guild shop items and attempt case-insensitive or slug match
    cursor.execute("SELECT item_name, price, description, atk, def, slot FROM shop_items WHERE guild_id=?", (guild_id,))
    rows = cursor.fetchall()
    if not rows:
        return None
    import re
    def slug(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    target = item_name.lower()
    for r in rows:
        name = r[0]
        if name.lower() == target or slug(name) == target:
            return r
    return None


def set_cooldown(guild_id, user_id, command, ts=None):
    if ts is None:
        ts = int(time.time())
    cursor.execute("INSERT INTO cooldowns(guild_id, user_id, command, last_used) VALUES (?, ?, ?, ?)"
                   " ON CONFLICT(guild_id, user_id, command) DO UPDATE SET last_used=?",
                   (guild_id, user_id, command, ts, ts))
    conn.commit()


def get_cooldown(guild_id, user_id, command):
    cursor.execute("SELECT last_used FROM cooldowns WHERE guild_id=? AND user_id=? AND command=?", (guild_id, user_id, command))
    row = cursor.fetchone()
    return row[0] if row else None


def _today_date():
    import time
    return time.strftime('%Y-%m-%d')


def _now_ts():
    import time
    return int(time.time())


def get_daily_quest(guild_id, user_id):
    """Return today's daily quest for a user or None."""
    date = _today_date()
    cursor.execute("SELECT quest_key, progress, target, completed, reward_gold, reward_xp, reward_item, created_ts FROM daily_quests WHERE guild_id=? AND user_id=? AND date=?", (guild_id, user_id, date))
    row = cursor.fetchone()
    if not row:
        return None
    # If quest is older than 24 hours, consider it expired
    created = row[7] if len(row) > 7 else 0
    if created:
        try:
            now = _now_ts()
            if now - int(created) >= 86400:
                return None
        except Exception:
            pass
    return {
        'quest_key': row[0],
        'progress': row[1],
        'target': row[2],
        'completed': bool(row[3]),
        'reward_gold': row[4],
        'reward_xp': row[5],
        'reward_item': row[6],
        'created_ts': created,
    }


def create_daily_quest(guild_id, user_id, quest_key: str, target: int = 1, reward_gold: int = 0, reward_xp: int = 0, reward_item: str | None = None):
    date = _today_date()
    created = _now_ts()
    cursor.execute("INSERT OR REPLACE INTO daily_quests(guild_id, user_id, date, quest_key, progress, target, completed, reward_gold, reward_xp, reward_item, created_ts) VALUES (?, ?, ?, ?, 0, ?, 0, ?, ?, ?, ?)", (guild_id, user_id, date, quest_key, target, reward_gold, reward_xp, reward_item, created))
    conn.commit()


def increment_daily_progress(guild_id, user_id, amount: int = 1):
    """Increment progress for today's quest. If target reached, apply rewards and mark completed.
    Returns a dict: {'completed': bool, 'claimed': bool, 'progress': int, 'target': int, 'rewards': {...}}
    """
    date = _today_date()
    q = get_daily_quest(guild_id, user_id)
    if not q:
        return {'error': 'no_quest'}
    if q['completed']:
        return {'completed': True, 'claimed': True, 'progress': q['progress'], 'target': q['target']}

    new_progress = q['progress'] + amount
    cursor.execute("UPDATE daily_quests SET progress=? WHERE guild_id=? AND user_id=? AND date=?", (new_progress, guild_id, user_id, date))
    conn.commit()

    claimed = False
    rewards = {}
    if new_progress >= q['target']:
        # mark completed and give rewards
        cursor.execute("UPDATE daily_quests SET completed=1 WHERE guild_id=? AND user_id=? AND date=?", (guild_id, user_id, date))
        conn.commit()
        claimed = True
        # apply rewards to profile/inventory
        if q['reward_xp'] and q['reward_xp'] > 0:
            try:
                add_user_xp(guild_id, user_id, q['reward_xp'])
                rewards['xp'] = q['reward_xp']
            except Exception:
                pass
        if q['reward_gold'] and q['reward_gold'] > 0:
            try:
                add_gold(guild_id, user_id, q['reward_gold'])
                rewards['gold'] = q['reward_gold']
            except Exception:
                pass
        if q['reward_item']:
            try:
                add_item(guild_id, user_id, q['reward_item'], qty=1)
                rewards['item'] = q['reward_item']
            except Exception:
                pass
        # remove finished quest row so next get_daily_quest returns None
        try:
            cursor.execute("DELETE FROM daily_quests WHERE guild_id=? AND user_id=? AND date=?", (guild_id, user_id, date))
            conn.commit()
        except Exception:
            pass

    return {'completed': new_progress >= q['target'], 'claimed': claimed, 'progress': new_progress, 'target': q['target'], 'rewards': rewards, 'deleted': claimed}


# Buffs management
try:
    cursor.execute("CREATE TABLE IF NOT EXISTS buffs (guild_id INTEGER, user_id INTEGER, buff_key TEXT, stat TEXT, amount INTEGER, expires_ts INTEGER, PRIMARY KEY (guild_id, user_id, buff_key))")
    conn.commit()
except Exception:
    pass

# Achievements / badges
try:
    cursor.execute("CREATE TABLE IF NOT EXISTS achievements (guild_id INTEGER, user_id INTEGER, badge_key TEXT, earned_ts INTEGER, PRIMARY KEY (guild_id, user_id, badge_key))")
    conn.commit()
except Exception:
    pass

try:
    cursor.execute("ALTER TABLE user_profile ADD COLUMN selected_badge TEXT DEFAULT NULL")
    conn.commit()
except Exception:
    pass


def add_buff(guild_id, user_id, buff_key: str, stat: str, amount: int, duration_seconds: int):
    expires = _now_ts() + int(duration_seconds)
    cursor.execute("INSERT OR REPLACE INTO buffs(guild_id, user_id, buff_key, stat, amount, expires_ts) VALUES (?, ?, ?, ?, ?, ?)", (guild_id, user_id, buff_key, stat, amount, expires))
    conn.commit()


def get_active_buffs(guild_id, user_id):
    now = _now_ts()
    cursor.execute("SELECT buff_key, stat, amount, expires_ts FROM buffs WHERE guild_id=? AND user_id=? AND expires_ts>?", (guild_id, user_id, now))
    return cursor.fetchall()


def cleanup_expired_buffs():
    now = _now_ts()
    cursor.execute("DELETE FROM buffs WHERE expires_ts<=?", (now,))
    conn.commit()


def delete_buff(guild_id, user_id, buff_key: str):
    cursor.execute("DELETE FROM buffs WHERE guild_id=? AND user_id=? AND buff_key=?", (guild_id, user_id, buff_key))
    conn.commit()


def get_effective_profile(guild_id, user_id):
    """Return profile with active buffs applied to atk/def."""
    prof = get_profile(guild_id, user_id)
    atk = prof.get('atk', 0)
    deff = prof.get('def', 0)
    buffs = get_active_buffs(guild_id, user_id)
    for bk, stat, amount, exp in buffs:
        if stat == 'atk':
            atk += int(amount)
        elif stat == 'def':
            deff += int(amount)
    out = prof.copy()
    out['atk'] = atk
    out['def'] = deff
    return out


def award_achievement(guild_id, user_id, badge_key: str):
    ts = _now_ts()
    cursor.execute("INSERT OR REPLACE INTO achievements(guild_id, user_id, badge_key, earned_ts) VALUES (?, ?, ?, ?)", (guild_id, user_id, badge_key, ts))
    conn.commit()


def list_user_achievements(guild_id, user_id):
    cursor.execute("SELECT badge_key, earned_ts FROM achievements WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    return cursor.fetchall()


def set_selected_badge(guild_id, user_id, badge_key: str):
    # ensure profile exists
    cursor.execute("INSERT INTO user_profile(guild_id, user_id) VALUES (?, ?) ON CONFLICT(guild_id, user_id) DO NOTHING", (guild_id, user_id))
    cursor.execute("UPDATE user_profile SET selected_badge=? WHERE guild_id=? AND user_id=?", (badge_key, guild_id, user_id))
    conn.commit()


def get_selected_badge(guild_id, user_id):
    cursor.execute("SELECT selected_badge FROM user_profile WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    row = cursor.fetchone()
    return row[0] if row and row[0] else None


def get_all_user_xp(guild_id):
    cursor.execute("SELECT xp FROM user_xp WHERE guild_id=?", (guild_id,))
    return [r[0] for r in cursor.fetchall()]


def get_wins(guild_id, user_id):
    cursor.execute("SELECT wins FROM user_profile WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO user_profile(guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
        conn.commit()
        return 0
    return int(row[0] or 0)


def add_win(guild_id, user_id, amount: int = 1):
    cur = get_wins(guild_id, user_id) + amount
    cursor.execute("INSERT INTO user_profile(guild_id, user_id) VALUES (?, ?) ON CONFLICT(guild_id, user_id) DO NOTHING", (guild_id, user_id))
    cursor.execute("UPDATE user_profile SET wins=? WHERE guild_id=? AND user_id=?", (cur, guild_id, user_id))
    conn.commit()
    return cur


def get_onboarded(guild_id, user_id):
    cursor.execute("SELECT onboarded FROM user_profile WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    row = cursor.fetchone()
    if not row:
        # create default profile
        cursor.execute("INSERT INTO user_profile(guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
        conn.commit()
        return False
    return bool(row[0])


def set_onboarded(guild_id, user_id):
    cursor.execute("INSERT INTO user_profile(guild_id, user_id) VALUES (?, ?) ON CONFLICT(guild_id, user_id) DO NOTHING", (guild_id, user_id))
    cursor.execute("UPDATE user_profile SET onboarded=1 WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    conn.commit()
