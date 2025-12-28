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

from database import get_connection, return_connection, get_param

def check_column_exists(cursor, table_name, column_name):
    """Проверяет существование колонки в таблице"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        )
    """, (table_name, column_name))
    return cursor.fetchone()[0]

def check_table_exists(cursor, table_name):
    """Проверяет существование таблицы"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = %s
        )
    """, (table_name,))
    return cursor.fetchone()[0]

def check_foreign_key_exists(cursor, constraint_name, table_name):
    """Проверяет существование внешнего ключа"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.table_constraints 
            WHERE constraint_name = %s AND table_name = %s
        )
    """, (constraint_name, table_name))
    return cursor.fetchone()[0]

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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(user_id, name)
            )
        """)
        logger.info("✅ Таблица lessons создана")
        
        # 2. Создаем таблицу categories
        logger.info("📋 Создание таблицы categories...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(user_id, name)
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
        
        # 5. Добавляем внешние ключи
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
        
        # 6. Создаем индексы
        logger.info("📋 Создание индексов...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocabulary_lesson_id ON vocabulary(lesson_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocabulary_category_id ON vocabulary(category_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lessons_user_id ON lessons(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories(user_id)")
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
    logger.info("🚀 Запуск миграции базы данных PostgreSQL...")
    
    success = migrate_database()
    
    if success:
        logger.info("✅ Миграция завершена успешно!")
        sys.exit(0)
    else:
        logger.error("❌ Миграция завершилась с ошибками!")
        sys.exit(1)
