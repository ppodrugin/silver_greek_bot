"""
Утилиты для работы со словарем и распознавания речи
"""
import logging
import re
import speech_recognition as sr
from io import BytesIO

logger = logging.getLogger(__name__)

def normalize_text(text):
    """
    Нормализует текст для сравнения:
    - убирает пунктуацию
    - приводит к нижнему регистру
    - убирает лишние пробелы
    - убирает греческие ударения для более гибкого сравнения
    """
    if not text:
        return ""
    # Убираем пунктуацию
    text = re.sub(r'[.,!?;:()]', '', text)
    # Приводим к нижнему регистру
    text = text.lower()
    # Убираем лишние пробелы
    text = ' '.join(text.split())
    return text.strip()

def remove_greek_accents(text):
    """
    Убирает греческие ударения и диакритику для более гибкого сравнения
    """
    # Маппинг греческих символов с ударениями на без ударений
    greek_accents = {
        'ά': 'α', 'έ': 'ε', 'ή': 'η', 'ί': 'ι', 'ό': 'ο', 'ύ': 'υ', 'ώ': 'ω',
        'Ά': 'α', 'Έ': 'ε', 'Ή': 'η', 'Ί': 'ι', 'Ό': 'ο', 'Ύ': 'υ', 'Ώ': 'ω',
        'ϊ': 'ι', 'ΐ': 'ι', 'ϋ': 'υ', 'ΰ': 'υ'
    }
    result = text
    for accented, unaccented in greek_accents.items():
        result = result.replace(accented, unaccented)
    return result

