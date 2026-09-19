import re
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, ChatPermissions, ChatMemberUpdated,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_ADMIN, IS_MEMBER
from config import NEON_HEADER, NEON_FOOTER, ADMIN_IDS
from database import (
    register_group, get_group_settings, update_group_setting,
    add_warn, reset_warns, is_user_gbanned, is_ghost_mode
)

router = Router()

BAD_WORDS = ["كس", "طيز", "زب", "منيوك", "شرموط", "قحبة", "كسمك", "نيك", "متناك", "عرص"]
LINK_REGEX = re.compile(r'(https?://[^\s]+|t\.me/[^\s]+|telegram\.me/[^\s]+)', re.IGNORECASE)
USERNAME_REGEX = re.compile(r'@[a-zA-Z0-9_]{4,}', re.IGNORECASE)

async def is_admin_or_dev(message: Message, bot: Bot) -> bool:
    if not message.from_user:
        return False
    if message.from_user.id in ADMIN_IDS:
        return True
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

def get_settings_keyboard(chat_id: int, s: dict) -> InlineKeyboardMarkup:
    def st(val):
        return "🔒 مقفول" if val == 1 else "🔓 مفتوح"
    
    buttons = [
        [
            InlineKeyboardButton(text=f"🔗 الروابط: {st(s.get('lock_links', 0))}", callback_data=f"guard_toggle:{chat_id}:lock_links"),
            InlineKeyboardButton(text=f"👤 المعرفات: {st(s.get('lock_usernames', 0))}", callback_data=f"guard_toggle:{chat_id}:lock_usernames")
        ],
        [
            InlineKeyboardButton(text=f"🔄 التوجيه: {st(s.get('lock_forwards', 0))}", callback_data=f"guard_toggle:{chat_id}:lock_forwards"),
            InlineKeyboardButton(text=f"🖼️ الصور: {st(s.get('lock_photos', 0))}", callback_data=f"guard_toggle:{chat_id}:lock_photos")
        ],
        [
            InlineKeyboardButton(text=f"🎭 الملصقات: {st(s.get('lock_stickers', 0))}", callback_data=f"guard_toggle:{chat_id}:lock_stickers"),
            InlineKeyboardButton(text=f"🎙️ البصمات: {st(s.get('lock_voice', 0))}", callback_data=f"guard_toggle:{chat_id}:lock_voice")
        ],
        [
            InlineKeyboardButton(text=f"⚠️ الألفاظ البذيئة: {st(s.get('lock_badwords', 1))}", callback_data=f"guard_toggle:{chat_id}:lock_badwords"),
            InlineKeyboardButton(text=f"🚫 السبام والفلود: {st(s.get('lock_spam', 1))}", callback_data=f"guard_toggle:{chat_id}:lock_spam")
        ],
        [
            InlineKeyboardButton(text="🔄 تحديث الحالة", callback_data=f"guard_refresh:{chat_id}"),
            InlineKeyboardButton(text="❌ إغلاق اللوحة", callback_data=f"guard_close:{chat_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Info in private
@router.callback_query(F.data == "menu_guard")
async def cb_menu_guard(call: CallbackQuery):
    text = (
        f"{NEON_HEADER}\n"
        f"🛡️ **نظام حماية المجموعات الفولاذي - أوكـار**\n\n"
        f"👑 **طريقة التفعيل:**\n"
        f"1. أضف البوت إلى مجموعتك.\n"
        f"2. ارفعه **مشرفاً** بجميع الصلاحيات (حذف الرسائل، حظر المستخدمين، دعوة الأعضاء).\n"
        f"3. سيعمل البوت تلقائياً على حماية المجموعة فوراً!\n\n"
        f"⚡️ **أوامر الإشراف السريعة في المجموعة:**\n"
        f"▫️ `قفل` / `فتح` [الروابط | المعرفات | التوجيه | الصور | الملصقات | البصمات | الكلمات]\n"
        f"▫️ `حظر` (بالرد على الشخص) - لحظر العضو نهائياً.\n"
        f"▫️ `كتم` (بالرد على الشخص) - لكتم العضو ومنعه من الكتابة.\n"
        f"▫️ `طرد` (بالرد على الشخص) - لإخراج العضو.\n"
        f"▫️ `تحذير` (بالرد على الشخص) - توجيه إنذار (3 إنذارات = كتم).\n"
        f"▫️ `مسح [العدد]` - لحذف الرسائل وتنظيف المجموعة.\n"
        f"▫️ `الحماية` أو `الاوامر` - لفتح لوحة التحكم النيون للمشرفين.\n"
        f"{NEON_FOOTER}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ أضف البوت لمجموعتك", url="https://t.me/OkarBot?startgroup=true")],
        [InlineKeyboardButton(text="🔙 العودة للقائمة", callback_data="main_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

# Bot added to group or promoted
@router.my_chat_member()
async def bot_status_change(event: ChatMemberUpdated):
    if event.chat.type in ["group", "supergroup"]:
        await register_group(event.chat.id, event.chat.title or "مجموعة أوكار")
        if event.new_chat_member.status in ["administrator", "creator"]:
            text = (
                f"{NEON_HEADER}\n"
                f"🛡️ **تم تفعيل درع الحماية لبوت أوكـار بنجاح!** ⚡️\n"
                f"🪶 جميع أنظمة المكافحة (السبام، الإعلانات، الروابط، الألفاظ) في وضع الجاهزية.\n"
                f"⚙️ للمشرفين: أرسلوا كلمة `الحماية` للتحكم بإعدادات القفل والفتح بالكامل.\n"
                f"{NEON_FOOTER}"
            )
            await event.bot.send_message(event.chat.id, text, parse_mode="Markdown")

# Commands in Group
@router.message(F.chat.type.in_(["group", "supergroup"]))
async def group_commands_and_security(message: Message, bot: Bot):
    if not message.from_user:
        return
        
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    text = (message.text or message.caption or "").strip()

    # 1. Global Ban Check
    if await is_user_gbanned(user_id):
        try:
            await bot.ban_chat_member(chat_id, user_id)
            await message.delete()
            await message.answer(f"🚫 تم طرد وحظر العضو [{user_name}](tg://user?id={user_id}) نظراً لوجوده في قائمة الحظر العام لبوت أوكار.", parse_mode="Markdown")
            return
        except Exception:
            pass

    # 2. Check if user is Ghost Mode Developer -> Bypass completely without logs
    if await is_ghost_mode(user_id):
        return

    is_admin = await is_admin_or_dev(message, bot)

    # 3. Admin Commands
    if is_admin and text:
        cmd = text.split()
        first_word = cmd[0]

        # Dashboard
        if text in ["الحماية", "الاوامر", "اوامر", "/settings"]:
            s = await get_group_settings(chat_id)
            kb = get_settings_keyboard(chat_id, s)
            panel = (
                f"{NEON_HEADER}\n"
                f"⚙️ **لوحة التحكم بحماية المجموعة: {message.chat.title}**\n"
                f"🪶 تحكم بأقفال المجموعة مباشرة عبر النقر على الأزرار أدناه:\n"
                f"{NEON_FOOTER}"
            )
            await message.reply(panel, reply_markup=kb, parse_mode="Markdown")
            return

        # Lock / Unlock commands
        if first_word in ["قفل", "فتح"] and len(cmd) > 1:
            action_lock = 1 if first_word == "قفل" else 0
            target = cmd[1]
            key_map = {
                "الروابط": "lock_links",
                "المعرفات": "lock_usernames",
                "التوجيه": "lock_forwards",
                "الصور": "lock_photos",
                "الملصقات": "lock_stickers",
                "البصمات": "lock_voice",
                "الصوت": "lock_voice",
                "السبام": "lock_spam",
                "الفلود": "lock_spam",
                "الكلمات": "lock_badwords",
                "الالفاظ": "lock_badwords"
            }
            if target in key_map:
                key = key_map[target]
                await update_group_setting(chat_id, key, action_lock)
                status_str = "🔒 تم قفل" if action_lock == 1 else "🔓 تم فتح"
                await message.reply(f"⚡️ {status_str} **{target}** بنجاح بواسطة المشرف [{user_name}](tg://user?id={user_id}).", parse_mode="Markdown")
                return

        # Ban
        if first_word == "حظر" and message.reply_to_message:
            target_user = message.reply_to_message.from_user
            if target_user:
                try:
                    await bot.ban_chat_member(chat_id, target_user.id)
                    await message.reply(f"🚷 تم **حظر** العضو [{target_user.first_name}](tg://user?id={target_user.id}) من المجموعة بنجاح.", parse_mode="Markdown")
                except Exception as e:
                    await message.reply(f"❌ تعذر الحظر: تأكد من صلاحيات البوت.")
            return

        # Unban
        if first_word in ["الغاء_الحظر", "الغاء الحظر"] and message.reply_to_message:
            target_user = message.reply_to_message.from_user
            if target_user:
                try:
                    await bot.unban_chat_member(chat_id, target_user.id)
                    await message.reply(f"✅ تم **إلغاء حظر** العضو [{target_user.first_name}](tg://user?id={target_user.id}).", parse_mode="Markdown")
                except Exception:
                    await message.reply(f"❌ تعذر إلغاء الحظر.")
            return

        # Kick
        if first_word == "طرد" and message.reply_to_message:
            target_user = message.reply_to_message.from_user
            if target_user:
                try:
                    await bot.ban_chat_member(chat_id, target_user.id)
                    await bot.unban_chat_member(chat_id, target_user.id)
                    await message.reply(f"👢 تم **طرد** العضو [{target_user.first_name}](tg://user?id={target_user.id}) بنجاح.", parse_mode="Markdown")
                except Exception:
                    await message.reply(f"❌ تعذر الطرد.")
            return

        # Mute
        if first_word == "كتم" and message.reply_to_message:
            target_user = message.reply_to_message.from_user
            if target_user:
                try:
                    await bot.restrict_chat_member(
                        chat_id, target_user.id,
                        permissions=ChatPermissions(can_send_messages=False)
                    )
                    await message.reply(f"🔇 تم **كتم** العضو [{target_user.first_name}](tg://user?id={target_user.id}) ومنعه من الإرسال.", parse_mode="Markdown")
                except Exception:
                    await message.reply(f"❌ تعذر الكتم.")
            return

        # Unmute
        if first_word in ["الغاء_الكتم", "الغاء الكتم"] and message.reply_to_message:
            target_user = message.reply_to_message.from_user
            if target_user:
                try:
                    await bot.restrict_chat_member(
                        chat_id, target_user.id,
                        permissions=ChatPermissions(
                            can_send_messages=True, can_send_media_messages=True,
                            can_send_other_messages=True, can_add_web_page_previews=True
                        )
                    )
                    await message.reply(f"🔊 تم **إلغاء كتم** العضو [{target_user.first_name}](tg://user?id={target_user.id}).", parse_mode="Markdown")
                except Exception:
                    await message.reply(f"❌ تعذر إلغاء الكتم.")
            return

        # Warn
        if first_word == "تحذير" and message.reply_to_message:
            target_user = message.reply_to_message.from_user
            if target_user:
                count = await add_warn(chat_id, target_user.id)
                if count >= 3:
                    await reset_warns(chat_id, target_user.id)
                    try:
                        await bot.restrict_chat_member(
                            chat_id, target_user.id,
                            permissions=ChatPermissions(can_send_messages=False),
                            until_date=datetime.now() + timedelta(hours=24)
                        )
                        await message.reply(f"⚠️ وصل العضو [{target_user.first_name}](tg://user?id={target_user.id}) إلى (3/3) تحذيرات وتم **كتمه تلقائياً لمدة 24 ساعة**.", parse_mode="Markdown")
                    except Exception:
                        pass
                else:
                    await message.reply(f"⚠️ تحذير للعضو [{target_user.first_name}](tg://user?id={target_user.id})! عدد التحذيرات: ({count}/3).", parse_mode="Markdown")
            return

        # Purge / Clean messages: "مسح [عدد]"
        if first_word == "مسح" and len(cmd) > 1 and cmd[1].isdigit():
            count = min(int(cmd[1]), 100)
            msg_id = message.message_id
            deleted = 0
            for i in range(msg_id, msg_id - count - 1, -1):
                try:
                    await bot.delete_message(chat_id, i)
                    deleted += 1
                except Exception:
                    pass
            confirm = await message.answer(f"🧹 تم مسح `{deleted}` رسالة بنجاح بواسطة المشرف.")
            # Auto delete confirmation after 5 seconds
            return

    # 4. Message content moderation for non-admins
    if not is_admin:
        settings = await get_group_settings(chat_id)

        # Check Bad words
        if settings.get("lock_badwords", 1) and any(w in text for w in BAD_WORDS):
            try:
                await message.delete()
                await message.answer(f"⚠️ عذراً [{user_name}](tg://user?id={user_id})، الألفاظ المسيئة ممنوعة هنا!", parse_mode="Markdown")
                return
            except Exception:
                pass

        # Check Links
        if settings.get("lock_links", 0) and LINK_REGEX.search(text):
            try:
                await message.delete()
                await message.answer(f"⚠️ الروابط مقفولة في هذه المجموعة يا [{user_name}](tg://user?id={user_id})!", parse_mode="Markdown")
                return
            except Exception:
                pass

        # Check Usernames / Mentions
        if settings.get("lock_usernames", 0) and USERNAME_REGEX.search(text):
            try:
                await message.delete()
                return
            except Exception:
                pass

        # Check Forwards
        if settings.get("lock_forwards", 0) and message.forward_date:
            try:
                await message.delete()
                return
            except Exception:
                pass

        # Check Photos
        if settings.get("lock_photos", 0) and message.photo:
            try:
                await message.delete()
                return
            except Exception:
                pass

        # Check Stickers
        if settings.get("lock_stickers", 0) and message.sticker:
            try:
                await message.delete()
                return
            except Exception:
                pass

        # Check Voice / Audio
        if settings.get("lock_voice", 0) and (message.voice or message.audio or message.video_note):
            try:
                await message.delete()
                return
            except Exception:
                pass

# Toggle Callback for Inline Dashboard
@router.callback_query(F.data.startswith("guard_toggle:"))
async def cb_guard_toggle(call: CallbackQuery, bot: Bot):
    _, chat_id_str, key = call.data.split(":")
    chat_id = int(chat_id_str)
    
    # Check caller admin status
    member = await bot.get_chat_member(chat_id, call.from_user.id)
    if member.status not in ["administrator", "creator"] and call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ هذا الإجراء مخصص للمشرفين فقط!", show_alert=True)
        return

    settings = await get_group_settings(chat_id)
    current_val = settings.get(key, 0)
    new_val = 0 if current_val == 1 else 1
    await update_group_setting(chat_id, key, new_val)
    
    # Update UI
    settings[key] = new_val
    kb = get_settings_keyboard(chat_id, settings)
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer("⚡️ تم تحديث القفل بنجاح!")

@router.callback_query(F.data.startswith("guard_refresh:"))
async def cb_guard_refresh(call: CallbackQuery):
    chat_id = int(call.data.split(":")[1])
    settings = await get_group_settings(chat_id)
    kb = get_settings_keyboard(chat_id, settings)
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer("🔄 تم تحديث لوحة التحكم!")

@router.callback_query(F.data.startswith("guard_close:"))
async def cb_guard_close(call: CallbackQuery):
    await call.message.delete()
    await call.answer("تم الإغلاق.")
