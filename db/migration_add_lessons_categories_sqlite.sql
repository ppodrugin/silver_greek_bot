-- Миграция: добавление таблиц lessons и categories, а также полей lesson_id и category_id в vocabulary
-- SQLite версия
-- Этот скрипт можно использовать для обновления существующей базы данных

-- Создаем таблицу lessons (если не существует)
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Создаем таблицу categories (если не существует)
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- SQLite не поддерживает ALTER TABLE ADD COLUMN с проверкой существования через IF NOT EXISTS
-- Поэтому сначала проверяем наличие колонок через PRAGMA table_info

-- Добавляем lesson_id (если его еще нет)
-- Примечание: SQLite не поддерживает проверку существования колонки напрямую в ALTER TABLE
-- Нужно выполнить это вручную или через скрипт Python
-- Для автоматической проверки можно использовать следующий подход:

-- В SQLite нужно сначала проверить наличие колонки через PRAGMA table_info,
-- а затем добавить её, если её нет. Это лучше делать через Python скрипт.
-- Но для ручного выполнения можно использовать:

-- Проверка: PRAGMA table_info(vocabulary);
-- Если lesson_id отсутствует, выполнить:
ALTER TABLE vocabulary ADD COLUMN lesson_id INTEGER;

-- Проверка: PRAGMA table_info(vocabulary);
-- Если category_id отсутствует, выполнить:
ALTER TABLE vocabulary ADD COLUMN category_id INTEGER;

-- Добавляем внешние ключи (SQLite требует включения поддержки внешних ключей)
-- Включение поддержки внешних ключей (должно быть выполнено перед созданием таблиц)
PRAGMA foreign_keys = ON;

-- В SQLite внешние ключи добавляются при создании таблицы или через пересоздание
-- Для существующей таблицы нужно пересоздать её с внешними ключами
-- Это сложная операция, требующая сохранения данных, пересоздания таблицы и восстановления данных
-- Рекомендуется выполнять через Python скрипт или вручную

-- Создаем индексы (если их еще нет)
CREATE INDEX IF NOT EXISTS idx_vocabulary_lesson_id ON vocabulary(lesson_id);
CREATE INDEX IF NOT EXISTS idx_vocabulary_category_id ON vocabulary(category_id);

