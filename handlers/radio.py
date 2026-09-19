from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import NEON_HEADER, NEON_FOOTER, WEBAPP_URL
router=Router()

@router.callback_query(F.data == "menu_radio")
async def cb_menu_radio(call:CallbackQuery):
    await call.answer()
    url=f"{WEBAPP_URL.rstrip('/')}/radio"
    text=(f"{NEON_HEADER}\n📻 **راديو أوكار FM — وضع السيارة**\n\n"
          "🚘 واجهة تردد عصرية داخل البوت.\n"
          "⏮ تنقل بين المحطات الحقيقية بالسابق/التالي.\n"
          "📡 إذا انقطع البث تظهر NO SIGNAL ويعمل تشويش الراديو بدلاً من صفحة 404.\n\n"
          "👇 افتح لوحة الراديو:\n" f"{NEON_FOOTER}")
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚘 فتح راديو السيارة FM",web_app=WebAppInfo(url=url))],[InlineKeyboardButton(text="🔙 القائمة الرئيسية",callback_data="main_menu")]])
    await call.message.edit_text(text,reply_markup=kb,parse_mode="Markdown")
