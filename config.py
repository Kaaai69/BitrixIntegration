import os
from dotenv import load_dotenv

load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
BITRIX_WEBHOOK_URL = os.getenv("BITRIX_WEBHOOK_URL")

BITRIX_DEFAULT_CURRENCY = os.getenv("BITRIX_DEFAULT_CURRENCY", "RUB")
BITRIX_DEFAULT_CATEGORY_ID = int(os.getenv("BITRIX_DEFAULT_CATEGORY_ID", "0"))


if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN в .env")

if not BITRIX_WEBHOOK_URL:
    raise RuntimeError("Не найден BITRIX_WEBHOOK_URL в .env")

if not BITRIX_WEBHOOK_URL.endswith("/"):
    BITRIX_WEBHOOK_URL += "/"
