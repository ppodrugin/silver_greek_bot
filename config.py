"""
Конфигурация бота
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# ID супер-пользователя (администратора бота)
SUPERUSER_ID_STR = os.getenv('SUPERUSER_ID')
if not SUPERUSER_ID_STR:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: SUPERUSER_ID не установлен в переменных окружения!", file=sys.stderr)
    print("Установите SUPERUSER_ID в .env файле или переменных окружения", file=sys.stderr)
    sys.exit(1)

try:
    SUPERUSER_ID = int(SUPERUSER_ID_STR)
except ValueError:
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: SUPERUSER_ID должен быть числом, получено: {SUPERUSER_ID_STR}", file=sys.stderr)
    sys.exit(1)

