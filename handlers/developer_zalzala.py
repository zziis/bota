import asyncio
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, ChatPermissions
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import NEON_HEADER, NEON_FOOTER, ADMIN_IDS, DB_PATH
from database import (
    get_stats, get_all_users, get_all_groups, add_gban, remove_gban,
    is_user_gbanned, is_ghost_mode, set_ghost_mode
)

router = Router()

class DevState(StatesGroup):
    waiting_for_gban_id = State()
    waiting_for_ungban_id = State()
    waiting_for_broadcast_msg = State()
    waiting_for_freeze_id = State()

def get_dev_keyboard(ghost_active: bool) -> InlineKeyboardMarkup:
    ghost_text = "🥷 وضع الشبح (خيال 2.0): 🟢 مفعّل" if ghost_active else "🥷 وضع الشبح (خيال 2.0): ⚪ معطّل"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 إدارة المستخدمين", callback_data="dev_users_mgr"),
            InlineKeyboardButton(text="🌋 ترسانة زلزال ⚡️", callback_data="dev_zalzala_menu")
        ],
        [
            InlineKeyboardButton(text=ghost_text, callback_data="dev_toggle_ghost")
        ],
        [
            InlineKeyboardButton(text="📢 إذاعة للمستخدمين والكروبات", callback_data="dev_broadcast"),
            InlineKeyboardButton(text="💾 سحب نسخة قاعدة البيانات", callback_data="dev_backup_db")
        ],
        [
            InlineKeyboardButton(text="🔄 تحديث الإحصائيات", callback_data="menu_dev"),
            InlineKeyboardButton(text="🏛️ القائمة الرئيسية", callback_data="main_menu")
        ]
    ])

