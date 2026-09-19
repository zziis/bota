from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, WebAppInfo
from aiogram.filters import CommandStart, Command
from config import NEON_HEADER, NEON_FOOTER, LOGO_PATH, DEV_USERNAME, ADMIN_IDS, WEBAPP_URL
from database import register_user, is_user_gbanned

router = Router()

def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🛡️ حماية المجموعات", callback_data="menu_guard"),
            InlineKeyboardButton(text="🎙️ كبسولة الرومات 4M", web_app=WebAppInfo(url=WEBAPP_URL))
        ],
        [
            InlineKeyboardButton(text="📻 راديو إف إم مباشر", callback_data="menu_radio"),
            InlineKeyboardButton(text="👥 التعارف العشوائي", callback_data="menu_random")
        ],
        [
            InlineKeyboardButton(text="📩 مراسلة الإدارة", callback_data="menu_support"),
            InlineKeyboardButton(text="📝 قسم الشكاوى", callback_data="menu_complaint")
        ],
        [
            InlineKeyboardButton(text="➕ أضف البوت إلى مجموعتك ➕", url="https://t.me/OkarBot?startgroup=true")
        ]
    ]
    if user_id in ADMIN_IDS:
        buttons.append([
            InlineKeyboardButton(text="⚡️ لوحة المطور وإضافات زلزال 🌋", callback_data="menu_dev")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    if not user:
        return
        
    await register_user(user.id, user.username, user.first_name)
    
    # Check if globally banned
    if await is_user_gbanned(user.id):
        await message.answer("🚫 أنت محظور عام من استخدام نظام أوكار.")
        return

    # In groups, send short notification
    if message.chat.type in ["group", "supergroup"]:
        text = (
            f"{NEON_HEADER}\n"
            f"👑 **بوت أوكار للحماية والذكاء الاصطناعي يعمل بنجاح!**\n"
            f"ارفـع البوت **مشرفاً بصلاحيات كاملة** لتفعيل درع الحماية الفولاذي.\n"
            f"⚡️ لعرض الأوامر: أرسل كلمة `الاوامر` أو `الحماية`.\n"
            f"{NEON_FOOTER}"
        )
        await message.reply(text, parse_mode="Markdown")
        return

    # In private chat
    caption = (
        f"{NEON_HEADER}\n"
        f"👋 أهـلاً بـك يا **{user.first_name}** في نظام **أوكـار (Okar)**!\n"
        f"🪶 البوت الأقوى لحماية المجموعات والتواصل الاجتماعي والكبسولة الصوتية.\n\n"
        f"✨ **أقسام البوت المتاحة لك:**\n"
        f"▫️ **درع الحماية:** حماية مجموعتك من التخريب والإعلانات والسبام.\n"
        f"▫️ **كبسولة الرومات:** روم كامل الشاشة مع 4 مايكات وكاميرا ودردشة.\n"
        f"▫️ **راديو إف إم:** استمع لمحطات الراديو الحية كالقرآن والأخبار والأغاني.\n"
        f"▫️ **التعارف العشوائي:** تحدث مع أشخاص جدد (شاب / فتاة) بأمان وتخفّي.\n"
        f"▫️ **مراسلة الإدارة والشكاوى:** تواصل مباشر مع مطوري النظام.\n\n"
        f"👇 **اختر القسم الذي تريده من الأزرار الشفافة أدناه:**\n"
        f"{NEON_FOOTER}"
    )

    kb = get_main_keyboard(user.id)
    if LOGO_PATH.exists():
        photo = FSInputFile(str(LOGO_PATH))
        await message.answer_photo(photo=photo, caption=caption, reply_markup=kb, parse_mode="Markdown")
    else:
        await message.answer(caption, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery):
    user = call.from_user
    caption = (
        f"{NEON_HEADER}\n"
        f"🏛️ **القائمة الرئيسية لنظام أوكـار (Okar)**\n"
        f"🪶 حدد وجهتك من خلال الأزرار أدناه:\n"
        f"{NEON_FOOTER}"
    )
    kb = get_main_keyboard(user.id)
    try:
        await call.message.edit_caption(caption=caption, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        try:
            await call.message.edit_text(text=caption, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await call.message.answer(caption, reply_markup=kb, parse_mode="Markdown")
    await call.answer()
