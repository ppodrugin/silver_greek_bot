"""
Работа с базой данных (SQLite для локальной разработки, PostgreSQL для продакшена)
"""
import logging
import os

logger = logging.getLogger(__name__)

# Определяем, какую БД использовать
USE_POSTGRES = bool(os.getenv('DATABASE_URL'))

if USE_POSTGRES:
    # Используем PostgreSQL (для Render)
    logger.info("Используется PostgreSQL (DATABASE_URL найден)")
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
                    connection_pool = ThreadedConnectionPool(1, 5, db_url)
                    logger.info("✅ Пул соединений PostgreSQL создан")
                except Exception as e:
                    logger.error(f"Ошибка создания пула соединений PostgreSQL: {e}", exc_info=True)
                    return None
            
            try:
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
    except ImportError:
        logger.error("psycopg2 не установлен! Установите: pip install psycopg2-binary")
        USE_POSTGRES = False

if not USE_POSTGRES:
    # Используем SQLite (для локальной разработки)
    logger.info("Используется SQLite (локальная разработка)")
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

def init_database():
    """Инициализирует базу данных и создает таблицу если её нет"""
    try:
        conn = get_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # Определяем тип БД и проверяем существование таблицы
        if USE_POSTGRES:
            # PostgreSQL - проверяем через information_schema
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'vocabulary');")
            table_exists = cursor.fetchone()[0]
        else:
            # SQLite - проверяем через sqlite_master
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vocabulary';")
            table_exists = cursor.fetchone()
        
        if table_exists and not USE_POSTGRES:
            # Таблица существует - для SQLite проверяем структуру
            cursor.execute("PRAGMA table_info(vocabulary);")
            columns = {row[1]: row for row in cursor.fetchall()}
            
            # Проверяем, есть ли колонка user_id
            if 'user_id' not in columns:
                # Старая таблица без user_id - нужно мигрировать
                logger.info("Обнаружена старая таблица vocabulary. Выполняем миграцию...")
                
                # ВАЖНО: Сохраняем статистику перед миграцией, чтобы не потерять данные
                logger.info("Сохранение статистики перед миграцией...")
                cursor.execute("""
                    SELECT ws.user_id, v.id as word_id, ws.successful, ws.unsuccessful
                    FROM word_statistics ws
                    JOIN vocabulary v ON ws.word_id = v.id
                """)
                saved_stats = cursor.fetchall()
                logger.info(f"Сохранено {len(saved_stats)} записей статистики")
                
                # Создаем временную таблицу с новой структурой
                cursor.execute("""
                CREATE TABLE vocabulary_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    greek TEXT NOT NULL,
                    russian TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, greek, russian)
                );
                """)
                
                # Копируем данные из старой таблицы
                cursor.execute("""
                INSERT INTO vocabulary_new (id, user_id, greek, russian, created_at)
                SELECT id, 0, greek, russian, created_at FROM vocabulary;
                """)
                
                # Временно отключаем внешний ключ для безопасного удаления таблицы
                cursor.execute("PRAGMA foreign_keys = OFF;")
                
                # Удаляем старую таблицу
                cursor.execute("DROP TABLE vocabulary;")
                
                # Переименовываем новую таблицу
                cursor.execute("ALTER TABLE vocabulary_new RENAME TO vocabulary;")
                
                # Включаем внешний ключ обратно
                cursor.execute("PRAGMA foreign_keys = ON;")
                
                # Восстанавливаем статистику после миграции
                if saved_stats:
                    logger.info("Восстановление статистики после миграции...")
                    for stat_row in saved_stats:
                        old_word_id = stat_row['word_id']
                        user_id_stat = stat_row['user_id']
                        successful = stat_row['successful']
                        unsuccessful = stat_row['unsuccessful']
                        
                        # Находим новый ID слова по старому ID (они должны совпадать)
                        cursor.execute("SELECT id FROM vocabulary WHERE id = ?", (old_word_id,))
                        new_word_row = cursor.fetchone()
                        if new_word_row:
                            new_word_id = new_word_row['id']
                            cursor.execute("""
                                INSERT INTO word_statistics (user_id, word_id, successful, unsuccessful)
                                VALUES (?, ?, ?, ?)
                            """, (user_id_stat, new_word_id, successful, unsuccessful))
                    logger.info(f"✅ Восстановлено {len(saved_stats)} записей статистики")
                
                # Коммитим изменения после миграции
                conn.commit()
                logger.info("✅ Миграция завершена")
            else:
                # Таблица уже имеет user_id - проверяем ограничение уникальности
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='vocabulary';")
                table_sql = cursor.fetchone()[0]
                
                # Если в SQL нет UNIQUE(user_id, greek, russian), нужно пересоздать таблицу
                if 'UNIQUE(user_id, greek, russian)' not in table_sql and 'UNIQUE(user_id,greek,russian)' not in table_sql:
                    logger.info("Обнаружено старое ограничение уникальности. Выполняем миграцию...")
                    
                    # ВАЖНО: Сохраняем статистику перед миграцией, чтобы не потерять данные
                    logger.info("Сохранение статистики перед миграцией...")
                    cursor.execute("""
                        SELECT ws.user_id, v.id as word_id, ws.successful, ws.unsuccessful
                        FROM word_statistics ws
                        JOIN vocabulary v ON ws.word_id = v.id
                    """)
                    saved_stats = cursor.fetchall()
                    logger.info(f"Сохранено {len(saved_stats)} записей статистики")
                    
                    # Создаем временную таблицу с правильным ограничением
                    cursor.execute("""
                    CREATE TABLE vocabulary_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL DEFAULT 0,
                        greek TEXT NOT NULL,
                        russian TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, greek, russian)
                    );
                    """)
                    
                    # Копируем данные
                    cursor.execute("""
                    INSERT OR IGNORE INTO vocabulary_new (id, user_id, greek, russian, created_at)
                    SELECT id, COALESCE(user_id, 0), greek, russian, created_at FROM vocabulary;
                    """)
                    
                    # Временно отключаем внешний ключ для безопасного удаления таблицы
                    cursor.execute("PRAGMA foreign_keys = OFF;")
                    
                    # Удаляем старую таблицу
                    cursor.execute("DROP TABLE vocabulary;")
                    
                    # Переименовываем новую таблицу
                    cursor.execute("ALTER TABLE vocabulary_new RENAME TO vocabulary;")
                    
                    # Включаем внешний ключ обратно
                    cursor.execute("PRAGMA foreign_keys = ON;")
                    
                    # Восстанавливаем статистику после миграции
                    if saved_stats:
                        logger.info("Восстановление статистики после миграции...")
                        for stat_row in saved_stats:
                            old_word_id = stat_row['word_id']
                            user_id_stat = stat_row['user_id']
                            successful = stat_row['successful']
                            unsuccessful = stat_row['unsuccessful']
                            
                            # Находим новый ID слова по старому ID (они должны совпадать)
                            cursor.execute("SELECT id FROM vocabulary WHERE id = ?", (old_word_id,))
                            new_word_row = cursor.fetchone()
                            if new_word_row:
                                new_word_id = new_word_row['id']
                                cursor.execute("""
                                    INSERT INTO word_statistics (user_id, word_id, successful, unsuccessful)
                                    VALUES (?, ?, ?, ?)
                                """, (user_id_stat, new_word_id, successful, unsuccessful))
                        logger.info(f"✅ Восстановлено {len(saved_stats)} записей статистики")
                    
                    # Коммитим изменения после миграции
                    conn.commit()
                    logger.info("✅ Миграция ограничения уникальности завершена")
        elif not table_exists:
            # Таблица не существует - создаем новую
            if USE_POSTGRES:
                # PostgreSQL
                create_table_query = """
                CREATE TABLE vocabulary (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    greek TEXT NOT NULL,
                    russian TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, greek, russian)
                );
                """
            else:
                # SQLite
                create_table_query = """
                CREATE TABLE vocabulary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    greek TEXT NOT NULL,
                    russian TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, greek, russian)
                );
                """
            cursor.execute(create_table_query)
        
        # Создаем таблицу статистики по словам для пользователей
        # Проверяем существование таблицы
        if USE_POSTGRES:
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'word_statistics');")
            stats_table_exists = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='word_statistics';")
            stats_table_exists = cursor.fetchone()
        
        if not stats_table_exists:
            # Таблица не существует - создаем
            if USE_POSTGRES:
                create_stats_table_query = """
                CREATE TABLE word_statistics (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    word_id INTEGER NOT NULL,
                    successful INTEGER DEFAULT 0,
                    unsuccessful INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, word_id),
                    FOREIGN KEY (word_id) REFERENCES vocabulary(id) ON DELETE CASCADE
                );
                """
            else:
                create_stats_table_query = """
                CREATE TABLE word_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    word_id INTEGER NOT NULL,
                    successful INTEGER DEFAULT 0,
                    unsuccessful INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, word_id),
                    FOREIGN KEY (word_id) REFERENCES vocabulary(id) ON DELETE CASCADE
                );
                """
            
            cursor.execute(create_stats_table_query)
            logger.info(f"✅ Таблица word_statistics создана для {'PostgreSQL' if USE_POSTGRES else 'SQLite'}")
        
        # Создаем единую таблицу пользователей
        if USE_POSTGRES:
            create_users_table_query = """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_admin INTEGER DEFAULT 0,
                is_tracked INTEGER DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            );
            """
        else:
            create_users_table_query = """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_admin INTEGER DEFAULT 0,
                is_tracked INTEGER DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            );
            """
        
        cursor.execute(create_users_table_query)
        
        # Миграция данных из старых таблиц (только для SQLite)
        if not USE_POSTGRES:
            try:
                # Проверяем существование старых таблиц
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='superusers'")
                if cursor.fetchone():
                    # Мигрируем супер-пользователей
                    cursor.execute("SELECT user_id, username FROM superusers")
                for row in cursor.fetchall():
                    username = row['username'] if 'username' in row.keys() else None
                    cursor.execute("""
                        INSERT OR REPLACE INTO users (user_id, username, is_admin, is_tracked)
                        VALUES (?, ?, 1, 1)
                    """, (row['user_id'], username))
                    
                    # Удаляем старую таблицу
                    cursor.execute("DROP TABLE superusers")
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_users'")
                if cursor.fetchone():
                    # Мигрируем отслеживаемых пользователей
                    cursor.execute("SELECT user_id, username FROM tracked_users")
                    for row in cursor.fetchall():
                        username = row['username'] if 'username' in row.keys() else None
                        cursor.execute("""
                            INSERT OR REPLACE INTO users (user_id, username, is_admin, is_tracked)
                            VALUES (?, ?, 
                                COALESCE((SELECT is_admin FROM users WHERE user_id = ?), 0),
                                1)
                        """, (row['user_id'], username, row['user_id']))
                    
                    # Удаляем старую таблицу
                    cursor.execute("DROP TABLE tracked_users")
            except Exception as e:
                logger.warning(f"Предупреждение при миграции: {e}", exc_info=True)
        
        # Добавляем первого супер-пользователя (владельца бота)
        SUPERUSER_ID = 799341043
        if USE_POSTGRES:
            cursor.execute("""
                INSERT INTO users (user_id, is_admin, is_tracked)
                VALUES (%s, 1, 1)
                ON CONFLICT (user_id) DO NOTHING
            """, (SUPERUSER_ID,))
        else:
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, is_admin, is_tracked)
                VALUES (?, 1, 1)
            """, (SUPERUSER_ID,))
        
        # Создаем индексы для быстрого поиска
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_word ON word_statistics(user_id, word_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_word_id ON word_statistics(word_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocabulary_user_id ON vocabulary(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_tracked ON users(is_tracked);")
        
        conn.commit()
        
        db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
        logger.info(f"✅ База данных {db_type} инициализирована")
        logger.info(f"✅ Супер-пользователь {SUPERUSER_ID} добавлен")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}", exc_info=True)
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
        # Проверяем, существует ли пользователь
        if USE_POSTGRES:
            cursor.execute("SELECT is_admin, is_tracked FROM users WHERE user_id = %s", (user_id,))
        else:
            cursor.execute("SELECT is_admin, is_tracked FROM users WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующего пользователя
            if USE_POSTGRES:
                cursor.execute("""
                    UPDATE users 
                    SET username = COALESCE(%s, username),
                        is_admin = %s,
                        is_tracked = %s,
                        notes = COALESCE(%s, notes)
                    WHERE user_id = %s
                """, (username, 1 if is_admin else existing['is_admin'], 
                      1 if is_tracked else existing['is_tracked'], notes, user_id))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET username = COALESCE(?, username),
                        is_admin = ?,
                        is_tracked = ?,
                        notes = COALESCE(?, notes)
                    WHERE user_id = ?
                """, (username, 1 if is_admin else existing['is_admin'], 
                      1 if is_tracked else existing['is_tracked'], notes, user_id))
        else:
            # Добавляем нового пользователя
            if USE_POSTGRES:
                cursor.execute("""
                    INSERT INTO users (user_id, username, is_admin, is_tracked, notes)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, username, 1 if is_admin else 0, 1 if is_tracked else 0, notes))
            else:
                cursor.execute("""
                    INSERT INTO users (user_id, username, is_admin, is_tracked, notes)
                    VALUES (?, ?, ?, ?, ?)
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
        # Убираем флаг отслеживания, но оставляем пользователя в БД
        cursor.execute("UPDATE users SET is_tracked = 0 WHERE user_id = ?", (user_id,))
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
        query = "SELECT user_id FROM users WHERE is_tracked = 1"
        cursor.execute(query)
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
        query = "SELECT user_id, username FROM users WHERE is_tracked = 1 ORDER BY added_at DESC"
        cursor.execute(query)
        results = cursor.fetchall()
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
        if USE_POSTGRES:
            query = "SELECT 1 FROM users WHERE user_id = %s AND is_admin = 1 LIMIT 1"
        else:
            query = "SELECT 1 FROM users WHERE user_id = ? AND is_admin = 1 LIMIT 1"
        cursor.execute(query, (user_id,))
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
        query = "SELECT 1 FROM users WHERE user_id = ? AND is_tracked = 1 LIMIT 1"
        cursor.execute(query, (user_id,))
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
        if USE_POSTGRES:
            cursor.execute("UPDATE users SET is_admin = 0 WHERE user_id = %s", (user_id,))
        else:
            cursor.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
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
