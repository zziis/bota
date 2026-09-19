from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import NEON_HEADER, NEON_FOOTER, ADMIN_IDS
from database import create_ticket

router = Router()

class SupportState(StatesGroup):
    waiting_for_user_message = State()
    waiting_for_dev_reply = State()

@router.callback_query(F.data == "menu_support")
async def cb_menu_support(call: CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.waiting_for_user_message)
    text = (
        f"{NEON_HEADER}\n"
        f"📩 **قسم المراسلة المباشرة مع إدارة ومطور أوكـار**\n\n"
        f"💬 اكتب رسالتك أو استفسارك الآن في رد على هذه الرسالة، وسيقوم المطور بالرد عليك مباشرة عبر البوت.\n"
        f"📌 يمكنك إرسال نصوص، صور، أو رسائل صوتية.\n\n"
        f"⚡️ للإلغاء والعودة: اضغط الزر بالأسفل.\n"
        f"{NEON_FOOTER}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء والعودة", callback_data="cancel_support")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data == "cancel_support")
async def cb_cancel_support(call: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏛️ القائمة الرئيسية", callback_data="main_menu")]
    ])
    await call.message.edit_text("⚡️ تم إلغاء الإرسال والعودة للقائمة الرئيسية.", reply_markup=kb)
    await call.answer()

# Receive message from user
@router.message(SupportState.waiting_for_user_message)
async def process_user_support_message(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    if not user:
        return
        
    await state.clear()
    msg_content = message.text or message.caption or "محتوى وسائط (صورة/صوت/ملف)"
    ticket_id = await create_ticket(user.id, "support", msg_content)

    # Notify user
    confirm_text = (
        f"{NEON_HEADER}\n"
        f"✅ **تم إرسال رسالتك إلى إدارة ومطور أوكـار بنجاح!**\n"
        f"🎫 رقم التذكرة: `#{ticket_id}`\n"
        f"⏳ سيصلك الرد هنا مباشرة بمجرد قراءته.\n"
        f"{NEON_FOOTER}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏛️ القائمة الرئيسية", callback_data="main_menu")]
    ])
    await message.reply(confirm_text, reply_markup=kb, parse_mode="Markdown")

    # Send to Developers
    dev_alert = (
        f"⚡️ **رسالة دعم فني جديدة!** ⚡️\n"
        f"👤 المستخدم: [{user.first_name}](tg://user?id={user.id})\n"
        f"🆔 الآيدي: `{user.id}`\n"
        f"🏷 المعرف: @{user.username or 'بدون معرف'}\n"
        f"🎫 تذكرة رقم: `#{ticket_id}`\n"
        f"───────────────\n"
        f"📝 **نص الرسالة:**\n{message.text or ''}"
    )
    dev_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ الرد على المستخدم", callback_data=f"dev_reply:{user.id}:{ticket_id}")],
        [InlineKeyboardButton(text="🚫 حظر عام للمستخدم", callback_data=f"dev_gban_quick:{user.id}")]
    ])

    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(admin_id, message.photo[-1].file_id, caption=dev_alert, reply_markup=dev_kb, parse_mode="Markdown")
            elif message.voice:
                await bot.send_voice(admin_id, message.voice.file_id, caption=dev_alert, reply_markup=dev_kb, parse_mode="Markdown")
            else:
                await bot.send_message(admin_id, dev_alert, reply_markup=dev_kb, parse_mode="Markdown")
        except Exception:
            pass

# Dev clicks Reply
@router.callback_query(F.data.startswith("dev_reply:"))
async def cb_dev_reply(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ مخصص للمطور فقط.", show_alert=True)
        return
        
    _, target_user_id, ticket_id = call.data.split(":")
    await state.set_state(SupportState.waiting_for_dev_reply)
    await state.update_data(target_user_id=int(target_user_id), ticket_id=ticket_id)

    await call.message.reply(
        f"✍️ اكتب الآن ردك للمستخدم صاحب الآيدي `{target_user_id}` (تذكرة `#{ticket_id}`):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_dev_reply")]
        ]),
        parse_mode="Markdown"
    )
    await call.answer()

@router.callback_query(F.data == "cancel_dev_reply")
async def cb_cancel_dev_reply(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("تم إلغاء كتابة الرد.")
    await call.answer()

# Dev sends reply message
@router.message(SupportState.waiting_for_dev_reply)
async def process_dev_reply(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    data = await state.get_data()
    target_id = data.get("target_user_id")
    ticket_id = data.get("ticket_id")
    await state.clear()

    reply_to_user = (
        f"{NEON_HEADER}\n"
        f"📬 **رد رسمي من إدارة ومطور أوكـار** (تذكرة `#{ticket_id}`):\n"
        f"───────────────\n"
        f"{message.text or ''}\n"
        f"{NEON_FOOTER}"
    )

    try:
        if message.photo:
            await bot.send_photo(target_id, message.photo[-1].file_id, caption=reply_to_user, parse_mode="Markdown")
        elif message.voice:
            await bot.send_voice(target_id, message.voice.file_id, caption=reply_to_user, parse_mode="Markdown")
        else:
            await bot.send_message(target_id, reply_to_user, parse_mode="Markdown")
        
        await message.reply(f"✅ تم إرسال الرد بنجاح إلى المستخدم `{target_id}`.", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ تعذر تسليم الرد للمستخدم: {e}")
