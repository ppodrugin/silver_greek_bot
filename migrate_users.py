#!/usr/bin/env python3
"""
Скрипт для миграции пользователей из users.txt в базу данных
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from database import init_database, add_tracked_user, get_tracked_users

def migrate_users_from_file():
    """Мигрирует пользователей из users.txt в базу данных"""
    # Инициализируем БД
    if not init_database():
        print("❌ Не удалось инициализировать БД")
        return False
    
    users_file = os.path.join(os.path.dirname(__file__), 'users.txt')
    
    if not os.path.exists(users_file):
        print("⚠️ Файл users.txt не найден")
        return True
    
    # Загружаем пользователей из файла
    users_from_file = []
    with open(users_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Пропускаем комментарии и пустые строки
            if line and not line.startswith('#'):
                try:
                    user_id = int(line)
                    users_from_file.append(user_id)
                except ValueError:
                    continue
    
    if not users_from_file:
        print("ℹ️ В файле users.txt нет пользователей для миграции")
        return True
    
    # Получаем уже существующих пользователей из БД
    existing_users = get_tracked_users()
    
    # Добавляем пользователей в БД
    added_count = 0
    skipped_count = 0
    
    for user_id in users_from_file:
        if user_id in existing_users:
            print(f"⏭️ Пользователь {user_id} уже в базе данных")
            skipped_count += 1
        else:
            if add_tracked_user(user_id):
                print(f"✅ Добавлен пользователь {user_id}")
                added_count += 1
            else:
                print(f"❌ Ошибка при добавлении пользователя {user_id}")
    
    print(f"\n📊 Результаты миграции:")
    print(f"   Добавлено: {added_count}")
    print(f"   Пропущено (уже есть): {skipped_count}")
    print(f"   Всего в БД: {len(get_tracked_users())}")
    
    return True

if __name__ == "__main__":
    print("Миграция пользователей из users.txt в базу данных...")
    print("=" * 60)
    
    if migrate_users_from_file():
        print("\n✅ Миграция завершена успешно!")
        print("\n💡 Теперь можно удалить файл users.txt - пользователи хранятся в БД")
    else:
        print("\n❌ Ошибка при миграции")

