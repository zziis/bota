import os
import aiosqlite
from datetime import datetime, timedelta, timezone
from src.config import DB_PATH

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, is_banned INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        for col, ddl in [('ban_until','TEXT'),('mute_until','TEXT'),('ban_reason','TEXT'),('mute_reason','TEXT')]:
            try: await db.execute(f'ALTER TABLE users ADD COLUMN {col} {ddl}')
            except Exception: pass
        await db.execute('''CREATE TABLE IF NOT EXISTS message_mappings (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,user_message_id INTEGER NOT NULL,admin_message_id INTEGER NOT NULL,admin_chat_id INTEGER NOT NULL,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS calls (room_id TEXT PRIMARY KEY,caller_id INTEGER,caller_name TEXT,status TEXT DEFAULT 'pending',call_type TEXT DEFAULT 'audio',created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS friends (user_id INTEGER NOT NULL, friend_id INTEGER NOT NULL, status TEXT DEFAULT 'pending', requested_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,friend_id))''')
        await db.execute('''CREATE TABLE IF NOT EXISTS direct_messages (id INTEGER PRIMARY KEY AUTOINCREMENT,sender_id INTEGER,receiver_id INTEGER,body TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,read_at TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS media (id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,title TEXT NOT NULL,url TEXT NOT NULL,active INTEGER DEFAULT 1,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS punishments (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT,reason TEXT,duration_minutes INTEGER,admin_id INTEGER,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,ends_at TEXT)''')
        await db.commit()

async def add_or_update_user(user_id, username=None, full_name=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''INSERT INTO users(user_id,username,full_name,last_active) VALUES(?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,full_name=excluded.full_name,last_active=CURRENT_TIMESTAMP''',(user_id,username,full_name)); await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute('SELECT * FROM users WHERE user_id=?',(user_id,)) as c:
            r=await c.fetchone(); return dict(r) if r else None

async def find_user(value):
    v=str(value).strip().lstrip('@')
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory=aiosqlite.Row
        if v.isdigit(): q=('SELECT * FROM users WHERE user_id=?',(int(v),))
        else: q=('SELECT * FROM users WHERE lower(username)=lower(?)',(v,))
        async with db.execute(*q) as c:
            r=await c.fetchone(); return dict(r) if r else None

def _now(): return datetime.now(timezone.utc)
def _iso(dt): return dt.isoformat() if dt else None

def _active_until(value):
    if not value: return False
    try: return datetime.fromisoformat(value) > _now()
    except Exception: return False

async def get_restriction(user_id):
    u=await get_user(user_id)
    if not u: return {'banned':False,'muted':False}
    permanent=bool(u.get('is_banned')) and not u.get('ban_until')
    return {'banned': permanent or _active_until(u.get('ban_until')), 'muted': _active_until(u.get('mute_until')), 'ban_until':u.get('ban_until'),'mute_until':u.get('mute_until'),'ban_reason':u.get('ban_reason'),'mute_reason':u.get('mute_reason')}

async def is_user_banned(user_id): return (await get_restriction(user_id))['banned']
async def is_user_muted(user_id): return (await get_restriction(user_id))['muted']

async def punish_user(user_id, action, duration_minutes, reason, admin_id):
    until=None if duration_minutes<=0 else _now()+timedelta(minutes=duration_minutes)
    async with aiosqlite.connect(DB_PATH) as db:
        if action=='ban': await db.execute('UPDATE users SET is_banned=1,ban_until=?,ban_reason=? WHERE user_id=?',(_iso(until),reason,user_id))
        elif action=='mute': await db.execute('UPDATE users SET mute_until=?,mute_reason=? WHERE user_id=?',(_iso(until),reason,user_id))
        await db.execute('INSERT INTO punishments(user_id,action,reason,duration_minutes,admin_id,ends_at) VALUES(?,?,?,?,?,?)',(user_id,action,reason,duration_minutes,admin_id,_iso(until)))
        await db.commit()

async def set_user_ban(user_id,banned):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET is_banned=?,ban_until=NULL,ban_reason=NULL WHERE user_id=?',(1 if banned else 0,user_id)); await db.commit(); return True

async def save_message_mapping(user_id,user_message_id,admin_message_id,admin_chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO message_mappings(user_id,user_message_id,admin_message_id,admin_chat_id) VALUES(?,?,?,?)',(user_id,user_message_id,admin_message_id,admin_chat_id)); await db.commit()

async def get_user_by_admin_message(admin_message_id,admin_chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id,user_message_id FROM message_mappings WHERE admin_message_id=? AND admin_chat_id=? ORDER BY id DESC LIMIT 1',(admin_message_id,admin_chat_id)) as c:
            r=await c.fetchone(); return {'user_id':r[0],'user_message_id':r[1]} if r else None

async def create_call_record(room_id,caller_id,caller_name,call_type='audio'):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO calls(room_id,caller_id,caller_name,call_type) VALUES(?,?,?,?)',(room_id,caller_id,caller_name,call_type)); await db.commit()

async def request_friend(user_id,friend_id):
    a,b=sorted((user_id,friend_id))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO friends(user_id,friend_id,status,requested_by) VALUES(?,?,"pending",?) ON CONFLICT(user_id,friend_id) DO UPDATE SET status="pending",requested_by=excluded.requested_by',(a,b,user_id)); await db.commit()

async def set_friend_status(user_id,friend_id,status):
    a,b=sorted((user_id,friend_id))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE friends SET status=? WHERE user_id=? AND friend_id=?',(status,a,b)); await db.commit()

async def are_friends(a,b):
    x,y=sorted((a,b))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM friends WHERE user_id=? AND friend_id=? AND status="accepted"',(x,y)) as c: return bool(await c.fetchone())

async def get_friends(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute('''SELECT u.* FROM friends f JOIN users u ON u.user_id=CASE WHEN f.user_id=? THEN f.friend_id ELSE f.user_id END WHERE (f.user_id=? OR f.friend_id=?) AND f.status='accepted' ORDER BY u.last_active DESC''',(user_id,user_id,user_id)) as c: return [dict(r) for r in await c.fetchall()]

async def save_direct_message(sender,receiver,body):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO direct_messages(sender_id,receiver_id,body) VALUES(?,?,?)',(sender,receiver,body)); await db.commit()

async def add_media(kind,title,url):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO media(kind,title,url) VALUES(?,?,?)',(kind,title,url)); await db.commit()

async def get_media():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute('SELECT * FROM media WHERE active=1 ORDER BY id DESC LIMIT 50') as c: return [dict(r) for r in await c.fetchall()]

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id FROM users') as c: return [r[0] for r in await c.fetchall()]

async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        vals=[]
        for q in ['SELECT COUNT(*) FROM users','SELECT COUNT(*) FROM users WHERE is_banned=1','SELECT COUNT(*) FROM message_mappings','SELECT COUNT(*) FROM calls']:
            async with db.execute(q) as c: vals.append((await c.fetchone())[0])
    return dict(zip(['total_users','banned_users','total_messages','total_calls'],vals))
