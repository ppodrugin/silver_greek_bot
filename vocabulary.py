"""
Работа со словарем через SQLite/PostgreSQL
Статистика хранится прямо в таблице vocabulary
"""
import logging
import random
import os
from database import get_connection, return_connection, get_param, USE_POSTGRES

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
            param = get_param()
            
            # Проверяем, существует ли уже такое слово у этого пользователя
            check_query = f"SELECT id FROM vocabulary WHERE user_id = {param} AND greek = {param} AND russian = {param}"
            cursor.execute(check_query, (self.user_id, greek, russian))
            
            result = cursor.fetchone()
            if result:
                return False  # Слово уже существует
            
            # Добавляем слово
            insert_query = f"INSERT INTO vocabulary (user_id, greek, russian) VALUES ({param}, {param}, {param})"
            cursor.execute(insert_query, (self.user_id, greek, russian))
            conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении слова: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            if conn:
                return_connection(conn)
    
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
            
            # Проверяем существующие слова
            param = get_param()
            existing_words = set()
            for greek, russian in valid_words:
                check_query = f"SELECT 1 FROM vocabulary WHERE user_id = {param} AND greek = {param} AND russian = {param}"
                cursor.execute(check_query, (self.user_id, greek, russian))
                if cursor.fetchone():
                    existing_words.add((greek, russian))
            
            # Добавляем только новые слова
            words_to_insert = [(self.user_id, greek, russian) 
                             for greek, russian in valid_words 
                             if (greek, russian) not in existing_words]
            
            if words_to_insert:
                insert_query = f"INSERT INTO vocabulary (user_id, greek, russian) VALUES ({param}, {param}, {param})"
                cursor.executemany(insert_query, words_to_insert)
                added = len(words_to_insert)
            
            skipped += len(valid_words) - added
            conn.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при пакетном добавлении слов: {e}", exc_info=True)
            conn.rollback()
        finally:
            if conn:
                return_connection(conn)
        
        return (added, skipped)
    
    def get_random_word(self, stats_user_id=None):
        """
        Возвращает случайное слово из словаря пользователя
        
        Args:
            stats_user_id: ID пользователя для фильтрации по статистике (опционально, для отслеживаемых пользователей)
                          Если указан, выбираются слова где (successful - unsuccessful) < 3
        
        Returns:
            tuple: (greek, russian) или None
        """
        if self.user_id is None:
            raise ValueError("user_id должен быть указан для получения слов")
        
        conn = get_connection()
        if not conn:
            logger.error("Не удалось подключиться к базе данных")
            return None
        
        try:
            cursor = conn.cursor()
            param = get_param()
            
            # Сначала проверяем, есть ли вообще слова у пользователя
            count_query = f"SELECT COUNT(*) as count FROM vocabulary WHERE user_id = {param}"
            cursor.execute(count_query, (self.user_id,))
            count_result = cursor.fetchone()
            if USE_POSTGRES:
                total_words = count_result[0] if count_result else 0
            else:
                total_words = count_result['count'] if count_result else 0
            
            logger.debug(f"Всего слов для user_id={self.user_id}: {total_words}")
            
            if total_words == 0:
                logger.warning(f"Словарь пуст для user_id={self.user_id}")
                return None
            
            # Если stats_user_id указан (для отслеживаемых пользователей), фильтруем слова по статистике
            if stats_user_id:
                # Выбираем только слова пользователя, где (successful - unsuccessful) < 3
                query = f"""
                SELECT greek, russian 
                FROM vocabulary
                WHERE user_id = {param} 
                AND (successful - unsuccessful < 3)
                ORDER BY RANDOM() 
                LIMIT 1
                """
                cursor.execute(query, (self.user_id,))
                result = cursor.fetchone()
                
                if result:
                    if USE_POSTGRES:
                        logger.debug(f"Найдено слово по статистике: {result[0]}")
                        return (result[0], result[1])
                    else:
                        logger.debug(f"Найдено слово по статистике: {result['greek']}")
                        return (result['greek'], result['russian'])
                
                # Если для отслеживаемого пользователя не нашлось подходящих слов по статистике,
                # возвращаем любое случайное из его словаря (fallback)
                logger.debug(f"Не найдено слов с (successful - unsuccessful) < 3 для user_id={self.user_id}, используем fallback")
                fallback_query = f"SELECT greek, russian FROM vocabulary WHERE user_id = {param} ORDER BY RANDOM() LIMIT 1"
                cursor.execute(fallback_query, (self.user_id,))
                result = cursor.fetchone()
                if result:
                    if USE_POSTGRES:
                        logger.debug(f"Fallback: найдено слово {result[0]}")
                        return (result[0], result[1])
                    else:
                        logger.debug(f"Fallback: найдено слово {result['greek']}")
                        return (result['greek'], result['russian'])
                else:
                    logger.error(f"Fallback тоже не нашел слов для user_id={self.user_id}, хотя count показал {total_words}")
                    return None
            else:
                # Обычный случайный выбор из словаря пользователя
                query = f"SELECT greek, russian FROM vocabulary WHERE user_id = {param} ORDER BY RANDOM() LIMIT 1"
                cursor.execute(query, (self.user_id,))
                result = cursor.fetchone()
                
                if result:
                    if USE_POSTGRES:
                        logger.debug(f"Найдено случайное слово: {result[0]}")
                        return (result[0], result[1])
                    else:
                        logger.debug(f"Найдено случайное слово: {result['greek']}")
                        return (result['greek'], result['russian'])
                else:
                    logger.error(f"Не найдено слов для user_id={self.user_id}, хотя count показал {total_words}")
                    return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении случайного слова: {e}", exc_info=True)
            return None
        finally:
            if conn:
                return_connection(conn)
    
    def record_word_result(self, stats_user_id, greek, russian, is_successful):
        """
        Записывает результат тренировки слова для пользователя
        Статистика хранится прямо в таблице vocabulary
        
        Args:
            stats_user_id: ID пользователя для статистики (должен совпадать с self.user_id)
            greek: греческое слово
            russian: русский перевод
            is_successful: True если успешно, False если нет
        """
        if self.user_id is None:
            raise ValueError("user_id должен быть указан для записи статистики")
        
        if stats_user_id != self.user_id:
            logger.warning(f"stats_user_id ({stats_user_id}) не совпадает с user_id словаря ({self.user_id})")
        
        conn = get_connection()
        if not conn:
            logger.error("Не удалось получить соединение с БД для записи статистики")
            return
        
        try:
            cursor = conn.cursor()
            param = get_param()
            
            # Обновляем статистику прямо в таблице vocabulary
            if is_successful:
                update_query = f"""
                UPDATE vocabulary 
                SET successful = successful + 1
                WHERE user_id = {param} AND greek = {param} AND russian = {param}
                """
            else:
                update_query = f"""
                UPDATE vocabulary 
                SET unsuccessful = unsuccessful + 1
                WHERE user_id = {param} AND greek = {param} AND russian = {param}
                """
            
            cursor.execute(update_query, (self.user_id, greek, russian))
            
            if cursor.rowcount == 0:
                logger.warning(f"Слово не найдено для обновления статистики: user_id={self.user_id}, greek={greek}, russian={russian}")
            else:
                logger.debug(f"✅ Статистика обновлена: user_id={self.user_id}, greek={greek}, "
                           f"результат={'успешно' if is_successful else 'неуспешно'}")
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при записи статистики слова: {e}", exc_info=True)
            if conn:
                conn.rollback()
        finally:
            if conn:
                return_connection(conn)
    
    def reset_user_statistics(self, user_id):
        """
        Сбрасывает статистику по словам для пользователя
        
        Args:
            user_id: ID пользователя
        
        Returns:
            int: количество обновленных записей
        """
        conn = get_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            param = get_param()
            update_query = f"UPDATE vocabulary SET successful = 0, unsuccessful = 0 WHERE user_id = {param}"
            cursor.execute(update_query, (user_id,))
            updated_count = cursor.rowcount
            conn.commit()
            return updated_count
        except Exception as e:
            logger.error(f"Ошибка при сбросе статистики: {e}", exc_info=True)
            conn.rollback()
            return 0
        finally:
            if conn:
                return_connection(conn)
    
    def get_all_words(self):
        """Возвращает все слова из словаря пользователя"""
        if self.user_id is None:
            raise ValueError("user_id должен быть указан для получения слов")
        
        conn = get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            param = get_param()
            query = f"SELECT greek, russian FROM vocabulary WHERE user_id = {param}"
            cursor.execute(query, (self.user_id,))
            results = cursor.fetchall()
            
            if USE_POSTGRES:
                return [(row[0], row[1]) for row in results]
            else:
                return [(row['greek'], row['russian']) for row in results]
            
        except Exception as e:
            logger.error(f"Ошибка при получении всех слов: {e}", exc_info=True)
            return []
        finally:
            if conn:
                return_connection(conn)
    
    def count(self):
        """Возвращает количество слов в словаре пользователя"""
        if self.user_id is None:
            raise ValueError("user_id должен быть указан для подсчета слов")
        
        conn = get_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            param = get_param()
            query = f"SELECT COUNT(*) as count FROM vocabulary WHERE user_id = {param}"
            cursor.execute(query, (self.user_id,))
            result = cursor.fetchone()
            
            if USE_POSTGRES:
                return result[0] if result else 0
            else:
                return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"Ошибка при подсчете слов: {e}", exc_info=True)
            return 0
        finally:
            if conn:
                return_connection(conn)
    
    # Методы для совместимости со старым кодом
    def add_word_csv(self, greek, russian):
        """Добавляет слово в формате CSV (для совместимости)"""
        return self.add_word(greek, russian)
    
    def add_word_multiline(self, greek, russian):
        """Добавляет слово в многострочном формате (для совместимости)"""
        return self.add_word(greek, russian)
