from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import NEON_HEADER, NEON_FOOTER, ADMIN_IDS
from database import create_ticket

router = Router()

class ComplaintState(StatesGroup):
    waiting_for_details = State()

@router.callback_query(F.data == "menu_complaint")
async def cb_menu_complaint(call: CallbackQuery, state: FSMContext):
    await state.set_state(ComplaintState.waiting_for_details)
    text = (
        f"{NEON_HEADER}\n"
        f"📝 **قسم الشكاوى والبلاغات الرسمية - أوكـار**\n\n"
        f"🛡️ لحماية مجتمع المجموعات والمستخدمين، يرجى كتابة تفاصيل الشكوى بدقة:\n"
        f"1. اسم أو آيدي الشخص أو المجموعة المخالفة.\n"
        f"2. سبب الشكوى (سب، احتيال، إزعاج، سبام).\n"
        f"3. إرفاق صورة إثبات أو لقطة شاشة إن وجدت.\n\n"
        f"⚡️ اكتب شكواك الآن رداً على هذه الرسالة:\n"
        f"{NEON_FOOTER}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء الشكوى", callback_data="cancel_complaint")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data == "cancel_complaint")
async def cb_cancel_complaint(call: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏛️ القائمة الرئيسية", callback_data="main_menu")]
    ])
    await call.message.edit_text("⚡️ تم إلغاء تقديم الشكوى.", reply_markup=kb)
    await call.answer()

@router.message(ComplaintState.waiting_for_details)
async def process_complaint(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    if not user:
        return
        
    await state.clear()
    content = message.text or message.caption or "إثبات بلاغ (صورة/مقطع)"
    ticket_id = await create_ticket(user.id, "complaint", content)

    # Confirm to complainant
    confirm = (
        f"{NEON_HEADER}\n"
        f"✅ **تم تسجيل شكواك بنجاح!**\n"
        f"🎫 رقم البلاغ: `#{ticket_id}`\n"
        f"⚖️ سيقوم فريق إدارة ومطوري أوكار بمراجعة الأدلة واتخاذ الإجراء اللازم فوراً.\n"
        f"{NEON_FOOTER}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏛️ القائمة الرئيسية", callback_data="main_menu")]
    ])
    await message.reply(confirm, reply_markup=kb, parse_mode="Markdown")

    # Send to Developers
    admin_alert = (
        f"🚨 **بلاغ وشكوى جديدة!** 🚨\n"
        f"🎫 رقم التذكرة: `#{ticket_id}`\n"
        f"👤 المشتكي: [{user.first_name}](tg://user?id={user.id}) (`{user.id}`)\n"
        f"🏷 المعرف: @{user.username or 'بدون'}\n"
        f"───────────────\n"
        f"📑 **تفاصيل البلاغ:**\n{content}"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ مراسلة صاحب الشكوى", callback_data=f"dev_reply:{user.id}:{ticket_id}")],
        [
            InlineKeyboardButton(text="✅ قبول وإغلاق", callback_data=f"ticket_resolve:{ticket_id}:accepted"),
            InlineKeyboardButton(text="❌ رفض الشكوى", callback_data=f"ticket_resolve:{ticket_id}:rejected")
        ]
    ])

    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                await bot.send_photo(admin_id, message.photo[-1].file_id, caption=admin_alert, reply_markup=admin_kb, parse_mode="Markdown")
            else:
                await bot.send_message(admin_id, admin_alert, reply_markup=admin_kb, parse_mode="Markdown")
        except Exception:
            pass

@router.callback_query(F.data.startswith("ticket_resolve:"))
async def cb_ticket_resolve(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ مخصص للمطور فقط.", show_alert=True)
        return
        
    _, ticket_id, action = call.data.split(":")
    status_str = "✅ تم قبول الشكوى واتخاذ الإجراء" if action == "accepted" else "❌ تم رفض الشكوى لعدم كفاية الأدلة"
    await call.message.reply(f"⚖️ التذكرة `#{ticket_id}`: {status_str}.")
    await call.answer("تم تحديث حالة التذكرة.")
