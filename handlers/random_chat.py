from aiogram import Router, F
from aiogram.dispatcher.event.bases import SkipHandler, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import NEON_HEADER, NEON_FOOTER
from database import (
    get_user, set_user_gender, join_random_queue, leave_random_queue,
    find_random_match, create_active_chat, get_active_chat_partner,
    end_active_chat, create_ticket
)

router = Router()

def get_random_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 بحث عشوائي عام", callback_data="find_partner:any"),
        ],
        [
            InlineKeyboardButton(text="👨 البحث عن شريك (شاب)", callback_data="find_partner:male"),
            InlineKeyboardButton(text="👩 البحث عن شريكة (فتاة)", callback_data="find_partner:female")
        ],
        [
            InlineKeyboardButton(text="⚙️ تحديد جنسي (ذكر / أنثى)", callback_data="set_my_gender")
        ],
        [
            InlineKeyboardButton(text="🔙 العودة للقائمة", callback_data="main_menu")
        ]
    ])

def get_in_chat_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏭️ التالي (شريك جديد)", callback_data="chat_next"),
            InlineKeyboardButton(text="🛑 إنهاء المحادثة", callback_data="chat_stop")
        ],
        [
            InlineKeyboardButton(text="🤝 طلب كشف الهوية", callback_data="chat_reveal"),
            InlineKeyboardButton(text="🚨 إبلاغ عن إساءة", callback_data="chat_report")
        ]
    ])

@router.callback_query(F.data == "menu_random")
async def cb_menu_random(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    current_gender = user.get("gender", "unknown") if user else "unknown"
    gender_text = "👨 ذكر" if current_gender == "male" else ("👩 أنثى" if current_gender == "female" else "❓ غير محدد")

    text = (
        f"{NEON_HEADER}\n"
        f"👥 **قسم التعارف والبحث العشوائي المشفر**\n"
        f"🔒 دردشة سرية مجهولة 1-on-1 دون كشف هويتك أو حسابك.\n\n"
        f"▫️ **جنسك الحالي المسجل:** {gender_text}\n"
        f"▫️ يمكنك تحديد من ترغب بالتحدث معه أو اختيار البحث العشوائي السريع.\n\n"
        f"👇 **اختر نوع البحث للبدء:**\n"
        f"{NEON_FOOTER}"
    )
    await call.message.edit_text(text, reply_markup=get_random_main_kb(), parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data == "set_my_gender")
async def cb_set_my_gender(call: CallbackQuery):
    text = (
        f"{NEON_HEADER}\n"
        f"⚙️ **تحديد جنسك في نظام أوكـار:**\n"
        f"يساعد هذا في توجيه طلبات التعارف لمن يبحث عن شريك محدد بدقة.\n"
        f"{NEON_FOOTER}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨 أنا شاب (ذكر)", callback_data="save_gender:male"),
            InlineKeyboardButton(text="👩 أنا فتاة (أنثى)", callback_data="save_gender:female")
        ],
        [InlineKeyboardButton(text="🔙 عودة", callback_data="menu_random")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data.startswith("save_gender:"))
async def cb_save_gender(call: CallbackQuery):
    gender = call.data.split(":")[1]
    await set_user_gender(call.from_user.id, gender)
    await call.answer("✅ تم حفظ جنسك بنجاح!", show_alert=True)
    await cb_menu_random(call)

@router.callback_query(F.data.startswith("find_partner:"))
async def cb_find_partner(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    pref = call.data.split(":")[1]

    # Check if already in active chat
    existing_partner = await get_active_chat_partner(user_id)
    if existing_partner:
        await call.answer("أنت بالفعل في محادثة نشطة!", show_alert=True)
        return

    user = await get_user(user_id)
    my_gender = user.get("gender", "any") if user else "any"

    # Search for match
    match_id = await find_random_match(user_id, my_gender, pref)
    if match_id:
        # Match found!
        await create_active_chat(user_id, match_id)
        msg_text = (
            f"{NEON_HEADER}\n"
            f"🎉 **تم العثور على شريك محادثة بنجاح!**\n"
            f"💬 يمكنكما الآن التحدث بكل حرية وأمان.\n"
            f"🔒 المحادثة مشفرة ومجهولة الهوية تماماً.\n"
            f"{NEON_FOOTER}"
        )
        chat_kb = get_in_chat_kb()
        await call.message.edit_text(msg_text, reply_markup=chat_kb, parse_mode="Markdown")
        try:
            await bot.send_message(match_id, msg_text, reply_markup=chat_kb, parse_mode="Markdown")
        except Exception:
            pass
        await call.answer()
    else:
        # Add to queue
        await join_random_queue(user_id, my_gender, pref)
        wait_text = (
            f"{NEON_HEADER}\n"
            f"⏳ **جاري البحث عن شريك مناسب في شبكة أوكـار...**\n"
            f"⚡️ سنقوم بربطك تلقائياً بمجرد توفر شخص يطابق طلبك.\n"
            f"{NEON_FOOTER}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء البحث والعودة", callback_data="cancel_random_search")]
        ])
        await call.message.edit_text(wait_text, reply_markup=kb, parse_mode="Markdown")
        await call.answer()

@router.callback_query(F.data == "cancel_random_search")
async def cb_cancel_random_search(call: CallbackQuery):
    await leave_random_queue(call.from_user.id)
    await cb_menu_random(call)

