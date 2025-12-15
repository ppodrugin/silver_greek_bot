"""
Работа с базой данных (SQLite для локальной разработки, PostgreSQL для продакшена)
Унифицированный подход без различий между БД
"""
import logging
import os

logger = logging.getLogger(__name__)

# Определяем, какую БД использовать
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = bool(DATABASE_URL)

# Логируем информацию о выборе БД
if USE_POSTGRES:
    logger.info(f"✅ Используется PostgreSQL (DATABASE_URL найден: {DATABASE_URL[:20]}...)")
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from psycopg2.pool import ThreadedConnectionPool
        
        # Пул соединений для PostgreSQL
        connection_pool = None
        
        def get_connection():
            """Создает соединение с базой данных PostgreSQL"""
            global connection_pool
            
            if connection_pool is None:
                try:
                    db_url = os.getenv('DATABASE_URL')
                    logger.info(f"🔗 Подключение к PostgreSQL: {db_url[:30]}...")
                    connection_pool = ThreadedConnectionPool(1, 5, db_url)
                    logger.info("✅ Пул соединений PostgreSQL создан")
                except Exception as e:
                    logger.error(f"❌ Ошибка создания пула соединений PostgreSQL: {e}", exc_info=True)
                    return None
            
            try:
                conn = connection_pool.getconn()
                return conn
            except Exception as e:
                logger.error(f"❌ Ошибка получения соединения из пула: {e}", exc_info=True)
                return None
        
        def return_connection(conn):
            """Возвращает соединение в пул"""
            global connection_pool
            if connection_pool and conn:
                try:
                    connection_pool.putconn(conn)
                except Exception as e:
                    logger.error(f"Ошибка возврата соединения в пул: {e}", exc_info=True)
    except ImportError:
        logger.error("❌ psycopg2 не установлен! Установите: pip install psycopg2-binary")
        USE_POSTGRES = False

if not USE_POSTGRES:
    logger.info("✅ Используется SQLite (DATABASE_URL не установлен)")
    import sqlite3
    
    DB_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(DB_DIR, 'vocabulary.db')
    
    def get_connection():
        """Создает соединение с базой данных SQLite"""
        try:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            return conn
        except Exception as e:
            logger.error(f"Ошибка подключения к SQLite: {e}", exc_info=True)
            logger.error(f"Путь к БД: {DB_PATH}")
            return None
    
    def return_connection(conn):
        """Закрывает соединение SQLite"""
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"Ошибка закрытия соединения SQLite: {e}", exc_info=True)

# Универсальная функция для получения placeholder
def get_param():
    """Возвращает placeholder для параметров запроса"""
    return '%s' if USE_POSTGRES else '?'

def init_database():
    """Проверяет подключение к базе данных и структуру таблиц"""
    logger.info(f"🔍 Проверка подключения к БД: USE_POSTGRES={USE_POSTGRES}")
    
    try:
        conn = get_connection()
        if not conn:
            logger.error("❌ Не удалось получить соединение с БД")
            return False
        
        cursor = conn.cursor()
        
        # Проверяем существование таблиц
        logger.info("📋 Проверка структуры базы данных...")
        
        # Проверяем таблицу vocabulary
        if USE_POSTGRES:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'vocabulary'
                )
            """)
            vocabulary_exists = cursor.fetchone()[0]
            
            if not vocabulary_exists:
                logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Таблица 'vocabulary' не существует!")
                logger.error("Создайте таблицы вручную согласно schema.sql")
                return False
            
            # Проверяем наличие необходимых колонок в vocabulary
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'vocabulary' 
                AND column_name IN ('id', 'user_id', 'greek', 'russian', 'successful', 'unsuccessful', 'created_at')
            """)
            vocabulary_columns = {row[0] for row in cursor.fetchall()}
            required_columns = {'id', 'user_id', 'greek', 'russian', 'successful', 'unsuccessful', 'created_at'}
            
            if vocabulary_columns != required_columns:
                missing = required_columns - vocabulary_columns
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: В таблице 'vocabulary' отсутствуют колонки: {missing}")
                logger.error("Структура таблицы не соответствует schema.sql")
                return False
            
            # Проверяем таблицу users
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'users'
                )
            """)
            users_exists = cursor.fetchone()[0]
            
            if not users_exists:
                logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Таблица 'users' не существует!")
                logger.error("Создайте таблицы вручную согласно schema.sql")
                return False
            
            # Проверяем наличие необходимых колонок в users
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name IN ('user_id', 'username', 'is_admin', 'is_tracked', 'added_at', 'notes')
            """)
            users_columns = {row[0] for row in cursor.fetchall()}
            required_users_columns = {'user_id', 'username', 'is_admin', 'is_tracked', 'added_at', 'notes'}
            
            if users_columns != required_users_columns:
                missing = required_users_columns - users_columns
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: В таблице 'users' отсутствуют колонки: {missing}")
                logger.error("Структура таблицы не соответствует schema.sql")
                return False
        else:
            # SQLite проверка
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vocabulary'")
            if not cursor.fetchone():
                logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Таблица 'vocabulary' не существует!")
                logger.error("Создайте таблицы вручную согласно schema.sql")
                return False
            
            cursor.execute("PRAGMA table_info(vocabulary)")
            vocabulary_columns = {row[1] for row in cursor.fetchall()}
            required_columns = {'id', 'user_id', 'greek', 'russian', 'successful', 'unsuccessful', 'created_at'}
            
            if vocabulary_columns != required_columns:
                missing = required_columns - vocabulary_columns
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: В таблице 'vocabulary' отсутствуют колонки: {missing}")
                logger.error("Структура таблицы не соответствует schema.sql")
                return False
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Таблица 'users' не существует!")
                logger.error("Создайте таблицы вручную согласно schema.sql")
                return False
            
            cursor.execute("PRAGMA table_info(users)")
            users_columns = {row[1] for row in cursor.fetchall()}
            required_users_columns = {'user_id', 'username', 'is_admin', 'is_tracked', 'added_at', 'notes'}
            
            if users_columns != required_users_columns:
                missing = required_users_columns - users_columns
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: В таблице 'users' отсутствуют колонки: {missing}")
                logger.error("Структура таблицы не соответствует schema.sql")
                return False
        
        db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
        logger.info(f"✅ База данных {db_type} подключена")
        logger.info("✅ Структура базы данных проверена и соответствует схеме")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при проверке БД: {e}", exc_info=True)
        return False
    finally:
        if conn:
            return_connection(conn)