@router.callback_query(F.data == "menu_dev")
async def cb_menu_dev(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ عذراً، لوحة التحكم مخصصة للمطور الرئيسي فقط.", show_alert=True)
        return

    stats = await get_stats()
    ghost_active = await is_ghost_mode(call.from_user.id)
    ghost_status = "🟢 نشط ومخفي (خيال 2.0)" if ghost_active else "⚪ معطل"

    text = (
        f"{NEON_HEADER}\n"
        f"👑 **لوحة تحكم المطور الخارقة - نـظـام أوكـار 🪶**\n\n"
        f"📊 **إحصائيات النظام الفورية:**\n"
        f"▫️ إجمالي المستخدمين: `{stats['users']}` مستخدم\n"
        f"▫️ إجمالي المجموعات المحمية: `{stats['groups']}` مجموعة\n"
        f"▫️ المحظورين عام (G-Ban): `{stats['gbans']}` شخص\n"
        f"▫️ البلاغات والتذاكر المفتوحة: `{stats['open_tickets']}` تذكرة\n"
        f"▫️ وضع التخفي (خيال): {ghost_status}\n\n"
        f"⚡️ اختر القسم أو الترسانة من الأزرار أدناه:\n"
        f"{NEON_FOOTER}"
    )
    await call.message.edit_text(text, reply_markup=get_dev_keyboard(ghost_active), parse_mode="Markdown")
    await call.answer()

# Toggle Ghost Mode
@router.callback_query(F.data == "dev_toggle_ghost")
async def cb_dev_toggle_ghost(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    current = await is_ghost_mode(call.from_user.id)
    new_state = not current
    await set_ghost_mode(call.from_user.id, new_state)

    status_msg = "🥷 **تم تفعيل وضع الشبح (خيال 2.0)!**\nأنت الآن في وضع التخفي التام، لا تظهر في سجلات الرقابة وتعمل كالشبح الخفي." if new_state else "⚪ **تم تعطيل وضع الشبح.** عدت للظهور العادي."
    await call.answer("تم تبديل حالة وضع الشبح!", show_alert=True)
    await cb_menu_dev(call)

# Users Management Menu
@router.callback_query(F.data == "dev_users_mgr")
async def cb_dev_users_mgr(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    text = (
        f"{NEON_HEADER}\n"
        f"👥 **قسم إدارة المستخدمين والحظر الشامل**\n\n"
        f"⚡️ تحكم فوري بجميع مستخدمي البوت والمجموعات:\n"
        f"▫️ **الحظر العام (G-Ban):** حظر المستخدم وطرده من كل الكروبات التي يحميها أوكار.\n"
        f"▫️ **فك الحظر العام:** استعادة صلاحية المستخدم.\n"
        f"{NEON_FOOTER}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚫 حظر عام (G-Ban)", callback_data="dev_start_gban"),
            InlineKeyboardButton(text="🔓 فك حظر عام", callback_data="dev_start_ungban")
        ],
        [
            InlineKeyboardButton(text="🔙 عودة للوحة المطور", callback_data="menu_dev")
        ]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

# G-Ban input
@router.callback_query(F.data == "dev_start_gban")
async def cb_dev_start_gban(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(DevState.waiting_for_gban_id)
    await call.message.edit_text(
        "🚫 أرسل الآن **آيدي (ID)** المستخدم الذي تريد تطبيق الحظر العام (G-Ban) عليه وطردة من كل الكروبات:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="menu_dev")]
        ]),
        parse_mode="Markdown"
    )
    await call.answer()

@router.message(DevState.waiting_for_gban_id)
async def process_gban_id(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.reply("❌ يرجى إرسال رقم آيدي صحيح.")
        return
        
    target_id = int(raw)
    await state.clear()
    await add_gban(target_id, "حظر عام بقرار من المطور (زلزال)", message.from_user.id)

    # Execute kick across all groups
    groups = await get_all_groups()
    kicked_count = 0
    for gid in groups:
        try:
            await bot.ban_chat_member(gid, target_id)
            kicked_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.reply(
        f"⚡️🌋 **تم تنفيذ الحظر العام (G-Ban) بنجاح!**\n"
        f"👤 الآيدي: `{target_id}`\n"
        f"🏰 تم طرده وحظره من `{kicked_count}` مجموعة يحميها البوت.",
        parse_mode="Markdown"
    )

# Un-GBan input
@router.callback_query(F.data == "dev_start_ungban")
async def cb_dev_start_ungban(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(DevState.waiting_for_ungban_id)
    await call.message.edit_text(
        "🔓 أرسل الآن **آيدي (ID)** المستخدم لإلغاء الحظر العام عنه:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="menu_dev")]
        ]),
        parse_mode="Markdown"
    )
    await call.answer()

@router.message(DevState.waiting_for_ungban_id)
async def process_ungban_id(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.reply("❌ يرجى إرسال رقم آيدي صحيح.")
        return
    target_id = int(raw)
    await state.clear()
    await remove_gban(target_id)

    # Unban across groups
    groups = await get_all_groups()
    for gid in groups:
        try:
            await bot.unban_chat_member(gid, target_id)
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.reply(f"✅ تم إلغاء الحظر العام عن المستخدم `{target_id}` بنجاح.", parse_mode="Markdown")

# Quick G-ban button from support ticket
@router.callback_query(F.data.startswith("dev_gban_quick:"))
async def cb_dev_gban_quick(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in ADMIN_IDS:
        return
    target_id = int(call.data.split(":")[1])
    await add_gban(target_id, "حظر سريع من تذكرة الدعم", call.from_user.id)
    await call.answer(f"🚫 تم فرض الحظر العام على {target_id}!", show_alert=True)

# Zalzala Super Arsenal Menu
@router.callback_query(F.data == "dev_zalzala_menu")
async def cb_dev_zalzala_menu(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    text = (
        f"{NEON_HEADER}\n"
        f"🌋 **ترسانة إضافات زلزال المطور الخارقة ⚡️**\n\n"
        f"▫️ **تجميد المجموعة (Emergency Freeze):** قفل إرسال الرسائل لجميع الأعضاء فورياً.\n"
        f"▫️ **فك التجميد:** إعادة فتح المجموعة للجميع.\n"
        f"▫️ **زلزال التطهير (Nuke Cleanup):** طرد الحسابات المحذوفة والوهمية.\n"
        f"▫️ **الإذاعة العامة (Zalzala Broadcast):** بث إشعار لكافة المشتركين والمجموعات.\n\n"
        f"👇 اختر القوة التي تريد تفعيلها:\n"
        f"{NEON_FOOTER}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❄️ تجميد مجموعة محددة", callback_data="dev_freeze_prompt"),
            InlineKeyboardButton(text="🔥 فك تجميد مجموعة", callback_data="dev_unfreeze_prompt")
        ],
        [
            InlineKeyboardButton(text="📢 إذاعة زلزال الشاملة", callback_data="dev_broadcast"),
            InlineKeyboardButton(text="💾 سحب قاعدة البيانات", callback_data="dev_backup_db")
        ],
        [
            InlineKeyboardButton(text="🔙 عودة للوحة المطور", callback_data="menu_dev")
        ]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

# Group Freeze
@router.callback_query(F.data == "dev_freeze_prompt")
async def cb_dev_freeze_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(DevState.waiting_for_freeze_id)
    await state.update_data(action="freeze")
    await call.message.edit_text(
        "❄️ أرسل **آيدي المجموعة** (مثال: `-100123456789`) لتجميدها وإيقاف الرسائل فيها فورياً:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="dev_zalzala_menu")]
        ])
    )
    await call.answer()

@router.callback_query(F.data == "dev_unfreeze_prompt")
async def cb_dev_unfreeze_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(DevState.waiting_for_freeze_id)
    await state.update_data(action="unfreeze")
    await call.message.edit_text(
        "🔥 أرسل **آيدي المجموعة** (مثال: `-100123456789`) لفك التجميد عنها والسماح بالأحاديث:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="dev_zalzala_menu")]
        ])
    )
    await call.answer()

