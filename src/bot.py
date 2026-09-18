import os
import uuid
import logging
from urllib.parse import quote
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

def make_miniapp_button(path: str, label: str, name: str = "") -> InlineKeyboardButton:
    """إنشاء زر Mini App متوافق مع HTTPS والرابط المحلي"""
    safe_name = quote(name or "", safe="")
    base = (BASE_URL or "").strip().rstrip("/")
    # Telegram يقبل روابط أزرار URL العامة فقط بصيغة صحيحة.
    # على Railway نستخدم RAILWAY_PUBLIC_DOMAIN تلقائياً من config.py.
    if not base.startswith(("https://", "http://")):
        base = "https://" + base.lstrip("/")
    full_url = f"{base}{path}?name={safe_name}"
    if base.startswith("https://"):
        return InlineKeyboardButton(text=label, web_app=WebAppInfo(url=full_url))
    # هذا الفرع للتطوير المحلي فقط؛ لا ترسله Telegram كرابط localhost.
    logger.warning("BASE_URL غير HTTPS (%s). اضبط BASE_URL على رابط Railway العام.", base)
    return InlineKeyboardButton(text=label, callback_data="webapp_url_missing")

# لوحة الأزرار الرئيسية الشاملة لجميع أقسام خيال
def get_user_super_keyboard(name: str = "") -> InlineKeyboardMarkup:
    buttons = [
        [
            make_miniapp_button("/crash", "🚀 لعبة الطيارة (Crash)", name),
            make_miniapp_button("/games", "🎮 ألعاب وتحدي الخصوم", name)
        ],
        [
            make_miniapp_button("/radio", "📻 راديو خيال FM مباشر", name),
            make_miniapp_button("/shop", "💎 المتجر ورصيد النقاط", name)
        ],
        [
            make_miniapp_button("/call", "📞 مكالمة صوت وفيديو مباشرة", name)
        ],
        [
            InlineKeyboardButton(text="🎁 هديتي اليومية", callback_data="claim_daily"),
            InlineKeyboardButton(text="💰 رصيدي", callback_data="my_balance")
        ],
        [
            InlineKeyboardButton(text="💬 حول خيال", callback_data="help_info")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# لوحة تحكم الأدمن للرسالة المحولة
def get_admin_message_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📞 بدء مكالمة معه", callback_data=f"admin_call_{user_id}"),
            InlineKeyboardButton(text="🚫 حظر المستخدم", callback_data=f"admin_ban_{user_id}")
        ],
        [
            InlineKeyboardButton(text="➕ شحن نقاط له", callback_data=f"admin_quick_pts_{user_id}"),
            InlineKeyboardButton(text="ℹ️ معلومات المستخدم", callback_data=f"admin_info_{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.callback_query(F.data == "webapp_url_missing")
async def webapp_url_missing(callback: CallbackQuery):
    await callback.answer("رابط التطبيق غير مضبوط. أضف BASE_URL كرابط Railway العام HTTPS.", show_alert=True)

# =================== معالجات الأوامر ===================

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    """الترحيب الشامل بالمستخدم في منصة خيال"""
    user = message.from_user
    await db.add_or_update_user(user.id, user.username, user.full_name)

    if await db.is_user_banned(user.id):
        await message.reply("🚫 <b>عذراً، حسابك محظور من استخدام البوت.</b>")
        return

    pts = await db.get_points(user.id)
    welcome_text = (
        f"🌌 <b>أهلاً بك في منصة وتطبيق {APP_NAME} المتكامل!</b>\n\n"
        f"💎 <b>رصيد نقاطك الحالي:</b> <code>{pts:,}</code> نقطة\n\n"
        "<b>اختر القسم الذي تريد الدخول إليه:</b>\n"
        "• 🚀 <b>لعبة الطيارة:</b> ضاعف نقاطك واكسب قبل انفجار الطائرة!\n"
        "• 🎮 <b>ألعاب وتحدي الخصوم:</b> العب X-O فردي أو ابحث عن خصم حقيقي.\n"
        "• 📻 <b>راديو خيال FM:</b> استمع لأقوى الإذاعات المباشرة ومسجل الصوت.\n"
        "• 💎 <b>شراء النقاط:</b> باقات شحن متنوعة وهدايا يومية مجانية.\n"
        "• 📞 <b>المكالمات:</b> تحدث مع الإدارة بصوت وفيديو مباشر.\n"
        "• ✉️ <b>تواصل فوري:</b> يمكنك إرسال رسالتك أو صورك هنا وسنرد عليك."
    )

    avatar_path = os.path.join(BASE_DIR, "assets", "avatar.jpg")
    keyboard = get_user_super_keyboard(name=user.full_name)

    if os.path.exists(avatar_path):
        try:
            photo = FSInputFile(avatar_path)
            await message.answer_photo(photo=photo, caption=welcome_text, reply_markup=keyboard)
            return
        except Exception as e:
            logger.warning(f"تعذر إرسال الصورة: {e}")

    await message.answer(welcome_text, reply_markup=keyboard)

@dp.message(Command("points"))
@dp.message(Command("balance"))
async def handle_points_cmd(message: types.Message):
    """عرض رصيد النقاط"""
    user = message.from_user
    pts = await db.get_points(user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_miniapp_button("/shop", "🛒 فتح المتجر وشحن النقاط", user.full_name)],
        [InlineKeyboardButton(text="🎁 استلام الهدية اليومية (+100)", callback_data="claim_daily")]
    ])
    await message.reply(
        f"💰 <b>محفظة نقاط خيال الخاصة بك:</b>\n\n"
        f"• رصيدك: <b>{pts:,}</b> نقطة 💎\n"
        "يمكنك استخدام نقاطك في لعبة الطيارة، ومباريات التحدي، أو طلب مكالمات مميزة.",
        reply_markup=kb
    )

@dp.message(Command("daily"))
async def handle_daily_cmd(message: types.Message):
    """استلام الهدية اليومية عبر الأمر"""
    user = message.from_user
    res = await db.claim_daily_bonus(user.id, 100)
    if res["success"]:
        await message.reply(f"🎉 {res['message']}\nرصيدك الحالي: <b>{res['points']:,}</b> نقطة!")
    else:
        await message.reply(f"⏳ {res['message']}")

@dp.message(Command("crash"))
async def handle_crash_cmd(message: types.Message):
    user = message.from_user
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_miniapp_button("/crash", "🚀 دخول لعبة الطيارة الآن", user.full_name)]
    ])
    await message.reply(
        "🚀 <b>لعبة الطيارة (Crash / Aviator):</b>\n"
        "ضع رهانك من النقاط، راقب تصاعد الطائرة والمضاعف، واسحب أرباحك قبل أن تنفجر!",
        reply_markup=kb
    )

