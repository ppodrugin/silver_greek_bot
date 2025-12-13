#!/usr/bin/env python3
"""
Тест добавления нескольких слов
"""
import sys
import os
sys.path.insert(0, '.')

from database import init_database
from vocabulary import Vocabulary

def test_add_words():
    """Тестирует добавление нескольких слов"""
    # Удаляем старую БД для чистого теста
    db_path = os.path.join(os.path.dirname(__file__), 'vocabulary.db')
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Удалена старая БД для чистого теста")
    
    print("Инициализация БД...")
    if not init_database():
        print("❌ Не удалось инициализировать БД")
        return False
    
    vocab = Vocabulary()
    
    # Тест 1: Многострочный формат (как в voc.txt)
    print("\nТест 1: Многострочный формат")
    test_text1 = """η οικογένεια
семья

ο πατέρας
отец

η μητέρα
мать
"""
    
    # Парсим тестовый текст
    words = []
    lines = test_text1.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        greek = line
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        
        if i < len(lines):
            russian = lines[i].strip()
            if greek and russian:
                words.append((greek, russian))
            i += 1
        else:
            break
    
    print(f"Найдено пар слов: {len(words)}")
    for greek, russian in words:
        print(f"  - {greek} -> {russian}")
    
    # Добавляем слова
    added, skipped = vocab.add_words_batch(words)
    print(f"\nРезультат: добавлено {added}, пропущено {skipped}")
    
    # Проверяем количество
    count = vocab.count()
    print(f"Всего слов в словаре: {count}")
    
    # Тест 2: CSV формат
    print("\nТест 2: CSV формат")
    test_text2 = """ο γιος,сын
η κόρη,дочь
ο αδελφός,брат"""
    
    words2 = []
    for line in test_text2.strip().split('\n'):
        if ',' in line:
            parts = line.split(',', 1)
            if len(parts) == 2:
                words2.append((parts[0].strip(), parts[1].strip()))
    
    print(f"Найдено пар слов: {len(words2)}")
    added2, skipped2 = vocab.add_words_batch(words2)
    print(f"Результат: добавлено {added2}, пропущено {skipped2}")
    
    count2 = vocab.count()
    print(f"Всего слов в словаре: {count2}")
    
    # Проверяем, что слова добавились
    if count2 >= len(words) + len(words2):
        print("\n✅ Тест пройден! Слова успешно добавлены")
        return True
    else:
        print(f"\n❌ Ошибка: ожидалось минимум {len(words) + len(words2)} слов, получено {count2}")
        return False

if __name__ == "__main__":
    success = test_add_words()
    sys.exit(0 if success else 1)