@router.message(DevState.waiting_for_freeze_id)
async def process_freeze_chat(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    action = data.get("action", "freeze")
    await state.clear()
    
    raw = (message.text or "").strip()
    try:
        chat_id = int(raw)
        if action == "freeze":
            await bot.set_chat_permissions(
                chat_id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            await message.reply(f"❄️🌋 **تم تفعيل زلزال التجميد بنجاح للمجموعة `{chat_id}`!**", parse_mode="Markdown")
            await bot.send_message(chat_id, "❄️ **تم تجميد المجموعة بقرار طارئ من مطور نظام أوكار.**", parse_mode="Markdown")
        else:
            await bot.set_chat_permissions(
                chat_id,
                permissions=ChatPermissions(
                    can_send_messages=True, can_send_media_messages=True,
                    can_send_other_messages=True, can_add_web_page_previews=True
                )
            )
            await message.reply(f"🔥 **تم فك تجميد المجموعة `{chat_id}` بنجاح.**", parse_mode="Markdown")
            await bot.send_message(chat_id, "🔥 **تم فك التجميد واستئناف المحادثة في المجموعة.**", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ حدث خطأ أثناء تنفيذ الإجراء: {e}")

# Database Backup Download
@router.callback_query(F.data == "dev_backup_db")
async def cb_dev_backup_db(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    if DB_PATH.exists():
        db_file = FSInputFile(str(DB_PATH), filename="okar_backup.sqlite")
        await call.message.answer_document(
            document=db_file,
            caption="💾 **نسخة احتياطية كاملة لقاعدة بيانات نظام أوكار.**\nتحتوي على كافة المجموعات، المستخدمين، وقوائم الحظر."
        )
        await call.answer("✅ تم تصدير قاعدة البيانات!")
    else:
        await call.answer("قاعدة البيانات فارغة أو غير موجودة.", show_alert=True)

# Broadcast
@router.callback_query(F.data == "dev_broadcast")
async def cb_dev_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(DevState.waiting_for_broadcast_msg)
    await call.message.edit_text(
        "📢 **أرسل الآن الرسالة التي ترغب في إذاعتها للجميع** (تدعم النصوص والصور والفيديو):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="menu_dev")]
        ]),
        parse_mode="Markdown"
    )
    await call.answer()

@router.message(DevState.waiting_for_broadcast_msg)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    
    users = await get_all_users()
    groups = await get_all_groups()
    targets = list(set(users + groups))

    progress = await message.reply(f"⏳ جاري إرسال الإذاعة الشاملة لـ `{len(targets)}` وجهة...", parse_mode="Markdown")

    sent = 0
    failed = 0

    header = f"{NEON_HEADER}\n📢 **إذاعة عامة من مطور أوكـار:**\n\n"
    footer = f"\n{NEON_FOOTER}"

    for tid in targets:
        try:
            if message.text:
                await bot.send_message(tid, f"{header}{message.text}{footer}", parse_mode="Markdown")
            elif message.photo:
                await bot.send_photo(tid, message.photo[-1].file_id, caption=f"{header}{message.caption or ''}{footer}", parse_mode="Markdown")
            elif message.video:
                await bot.send_video(tid, message.video.file_id, caption=f"{header}{message.caption or ''}{footer}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.04)
        except Exception:
            failed += 1

    await progress.edit_text(
        f"✅ **اكتملت الإذاعة الشاملة بنجاح!**\n"
        f"▫️ تم التسليم: `{sent}`\n"
        f"▫️ تعذر التسليم: `{failed}`",
        parse_mode="Markdown"
    )
