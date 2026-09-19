from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command
from config import NEON_HEADER, NEON_FOOTER, ADMIN_IDS, WEBAPP_URL
from database import (add_support_message, get_support_threads, get_support_history,
                      support_should_ack, mark_support_ack_sent, set_support_ack)

router = Router()

class SupportState(StatesGroup):
    user_chat = State()
    admin_chat = State()

def support_menu(user_id:int):
    call_url=f"{WEBAPP_URL.rstrip('/')}/call?room=support-{user_id}&userId={user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 بدء المراسلة", callback_data="support_text")],
        [InlineKeyboardButton(text="🎙️ اتصال صوتي / 📹 كامرة", callback_data="support_call")],
        [InlineKeyboardButton(text="🏛️ القائمة الرئيسية", callback_data="main_menu")]
    ])

@router.callback_query(F.data == "menu_support")
async def cb_menu_support(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.clear()
    text=(f"{NEON_HEADER}\n📩 **التواصل المباشر مع الإدارة**\n\n"
          "💬 الرسائل تصل للمطور فوراً وتبقى مجمعة باسمك.\n"
          "🎙️ يمكنك أيضاً فتح الاتصال ثم تشغيل المايك أو الكامرة.\n\n"
          "اختر طريقة التواصل:\n" f"{NEON_FOOTER}")
    await call.message.edit_text(text,reply_markup=support_menu(call.from_user.id),parse_mode="Markdown")


@router.callback_query(F.data == "support_call")
async def support_call(call:CallbackQuery, bot:Bot):
    await call.answer("تم تجهيز غرفة الاتصال")
    uid=call.from_user.id
    url=f"{WEBAPP_URL.rstrip('/')}/call?room=support-{uid}&userId={uid}"
    user_kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎙️ فتح غرفة الاتصال",web_app=WebAppInfo(url=url))],[InlineKeyboardButton(text="🔙 رجوع",callback_data="menu_support")]])
    await call.message.edit_text("📞 غرفة الاتصال جاهزة. افتحها ثم فعّل المايك، ويمكنك تشغيل الكامرة من داخل المكالمة. تم إشعار المطور أيضاً.",reply_markup=user_kb)
    for aid in ADMIN_IDS:
        try:
            admin_url=f"{WEBAPP_URL.rstrip('/')}/call?room=support-{uid}&userId={aid}"
            await bot.send_message(aid,f"📞 طلب اتصال من {call.from_user.first_name}\nID: {uid}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📞 دخول الاتصال",web_app=WebAppInfo(url=admin_url))],[InlineKeyboardButton(text="💬 فتح رسائله",callback_data=f"support_thread:{uid}")]]))
        except Exception: pass

@router.callback_query(F.data == "support_text")
async def start_support_text(call:CallbackQuery,state:FSMContext):
    await call.answer("المراسلة المباشرة مفعلة")
    await state.set_state(SupportState.user_chat)
    await call.message.edit_text("💬 أرسل رسائلك الآن. ستصل مباشرة إلى المطور.\nيمكنك إرسال نص، صورة أو صوت.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔕 إيقاف رسالة الاستلام",callback_data="support_ack_off")],[InlineKeyboardButton(text="🔙 إنهاء المراسلة",callback_data="support_close")]]))

@router.callback_query(F.data == "support_ack_off")
async def ack_off(call:CallbackQuery):
    await set_support_ack(call.from_user.id,False); await call.answer("لن تتكرر رسالة الاستلام",show_alert=False)

@router.callback_query(F.data == "support_close")
async def support_close(call:CallbackQuery,state:FSMContext):
    await state.clear(); await call.answer(); await call.message.edit_text("تم إنهاء المراسلة.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏛️ القائمة الرئيسية",callback_data="main_menu")]]))