def add_user(user_id, username=None, is_admin=False, is_tracked=False, notes=None):
    """
    Добавляет или обновляет пользователя
    
    Args:
        user_id: ID пользователя Telegram
        username: Username пользователя (опционально)
        is_admin: Является ли пользователь администратором
        is_tracked: Отслеживается ли статистика пользователя
        notes: Опциональные заметки
    
    Returns:
        bool: True если успешно
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        param = get_param()
        
        # Проверяем, существует ли пользователь
        cursor.execute(f"SELECT is_admin, is_tracked FROM users WHERE user_id = {param}", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующего пользователя
            existing_admin = existing[0] if USE_POSTGRES else existing['is_admin']
            existing_tracked = existing[1] if USE_POSTGRES else existing['is_tracked']
            
            if USE_POSTGRES:
                cursor.execute(f"""
                    UPDATE users 
                    SET username = COALESCE({param}, username),
                        is_admin = {param},
                        is_tracked = {param},
                        notes = COALESCE({param}, notes)
                    WHERE user_id = {param}
                """, (username, 1 if is_admin else existing_admin, 
                      1 if is_tracked else existing_tracked, notes, user_id))
            else:
                cursor.execute(f"""
                    UPDATE users 
                    SET username = COALESCE({param}, username),
                        is_admin = {param},
                        is_tracked = {param},
                        notes = COALESCE({param}, notes)
                    WHERE user_id = {param}
                """, (username, 1 if is_admin else existing_admin, 
                      1 if is_tracked else existing_tracked, notes, user_id))
        else:
            # Добавляем нового пользователя
            cursor.execute(f"""
                INSERT INTO users (user_id, username, is_admin, is_tracked, notes)
                VALUES ({param}, {param}, {param}, {param}, {param})
            """, (user_id, username, 1 if is_admin else 0, 1 if is_tracked else 0, notes))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении/обновлении пользователя: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        if conn:
            return_connection(conn)

def remove_user(user_id):
    """
    Удаляет пользователя из списка отслеживаемых (но не удаляет из БД полностью)
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        bool: True если удалено успешно
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        param = get_param()
        cursor.execute(f"UPDATE users SET is_tracked = 0 WHERE user_id = {param}", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        if conn:
            return_connection(conn)

def get_tracked_users():
    """
    Получает список всех отслеживаемых пользователей
    
    Returns:
        set: Множество user_id
    """
    conn = get_connection()
    if not conn:
        return set()
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE is_tracked = 1")
        results = cursor.fetchall()
        if USE_POSTGRES:
            return {row[0] for row in results}
        else:
            return {row['user_id'] for row in results}
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}", exc_info=True)
        return set()
    finally:
        if conn:
            return_connection(conn)

def get_tracked_users_with_info():
    """
    Получает список всех отслеживаемых пользователей с информацией
    
    Returns:
        list: Список словарей с user_id и username
    """
    conn = get_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username FROM users WHERE is_tracked = 1 ORDER BY added_at DESC")
        results = cursor.fetchall()
        if USE_POSTGRES:
            return [{'user_id': row[0], 'username': row[1]} for row in results]
        else:
            return [{'user_id': row['user_id'], 'username': row['username']} for row in results]
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}", exc_info=True)
        return []
    finally:
        if conn:
            return_connection(conn)

def is_superuser(user_id):
    """
    Проверяет, является ли пользователь супер-пользователем
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        bool: True если пользователь супер-пользователь
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        param = get_param()
        cursor.execute(f"SELECT 1 FROM users WHERE user_id = {param} AND is_admin = 1 LIMIT 1", (user_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке супер-пользователя: {e}", exc_info=True)
        return False
    finally:
        if conn:
            return_connection(conn)

def is_tracked_user(user_id):
    """
    Проверяет, отслеживается ли пользователь
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        bool: True если пользователь отслеживается
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        param = get_param()
        cursor.execute(f"SELECT 1 FROM users WHERE user_id = {param} AND is_tracked = 1 LIMIT 1", (user_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя: {e}", exc_info=True)
        return False
    finally:
        if conn:
            return_connection(conn)

def add_admin(user_id, username=None):
    """
    Добавляет пользователя в список администраторов
    
    Args:
        user_id: ID пользователя Telegram
        username: Username пользователя (опционально)
    
    Returns:
        bool: True если добавлено успешно
    """
    return add_user(user_id, username=username, is_admin=True, is_tracked=True)

def remove_admin(user_id):
    """
    Убирает права администратора у пользователя
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        bool: True если успешно
    """
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        param = get_param()
        cursor.execute(f"UPDATE users SET is_admin = 0 WHERE user_id = {param}", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении администратора: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        if conn:
            return_connection(conn)

# Алиасы для обратной совместимости
def add_tracked_user(user_id, username=None, notes=None):
    """Добавляет пользователя в список отслеживаемых (для обратной совместимости)"""
    return add_user(user_id, username=username, is_tracked=True, notes=notes)
