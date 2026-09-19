import asyncio
import logging
import sys

# Ensure UTF-8 stdout on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, DEV_USERNAME
from database import init_db
from handlers import (
    common,
    group_guard,
    support,
    radio,
    random_chat,
    complaints,
    developer_zalzala
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("OkarBot")

async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.warning("[WARNING] BOT_TOKEN is not set yet! Please put your token in .env file.")
        print("\n" + "="*60)
        print("⚠️ تنبيه: يرجى وضع توكن البوت الخاص بك من @BotFather في ملف .env")
        print("مثال: BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")
        print("="*60 + "\n")
        return

    logger.info("Initializing SQLite database...")
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register all handlers/routers
    dp.include_router(common.router)
    dp.include_router(developer_zalzala.router)
    dp.include_router(group_guard.router)
    dp.include_router(support.router)
    dp.include_router(radio.router)
    dp.include_router(random_chat.router)
    dp.include_router(complaints.router)

    banner = """
    🪶 ❪ أوكـــــار ❫ • ᴏᴋᴀʀ sʏsᴛᴇᴍ ᴀᴄᴛɪᴠᴀᴛᴇᴅ
    ⚡️ ◈ ────────────────────────────────────── ◈ ⚡️
    👑 بوت حماية المجموعات + كبسولة الرومات (4M)
    📻 إذاعة إف إم الحية + التعارف العشوائي المشفر
    🌋 لوحة المطور الخارقة ووضع التخفي (خيال 2.0)
    ⚡️ ◈ ────────────────────────────────────── ◈ ⚡️
    """
    print(banner)
    logger.info("🚀 Okar Bot is successfully running and listening for updates...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