@dp.message(Command("games"))
async def handle_games_cmd(message: types.Message):
    user = message.from_user
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_miniapp_button("/games", "🎮 فتح صالة الألعاب والتحدي", user.full_name)]
    ])
    await message.reply("🎮 <b>ألعاب خيال:</b> العب X-O وتحدَّ الذكاء الاصطناعي أو نافس خصوماً أونلاين!", reply_markup=kb)

@dp.message(Command("radio"))
async def handle_radio_cmd(message: types.Message):
    user = message.from_user
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_miniapp_button("/radio", "📻 تشغيل راديو خيال FM", user.full_name)]
    ])
    await message.reply("📻 <b>راديو خيال FM:</b> استمع لأقوى المحطات الحية (القرآن، نجوم، روتانا، أخبار، ولوفاي).", reply_markup=kb)

@dp.message(Command("addpoints"))
async def handle_addpoints_cmd(message: types.Message):
    """أمر إداري لإضافة أو خصم نقاط من أي مستخدم: /addpoints 123456 1000"""
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not (parts[2].isdigit() or (parts[2].startswith("-") and parts[2][1:].isdigit())):
        await message.reply("⚠️ الاستخدام الصحيح:\n<code>/addpoints 123456789 1000</code>")
        return
    
    target_id = int(parts[1])
    amount = int(parts[2])
    new_pts = await db.update_points(target_id, amount, "admin_grant", "تعديل رصيد من الإدارة")
    await message.reply(f"✅ تم تعديل رصيد المستخدم <code>{target_id}</code> بمقدار <b>{amount:+}</b> نقطة.\nالرصيد الحالي: <b>{new_pts:,}</b> نقطة.")
    
    # إشعار المستخدم
    try:
        if amount > 0:
            await bot.send_message(target_id, f"🎁 <b>مبروك! قامت إدارة خيال بإضافة {amount:,} نقطة إلى رصيدك.</b>\nرصيدك الإجمالي: <b>{new_pts:,}</b> نقطة 💎")
    except Exception:
        pass

