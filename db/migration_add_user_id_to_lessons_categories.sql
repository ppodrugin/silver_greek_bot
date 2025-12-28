-- Миграция: добавление поля user_id в таблицы lessons и categories
-- PostgreSQL версия
-- Этот скрипт можно использовать для обновления существующей базы данных

-- ВАЖНО: Перед выполнением этого скрипта убедитесь, что у вас есть хотя бы один отслеживаемый пользователь или администратор.
-- Существующие уроки и категории будут присвоены первому найденному администратору или отслеживаемому пользователю.

-- 1. Добавляем поле user_id в таблицу lessons
DO $$
DECLARE
    default_user_id INTEGER;
BEGIN
    -- Получаем ID первого администратора или отслеживаемого пользователя
    SELECT user_id INTO default_user_id 
    FROM users 
    WHERE is_admin = 1 OR is_tracked = 1 
    ORDER BY is_admin DESC, added_at ASC 
    LIMIT 1;
    
    -- Проверяем, существует ли уже поле user_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'lessons' AND column_name = 'user_id'
    ) THEN
        -- Добавляем колонку с временным значением NULL
        ALTER TABLE lessons ADD COLUMN user_id INTEGER;
        
        -- Если есть пользователь, присваиваем существующие уроки ему
        IF default_user_id IS NOT NULL THEN
            UPDATE lessons SET user_id = default_user_id WHERE user_id IS NULL;
            RAISE NOTICE 'Существующие уроки присвоены пользователю %', default_user_id;
        ELSE
            -- Если нет пользователей, удаляем существующие уроки
            DELETE FROM lessons WHERE user_id IS NULL;
            RAISE WARNING 'Существующие уроки удалены (нет пользователей для присвоения)';
        END IF;
        
        -- Делаем поле обязательным
        ALTER TABLE lessons ALTER COLUMN user_id SET NOT NULL;
        
        -- Удаляем старое уникальное ограничение на name (если существует)
        ALTER TABLE lessons DROP CONSTRAINT IF EXISTS lessons_name_key;
        
        -- Создаем новый уникальный индекс на (user_id, name)
        CREATE UNIQUE INDEX IF NOT EXISTS lessons_user_id_name_key ON lessons(user_id, name);
        
        -- Создаем индекс на user_id
        CREATE INDEX IF NOT EXISTS idx_lessons_user_id ON lessons(user_id);
        
        RAISE NOTICE 'Поле user_id добавлено в таблицу lessons';
    ELSE
        RAISE NOTICE 'Поле user_id уже существует в таблице lessons';
    END IF;
END $$;

-- 2. Добавляем поле user_id в таблицу categories
DO $$
DECLARE
    default_user_id INTEGER;
BEGIN
    -- Получаем ID первого администратора или отслеживаемого пользователя
    SELECT user_id INTO default_user_id 
    FROM users 
    WHERE is_admin = 1 OR is_tracked = 1 
    ORDER BY is_admin DESC, added_at ASC 
    LIMIT 1;
    
    -- Проверяем, существует ли уже поле user_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'categories' AND column_name = 'user_id'
    ) THEN
        -- Добавляем колонку с временным значением NULL
        ALTER TABLE categories ADD COLUMN user_id INTEGER;
        
        -- Если есть пользователь, присваиваем существующие категории ему
        IF default_user_id IS NOT NULL THEN
            UPDATE categories SET user_id = default_user_id WHERE user_id IS NULL;
            RAISE NOTICE 'Существующие категории присвоены пользователю %', default_user_id;
        ELSE
            -- Если нет пользователей, удаляем существующие категории
            DELETE FROM categories WHERE user_id IS NULL;
            RAISE WARNING 'Существующие категории удалены (нет пользователей для присвоения)';
        END IF;
        
        -- Делаем поле обязательным
        ALTER TABLE categories ALTER COLUMN user_id SET NOT NULL;
        
        -- Удаляем старое уникальное ограничение на name (если существует)
        ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_name_key;
        
        -- Создаем новый уникальный индекс на (user_id, name)
        CREATE UNIQUE INDEX IF NOT EXISTS categories_user_id_name_key ON categories(user_id, name);
        
        -- Создаем индекс на user_id
        CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories(user_id);
        
        RAISE NOTICE 'Поле user_id добавлено в таблицу categories';
    ELSE
        RAISE NOTICE 'Поле user_id уже существует в таблице categories';
    END IF;
END $$;

