import os
import aiosqlite
from src.config import DB_PATH

async def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول إذا لم تكن موجودة"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                is_banned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS message_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_message_id INTEGER NOT NULL,
                admin_message_id INTEGER NOT NULL,
                admin_chat_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                room_id TEXT PRIMARY KEY,
                caller_id INTEGER,
                caller_name TEXT,
                status TEXT DEFAULT 'pending',
                call_type TEXT DEFAULT 'audio_video',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def add_or_update_user(user_id: int, username: str = None, full_name: str = None):
    """إضافة أو تحديث بيانات المستخدم"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name, last_active)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_active = CURRENT_TIMESTAMP
        """, (user_id, username, full_name))
        await db.commit()

async def is_user_banned(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم محظوراً"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0] == 1)

async def set_user_ban(user_id: int, banned: bool) -> bool:
    """حظر أو إلغاء حظر مستخدم"""
    async with aiosqlite.connect(DB_PATH) as db:
        res = await db.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if banned else 0, user_id))
        await db.commit()
        return res.rowcount > 0

async def save_message_mapping(user_id: int, user_message_id: int, admin_message_id: int, admin_chat_id: int):
    """حفظ ربط الرسالة لمعرفة صاحبها عند رد الأدمن"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO message_mappings (user_id, user_message_id, admin_message_id, admin_chat_id)
            VALUES (?, ?, ?, ?)
        """, (user_id, user_message_id, admin_message_id, admin_chat_id))
        await db.commit()

async def get_user_by_admin_message(admin_message_id: int, admin_chat_id: int):
    """جلب معرّف ورسالة المستخدم من خلال معرف رسالة الأدمن المحولة"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT user_id, user_message_id 
            FROM message_mappings 
            WHERE admin_message_id = ? AND admin_chat_id = ?
            ORDER BY id DESC LIMIT 1
        """, (admin_message_id, admin_chat_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"user_id": row[0], "user_message_id": row[1]}
            return None

async def create_call_record(room_id: str, caller_id: int, caller_name: str, call_type: str = "audio_video"):
    """تسجيل طلب مكالمة جديدة"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO calls (room_id, caller_id, caller_name, call_type)
            VALUES (?, ?, ?, ?)
        """, (room_id, caller_id, caller_name, call_type))
        await db.commit()

async def get_all_users():
    """جلب جميع المشتركين (لأغراض الإذاعة والإحصاء)"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE is_banned = 0") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def get_stats():
    """إحصائيات المنصة"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c1:
            total_users = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1") as c2:
            banned_users = (await c2.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM message_mappings") as c3:
            total_messages = (await c3.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM calls") as c4:
            total_calls = (await c4.fetchone())[0]
        return {
            "total_users": total_users,
            "banned_users": banned_users,
            "total_messages": total_messages,
            "total_calls": total_calls
        }