@dp.message(Command("stats"))
async def handle_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    stats = await db.get_stats()
    text = (
        "📊 <b>إحصائيات منصة خيال الشاملة:</b>\n\n"
        f"👥 <b>إجمالي المستخدمين:</b> {stats['total_users']}\n"
        f"💎 <b>إجمالي النقاط المتداولة:</b> {stats.get('total_points', 0):,} نقطة\n"
        f"💬 <b>الرسائل المتبادلة:</b> {stats['total_messages']}\n"
        f"📞 <b>المكالمات:</b> {stats['total_calls']}\n"
        f"🚫 <b>المحظورين:</b> {stats['banned_users']}"
    )
    await message.reply(text)

@dp.message(Command("broadcast"))
async def handle_broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⚠️ اكتب الرسالة بعد الأمر:\n<code>/broadcast مرحباً بكم في خيال</code>")
        return
    broadcast_text = parts[1]
    users = await db.get_all_users()
    sent = 0
    fail = 0
    st = await message.reply(f"⏳ جاري الإذاعة إلى {len(users)} مشترك...")
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 <b>إعلان من إدارة خيال:</b>\n\n{broadcast_text}")
            sent += 1
        except Exception:
            fail += 1
    await st.edit_text(f"✅ تمت الإذاعة بنجاح:\n• تم الإرسال: {sent}\n• فشل (حظروا البوت): {fail}")

@dp.message(Command("ban"))
async def handle_ban_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("⚠️ الاستخدام: <code>/ban 12345678</code>")
        return
    target_id = int(parts[1])
    await db.set_user_ban(target_id, True)
    await message.reply(f"✅ تم حظر المستخدم <code>{target_id}</code>.")

@dp.message(Command("unban"))
async def handle_unban_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("⚠️ الاستخدام: <code>/unban 12345678</code>")
        return
    target_id = int(parts[1])
    await db.set_user_ban(target_id, False)
    await message.reply(f"✅ تم إلغاء حظر المستخدم <code>{target_id}</code>.")

# =================== معالجة الرسائل العادية ===================

