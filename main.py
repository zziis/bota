import sys
import asyncio
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import common, group_guard, support, radio, random_chat, complaints, developer_zalzala
from src.server import create_app
from src.config import PORT, HOST, BASE_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("KhayalUnified")


async def start_web_server():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    logger.info("Khayal web/Mini App server: %s", BASE_URL)
    return runner


def build_dispatcher():
    dp = Dispatcher(storage=MemoryStorage())
    # هذه هي النسخة الوحيدة الفعالة من معالجات البوت الآن.
    dp.include_router(common.router)
    dp.include_router(developer_zalzala.router)
    dp.include_router(group_guard.router)
    dp.include_router(support.router)
    dp.include_router(radio.router)
    dp.include_router(random_chat.router)
    dp.include_router(complaints.router)
    return dp


async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("BOT_TOKEN is not configured")

    await init_db()
    web_runner = await start_web_server()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = build_dispatcher()

    try:
        # يمنع تشغيل webhook/نسخة قديمة بالتوازي مع النسخة الحالية.
        await bot.delete_webhook(drop_pending_updates=True)
        me = await bot.get_me()
        logger.info("Unified bot started: @%s (%s)", me.username, me.id)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await web_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
