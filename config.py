import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if available
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Credentials
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "123456789")
ADMIN_IDS = [int(i.strip()) for i in ADMIN_IDS_RAW.split(",") if i.strip().isdigit()]

# Developer / Support info
DEV_USERNAME = os.getenv("DEV_USERNAME", "@OkarDev")
SUPPORT_CHANNEL = os.getenv("SUPPORT_CHANNEL", "")

# WebApp / Capsule URL
# The WebApp capsule can be hosted locally via server.py or hosted online
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8080")

# Database Path
DB_PATH = BASE_DIR / "okar_database.sqlite"

# Logo Path
LOGO_PATH = BASE_DIR / "assets" / "okar_logo.jpg"

# Live Radio FM Stream Channels (High quality real audio streams)
RADIO_STREAMS = {
    "quran_cairo": {
        "title": "📻 إذاعة القرآن الكريم - القاهرة",
        "url": "https://stream.zeno.fm/8wv40vdbtm0uv",
        "genre": "قرآن كريم"
    },
    "quran_makkah": {
        "title": "🕋 إذاعة القرآن الكريم - الحرم المكي",
        "url": "https://stream.radiojar.com/0tpy1h0kxtzuv",
        "genre": "تلاوات مباركة"
    },
    "bbc_arabic": {
        "title": "🌍 بي بي سي عربي (BBC Arabic FM)",
        "url": "https://stream.live.vc.bbcmedia.co.uk/bbc_arabic_radio",
        "genre": "أخبار وتحليلات عالمية"
    },
    "monte_carlo": {
        "title": "🎙️ مونت كارلو الدولية (MCD FM)",
        "url": "https://montecarlodoualiyaaudio.akacdn.net/mcd/ar/midfi/mp3/mcd_midfi.mp3",
        "genre": "أخبار وبرامج حوارية"
    },
    "nogoum_fm": {
        "title": "🎶 نجوم إف إم (Nogoum FM 100.6)",
        "url": "https://audiostreaming.twesto.com/nogoumfm",
        "genre": "موسيقى وبرامج شبابية"
    },
    "rotana_fm": {
        "title": "🎵 روتانا إف إم (Rotana FM)",
        "url": "https://stream.zeno.fm/f3wvbbw41qruv",
        "genre": "طرب وأغاني عربية"
    },
    "mix_fm": {
        "title": "🎧 ميكس إف إم (Mix FM)",
        "url": "https://stream.zeno.fm/24u1k3w11qruv",
        "genre": "أحدث الإيقاعات والأغاني"
    }
}

# Neon UI Branding Text Decorators
NEON_HEADER = "🪶 ❪ أوكــار ❫ • ᴏᴋᴀʀ ɴᴇᴏɴ sʏsᴛᴇᴍ\n⚡️ ◈ ─────────────── ◈ ⚡️"
NEON_FOOTER = "⚡️ ◈ ─────────────── ◈ ⚡️\n🪶 ᴍᴀᴅᴇ ʙʏ ᴏᴋᴀʀ ɢᴏʟᴅᴇɴ ғᴇᴀᴛʜᴇʀ"