async def _forward_user_message(message:Message, bot:Bot):
    u=message.from_user
    kind='photo' if message.photo else 'voice' if message.voice else 'video' if message.video else 'document' if message.document else 'text'
    content=message.text or message.caption or f"[{kind}]"
    await add_support_message(u.id,u.username or '',u.first_name or 'مستخدم','user',content,kind)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"💬 {u.first_name or 'مستخدم'}",callback_data=f"support_thread:{u.id}")]])
    for aid in ADMIN_IDS:
        try:
            header=f"📩 رسالة جديدة من {u.first_name or 'مستخدم'}\nID: {u.id}\n@{u.username or 'بدون_معرف'}"
            await bot.send_message(aid,header,reply_markup=kb)
            await message.copy_to(aid)
        except Exception:
            pass
    if await support_should_ack(u.id):
        await message.answer("✅ تم استلام رسالتك ووصلت إلى المطور. يمكنك متابعة إرسال الرسائل هنا.")
        await mark_support_ack_sent(u.id)

@router.message(SupportState.user_chat)
async def support_user_message(message:Message,state:FSMContext,bot:Bot):
    if message.chat.type!='private' or message.from_user.id in ADMIN_IDS:return
    await _forward_user_message(message,bot)

@router.callback_query(F.data == "support_inbox")
async def support_inbox(call:CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:return await call.answer("للمطور فقط",show_alert=True)
    await call.answer()
    rows=await get_support_threads()
    buttons=[]
    for r in rows:
        name=(r.get('first_name') or 'مستخدم')[:22]; count=r.get('message_count',0)
        buttons.append([InlineKeyboardButton(text=f"👤 {name}  •  {count} رسائل",callback_data=f"support_thread:{r['user_id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع",callback_data="main_menu")])
    await call.message.edit_text("📥 صندوق مراسلات المستخدمين\nاختر المستخدم لفتح كامل المحادثة:",reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("support_thread:"))
async def open_thread(call:CallbackQuery,state:FSMContext):
    if call.from_user.id not in ADMIN_IDS:return await call.answer("للمطور فقط",show_alert=True)
    await call.answer()
    uid=int(call.data.split(':',1)[1]); hist=await get_support_history(uid,20)
    lines=[]
    for m in hist:
        who='👤' if m['sender']=='user' else '🛠'
        txt=(m.get('content') or '')[:350]
        lines.append(f"{who} {txt}")
    body="\n\n".join(lines) or "لا توجد رسائل"
    await state.set_state(SupportState.admin_chat); await state.update_data(target_user_id=uid)
    await call.message.edit_text(f"💬 محادثة المستخدم {uid}\n──────────\n{body[-3500:]}\n──────────\n✍️ أي رسالة ترسلها الآن ستصل إليه مباشرة.",
      reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 كل المستخدمين",callback_data="support_inbox")],[InlineKeyboardButton(text="❌ إنهاء الرد",callback_data="support_admin_close")]]))

@router.callback_query(F.data == "support_admin_close")
async def admin_close(call:CallbackQuery,state:FSMContext):
    await state.clear(); await call.answer(); await call.message.edit_text("تم إغلاق المحادثة.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 صندوق المراسلات",callback_data="support_inbox")]]))

@router.message(SupportState.admin_chat)
async def admin_reply(message:Message,state:FSMContext,bot:Bot):
    if message.from_user.id not in ADMIN_IDS:return
    data=await state.get_data(); uid=data.get('target_user_id')
    if not uid:return
    content=message.text or message.caption or '[وسائط]'
    kind='photo' if message.photo else 'voice' if message.voice else 'video' if message.video else 'document' if message.document else 'text'
    try:
        await bot.send_message(uid,"📬 رسالة من الإدارة:")
        await message.copy_to(uid)
        await add_support_message(uid,'','مستخدم','admin',content,kind)
        await message.reply("✅ تم الإرسال. ابقَ هنا وأرسل رسالة أخرى لنفس المستخدم أو اضغط إنهاء الرد.")
    except Exception as e:
        await message.reply(f"❌ تعذر الإرسال: {e}")


@router.message(F.chat.type == "private")
async def direct_message_to_admin(message:Message, bot:Bot):
    # أي رسالة خاصة عادية للبوت تصل للمطور مباشرة، ما لم تكن أمراً أو من المطور نفسه.
    if not message.from_user or message.from_user.id in ADMIN_IDS:
        return
    if message.text and message.text.startswith('/'):
        return
    await _forward_user_message(message, bot)