@dp.message(F.chat.type == "private")
async def handle_all_messages(message: types.Message):
    sender = message.from_user
    is_admin = sender.id in ADMIN_IDS

    # رد المشرف
    if is_admin and message.reply_to_message:
        reply_to_id = message.reply_to_message.message_id
        mapping = await db.get_user_by_admin_message(reply_to_id, message.chat.id)
        if mapping:
            target_user_id = mapping["user_id"]
            try:
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
                await message.reply("✅ <b>تم تسليم ردك للمستخدم بنجاح!</b>")
                return
            except Exception as e:
                await message.reply(f"❌ تعذر التسليم: {e}")
                return

    if is_admin:
        await message.reply(
            "👑 <b>لوحة المشرف:</b> للرد على أي مستخدم، قم بعمل (Reply) على رسالته المحولة.\n"
            "الأوامر المتاحة: /stats, /broadcast, /addpoints, /ban, /unban"
        )
        return

    # المستخدم العادي
    if await db.is_user_banned(sender.id):
        await message.reply("🚫 حسابك محظور من التواصل.")
        return

    await db.add_or_update_user(sender.id, sender.username, sender.full_name)

    header = (
        "📩 <b>رسالة جديدة واردة عبر خيال</b>\n"
        f"👤 <b>المرسل:</b> {sender.full_name} (@{sender.username or 'بدون'})\n"
        f"🆔 <b>الآيدي:</b> <code>{sender.id}</code>\n"
        "------------------------------------"
    )
    admin_kb = get_admin_message_keyboard(sender.id)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=header)
            admin_msg = await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=admin_kb
            )
            await db.save_message_mapping(
                user_id=sender.id,
                user_message_id=message.message_id,
                admin_message_id=admin_msg.message_id,
                admin_chat_id=admin_id
            )
        except Exception as e:
            logger.error(f"خطأ تحويل الرسالة للمشرف {admin_id}: {e}")

    await message.reply("✅ <b>تم استلام رسالتك بنجاح!</b>\nسيقوم فريق خيال بالرد عليك قريباً.")

# =================== استجابات الـ Callbacks ===================

@dp.callback_query(F.data == "claim_daily")
async def cb_claim_daily(query: CallbackQuery):
    res = await db.claim_daily_bonus(query.from_user.id, 100)
    await query.answer(res["message"], show_alert=True)

@dp.callback_query(F.data == "my_balance")
async def cb_my_balance(query: CallbackQuery):
    pts = await db.get_points(query.from_user.id)
    await query.answer(f"رصيدك الحالي: {pts:,} نقطة 💎", show_alert=True)

@dp.callback_query(F.data == "help_info")
async def cb_help_info(query: CallbackQuery):
    await query.answer()
    info = (
        f"✨ <b>منصة {APP_NAME} الشاملة:</b>\n\n"
        "• 🚀 <b>لعبة الطيارة:</b> العب واربح نقاط حقيقية.\n"
        "• 🎮 <b>ألعاب الخصوم:</b> مباريات X-O أونلاين ضد لاعبين.\n"
        "• 📻 <b>راديو FM:</b> بث حي لإذاعات القرآن والموسيقى والأخبار.\n"
        "• 📞 <b>مكالمات WebRTC:</b> صوت وفيديو بدقة فائقة.\n"
        "• 💎 <b>متجر النقاط:</b> شحن وهدايا يومية مجانية."
    )
    await query.message.answer(info)

@dp.callback_query(F.data.startswith("approve_pts_"))
async def cb_approve_points(query: CallbackQuery):
    """موافقة المشرف على طلب شحن نقاط"""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("غير مصرح لك.", show_alert=True)
        return

    req_id = int(query.data.replace("approve_pts_", ""))
    req = await db.get_point_request(req_id)
    if not req or req["status"] != "pending":
        await query.answer("هذا الطلب تمت معالجته مسبقاً!", show_alert=True)
        return

    # شحن النقاط
    new_pts = await db.update_points(req["user_id"], req["points"], "store_purchase", f"شحن باقة {req['package_name']}")
    await db.set_point_request_status(req_id, "approved")
    await query.answer("تم قبول الطلب وشحن النقاط بنجاح!", show_alert=True)
    await query.message.edit_text(
        f"✅ <b>تم قبول طلب الشحن #{req_id} بنجاح!</b>\n"
        f"تمت إضافة <b>{req['points']:,}</b> نقطة لحساب المستخدم <code>{req['user_id']}</code>.\n"
        f"رصيده الحالي: <b>{new_pts:,}</b> نقطة."
    )

    # إشعار العميل في تلجرام
    try:
        await bot.send_message(
            chat_id=req["user_id"],
            text=(
                f"🎉 <b>مبروك! تم تأكيد وشحن باقتك في خيال بنجاح:</b>\n\n"
                f"📦 <b>الباقة:</b> {req['package_name']}\n"
                f"💎 <b>النقاط المضافة:</b> +{req['points']:,} نقطة\n"
                f"💰 <b>رصيدك الجديد:</b> {new_pts:,} نقطة 💎\n\n"
                "<i>نتمنى لك وقتاً ممتعاً في ألعاب خيال ومكالماتها!</i>"
            )
        )
    except Exception as e:
        logger.error(f"فشل إشعار المستخدم بالشحن: {e}")

