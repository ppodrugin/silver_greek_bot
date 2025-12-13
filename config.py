"""
Конфигурация бота
"""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# SQLite не требует настроек подключения - используется файл vocabulary.db

# Загружаем список пользователей с расширенной статистикой из базы данных
def load_tracked_users():
    """Загружает список user_id пользователей из базы данных"""
    from database import get_tracked_users
    return get_tracked_users()

TRACKED_USERS = load_tracked_users()

