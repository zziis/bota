from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import NEON_HEADER, NEON_FOOTER, RADIO_STREAMS

router = Router()

def get_radio_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, info in RADIO_STREAMS.items():
        buttons.append([
            InlineKeyboardButton(text=info["title"], callback_data=f"play_radio:{key}")
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data == "menu_radio")
async def cb_menu_radio(call: CallbackQuery):
    text = (
        f"{NEON_HEADER}\n"
        f"📻 **قسم إذاعة إف إم (Live FM Radio) - راديو السيارة**\n"
        f"🚗 استمع الآن لأقوى الإذاعات العربية والعالمية الحية بجودة صوت نقية وفورية:\n\n"
        f"▫️ تلاوات القرآن الكريم العطرة على مدار 24 ساعة.\n"
        f"▫️ نشرات الأخبار والبرامج التحليلية العالمية.\n"
        f"▫️ المحطات الغنائية والشبابية والترفيهية.\n\n"
        f"👇 **اختر المحطة الإذاعية للتشغيل المباشر:**\n"
        f"{NEON_FOOTER}"
    )
    await call.message.edit_text(text, reply_markup=get_radio_keyboard(), parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data.startswith("play_radio:"))
async def cb_play_radio(call: CallbackQuery):
    station_key = call.data.split(":")[1]
    station = RADIO_STREAMS.get(station_key)
    if not station:
        await call.answer("المحطة غير متوفرة حالياً.", show_alert=True)
        return

    text = (
        f"{NEON_HEADER}\n"
        f"📡 **جاري البث المباشر: {station['title']}**\n"
        f"🎙️ **التصنيف:** {station['genre']}\n"
        f"⚡️ **حالة البث:** 🟢 متصل وحي (Live Stream)\n\n"
        f"اضغط على زر **[تشغيل البث الحي 🔊]** للاستماع فورياً عبر مشغل التلجرام، أو اضغط على **[راديو الكبسولة 🎙️]** للاستماع داخل الروم مع الأعضاء.\n"
        f"{NEON_FOOTER}"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔊 تشغيل البث المباشر (FM)", url=station["url"])],
        [InlineKeyboardButton(text="📻 تغيير المحطة الإذاعية", callback_data="menu_radio")],
        [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="main_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()
