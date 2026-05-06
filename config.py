import os
from dotenv import load_dotenv

load_dotenv()

# Telegram настройки
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Funpay Golden Key
GOLDEN_KEY = os.getenv("GOLDEN_KEY")

# Настройки парсинга
PARSE_INTERVAL = int(os.getenv("PARSE_INTERVAL", "60"))
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "10"))

# Файлы для хранения
AUTODELIVERY_FILE = "autodelivery_items.json"
LAST_SALES_FILE = "last_sales.json"

# Проверка обязательных переменных
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

if not ADMIN_ID:
    raise ValueError("❌ ADMIN_ID не найден в .env файле!")

print(f"✅ Конфигурация загружена")
print(f"🤖 Режим: {'Полный (с Golden Key)' if GOLDEN_KEY else 'Ограниченный (только парсинг)'}")