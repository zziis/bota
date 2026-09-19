import sys

# ضمان دعم ترميز UTF-8 على أنظمة Windows لمنع أخطاء الرموز التعبيرية
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncio
import logging
from aiohttp import web
from src.config import BOT_TOKEN, ADMIN_IDS, PORT, HOST, BASE_URL, APP_NAME
from src.db import init_db
from database import init_db as init_legacy_features_db
from handlers import common, group_guard, support, radio, random_chat, complaints, developer_zalzala
from src.server import create_app
from src.bot import bot
from aiogram import Dispatcher

# Dispatcher نظيف: يمنع تعارض أزرار/أوامر النسخة القديمة داخل src/bot.py
dp = Dispatcher()

# إعداد السجلات (Logging)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("KhayalMain")

async def start_web_server():
    """تشغيل خادم الويب وتطبيق Mini App وإشارات WebRTC"""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    logger.info(f"خادم تطبيق خيال يعمل الآن على: http://{HOST}:{PORT}")
    logger.info(f"رابط Mini App والمكالمات: {BASE_URL}")
    return runner

async def main():
    print("=" * 50)
    print(f"    منصة وبوت تواصل {APP_NAME}")
    print("=" * 50)

    # 1. تهيئة قاعدة البيانات
    logger.info("جاري تهيئة قاعدة البيانات المحلية SQLite...")
    await init_db()
    await init_legacy_features_db()
    logger.info("قاعدة البيانات الموحدة جاهزة بنجاح.")

    # دمج خصائص أوكار القديمة داخل Dispatcher الرئيسي نفسه.
    # بهذه الطريقة يوجد بوت واحد وPolling واحد فقط على Railway.
    for router in (common.router, developer_zalzala.router, group_guard.router,
                   support.router, radio.router, random_chat.router, complaints.router):
        dp.include_router(router)

    # 2. تشغيل خادم الويب
    web_runner = await start_web_server()

    # 3. تشغيل بوت تلجرام
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.warning("=" * 60)
        logger.warning("تنبيه: لم يتم تعيين BOT_TOKEN في ملف .env حتى الآن!")
        logger.warning("خادم المكالمات وتطبيق الويب يعمل، لكن البوت لن يعمل حتى تضع التوكن.")
        logger.warning("يرجى نسخ .env.example إلى .env ووضع توكن البوت ومعرف المشرف.")
        logger.warning("=" * 60)
        # إبقاء خادم الويب يعمل
        while True:
            await asyncio.sleep(3600)
    else:
        logger.info(f"جاري تشغيل بوت تلجرام للمشرفين: {ADMIN_IDS}")
        try:
            # حذف أي Webhook قديم لتفادي التعارض مع Polling
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("البوت متصل وجاهز لاستقبال الرسائل والمكالمات!")
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"حدث خطأ أثناء تشغيل البوت: {e}")
        finally:
            await bot.session.close()
            await web_runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("تم إيقاف تشغيل النظام.")
