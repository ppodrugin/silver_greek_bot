#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных SQLite
"""
from database import init_database

if __name__ == "__main__":
    print("Инициализация базы данных SQLite...")
    if init_database():
        print("✅ База данных успешно инициализирована!")
        print("Файл vocabulary.db создан в текущей директории")
    else:
        print("❌ Ошибка при инициализации базы данных")
        print("\nУбедитесь, что:")
        print("1. У вас есть права на запись в текущую директорию")
        print("2. SQLite доступен (обычно встроен в Python)")

