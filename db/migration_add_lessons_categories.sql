-- Миграция: добавление таблиц lessons и categories, а также полей lesson_id и category_id в vocabulary
-- Этот скрипт можно использовать для обновления существующей базы данных

-- ============================================
-- PostgreSQL версия
-- ============================================

-- Создаем таблицу lessons (если не существует)
CREATE TABLE IF NOT EXISTS lessons (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- Создаем таблицу categories (если не существует)
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- Добавляем поля lesson_id и category_id в таблицу vocabulary (если их еще нет)
DO $$
BEGIN
    -- Проверяем и добавляем lesson_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vocabulary' AND column_name = 'lesson_id'
    ) THEN
        ALTER TABLE vocabulary ADD COLUMN lesson_id INTEGER;
    END IF;
    
    -- Проверяем и добавляем category_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vocabulary' AND column_name = 'category_id'
    ) THEN
        ALTER TABLE vocabulary ADD COLUMN category_id INTEGER;
    END IF;
END $$;

-- Добавляем внешние ключи (если их еще нет)
DO $$
BEGIN
    -- Проверяем существование внешнего ключа для lesson_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'vocabulary_lesson_id_fkey' 
        AND table_name = 'vocabulary'
    ) THEN
        ALTER TABLE vocabulary 
        ADD CONSTRAINT vocabulary_lesson_id_fkey 
        FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE SET NULL;
    END IF;
    
    -- Проверяем существование внешнего ключа для category_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'vocabulary_category_id_fkey' 
        AND table_name = 'vocabulary'
    ) THEN
        ALTER TABLE vocabulary 
        ADD CONSTRAINT vocabulary_category_id_fkey 
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Создаем индексы (если их еще нет)
CREATE INDEX IF NOT EXISTS idx_vocabulary_lesson_id ON vocabulary(lesson_id);
CREATE INDEX IF NOT EXISTS idx_vocabulary_category_id ON vocabulary(category_id);

