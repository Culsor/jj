import os

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

MONGO_URI = os.environ.get("MONGO_URI", "")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "sticker_video_bot")

PORT = int(os.environ.get("PORT", "8080"))

OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# Limits
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))
FFMPEG_TIMEOUT = int(os.environ.get("FFMPEG_TIMEOUT", "120"))

TEMP_DIR = os.environ.get("TEMP_DIR", "/tmp/svbot")

FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", "")  # optional, e.g. "@yourchannel"
