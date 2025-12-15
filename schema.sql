-- Схема базы данных для Telegram бота изучения греческого языка
-- Поддерживает как SQLite, так и PostgreSQL

-- Таблица словаря пользователей
-- Каждое слово привязано к пользователю и содержит статистику тренировок
CREATE TABLE IF NOT EXISTS vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- SQLite: AUTOINCREMENT, PostgreSQL: SERIAL
    user_id INTEGER NOT NULL,
    greek TEXT NOT NULL,
    russian TEXT NOT NULL,
    successful INTEGER DEFAULT 0,
    unsuccessful INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, greek, russian)
);

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    is_admin INTEGER DEFAULT 0,
    is_tracked INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_vocabulary_user_id ON vocabulary(user_id);
CREATE INDEX IF NOT EXISTS idx_vocabulary_stats ON vocabulary(user_id, successful, unsuccessful);
CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);
CREATE INDEX IF NOT EXISTS idx_users_is_tracked ON users(is_tracked);

