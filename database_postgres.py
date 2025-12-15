"""
Работа с базой данных PostgreSQL (для Render)
"""
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

# Пул соединений для PostgreSQL
connection_pool = None

def get_connection():
    """Создает соединение с базой данных PostgreSQL"""
    global connection_pool
    
    # Если пул не создан, создаем его
    if connection_pool is None:
        try:
            # Получаем параметры подключения из переменных окружения
            db_url = os.getenv('DATABASE_URL')
            
            if not db_url:
                # Если DATABASE_URL не установлен, пробуем отдельные параметры
                db_host = os.getenv('DB_HOST', 'localhost')
                db_port = os.getenv('DB_PORT', '5432')
                db_name = os.getenv('DB_NAME', 'vocabulary')
                db_user = os.getenv('DB_USER', 'postgres')
                db_password = os.getenv('DB_PASSWORD', '')
                
                # Формируем строку подключения
                db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            
            # Создаем пул соединений (минимум 1, максимум 5 соединений)
            connection_pool = ThreadedConnectionPool(1, 5, db_url)
            logger.info("✅ Пул соединений PostgreSQL создан")
        except Exception as e:
            logger.error(f"Ошибка создания пула соединений PostgreSQL: {e}", exc_info=True)
            return None
    
    try:
        # Получаем соединение из пула
        conn = connection_pool.getconn()
        return conn
    except Exception as e:
        logger.error(f"Ошибка получения соединения из пула: {e}", exc_info=True)
        return None

def return_connection(conn):
    """Возвращает соединение в пул"""
    global connection_pool
    if connection_pool and conn:
        try:
            connection_pool.putconn(conn)
        except Exception as e:
            logger.error(f"Ошибка возврата соединения в пул: {e}", exc_info=True)

def init_database():
    """Инициализирует базу данных и создает таблицы если их нет"""
    conn = get_connection()
    if not conn:
        logger.error("Не удалось подключиться к PostgreSQL")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Создаем таблицу vocabulary
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 0,
                greek TEXT NOT NULL,
                russian TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, greek, russian)
            );
        """)
        
        # Создаем таблицу статистики по словам
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS word_statistics (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                successful INTEGER DEFAULT 0,
                unsuccessful INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, word_id),
                FOREIGN KEY (word_id) REFERENCES vocabulary(id) ON DELETE CASCADE
            );
        """)
        
        # Создаем таблицу пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_admin INTEGER DEFAULT 0,
                is_tracked INTEGER DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            );
        """)
        
        # Добавляем первого супер-пользователя
        SUPERUSER_ID = 799341043
        cursor.execute("""
            INSERT INTO users (user_id, is_admin, is_tracked)
            VALUES (%s, 1, 1)
            ON CONFLICT (user_id) DO NOTHING
        """, (SUPERUSER_ID,))
        
        # Создаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_word ON word_statistics(user_id, word_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_word_id ON word_statistics(word_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocabulary_user_id ON vocabulary(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_tracked ON users(is_tracked);")
        
        conn.commit()
        
        logger.info("✅ База данных PostgreSQL инициализирована")
        logger.info(f"✅ Супер-пользователь {SUPERUSER_ID} добавлен")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        return_connection(conn)

def add_user(user_id, username=None, is_admin=False, is_tracked=False, notes=None):
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, username, is_admin, is_tracked, notes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET username = COALESCE(EXCLUDED.username, users.username),
                is_admin = CASE WHEN %s THEN EXCLUDED.is_admin ELSE users.is_admin END,
                is_tracked = CASE WHEN %s THEN EXCLUDED.is_tracked ELSE users.is_tracked END,
                notes = COALESCE(EXCLUDED.notes, users.notes)
        """, (user_id, username, 1 if is_admin else 0, 1 if is_tracked else 0, notes, is_admin, is_tracked))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении/обновлении пользователя: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        return_connection(conn)

def remove_user(user_id):
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_tracked = 0 WHERE user_id = %s", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        return_connection(conn)

def get_tracked_users():
    conn = get_connection()
    if not conn:
        return set()
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE is_tracked = 1")
        results = cursor.fetchall()
        return {row[0] for row in results}
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}", exc_info=True)
        return set()
    finally:
        return_connection(conn)

def get_tracked_users_with_info():
    conn = get_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username FROM users WHERE is_tracked = 1 ORDER BY added_at DESC")
        results = cursor.fetchall()
        return [{'user_id': row[0], 'username': row[1]} for row in results]
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}", exc_info=True)
        return []
    finally:
        return_connection(conn)

def is_superuser(user_id):
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = %s AND is_admin = 1 LIMIT 1", (user_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке супер-пользователя: {e}", exc_info=True)
        return False
    finally:
        return_connection(conn)

def is_tracked_user(user_id):
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = %s AND is_tracked = 1 LIMIT 1", (user_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя: {e}", exc_info=True)
        return False
    finally:
        return_connection(conn)

def add_admin(user_id, username=None):
    return add_user(user_id, username=username, is_admin=True, is_tracked=True)

def remove_admin(user_id):
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_admin = 0 WHERE user_id = %s", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении администратора: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        return_connection(conn)