@router.callback_query(F.data == "chat_stop")
async def cb_chat_stop(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    partner_id = await end_active_chat(user_id)
    
    farewell_caller = (
        f"{NEON_HEADER}\n"
        f"🛑 **تم إنهاء المحادثة بنجاح.**\n"
        f"يمكنك العودة للقائمة أو بدء بحث جديد.\n"
        f"{NEON_FOOTER}"
    )
    await call.message.edit_text(farewell_caller, reply_markup=get_random_main_kb(), parse_mode="Markdown")
    
    if partner_id:
        farewell_partner = (
            f"{NEON_HEADER}\n"
            f"🚶‍♂️ **قام الشريك بإنهاء المحادثة.**\n"
            f"نتمنى لك أوقاتاً ممتعة، يمكنك البحث عن شريك آخر الآن.\n"
            f"{NEON_FOOTER}"
        )
        try:
            await bot.send_message(partner_id, farewell_partner, reply_markup=get_random_main_kb(), parse_mode="Markdown")
        except Exception:
            pass
    await call.answer()

@router.callback_query(F.data == "chat_next")
async def cb_chat_next(call: CallbackQuery, bot: Bot):
    # End current and search again
    user_id = call.from_user.id
    partner_id = await end_active_chat(user_id)
    if partner_id:
        try:
            await bot.send_message(
                partner_id,
                f"{NEON_HEADER}\n🚶‍♂️ **انتقل الشريك إلى محادثة أخرى.**\n{NEON_FOOTER}",
                reply_markup=get_random_main_kb(), parse_mode="Markdown"
            )
        except Exception:
            pass
    
    # Re-queue
    user = await get_user(user_id)
    my_gender = user.get("gender", "any") if user else "any"
    match_id = await find_random_match(user_id, my_gender, "any")
    if match_id:
        await create_active_chat(user_id, match_id)
        msg_text = (
            f"{NEON_HEADER}\n"
            f"🎉 **تم العثور على شريك جديد فوراً!**\n"
            f"💬 يمكنكما التحدث الآن.\n"
            f"{NEON_FOOTER}"
        )
        chat_kb = get_in_chat_kb()
        await call.message.edit_text(msg_text, reply_markup=chat_kb, parse_mode="Markdown")
        try:
            await bot.send_message(match_id, msg_text, reply_markup=chat_kb, parse_mode="Markdown")
        except Exception:
            pass
    else:
        await join_random_queue(user_id, my_gender, "any")
        wait_text = (
            f"{NEON_HEADER}\n"
            f"⏳ **جاري البحث عن شريك جديد...**\n"
            f"{NEON_FOOTER}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء البحث", callback_data="cancel_random_search")]
        ])
        await call.message.edit_text(wait_text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data == "chat_reveal")
async def cb_chat_reveal(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    partner_id = await get_active_chat_partner(user_id)
    if not partner_id:
        await call.answer("لا توجد محادثة نشطة حالياً!", show_alert=True)
        return
        
    caller_name = call.from_user.first_name
    caller_user = f"@{call.from_user.username}" if call.from_user.username else f"tg://user?id={user_id}"
    
    notify_partner = (
        f"🤝 **طلب كشف الهوية:**\n"
        f"الشريك يود تبادل الحسابات والتواصل معك خارج البوت!\n"
        f"👤 حسابه: [{caller_name}]({caller_user})"
    )
    try:
        await bot.send_message(partner_id, notify_partner, parse_mode="Markdown")
        await call.answer("✅ تم إرسال طلب كشف الهوية لشريكك!", show_alert=True)
    except Exception:
        await call.answer("تعذر الإرسال.")

@router.callback_query(F.data == "chat_report")
async def cb_chat_report(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    partner_id = await end_active_chat(user_id)
    if partner_id:
        await create_ticket(user_id, "abuse_report", f"Report against user_id: {partner_id}")
        await call.answer("🚨 تم تسجيل البلاغ وإنهاء المحادثة لحمايتك.", show_alert=True)
        await call.message.edit_text("🚨 تم حظر الشريك وتقديم بلاغ للإدارة.", reply_markup=get_random_main_kb())
        try:
            await bot.send_message(partner_id, "⚠️ تم إنهاء المحادثة بسبب تلقي بلاغ إساءة.", reply_markup=get_random_main_kb())
        except Exception:
            pass
    else:
        await call.answer("لا توجد محادثة نشطة.")

# Relay messages between partners in private chat
@router.message(F.chat.type == "private")
async def relay_random_chat_messages(message: Message, bot: Bot):
    # Ignore commands
    if message.text and message.text.startswith("/"):
        return

    user_id = message.from_user.id
    partner_id = await get_active_chat_partner(user_id)
    if not partner_id:
        raise SkipHandler()  # اسمح لمعالج مراسلة الإدارة باستلام الرسالة

    # Relay content safely
    try:
        if message.text:
            await bot.send_message(partner_id, f"💬 **الشريك:** {message.text}", parse_mode="Markdown")
        elif message.sticker:
            await bot.send_sticker(partner_id, message.sticker.file_id)
        elif message.photo:
            await bot.send_photo(partner_id, message.photo[-1].file_id, caption="📷 صورة من الشريك")
        elif message.voice:
            await bot.send_voice(partner_id, message.voice.file_id, caption="🎙️ بصمة من الشريك")
        elif message.video:
            await bot.send_video(partner_id, message.video.file_id, caption="🎥 فيديو من الشريك")
        elif message.audio:
            await bot.send_audio(partner_id, message.audio.file_id, caption="🎵 صوتية من الشريك")
    except Exception as e:
        await message.reply("⚠️ تعذر إيصال الرسالة، قد يكون الشريك غادر.")