def levenshtein_distance(s1, s2):
    """
    Вычисляет расстояние Левенштейна между двумя строками
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def word_similarity(word1, word2):
    """
    Вычисляет похожесть между двумя словами (0.0 - 1.0)
    Учитывает фонетическую похожесть греческих слов
    """
    if word1 == word2:
        return 1.0
    
    # Убираем ударения для сравнения
    word1_no_accents = remove_greek_accents(word1)
    word2_no_accents = remove_greek_accents(word2)
    
    if word1_no_accents == word2_no_accents:
        return 0.95  # Почти совпадает, только ударения разные
    
    # Специальная обработка для похожих греческих окончаний
    # Например, "φίλοι" и "φίλη" фонетически очень похожи
    # Проверяем, если слова отличаются только последними 1-2 символами
    if len(word1_no_accents) >= 3 and len(word2_no_accents) >= 3:
        # Берем корень слова (без последних 2 символов)
        root1 = word1_no_accents[:-2] if len(word1_no_accents) > 2 else word1_no_accents
        root2 = word2_no_accents[:-2] if len(word2_no_accents) > 2 else word2_no_accents
        
        if root1 == root2:
            # Корни совпадают, отличаются только окончания - это фонетически похоже
            return 0.75
    
    # Используем расстояние Левенштейна
    max_len = max(len(word1_no_accents), len(word2_no_accents))
    if max_len == 0:
        return 1.0
    
    distance = levenshtein_distance(word1_no_accents, word2_no_accents)
    similarity = 1.0 - (distance / max_len)
    
    # Если слова очень похожи по длине и содержанию, повышаем похожесть
    if abs(len(word1_no_accents) - len(word2_no_accents)) <= 1:
        # Проверяем, сколько общих символов в начале
        common_prefix = 0
        min_len = min(len(word1_no_accents), len(word2_no_accents))
        for i in range(min_len):
            if word1_no_accents[i] == word2_no_accents[i]:
                common_prefix += 1
            else:
                break
        
        if common_prefix >= min_len * 0.7:  # Если 70%+ символов совпадают в начале
            similarity = max(similarity, 0.7)
    
    return max(0.0, similarity)

def compare_texts_detailed(user_text, correct_text):
    """
    Сравнивает произнесенный текст с правильным и возвращает детальную информацию
    Сравнивает слова по порядку с учетом возможных пропусков и лишних слов
    
    Returns:
        tuple: (is_correct, similarity_score, mistakes_list)
        mistakes_list: список словарей с информацией об ошибках
            [{'position': int, 'recognized': str, 'correct': str, 'similarity': float}, ...]
    """
    if not user_text:
        return False, 0.0, []
    
    # Нормализуем оба текста
    user_normalized = normalize_text(user_text)
    correct_normalized = normalize_text(correct_text)
    
    # Точное совпадение
    if user_normalized == correct_normalized:
        return True, 1.0, []
    
    # Разбиваем на слова
    user_words = user_normalized.split()
    correct_words = correct_normalized.split()
    
    mistakes = []
    user_idx = 0
    
    # Сравниваем слова по порядку с окном поиска
    for correct_idx, correct_word in enumerate(correct_words):
        # Ищем совпадение в окне ±3 слова от текущей позиции
        search_start = max(0, user_idx - 1)
        search_end = min(len(user_words), user_idx + 4)
        
        best_match_idx = None
        best_similarity = 0.0
        
        for j in range(search_start, search_end):
            if j >= len(user_words):
                break
            
            sim = word_similarity(user_words[j], correct_word)
            if sim > best_similarity:
                best_similarity = sim
                best_match_idx = j
        
        # Если похожесть достаточна (>= 0.7), считаем совпадением
        if best_similarity >= 0.7 and best_match_idx is not None:
            user_idx = best_match_idx + 1  # Переходим к следующему слову
        else:
            # Ошибка: слово не распознано или распознано неправильно
            if best_match_idx is not None and best_similarity > 0.3:
                # Слово распознано, но неправильно
                mistakes.append({
                    'position': correct_idx,
                    'recognized': user_words[best_match_idx],
                    'correct': correct_word,
                    'similarity': best_similarity
                })
                user_idx = best_match_idx + 1
            else:
                # Слово пропущено
                mistakes.append({
                    'position': correct_idx,
                    'recognized': None,
                    'correct': correct_word,
                    'similarity': 0.0
                })
                # Не двигаем user_idx, так как слово пропущено
    
    # Проверяем лишние слова в конце распознанного текста
    if user_idx < len(user_words):
        for j in range(user_idx, len(user_words)):
            # Ищем ближайшее слово из правильного текста
            best_sim = 0.0
            nearest_correct_idx = None
            for k, correct_word in enumerate(correct_words):
                sim = word_similarity(user_words[j], correct_word)
                if sim > best_sim:
                    best_sim = sim
                    nearest_correct_idx = k
            
            if best_sim < 0.7:
                mistakes.append({
                    'position': nearest_correct_idx if nearest_correct_idx is not None else len(correct_words),
                    'recognized': user_words[j],
                    'correct': None,
                    'similarity': best_sim
                })
    
    # Вычисляем общую похожесть
    total_words = max(len(user_words), len(correct_words))
    correct_matches = total_words - len(mistakes)
    similarity = correct_matches / total_words if total_words > 0 else 0.0
    
    is_correct = similarity >= 0.7 and len(mistakes) == 0
    
    return is_correct, similarity, mistakes

def compare_texts(user_text, correct_text):
    """
    Сравнивает произнесенный текст с правильным
    Использует более гибкий алгоритм с учетом фонетической похожести
    
    Returns:
        tuple: (is_correct, similarity_score)
    """
    if not user_text:
        return False, 0.0
    
    # Нормализуем оба текста
    user_normalized = normalize_text(user_text)
    correct_normalized = normalize_text(correct_text)
    
    # Точное совпадение
    if user_normalized == correct_normalized:
        return True, 1.0
    
    # Проверяем похожесть без ударений
    user_no_accents = remove_greek_accents(user_normalized)
    correct_no_accents = remove_greek_accents(correct_normalized)
    
    if user_no_accents == correct_no_accents:
        return True, 0.95
    
    # Разбиваем на слова
    user_words = user_normalized.split()
    correct_words = correct_normalized.split()
    
    if len(user_words) == 0 or len(correct_words) == 0:
        # Сравниваем как целые строки
        similarity = word_similarity(user_no_accents, correct_no_accents)
        return similarity >= 0.6, similarity
    
    # Греческие артикли (для более гибкого сравнения)
    greek_articles = {'ο', 'η', 'το', 'οι', 'τα', 'του', 'της', 'των'}
    
    # Разделяем на артикли и основные слова
    user_articles = [w for w in user_words if w in greek_articles]
    user_main_words = [w for w in user_words if w not in greek_articles]
    
    correct_articles = [w for w in correct_words if w in greek_articles]
    correct_main_words = [w for w in correct_words if w not in greek_articles]
    
    # Если есть основные слова, сравниваем их
    if user_main_words and correct_main_words:
        # Для каждого основного слова из правильного ответа ищем наиболее похожее
        total_similarity = 0.0
        matched_words = []
        
        for correct_word in correct_main_words:
            best_similarity = 0.0
            best_match = None
            
            for user_word in user_main_words:
                if user_word in matched_words:
                    continue
                sim = word_similarity(user_word, correct_word)
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = user_word
            
            if best_match:
                matched_words.append(best_match)
            total_similarity += best_similarity
        
        # Средняя похожесть основных слов
        main_similarity = total_similarity / len(correct_main_words) if correct_main_words else 0.0
        
        # Если основные слова очень похожи (>0.7), считаем это хорошим результатом
        # даже если артикли не совпадают
        if main_similarity >= 0.7:
            final_similarity = main_similarity
            is_correct = True
        else:
            # Учитываем артикли, но с меньшим весом
            article_similarity = 1.0 if user_articles == correct_articles else 0.5
            final_similarity = main_similarity * 0.8 + article_similarity * 0.2
            is_correct = final_similarity >= 0.6
    else:
        # Нет основных слов, сравниваем как есть
        total_similarity = 0.0
        matched_words = []
        
        for correct_word in correct_words:
            best_similarity = 0.0
            best_match = None
            
            for user_word in user_words:
                if user_word in matched_words:
                    continue
                sim = word_similarity(user_word, correct_word)
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = user_word
            
            if best_match:
                matched_words.append(best_match)
            total_similarity += best_similarity
        
        final_similarity = total_similarity / len(correct_words) if correct_words else 0.0
        is_correct = final_similarity >= 0.6
    
    # Также проверяем общую похожесть строки (как запасной вариант)
    string_similarity = word_similarity(user_no_accents, correct_no_accents)
    final_similarity = max(final_similarity, string_similarity * 0.9)
    
    # Дополнительная проверка: если хотя бы одно слово очень похоже (>0.75), повышаем общую похожесть
    if len(user_words) > 0 and len(correct_words) > 0:
        max_word_sim = max(
            word_similarity(uw, cw) 
            for uw in user_words 
            for cw in correct_words
        )
        if max_word_sim > 0.75:
            final_similarity = max(final_similarity, max_word_sim * 0.85)
            if max_word_sim >= 0.7:
                is_correct = True
    
    # Для греческого языка делаем более гибкое сравнение
    # Считаем правильным, если похожесть >= 0.6 (учитывая особенности распознавания греческого)
    is_correct = is_correct or final_similarity >= 0.6
    
    return is_correct, final_similarity

def recognize_voice_from_file(audio_path, language='el-GR'):
    """
    Распознает речь из аудио файла
    
    Args:
        audio_path: путь к аудио файлу (OGG или WAV)
        language: код языка для распознавания
    
    Returns:
        str: распознанный текст или None
    """
    recognizer = sr.Recognizer()
    
    try:
        # Конвертируем OGG в WAV если нужно
        import os
        import subprocess
        
        wav_path = audio_path
        if audio_path.endswith('.ogg'):
            wav_path = audio_path.replace('.ogg', '.wav')
            try:
                # Используем ffmpeg для конвертации OGG в WAV
                result = subprocess.run(
                    ['ffmpeg', '-i', audio_path, '-ar', '16000', '-ac', '1', '-y', wav_path],
                    check=True,
                    capture_output=True,
                    timeout=10
                )
                logger.debug(f"Конвертирован OGG в WAV: {wav_path}")
            except FileNotFoundError:
                logger.debug("ffmpeg не найден. Пробуем использовать pydub для конвертации...")
                try:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_ogg(audio_path)
                    audio = audio.set_frame_rate(16000).set_channels(1)
                    audio.export(wav_path, format="wav")
                    logger.debug(f"Конвертирован OGG в WAV через pydub: {wav_path}")
                except Exception as e2:
                    logger.warning(f"Ошибка конвертации через pydub: {e2}")
                    # Пробуем без конвертации - может сработать
                    wav_path = audio_path
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                logger.warning(f"Ошибка конвертации OGG в WAV: {e}")
                # Пробуем без конвертации - может сработать
                wav_path = audio_path
        
        # Читаем аудио файл
        with sr.AudioFile(wav_path) as source:
            # Настраиваем для фонового шума
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.record(source)
        
        # Распознаем речь
        try:
            text = recognizer.recognize_google(audio, language=language)
            return text
        except sr.UnknownValueError:
            logger.debug("Не удалось распознать речь (UnknownValueError)")
            return None
        except sr.RequestError as e:
            logger.error(f"Ошибка сервиса распознавания: {e}", exc_info=True)
            return None
            
    except Exception as e:
        logger.error(f"Ошибка при обработке аудио: {e}", exc_info=True)
        return None
    finally:
        # Удаляем временный WAV файл если он был создан
        if wav_path != audio_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить временный WAV файл {wav_path}: {e}")

