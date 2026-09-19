import aiosqlite
from typing import Optional, Dict, List, Tuple
from config import DB_PATH

async def init_db():
    # قاعدة موحدة مع نظام Mini App الرئيسي
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            full_name TEXT,
            points INTEGER DEFAULT 500,
            last_daily_claim TEXT DEFAULT '',
            gender TEXT DEFAULT 'unknown',
            is_banned INTEGER DEFAULT 0,
            ghost_mode INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        await db.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            is_protected INTEGER DEFAULT 1,
            lock_links INTEGER DEFAULT 0,
            lock_forwards INTEGER DEFAULT 0,
            lock_usernames INTEGER DEFAULT 0,
            lock_photos INTEGER DEFAULT 0,
            lock_stickers INTEGER DEFAULT 0,
            lock_voice INTEGER DEFAULT 0,
            lock_spam INTEGER DEFAULT 1,
            lock_badwords INTEGER DEFAULT 1,
            welcome_enabled INTEGER DEFAULT 1,
            rules TEXT DEFAULT '',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS group_warns (
            chat_id INTEGER,
            user_id INTEGER,
            warn_count INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS global_bans (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            banned_by INTEGER,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            content TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS random_queue (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            preference TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS active_random_chats (
            user1_id INTEGER UNIQUE,
            user2_id INTEGER UNIQUE,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS capsule_rooms (
            room_id TEXT PRIMARY KEY,
            title TEXT,
            host_id INTEGER,
            host_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # ترقيات توافقية: توحيد جدول users بين النظامين القديم والجديد
        async with db.execute("PRAGMA table_info(users)") as cursor:
            cols = {row[1] for row in await cursor.fetchall()}
        migrations = {
            "first_name": "TEXT", "full_name": "TEXT", "points": "INTEGER DEFAULT 500",
            "last_daily_claim": "TEXT DEFAULT ''", "gender": "TEXT DEFAULT 'unknown'",
            "ghost_mode": "INTEGER DEFAULT 0", "created_at": "TIMESTAMP",
            "last_active": "TIMESTAMP", "joined_at": "TIMESTAMP"
        }
        for col, decl in migrations.items():
            if col not in cols:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")
        await db.commit()

# --- Users & Dev Superpowers ---
async def register_user(user_id: int, username: Optional[str], first_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
        """, (user_id, username or "", first_name))
        await db.commit()

async def set_user_gender(user_id: int, gender: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET gender = ? WHERE user_id = ?", (gender, user_id))
        await db.commit()

async def get_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def set_ghost_mode(user_id: int, active: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET ghost_mode = ? WHERE user_id = ?", (1 if active else 0, user_id))
        await db.commit()

async def is_ghost_mode(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT ghost_mode FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False

async def get_global_bans() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM global_bans") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def is_user_gbanned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM global_bans WHERE user_id = ?", (user_id,)) as cursor:
            return bool(await cursor.fetchone())

async def add_gban(user_id: int, reason: str, admin_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT OR REPLACE INTO global_bans (user_id, reason, banned_by)
        VALUES (?, ?, ?)
        """, (user_id, reason, admin_id))
        await db.commit()

async def remove_gban(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM global_bans WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            users_count = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM groups") as c:
            groups_count = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM global_bans") as c:
            gbans_count = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'") as c:
            open_tickets = (await c.fetchone())[0]
        return {
            "users": users_count,
            "groups": groups_count,
            "gbans": gbans_count,
            "open_tickets": open_tickets
        }

async def get_all_users() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as c:
            rows = await c.fetchall()
            return [r[0] for r in rows]

async def get_all_groups() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT chat_id FROM groups") as c:
            rows = await c.fetchall()
            return [r[0] for r in rows]

# --- Group Protection Engine ---
async def register_group(chat_id: int, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO groups (chat_id, title)
        VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title
        """, (chat_id, title))
        await db.commit()

async def get_group_settings(chat_id: int) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM groups WHERE chat_id = ?", (chat_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            # Default settings if group is newly seen
            await db.execute("INSERT OR IGNORE INTO groups (chat_id, title) VALUES (?, ?)", (chat_id, "مجموعة جديدة"))
            await db.commit()
            return {
                "chat_id": chat_id, "title": "مجموعة جديدة", "is_protected": 1,
                "lock_links": 0, "lock_forwards": 0, "lock_usernames": 0,
                "lock_photos": 0, "lock_stickers": 0, "lock_voice": 0,
                "lock_spam": 1, "lock_badwords": 1, "welcome_enabled": 1, "rules": ""
            }

async def update_group_setting(chat_id: int, key: str, value: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE groups SET {key} = ? WHERE chat_id = ?", (value, chat_id))
        await db.commit()

async def add_warn(chat_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO group_warns (chat_id, user_id, warn_count)
        VALUES (?, ?, 1)
        ON CONFLICT(chat_id, user_id) DO UPDATE SET warn_count = warn_count + 1
        """, (chat_id, user_id))
        await db.commit()
        async with db.execute("SELECT warn_count FROM group_warns WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)) as c:
            row = await c.fetchone()
            return row[0] if row else 1

async def reset_warns(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM group_warns WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()

# --- Tickets & Complaints & Direct Support ---
async def create_ticket(user_id: int, ticket_type: str, content: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
        INSERT INTO tickets (user_id, type, content)
        VALUES (?, ?, ?)
        """, (user_id, ticket_type, content))
        await db.commit()
        return cursor.lastrowid

# --- Random Chat System ---
async def join_random_queue(user_id: int, gender: str, preference: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT OR REPLACE INTO random_queue (user_id, gender, preference)
        VALUES (?, ?, ?)
        """, (user_id, gender, preference))
        await db.commit()

async def leave_random_queue(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM random_queue WHERE user_id = ?", (user_id,))
        await db.commit()

async def find_random_match(user_id: int, gender: str, preference: str) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        # Match condition:
        # Waiting user not current user
        # Waiting user preference matches current gender (or 'any')
        # Current preference matches waiting user gender (or 'any')
        query = """
        SELECT user_id FROM random_queue 
        WHERE user_id != ? 
          AND (preference = 'any' OR preference = ?)
          AND (? = 'any' OR gender = ?)
        ORDER BY joined_at ASC LIMIT 1
        """
        async with db.execute(query, (user_id, gender, preference, preference)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def create_active_chat(user1_id: int, user2_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM random_queue WHERE user_id IN (?, ?)", (user1_id, user2_id))
        await db.execute("INSERT OR REPLACE INTO active_random_chats (user1_id, user2_id) VALUES (?, ?)", (user1_id, user2_id))
        await db.commit()

async def get_active_chat_partner(user_id: int) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
        SELECT user2_id FROM active_random_chats WHERE user1_id = ?
        UNION
        SELECT user1_id FROM active_random_chats WHERE user2_id = ?
        """, (user_id, user_id)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def end_active_chat(user_id: int) -> Optional[int]:
    partner_id = await get_active_chat_partner(user_id)
    if partner_id:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM active_random_chats WHERE user1_id = ? OR user2_id = ?", (user_id, user_id))
            await db.commit()
    return partner_id

# --- Capsule Rooms ---
async def save_room(room_id: str, title: str, host_id: int, host_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT OR REPLACE INTO capsule_rooms (room_id, title, host_id, host_name)
        VALUES (?, ?, ?, ?)
        """, (room_id, title, host_id, host_name))
        await db.commit()

async def get_rooms() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM capsule_rooms ORDER BY created_at DESC LIMIT 20") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

# --- Persistent direct support inbox ---
async def ensure_support_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS support_threads (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            ack_enabled INTEGER DEFAULT 1,
            ack_sent INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            content TEXT,
            media_type TEXT DEFAULT 'text',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        await db.commit()

async def add_support_message(user_id:int, username:str, first_name:str, sender:str, content:str, media_type:str='text'):
    await ensure_support_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""INSERT INTO support_threads(user_id,username,first_name,updated_at)
            VALUES(?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name,updated_at=CURRENT_TIMESTAMP""",
            (user_id, username or '', first_name or 'مستخدم'))
        cur=await db.execute("INSERT INTO support_messages(user_id,sender,content,media_type) VALUES(?,?,?,?)",
                             (user_id,sender,content,media_type))
        await db.commit(); return cur.lastrowid

async def get_support_threads(limit:int=40):
    await ensure_support_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute("""SELECT t.*, (SELECT content FROM support_messages m WHERE m.user_id=t.user_id ORDER BY m.id DESC LIMIT 1) last_message,
            (SELECT COUNT(*) FROM support_messages m WHERE m.user_id=t.user_id) message_count
            FROM support_threads t ORDER BY t.updated_at DESC LIMIT ?""", (limit,)) as c:
            return [dict(x) for x in await c.fetchall()]

async def get_support_history(user_id:int, limit:int=20):
    await ensure_support_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute("SELECT * FROM support_messages WHERE user_id=? ORDER BY id DESC LIMIT ?",(user_id,limit)) as c:
            rows=[dict(x) for x in await c.fetchall()]
            return list(reversed(rows))

async def support_should_ack(user_id:int):
    await ensure_support_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT ack_enabled,ack_sent FROM support_threads WHERE user_id=?",(user_id,)) as c:
            r=await c.fetchone(); return bool(r and r[0] and not r[1])

async def mark_support_ack_sent(user_id:int):
    await ensure_support_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE support_threads SET ack_sent=1 WHERE user_id=?",(user_id,)); await db.commit()

async def set_support_ack(user_id:int, enabled:bool):
    await ensure_support_tables()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE support_threads SET ack_enabled=?,ack_sent=? WHERE user_id=?",(1 if enabled else 0,0 if enabled else 1,user_id)); await db.commit()
