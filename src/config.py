import os
from dotenv import load_dotenv

# تحميل المتغيرات من ملف .env
load_dotenv()

# إعدادات بوت تلجرام
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# قائمة معرفات المشرفين (Admin IDs) مفصولة بفواصل
raw_admins = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "0")).strip()
ADMIN_IDS = [int(x.strip()) for x in raw_admins.split(",") if x.strip().isdigit()]

# إعدادات الخادم والويب
PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")

# الرابط الأساسي للموقع (مهم لفتح Telegram Mini App للمكالمات)
# مثال: https://khayal-bot.onrender.com أو رابط ngrok محلي
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080").rstrip("/")

# اسم وهوية المشروع
APP_NAME = "خيال | Khayal"
VERSION = "1.0.0"

# مسارات الملفات
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "khayal.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")
