import os
import uuid
import logging
from urllib.parse import urlencode, quote
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    FSInputFile,
    CallbackQuery
)
from src.config import BOT_TOKEN, ADMIN_IDS, BASE_URL, APP_NAME, BASE_DIR
from src import db

logger = logging.getLogger("KhayalBot")

# تهيئة البوت والموزع
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
) if BOT_TOKEN else None

dp = Dispatcher()

def get_call_url(room_id: str, name: str = "") -> str:
    """توليد رابط المكالمة"""
    # Encode the complete query string (including Arabic names) so Telegram receives a valid HTTPS URL.
    query = urlencode({"room": room_id, "name": name})
    return f"{BASE_URL}/call?{query}"

def make_call_button(room_id: str, label: str = "📞 فتح مكالمة خيال المباشرة", name: str = "") -> InlineKeyboardButton:
    """إنشاء زر المكالمة كـ Mini App إذا كان الرابط يدعم HTTPS أو كرابط عادي"""
    call_url = get_call_url(room_id, name)
    if BASE_URL.startswith("https://"):
        return InlineKeyboardButton(text=label, web_app=WebAppInfo(url=call_url))
    else:
        return InlineKeyboardButton(text=label, url=call_url)

# لوحة الأزرار الرئيسية للمستخدم
def get_user_main_keyboard(room_id: str = None, name: str = "") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📞 الاتصال", callback_data="call_menu")],
        [InlineKeyboardButton(text="👥 الأصدقاء", callback_data="friends_menu"), InlineKeyboardButton(text="🎵 الأغاني والفيديو", callback_data="media_menu")],
        [InlineKeyboardButton(text="💬 حول خيال", callback_data="help_info"), InlineKeyboardButton(text="👤 حسابي", callback_data="my_account")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def call_choice_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 الاتصال بالإدارة", callback_data="call_admin")],
        [InlineKeyboardButton(text="👤 الاتصال بمستخدم", callback_data="call_user_help")]
    ])

def share_call_keyboard(room_id, name="مستخدم"):
    url=get_call_url(room_id,name)
    share=f"https://t.me/share/url?{urlencode({'url':url,'text':'دعوة مكالمة خيال'})}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [make_call_button(room_id,"🎙️ دخول المكالمة",name)],
        [InlineKeyboardButton(text="🔗 مشاركة رابط المكالمة",url=share)]
    ])

# لوحة تحكم الأدمن للرسالة المحولة
def get_admin_message_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📞 بدء مكالمة معه", callback_data=f"admin_call_{user_id}"),
            InlineKeyboardButton(text="🚫 حظر المستخدم", callback_data=f"admin_ban_{user_id}")
        ],
        [
            InlineKeyboardButton(text="ℹ️ معلومات المستخدم", callback_data=f"admin_info_{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# =================== معالجات الأوامر ===================

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    """الترحيب بالمستخدم وتسجيله"""
    user = message.from_user
    await db.add_or_update_user(user.id, user.username, user.full_name)

    if await db.is_user_banned(user.id):
        await message.reply("🚫 <b>عذراً، حسابك محظور من استخدام البوت.</b>")
        return

    welcome_text = (
        f"🌌 <b>أهلاً بك في منصة وتواصل {APP_NAME}</b>\n\n"
        "يسعدنا تواصلك معنا! هنا يمكنك:\n"
        "• ✉️ إرسال رسائلك واستفساراتك النصية.\n"
        "• 📸 مشاركة الصور، المقاطع، والملفات.\n"
        "• 🎙️ إرسال الملاحظات الصوتية الفورية.\n"
        "• 📞 <b>إجراء مكالمة مباشرة (صوت وفيديو)</b> مع الإدارة داخل تلجرام.\n\n"
        "<i>اكتب رسالتك الآن وسيقوم فريق خيال بالرد عليك فوراً.</i>"
    )

    avatar_path = os.path.join(BASE_DIR, "assets", "avatar.jpg")
    keyboard = get_user_main_keyboard(name=user.full_name)

    if os.path.exists(avatar_path):
        try:
            photo = FSInputFile(avatar_path)
            await message.answer_photo(photo=photo, caption=welcome_text, reply_markup=keyboard)
            return
        except Exception as e:
            logger.warning(f"تعذر إرسال الصورة الرمزية: {e}")

    await message.answer(welcome_text, reply_markup=keyboard)

@dp.message(Command("call"))
async def handle_call_command(message: types.Message):
    """طلب مكالمة مباشرة"""
    user = message.from_user
    if await db.is_user_banned(user.id):
        await message.reply("🚫 حسابك محظور.")
        return

    room_id = f"khayal-{uuid.uuid4().hex[:8]}"
    await db.create_call_record(room_id, user.id, user.full_name)

    user_kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_call_button(room_id, "📞 دخول غرفة المكالمة الآن", user.full_name)]
    ])

    await message.reply(
        "🎧 <b>تم إنشاء غرفة المكالمة المباشرة الخاصة بك:</b>\n\n"
        "اضغط على الزر أدناه لبدء المكالمة الصوتية أو المرئية مباشرة عبر تطبيق الويب المصغر.\n"
        "<i>تم إرسال إشعار للإدارة للانضمام معك.</i>",
        reply_markup=user_kb
    )

    # إشعار المشرفين
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_call_button(room_id, "📞 انضم للمكالمة كمشرف", "المشرف")],
        [InlineKeyboardButton(text="🚫 حظر المستخدم", callback_data=f"admin_ban_{user.id}")]
    ])

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🚨 <b>طلب مكالمة صوت وفيديو مباشر!</b>\n\n"
                    f"👤 <b>المرسل:</b> {user.full_name} (@{user.username or 'بدون'})\n"
                    f"🆔 <b>الآيدي:</b> <code>{user.id}</code>\n"
                    f"🔑 <b>الغرفة:</b> <code>{room_id}</code>"
                ),
                reply_markup=admin_kb
            )
        except Exception as e:
            logger.error(f"فشل إشعار المشرف {admin_id}: {e}")

