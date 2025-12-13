"""
Работа со словарем через SQLite
"""
import logging
import random
from database import get_connection

logger = logging.getLogger(__name__)

class Vocabulary:
    def __init__(self, user_id=None):
        """
        Args:
            user_id: ID пользователя для работы с персональным словарем
        """
        self.user_id = user_id
    
    def load_vocabulary(self):
        """Загружает словарь из базы данных (для совместимости)"""
        pass
    
    def add_word(self, greek, russian):
        """
        Добавляет слово в словарь пользователя
        
        Args:
            greek: греческое слово
            russian: русский перевод
        
        Returns:
            bool: True если добавлено успешно, False если уже существует
        """
        if self.user_id is None:
            raise ValueError("user_id должен быть указан для добавления слов")
        
        conn = get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            # Проверяем, существует ли уже такое слово у этого пользователя
            check_query = "SELECT id FROM vocabulary WHERE user_id = ? AND greek = ? AND russian = ?"
            cursor.execute(check_query, (self.user_id, greek, russian))
            
            if cursor.fetchone():
                return False  # Слово уже существует
            
            # Добавляем слово
            insert_query = "INSERT INTO vocabulary (user_id, greek, russian) VALUES (?, ?, ?)"
            cursor.execute(insert_query, (self.user_id, greek, russian))
            conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении слова: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def add_words_batch(self, words):
        """
        Добавляет несколько слов за раз (оптимизированная версия)
        
        Args:
            words: список кортежей [(greek, russian), ...]
        
        Returns:
            tuple: (добавлено, пропущено_дубликатов)
        """
        if self.user_id is None:
            raise ValueError("user_id должен быть указан для добавления слов")
        
        if not words:
            return (0, 0)
        
        conn = get_connection()
        if not conn:
            return (0, 0)
        
        added = 0
        skipped = 0
        
        try:
            cursor = conn.cursor()
            
            # Валидация входных данных
            valid_words = []
            for greek, russian in words:
                # Проверяем, что слова не пустые и не слишком длинные
                if greek and russian and len(greek.strip()) > 0 and len(russian.strip()) > 0:
                    if len(greek) > 500 or len(russian) > 500:
                        logger.warning(f"Слово пропущено из-за длины: greek={len(greek)}, russian={len(russian)}")
                        skipped += 1
                        continue
                    valid_words.append((greek.strip(), russian.strip()))
                else:
                    skipped += 1
            
            if not valid_words:
                return (0, skipped)
            
            # Оптимизация: проверяем все слова одним запросом
            # Используем более простой подход для совместимости с SQLite
            if len(valid_words) == 1:
                # Для одного слова используем простой запрос
                greek, russian = valid_words[0]
                check_query = "SELECT 1 FROM vocabulary WHERE user_id = ? AND greek = ? AND russian = ?"
                cursor.execute(check_query, (self.user_id, greek, russian))
                existing_words = set() if cursor.fetchone() else set()
            else:
                # Для множества слов проверяем каждое, но используем executemany для вставки
                existing_words = set()
                for greek, russian in valid_words:
                    check_query = "SELECT 1 FROM vocabulary WHERE user_id = ? AND greek = ? AND russian = ?"
                    cursor.execute(check_query, (self.user_id, greek, russian))
                    if cursor.fetchone():
                        existing_words.add((greek, russian))
            
            # Добавляем только новые слова
            words_to_insert = [(self.user_id, greek, russian) 
                             for greek, russian in valid_words 
                             if (greek, russian) not in existing_words]
            
            if words_to_insert:
                insert_query = "INSERT INTO vocabulary (user_id, greek, russian) VALUES (?, ?, ?)"
                cursor.executemany(insert_query, words_to_insert)
                added = len(words_to_insert)
            
            skipped += len(valid_words) - added
            conn.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при пакетном добавлении слов: {e}", exc_info=True)
            conn.rollback()
        finally:
            if conn:
                conn.close()
        
        return (added, skipped)
    
    def get_random_word(self, stats_user_id=None):
        """
        Возвращает случайное слово из словаря пользователя
        
        Args:
            stats_user_id: ID пользователя для фильтрации по статистике (опционально, для отслеживаемых пользователей)
        
        Returns:
            tuple: (greek, russian) или None
        """
        if self.user_id is None:
            raise ValueError("user_id должен быть указан для получения слов")
        
        conn = get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            # Если stats_user_id указан (для отслеживаемых пользователей), фильтруем слова по статистике
            if stats_user_id:
                # Выбираем только слова пользователя, где (successful - unsuccessful) < 3
                query = """
                SELECT v.greek, v.russian 
                FROM vocabulary v
                LEFT JOIN word_statistics ws ON v.id = ws.word_id AND ws.user_id = ?
                WHERE v.user_id = ? 
                AND (COALESCE(ws.successful, 0) - COALESCE(ws.unsuccessful, 0) < 3)
                ORDER BY RANDOM() 
                LIMIT 1
                """
                cursor.execute(query, (stats_user_id, self.user_id))
            else:
                # Обычный случайный выбор из словаря пользователя
                query = "SELECT greek, russian FROM vocabulary WHERE user_id = ? ORDER BY RANDOM() LIMIT 1"
                cursor.execute(query, (self.user_id,))
            
            result = cursor.fetchone()
            
            if result:
                return (result['greek'], result['russian'])
            
            # Если для отслеживаемого пользователя не нашлось подходящих слов, возвращаем любое случайное из его словаря
            if stats_user_id:
                query = "SELECT greek, russian FROM vocabulary WHERE user_id = ? ORDER BY RANDOM() LIMIT 1"
                cursor.execute(query, (self.user_id,))
                result = cursor.fetchone()
                if result:
                    return (result['greek'], result['russian'])
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении случайного слова: {e}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()
    
    def record_word_result(self, stats_user_id, greek, russian, is_successful):
        """
        Записывает результат тренировки слова для пользователя
        
        Args:
            stats_user_id: ID пользователя для статистики
            greek: греческое слово
            russian: русский перевод
            is_successful: True если успешно, False если нет
        """
        if self.user_id is None:
            raise ValueError("user_id должен быть указан для записи статистики")
        
        conn = get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            # Находим ID слова в словаре пользователя
            word_query = "SELECT id FROM vocabulary WHERE user_id = ? AND greek = ? AND russian = ?"
            cursor.execute(word_query, (self.user_id, greek, russian))
            word_row = cursor.fetchone()
            
            if not word_row:
                return  # Слово не найдено в словаре пользователя
            
            word_id = word_row['id']
            
            # Проверяем, есть ли уже статистика для этого слова и пользователя
            check_query = "SELECT id, successful, unsuccessful FROM word_statistics WHERE user_id = ? AND word_id = ?"
            cursor.execute(check_query, (stats_user_id, word_id))
            stats_row = cursor.fetchone()
            
            if stats_row:
                # Обновляем существующую статистику
                if is_successful:
                    update_query = """
                    UPDATE word_statistics 
                    SET successful = successful + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND word_id = ?
                    """
                else:
                    update_query = """
                    UPDATE word_statistics 
                    SET unsuccessful = unsuccessful + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND word_id = ?
                    """
                cursor.execute(update_query, (stats_user_id, word_id))
            else:
                # Создаем новую запись статистики
                if is_successful:
                    insert_query = """
                    INSERT INTO word_statistics (user_id, word_id, successful, unsuccessful)
                    VALUES (?, ?, 1, 0)
                    """
                else:
                    insert_query = """
                    INSERT INTO word_statistics (user_id, word_id, successful, unsuccessful)
                    VALUES (?, ?, 0, 1)
                    """
                cursor.execute(insert_query, (stats_user_id, word_id))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при записи статистики слова: {e}", exc_info=True)
            conn.rollback()
        finally:
            if conn:
                conn.close()
    
    def reset_user_statistics(self, user_id):
        """
        Сбрасывает статистику по словам для пользователя
        
        Args:
            user_id: ID пользователя
        
        Returns:
            int: количество удаленных записей
        """
        conn = get_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            delete_query = "DELETE FROM word_statistics WHERE user_id = ?"
            cursor.execute(delete_query, (user_id,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
        except Exception as e:
            logger.error(f"Ошибка при сбросе статистики: {e}", exc_info=True)
            conn.rollback()
            return 0
        finally:
            if conn:
                conn.close()
    
    def get_all_words(self):
        """Возвращает все слова из словаря пользователя"""
        if self.user_id is None:
            raise ValueError("user_id должен быть указан для получения слов")
        
        conn = get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            query = "SELECT greek, russian FROM vocabulary WHERE user_id = ?"
            cursor.execute(query, (self.user_id,))
            results = cursor.fetchall()
            
            return [(row['greek'], row['russian']) for row in results]
            
        except Exception as e:
            logger.error(f"Ошибка при получении всех слов: {e}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
    
    def count(self):
        """Возвращает количество слов в словаре пользователя"""
        if self.user_id is None:
            raise ValueError("user_id должен быть указан для подсчета слов")
        
        conn = get_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            query = "SELECT COUNT(*) as count FROM vocabulary WHERE user_id = ?"
            cursor.execute(query, (self.user_id,))
            result = cursor.fetchone()
            
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"Ошибка при подсчете слов: {e}", exc_info=True)
            return 0
        finally:
            if conn:
                conn.close()
    
    # Методы для совместимости со старым кодом
    def add_word_csv(self, greek, russian):
        """Добавляет слово в формате CSV (для совместимости)"""
        return self.add_word(greek, russian)
    
    def add_word_multiline(self, greek, russian):
        """Добавляет слово в многострочном формате (для совместимости)"""
        return self.add_word(greek, russian)