@dp.callback_query(F.data.startswith("reject_pts_"))
async def cb_reject_points(query: CallbackQuery):
    """رفض طلب شحن النقاط"""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("غير مصرح لك.", show_alert=True)
        return

    req_id = int(query.data.replace("reject_pts_", ""))
    await db.set_point_request_status(req_id, "rejected")
    await query.answer("تم رفض الطلب.", show_alert=True)
    await query.message.edit_text(f"❌ <b>تم رفض طلب الشحن #{req_id}.</b>")

@dp.callback_query(F.data.startswith("admin_quick_pts_"))
async def cb_admin_quick_pts(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS:
        return
    uid = int(query.data.replace("admin_quick_pts_", ""))
    new_pts = await db.update_points(uid, 500, "admin_grant", "هدية سريعة 500 نقطة")
    await query.answer(f"تمت إضافة 500 نقطة! الرصيد: {new_pts}", show_alert=True)
    try:
        await bot.send_message(uid, f"🎁 حصلت على 500 نقطة هدية من الإدارة! رصيدك: {new_pts:,} نقطة 💎")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("admin_ban_"))
async def cb_admin_ban(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS:
        return
    target_id = int(query.data.replace("admin_ban_", ""))
    await db.set_user_ban(target_id, True)
    await query.answer("تم حظر المستخدم بنجاح!", show_alert=True)
    await query.message.reply(f"🚫 تم حظر المستخدم <code>{target_id}</code>.")

@dp.callback_query(F.data.startswith("admin_info_"))
async def cb_admin_info(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS:
        return
    target_id = int(query.data.replace("admin_info_", ""))
    pts = await db.get_points(target_id)
    await query.answer()
    await query.message.reply(
        f"ℹ️ <b>معلومات المستخدم:</b>\n"
        f"• <b>الآيدي:</b> <code>{target_id}</code>\n"
        f"• <b>النقاط:</b> {pts:,} نقطة 💎\n"
        f"• <b>الرابط المباشر:</b> tg://user?id={target_id}"
    )

@dp.callback_query(F.data.startswith("admin_call_"))
async def cb_admin_call(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS:
        return
    target_id = int(query.data.replace("admin_call_", ""))
    room_id = f"khayal-{uuid.uuid4().hex[:8]}"

    user_call_kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_miniapp_button(f"/call?room={room_id}", "📞 قبول ودخول المكالمة", "مستخدم")]
    ])
    try:
        await bot.send_message(
            chat_id=target_id,
            text="📞 <b>إدارة خيال تدعوك لمكالمة صوت/فيديو مباشرة!</b>\nاضغط على الزر أدناه للدخول فوراً:",
            reply_markup=user_call_kb
        )
        admin_call_kb = InlineKeyboardMarkup(inline_keyboard=[
            [make_miniapp_button(f"/call?room={room_id}", "📞 دخول غرفة المكالمة الآن", "المشرف")]
        ])
        await query.message.reply("✅ تم إرسال دعوة المكالمة للمستخدم!", reply_markup=admin_call_kb)
    except Exception as e:
        await query.message.reply(f"❌ تعذر إرسال الدعوة: {e}")