@dp.callback_query(F.data == "call_menu")
async def cb_call_menu(query: CallbackQuery):
    await query.answer()
    await query.message.answer("📞 <b>اختر جهة الاتصال:</b>\n\n• الإدارة: يصل الطلب مباشرة للمشرف.\n• مستخدم: استخدم صديقاً داخل خيال أو شارك رابط الدعوة.", reply_markup=call_choice_keyboard())

@dp.callback_query(F.data == "call_admin")
async def cb_call_admin(query: CallbackQuery):
    await query.answer()
    user=query.from_user
    room_id=f"khayal-{uuid.uuid4().hex[:8]}"
    await db.create_call_record(room_id,user.id,user.full_name,"audio")
    await query.message.answer("🎙️ <b>تم إرسال طلب الاتصال للإدارة.</b>\nيبدأ الاتصال بالمايك فقط، ويمكن فتح الكاميرا من داخل المكالمة.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[make_call_button(room_id,"🎙️ دخول وانتظار الإدارة",user.full_name)]]))
    kb=InlineKeyboardMarkup(inline_keyboard=[[make_call_button(room_id,"📞 قبول اتصال المستخدم","الإدارة")],[InlineKeyboardButton(text="🚫 إدارة العقوبة",callback_data=f"punish_{user.id}")]])
    for aid in ADMIN_IDS:
        try: await bot.send_message(aid,f"📞 <b>اتصال جديد إلى الإدارة</b>\n👤 {user.full_name}\n🆔 <code>{user.id}</code>\n🎙️ يبدأ صوتياً فقط.",reply_markup=kb)
        except Exception as e: logger.error(f"admin call notify failed {aid}: {e}")

@dp.callback_query(F.data == "call_user_help")
async def cb_call_user_help(query: CallbackQuery):
    await query.answer()
    await query.message.answer("👤 <b>اتصال بمستخدم</b>\nأرسل: <code>/calluser ID</code> أو <code>/calluser @username</code>\nإذا كان صديقاً في خيال تصله دعوة مباشرة. وإذا لم يكن، ستحصل على زر مشاركة للرابط.")

@dp.message(Command("calluser"))
async def call_user(message: types.Message):
    parts=(message.text or '').split(maxsplit=1)
    if len(parts)<2:
        await message.reply("الاستخدام: <code>/calluser @username</code> أو <code>/calluser ID</code>"); return
    target=await db.find_user(parts[1]); room_id=f"khayal-{uuid.uuid4().hex[:8]}"
    await db.create_call_record(room_id,message.from_user.id,message.from_user.full_name,"audio")
    if target and target['user_id']!=message.from_user.id and await db.are_friends(message.from_user.id,target['user_id']):
        kb=InlineKeyboardMarkup(inline_keyboard=[[make_call_button(room_id,"📞 قبول المكالمة",target.get('full_name') or 'مستخدم')]])
        try:
            await bot.send_message(target['user_id'],f"📞 <b>{message.from_user.full_name} يتصل بك عبر خيال</b>\n🎙️ يبدأ الاتصال صوتياً ويمكن تشغيل الكاميرا اختيارياً.",reply_markup=kb)
            await message.reply("✅ تم إرسال طلب الاتصال لصديقك.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[make_call_button(room_id,"🎙️ دخول المكالمة",message.from_user.full_name)]])); return
        except Exception: pass
    await message.reply("🔗 <b>تم إنشاء رابط دعوة.</b>\nلن نعرض الرابط الطويل؛ استخدم زر المشاركة.",reply_markup=share_call_keyboard(room_id,message.from_user.full_name))

@dp.callback_query(F.data == "friends_menu")
async def friends_menu(query: CallbackQuery):
    await query.answer(); friends=await db.get_friends(query.from_user.id)
    text="👥 <b>أصدقاؤك في خيال</b>\n"
    if friends:
        for u in friends[:20]: text+=f"\n🟢 {u.get('full_name') or 'مستخدم'} — <code>{u['user_id']}</code>"
    else: text+="\nلا يوجد أصدقاء بعد."
    text+="\n\nلإضافة شخص: <code>/addfriend @username</code>\nللمراسلة: <code>/msg ID رسالتك</code>\nللاتصال: <code>/calluser ID</code>"
    await query.message.answer(text)

@dp.message(Command("addfriend"))
async def add_friend(message: types.Message):
    parts=(message.text or '').split(maxsplit=1)
    if len(parts)<2: await message.reply("الاستخدام: <code>/addfriend @username</code>"); return
    target=await db.find_user(parts[1])
    if not target or target['user_id']==message.from_user.id: await message.reply("❌ لم أجد هذا المستخدم داخل خيال."); return
    await db.request_friend(message.from_user.id,target['user_id'])
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ قبول",callback_data=f"friend_accept_{message.from_user.id}"),InlineKeyboardButton(text="❌ رفض",callback_data=f"friend_reject_{message.from_user.id}")]])
    await bot.send_message(target['user_id'],f"👥 <b>طلب صداقة جديد</b>\nمن: {message.from_user.full_name}\n🆔 <code>{message.from_user.id}</code>",reply_markup=kb)
    await message.reply("✅ تم إرسال طلب الصداقة.")

@dp.callback_query(F.data.startswith("friend_accept_"))
async def friend_accept(query: CallbackQuery):
    other=int(query.data.rsplit('_',1)[1]); await db.set_friend_status(query.from_user.id,other,'accepted'); await query.answer("تمت الإضافة",show_alert=True)
    try: await bot.send_message(other,f"✅ <b>{query.from_user.full_name}</b> قبل طلب صداقتك في خيال.")
    except: pass

@dp.callback_query(F.data.startswith("friend_reject_"))
async def friend_reject(query: CallbackQuery):
    other=int(query.data.rsplit('_',1)[1]); await db.set_friend_status(query.from_user.id,other,'rejected'); await query.answer("تم الرفض",show_alert=True)

@dp.message(Command("msg"))
async def direct_msg(message: types.Message):
    parts=(message.text or '').split(maxsplit=2)
    if len(parts)<3 or not parts[1].isdigit(): await message.reply("الاستخدام: <code>/msg ID رسالتك</code>"); return
    target=int(parts[1]); body=parts[2]
    if not await db.are_friends(message.from_user.id,target): await message.reply("❌ المراسلة المباشرة متاحة بين الأصدقاء فقط."); return
    if await db.is_user_muted(message.from_user.id): await message.reply("🔇 أنت مكتوم حالياً ولا تستطيع إرسال رسائل."); return
    await db.save_direct_message(message.from_user.id,target,body)
    try: await bot.send_message(target,f"💬 <b>رسالة من {message.from_user.full_name}</b>\n{body}\n\nللرد: <code>/msg {message.from_user.id} ردك</code>"); await message.reply("✅ تم الإرسال.")
    except: await message.reply("❌ تعذر تسليم الرسالة.")

@dp.callback_query(F.data == "media_menu")
async def media_menu(query: CallbackQuery):
    await query.answer(); items=await db.get_media()
    if not items: await query.message.answer("🎵 <b>مكتبة خيال</b>\nلا توجد أغاني أو فيديوهات منشورة من الإدارة حالياً."); return
    rows=[]
    for m in items[:20]: rows.append([InlineKeyboardButton(text=("🎵 " if m['kind']=='audio' else "🎬 ")+m['title'],url=m['url'])])
    await query.message.answer("🎵 <b>الأغاني والفيديو</b>\nالمحتوى المنشور من إدارة خيال:",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@dp.message(Command("addmedia"))
async def add_media(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    parts=(message.text or '').split(maxsplit=3)
    if len(parts)<4 or parts[1] not in ('audio','video') or not parts[3].startswith('https://'):
        await message.reply("الاستخدام: <code>/addmedia audio عنوان https://...</code>\nأو video"); return
    await db.add_media(parts[1],parts[2],parts[3]); await message.reply("✅ تمت إضافة المحتوى إلى مكتبة خيال.")

@dp.callback_query(F.data.startswith("punish_"))
async def punish_menu(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS: return
    uid=int(query.data.split('_')[1]); await query.answer()
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚫 حظر 5 دقائق",callback_data=f"act_ban_5_{uid}"),InlineKeyboardButton(text="🔇 كتم 5 دقائق",callback_data=f"act_mute_5_{uid}")],[InlineKeyboardButton(text="🚫 حظر يوم",callback_data=f"act_ban_1440_{uid}"),InlineKeyboardButton(text="🔇 كتم ساعة",callback_data=f"act_mute_60_{uid}")],[InlineKeyboardButton(text="⛔ حظر دائم",callback_data=f"act_ban_0_{uid}"),InlineKeyboardButton(text="👢 طرد",callback_data=f"act_kick_0_{uid}")]])
    await query.message.answer(f"إدارة المستخدم <code>{uid}</code>",reply_markup=kb)

@dp.callback_query(F.data.startswith("act_"))
async def punish_action(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS: return
    _,action,mins,uid=query.data.split('_'); mins=int(mins); uid=int(uid); reason="بقرار إدارة خيال"
    labels={'ban':'حظرك','mute':'كتمك','kick':'طردك'}
    if action in ('ban','mute'): await db.punish_user(uid,action,mins,reason,query.from_user.id)
    duration='دائم' if mins==0 and action=='ban' else ('5 دقائق' if mins==5 else 'ساعة' if mins==60 else 'يوم' if mins==1440 else 'فوري')
    try: await bot.send_message(uid,f"⚠️ <b>تم {labels[action]} من خيال</b>\nالمدة: <b>{duration}</b>\nالسبب: {reason}")
    except: pass
    await query.answer("تم تنفيذ الإجراء",show_alert=True)

@dp.message(Command("stats"))
async def handle_stats(message: types.Message):
    """إحصائيات المنصة (خاص بالمشرفين)"""
    if message.from_user.id not in ADMIN_IDS:
        return

    stats = await db.get_stats()
    text = (
        "📊 <b>إحصائيات منصة خيال:</b>\n\n"
        f"👥 <b>إجمالي المستخدمين:</b> {stats['total_users']}\n"
        f"🚫 <b>المحظورين:</b> {stats['banned_users']}\n"
        f"💬 <b>إجمالي الرسائل المتبادلة:</b> {stats['total_messages']}\n"
        f"📞 <b>إجمالي المكالمات:</b> {stats['total_calls']}"
    )
    await message.reply(text)

@dp.message(Command("broadcast"))
async def handle_broadcast(message: types.Message):
    """إذاعة رسالة لجميع المشتركين (خاص بالمشرفين)"""
    if message.from_user.id not in ADMIN_IDS:
        return

    # استخراج نص الرسالة بعد الأمر /broadcast
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⚠️ يرجى كتابة نص الرسالة بعد الأمر:\n<code>/broadcast مرحباً بكم جميعاً</code>")
        return

    broadcast_text = parts[1]
    users = await db.get_all_users()
    sent_count = 0
    fail_count = 0

    status_msg = await message.reply(f"⏳ جاري الإذاعة إلى {len(users)} مشترك...")

    for uid in users:
        try:
            await bot.send_message(
                chat_id=uid,
                text=f"📢 <b>إعلان من إدارة خيال:</b>\n\n{broadcast_text}"
            )
            sent_count += 1
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ <b>اكتملت الإذاعة:</b>\n"
        f"• تم الإرسال بنجاح: {sent_count}\n"
        f"• تعذر الإرسال (حظروا البوت): {fail_count}"
    )

@dp.message(Command("ban"))
async def handle_ban_cmd(message: types.Message):
    """حظر مستخدم عبر الآيدي"""
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("⚠️ الاستخدام: <code>/ban 12345678</code>")
        return
    target_id = int(parts[1])
    await db.set_user_ban(target_id, True)
    await message.reply(f"✅ تم حظر المستخدم <code>{target_id}</code> بنجاح.")

@dp.message(Command("unban"))
async def handle_unban_cmd(message: types.Message):
    """إلغاء حظر مستخدم"""
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("⚠️ الاستخدام: <code>/unban 12345678</code>")
        return
    target_id = int(parts[1])
    await db.set_user_ban(target_id, False)
    await message.reply(f"✅ تم إلغاء حظر المستخدم <code>{target_id}</code> بنجاح.")

# =================== معالجة الرسائل والردود ===================

@dp.message(F.chat.type == "private")
async def handle_all_messages(message: types.Message):
    """معالجة جميع أنواع الرسائل (نصوص، صور، فويس، فيديو، ملفات)"""
    sender = message.from_user
    is_admin = sender.id in ADMIN_IDS

    # 1. إذا كان المرسل هو المشرف ويقوم بعمل Reply للرد على رسالة
    if is_admin and message.reply_to_message:
        reply_to_id = message.reply_to_message.message_id
        mapping = await db.get_user_by_admin_message(reply_to_id, message.chat.id)

        if mapping:
            target_user_id = mapping["user_id"]
            try:
                # إرسال إشعار ومحتوى الرد للمستخدم
                await bot.send_message(
                    chat_id=target_user_id,
                    text="💬 <b>رد وارد من إدارة خيال:</b>",
                    reply_to_message_id=mapping["user_message_id"]
                )
                await bot.copy_message(
                    chat_id=target_user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                await message.reply("✅ <b>تم إرسال ردك إلى المستخدم بنجاح!</b>")
                return
            except Exception as e:
                await message.reply(f"❌ تعذر تسليم الرد (قد يكون المستخدم حظر البوت): {e}")
                return

    # إذا كان المشرف يرسل رسالة عادية غير رد
    if is_admin:
        await message.reply(
            "👑 <b>أنت في وضع المشرف.</b>\n"
            "للرد على أي مستخدم، قم بعمل <b>Reply</b> (رد مباشر) على رسالته المحولة.\n"
            "أو استخدم الأوامر: /stats, /broadcast, /ban, /unban"
        )
        return

    # 2. المستخدم العادي يرسل رسالة
    if await db.is_user_banned(sender.id):
        await message.reply("🚫 تم حظرك من خيال. لا يمكنك استخدام المراسلة حالياً.")
        return
    if await db.is_user_muted(sender.id):
        await message.reply("🔇 تم كتمك من خيال مؤقتاً، ولا يمكنك إرسال الرسائل خلال مدة الكتم.")
        return

    await db.add_or_update_user(sender.id, sender.username, sender.full_name)

    # توجيه الرسالة لكافة المشرفين
    forward_header = (
        "📩 <b>رسالة واردة جديدة عبر خيال</b>\n"
        f"👤 <b>المرسل:</b> {sender.full_name}\n"
        f"🔗 <b>المعرف:</b> @{sender.username or 'بدون'}\n"
        f"🆔 <b>الآيدي:</b> <code>{sender.id}</code>\n"
        "------------------------------------"
    )

    admin_kb = get_admin_message_keyboard(sender.id)

    for admin_id in ADMIN_IDS:
        try:
            # إرسال البطاقة التعريفية
            await bot.send_message(chat_id=admin_id, text=forward_header)
            # نسخ الرسالة كاملة (نص، صورة، صوت، فيديو، مستند...)
            admin_msg = await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=admin_kb
            )
            # حفظ الربط للرد التلقائي
            await db.save_message_mapping(
                user_id=sender.id,
                user_message_id=message.message_id,
                admin_message_id=admin_msg.message_id,
                admin_chat_id=admin_id
            )
        except Exception as e:
            logger.error(f"خطأ في تحويل الرسالة للمشرف {admin_id}: {e}")

    # تأكيد الاستلام للمستخدم
    await message.reply(
        "✅ <b>تم استلام رسالتك بنجاح!</b>\n"
        "سيقوم فريق خيال بمراجعتها والرد عليك هنا في أقرب وقت."
    )

# =================== أزرار Inline Callbacks ===================

@dp.callback_query(F.data == "help_info")
async def cb_help_info(query: CallbackQuery):
    await query.answer()
    info_text = (
        "✨ <b>حول منصة وبوت خيال (Khayal):</b>\n\n"
        "• يمكنك محادثتنا نصياً ومشاركة أي صور أو تسجيلات صوتية.\n"
        "• للمكالمات: اضغط على زر 'مكالمة خيال' لبدء مكالمة صوت وفيديو مباشرة داخل تطبيق تلجرام.\n"
        "• جميع محادثاتك ومكالماتك مشفرة ومحمية بالكامل."
    )
    await query.message.answer(info_text)

@dp.callback_query(F.data == "my_account")
async def cb_my_account(query: CallbackQuery):
    await query.answer()
    user = query.from_user
    acc_text = (
        "👤 <b>معلومات حسابك في خيال:</b>\n\n"
        f"• <b>الاسم:</b> {user.full_name}\n"
        f"• <b>المعرف:</b> @{user.username or 'لا يوجد'}\n"
        f"• <b>الآيدي:</b> <code>{user.id}</code>\n"
        "• <b>الحالة:</b> نشط ومصرح 🟢"
    )
    await query.message.answer(acc_text)

@dp.callback_query(F.data.startswith("admin_ban_"))
async def cb_admin_ban(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("غير مصرح لك.", show_alert=True)
        return
    target_id = int(query.data.replace("admin_ban_", ""))
    await query.answer()
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚫 حظر 5 دقائق",callback_data=f"act_ban_5_{target_id}"),InlineKeyboardButton(text="🔇 كتم 5 دقائق",callback_data=f"act_mute_5_{target_id}")],[InlineKeyboardButton(text="🚫 حظر يوم",callback_data=f"act_ban_1440_{target_id}"),InlineKeyboardButton(text="🔇 كتم ساعة",callback_data=f"act_mute_60_{target_id}")],[InlineKeyboardButton(text="⛔ حظر دائم",callback_data=f"act_ban_0_{target_id}"),InlineKeyboardButton(text="👢 طرد",callback_data=f"act_kick_0_{target_id}")]])
    await query.message.reply(f"⚙️ اختر الإجراء للمستخدم <code>{target_id}</code>",reply_markup=kb)

@dp.callback_query(F.data.startswith("admin_info_"))
async def cb_admin_info(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("غير مصرح.", show_alert=True)
        return
    target_id = int(query.data.replace("admin_info_", ""))
    await query.answer()
    await query.message.reply(
        f"ℹ️ <b>معلومات المستخدم:</b>\n"
        f"• <b>الآيدي:</b> <code>{target_id}</code>\n"
        f"• <b>الرابط المباشر:</b> tg://user?id={target_id}"
    )

@dp.callback_query(F.data.startswith("admin_call_"))
async def cb_admin_call(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("غير مصرح.", show_alert=True)
        return
    target_id = int(query.data.replace("admin_call_", ""))
    room_id = f"khayal-{uuid.uuid4().hex[:8]}"

    # إرسال رابط المكالمة للمستخدم
    user_call_kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_call_button(room_id, "📞 قبول ودخول المكالمة المباشرة", "مستخدم")]
    ])
    try:
        await bot.send_message(
            chat_id=target_id,
            text="📞 <b>إدارة خيال تدعوك لمكالمة صوت/فيديو مباشرة!</b>\nاضغط على الزر أدناه للانضمام فوراً:",
            reply_markup=user_call_kb
        )
        admin_call_kb = InlineKeyboardMarkup(inline_keyboard=[
            [make_call_button(room_id, "📞 دخول غرفة المكالمة الآن", "المشرف")]
        ])
        await query.message.reply("✅ تم إرسال دعوة المكالمة للمستخدم!", reply_markup=admin_call_kb)
    except Exception as e:
        await query.message.reply(f"❌ تعذر إرسال الدعوة للمستخدم: {e}")
