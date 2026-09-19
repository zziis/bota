import os
import aiosqlite
from datetime import datetime, date
from src.config import DB_PATH

async def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول وترقيتها إذا لزم الأمر"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # جدول المستخدمين
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                points INTEGER DEFAULT 500,
                last_daily_claim TEXT DEFAULT '',
                is_banned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # فحص وترقية جدول المستخدمين في حال كانت قاعدة البيانات قديمة
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if "points" not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 500")
            if "last_daily_claim" not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN last_daily_claim TEXT DEFAULT ''")

        # جدول ربط الرسائل
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

        # جدول سجل المكالمات
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

        # جدول حركات النقاط (Transactions)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                tx_type TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول طلبات شراء وشحن النقاط
        await db.execute("""
            CREATE TABLE IF NOT EXISTS point_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                package_name TEXT,
                points INTEGER NOT NULL,
                price TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول مباريات الألعاب المباشرة (Matchmaking)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS game_matches (
                match_id TEXT PRIMARY KEY,
                player1_id INTEGER NOT NULL,
                player2_id INTEGER,
                game_type TEXT NOT NULL,
                bet_amount INTEGER DEFAULT 0,
                status TEXT DEFAULT 'waiting',
                winner_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()

async def add_or_update_user(user_id: int, username: str = None, full_name: str = None):
    """إضافة أو تحديث بيانات المستخدم مع رصيد افتراضي 500 نقطة"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name, points, last_active)
            VALUES (?, ?, ?, 500, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_active = CURRENT_TIMESTAMP
        """, (user_id, username, full_name))
        await db.commit()

async def get_user(user_id: int):
    """جلب بيانات المستخدم الكاملة"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def get_points(user_id: int) -> int:
    """جلب رصيد نقاط المستخدم"""
    user = await get_user(user_id)
    if user:
        return user.get("points", 500)
    return 500

async def update_points(user_id: int, delta: int, tx_type: str = "general", description: str = "") -> int:
    """تعديل رصيد النقاط وإرجاع الرصيد الجديد وتسجيل الحركة"""
    async with aiosqlite.connect(DB_PATH) as db:
        # التأكد من وجود المستخدم
        await db.execute("INSERT OR IGNORE INTO users (user_id, points) VALUES (?, 500)", (user_id,))
        await db.execute("UPDATE users SET points = MAX(0, points + ?) WHERE user_id = ?", (delta, user_id))
        await db.execute("""
            INSERT INTO transactions (user_id, amount, tx_type, description)
            VALUES (?, ?, ?, ?)
        """, (user_id, delta, tx_type, description))
        await db.commit()
        
        async with db.execute("SELECT points FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def claim_daily_bonus(user_id: int, bonus_amount: int = 100):
    """استلام المكافأة اليومية المجانية"""
    today_str = date.today().isoformat()
    user = await get_user(user_id)
    if not user:
        await add_or_update_user(user_id)
        user = await get_user(user_id)

    last_claim = user.get("last_daily_claim", "")
    if last_claim == today_str:
        return {"success": False, "message": "لقد استلمت هديتك اليومية بالفعل! عد غداً للحصول على المزيد.", "points": user.get("points", 0)}

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users 
            SET points = points + ?, last_daily_claim = ? 
            WHERE user_id = ?
        """, (bonus_amount, today_str, user_id))
        await db.execute("""
            INSERT INTO transactions (user_id, amount, tx_type, description)
            VALUES (?, ?, 'daily_bonus', 'هدية يومية مجانية')
        """, (user_id, bonus_amount))
        await db.commit()

    new_points = await get_points(user_id)
    return {"success": True, "message": f"مبروك! حصلت على {bonus_amount} نقطة هدية يومية 🎁", "points": new_points}

# إدارة طلبات شراء النقاط
async def create_point_request(user_id: int, user_name: str, package_name: str, points: int, price: str) -> int:
    """إنشاء طلب شراء نقاط جديد للمشرف"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO point_requests (user_id, user_name, package_name, points, price)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, user_name, package_name, points, price))
        await db.commit()
        return cursor.lastrowid

async def get_point_request(request_id: int):
    """جلب تفاصيل طلب الشحن"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM point_requests WHERE id = ?", (request_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def set_point_request_status(request_id: int, status: str) -> bool:
    """تحديث حالة طلب الشحن (approved / rejected)"""
    async with aiosqlite.connect(DB_PATH) as db:
        res = await db.execute("UPDATE point_requests SET status = ? WHERE id = ?", (status, request_id))
        await db.commit()
        return res.rowcount > 0

# الوظائف السابقة للبوت والمكالمات
async def is_user_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0] == 1)

async def set_user_ban(user_id: int, banned: bool) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        res = await db.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if banned else 0, user_id))
        await db.commit()
        return res.rowcount > 0

async def save_message_mapping(user_id: int, user_message_id: int, admin_message_id: int, admin_chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO message_mappings (user_id, user_message_id, admin_message_id, admin_chat_id)
            VALUES (?, ?, ?, ?)
        """, (user_id, user_message_id, admin_message_id, admin_chat_id))
        await db.commit()

async def get_user_by_admin_message(admin_message_id: int, admin_chat_id: int):
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO calls (room_id, caller_id, caller_name, call_type)
            VALUES (?, ?, ?, ?)
        """, (room_id, caller_id, caller_name, call_type))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE is_banned = 0") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c1:
            total_users = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1") as c2:
            banned_users = (await c2.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM message_mappings") as c3:
            total_messages = (await c3.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM calls") as c4:
            total_calls = (await c4.fetchone())[0]
        async with db.execute("SELECT SUM(points) FROM users") as c5:
            total_points = (await c5.fetchone())[0] or 0
        return {
            "total_users": total_users,
            "banned_users": banned_users,
            "total_messages": total_messages,
            "total_calls": total_calls,
            "total_points": total_points
        }
