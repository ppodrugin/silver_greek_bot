#!/usr/bin/env python3
"""
Скрипт для миграции базы данных: добавление таблиц lessons и categories,
а также полей lesson_id и category_id в таблицу vocabulary.

Использование:
    python3 migrate_database.py
"""

import os
import sys
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Добавляем путь к модулям проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection, return_connection, USE_POSTGRES, get_param

def check_column_exists(cursor, table_name, column_name):
    """Проверяет существование колонки в таблице"""
    if USE_POSTGRES:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = %s AND column_name = %s
            )
        """, (table_name, column_name))
        return cursor.fetchone()[0]
    else:
        # SQLite
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return column_name in columns

def check_table_exists(cursor, table_name):
    """Проверяет существование таблицы"""
    if USE_POSTGRES:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table_name,))
        return cursor.fetchone()[0]
    else:
        # SQLite
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cursor.fetchone() is not None

def check_foreign_key_exists(cursor, constraint_name, table_name):
    """Проверяет существование внешнего ключа"""
    if USE_POSTGRES:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = %s AND table_name = %s
            )
        """, (constraint_name, table_name))
        return cursor.fetchone()[0]
    else:
        # SQLite не поддерживает именованные ограничения таким же образом
        # Проверяем через PRAGMA foreign_key_list
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        foreign_keys = cursor.fetchall()
        # В SQLite проверка сложнее, для простоты возвращаем False
        # и полагаемся на то, что внешние ключи будут добавлены при пересоздании таблицы
        return False

def migrate_database():
    """Выполняет миграцию базы данных"""
    conn = get_connection()
    if not conn:
        logger.error("❌ Не удалось подключиться к базе данных")
        return False
    
    try:
        cursor = conn.cursor()
        param = get_param()
        
        logger.info("🔄 Начало миграции базы данных...")
        
        # 1. Создаем таблицу lessons
        logger.info("📋 Создание таблицы lessons...")
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
            """)
        logger.info("✅ Таблица lessons создана")
        
        # 2. Создаем таблицу categories
        logger.info("📋 Создание таблицы categories...")
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
            """)
        logger.info("✅ Таблица categories создана")
        
        # 3. Добавляем lesson_id в vocabulary
        logger.info("📋 Проверка поля lesson_id в таблице vocabulary...")
        if not check_column_exists(cursor, 'vocabulary', 'lesson_id'):
            logger.info("   Добавление поля lesson_id...")
            cursor.execute("ALTER TABLE vocabulary ADD COLUMN lesson_id INTEGER")
            logger.info("✅ Поле lesson_id добавлено")
        else:
            logger.info("   Поле lesson_id уже существует")
        
        # 4. Добавляем category_id в vocabulary
        logger.info("📋 Проверка поля category_id в таблице vocabulary...")
        if not check_column_exists(cursor, 'vocabulary', 'category_id'):
            logger.info("   Добавление поля category_id...")
            cursor.execute("ALTER TABLE vocabulary ADD COLUMN category_id INTEGER")
            logger.info("✅ Поле category_id добавлено")
        else:
            logger.info("   Поле category_id уже существует")
        
        # 5. Добавляем внешние ключи (только для PostgreSQL, SQLite требует пересоздания таблицы)
        if USE_POSTGRES:
            logger.info("📋 Проверка внешних ключей...")
            
            if not check_foreign_key_exists(cursor, 'vocabulary_lesson_id_fkey', 'vocabulary'):
                logger.info("   Добавление внешнего ключа для lesson_id...")
                cursor.execute("""
                    ALTER TABLE vocabulary 
                    ADD CONSTRAINT vocabulary_lesson_id_fkey 
                    FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE SET NULL
                """)
                logger.info("✅ Внешний ключ для lesson_id добавлен")
            else:
                logger.info("   Внешний ключ для lesson_id уже существует")
            
            if not check_foreign_key_exists(cursor, 'vocabulary_category_id_fkey', 'vocabulary'):
                logger.info("   Добавление внешнего ключа для category_id...")
                cursor.execute("""
                    ALTER TABLE vocabulary 
                    ADD CONSTRAINT vocabulary_category_id_fkey 
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
                """)
                logger.info("✅ Внешний ключ для category_id добавлен")
            else:
                logger.info("   Внешний ключ для category_id уже существует")
        else:
            # SQLite: включаем поддержку внешних ключей
            logger.info("📋 Включение поддержки внешних ключей для SQLite...")
            cursor.execute("PRAGMA foreign_keys = ON")
            logger.info("⚠️  Для SQLite внешние ключи должны быть определены при создании таблицы.")
            logger.info("   Если нужно добавить внешние ключи, потребуется пересоздание таблицы.")
        
        # 6. Создаем индексы
        logger.info("📋 Создание индексов...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocabulary_lesson_id ON vocabulary(lesson_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocabulary_category_id ON vocabulary(category_id)")
        logger.info("✅ Индексы созданы")
        
        conn.commit()
        logger.info("✅ Миграция успешно завершена!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при миграции: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        if conn:
            return_connection(conn)

if __name__ == "__main__":
    logger.info("🚀 Запуск миграции базы данных...")
    logger.info(f"📊 Тип БД: {'PostgreSQL' if USE_POSTGRES else 'SQLite'}")
    
    success = migrate_database()
    
    if success:
        logger.info("✅ Миграция завершена успешно!")
        sys.exit(0)
    else:
        logger.error("❌ Миграция завершилась с ошибками!")
        sys.exit(1)

