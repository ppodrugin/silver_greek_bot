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
    - преобразует числа в греческие числительные
    - убирает греческие ударения для более гибкого сравнения
    """
    if not text:
        return ""
    
    # Проверяем, является ли весь текст числом
    text_stripped = text.strip()
    if text_stripped.isdigit():
        # Преобразуем число в греческое числительное
        greek_num = number_to_greek(text_stripped)
        if greek_num:
            text = greek_num
        # Если не удалось преобразовать, оставляем как есть
    
    # Убираем пунктуацию
    text = re.sub(r'[.,!?;:()]', '', text)
    # Приводим к нижнему регистру
    text = text.lower()
    # Убираем греческие ударения перед дальнейшей обработкой
    text = remove_greek_accents(text)
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

def analyze_article_error(user_articles, correct_articles):
    """
    Анализирует ошибку в артиклях и возвращает описание ошибки
    
    Returns:
        str: описание ошибки или None, если ошибки нет
    """
    if user_articles == correct_articles:
        return None
    
    # Греческие артикли с их характеристиками
    article_info = {
        'ο': {'gender': 'm', 'number': 'sg', 'name': 'мужской род, единственное число'},
        'η': {'gender': 'f', 'number': 'sg', 'name': 'женский род, единственное число'},
        'το': {'gender': 'n', 'number': 'sg', 'name': 'средний род, единственное число'},
        'οι': {'gender': 'm', 'number': 'pl', 'name': 'мужской род, множественное число'},
        'τα': {'gender': 'n', 'number': 'pl', 'name': 'средний род, множественное число'},
        'του': {'gender': 'm', 'number': 'sg', 'case': 'gen', 'name': 'мужской род, единственное число, родительный падеж'},
        'της': {'gender': 'f', 'number': 'sg', 'case': 'gen', 'name': 'женский род, единственное число, родительный падеж'},
        'των': {'gender': 'any', 'number': 'pl', 'case': 'gen', 'name': 'множественное число, родительный падеж'}
    }
    
    if len(user_articles) != len(correct_articles):
        return f"Количество артиклей не совпадает: вы использовали {len(user_articles)}, нужно {len(correct_articles)}"
    
    if len(user_articles) == 0:
        return "Артикль отсутствует"
    
    if len(user_articles) == 1 and len(correct_articles) == 1:
        user_art = user_articles[0]
        correct_art = correct_articles[0]
        
        user_info = article_info.get(user_art, {})
        correct_info = article_info.get(correct_art, {})
        
        if user_info and correct_info:
            # Проверяем число
            if user_info.get('number') != correct_info.get('number'):
                if user_info.get('number') == 'pl' and correct_info.get('number') == 'sg':
                    return "Использован артикль множественного числа вместо единственного"
                elif user_info.get('number') == 'sg' and correct_info.get('number') == 'pl':
                    return "Использован артикль единственного числа вместо множественного"
            
            # Проверяем род
            if user_info.get('gender') != correct_info.get('gender'):
                return f"Неправильный род артикля: {user_info.get('name', 'неизвестно')} вместо {correct_info.get('name', 'неизвестно')}"
    
    return "Неправильный артикль"

def normalize_greek_i_sound(text):
    """
    Нормализует различные варианты написания звука "и" в греческом языке.
    Преобразует η, υ, οι, ει, υι в ι для более гибкого сравнения при распознавании речи.
    
    ВАЖНО: Это делается только для сравнения произношения, не меняет правильное написание.
    Используется для обработки ошибок распознавания речи, когда правильный звук записан другой буквой.
    """
    if not text:
        return text
    
    result = text
    
    # Список греческих артиклей, которые не должны изменяться
    greek_articles = {'ο', 'η', 'το', 'οι', 'τα', 'του', 'της', 'των'}
    
    # Разбиваем на слова для более точной обработки
    words = result.split()
    normalized_words = []
    
    for word in words:
        # Не изменяем артикли
        if word in greek_articles:
            normalized_words.append(word)
            continue
        
        normalized_word = word
        
        # Заменяем диграфы οι, ει, υι на ι
        # Но только если это не артикль "οι" (уже обработано выше)
        normalized_word = normalized_word.replace('οι', 'ι')
        normalized_word = normalized_word.replace('ει', 'ι')
        normalized_word = normalized_word.replace('υι', 'ι')
        
        # Заменяем η на ι (но сохраняем в артиклях, которые уже обработаны)
        normalized_word = normalized_word.replace('η', 'ι')
        
        # Заменяем υ на ι
        normalized_word = normalized_word.replace('υ', 'ι')
        
        normalized_words.append(normalized_word)
    
    return ' '.join(normalized_words)

def number_to_greek(num_str):
    """
    Преобразует число (строку) в греческое числительное
    Поддерживает числа от 1 до 100, сотни (100-900) и 1000
    """
    try:
        num = int(num_str.strip())
    except (ValueError, AttributeError):
        return None
    
    # Базовые числа 0-20
    basic_numbers = {
        0: 'μηδέν', 1: 'ένα', 2: 'δύο', 3: 'τρία', 4: 'τέσσερα', 5: 'πέντε',
        6: 'έξι', 7: 'επτά', 8: 'οκτώ', 9: 'εννέα', 10: 'δέκα',
        11: 'έντεκα', 12: 'δώδεκα', 13: 'δεκατρία', 14: 'δεκατέσσερα',
        15: 'δεκαπέντε', 16: 'δεκαέξι', 17: 'δεκαεπτά', 18: 'δεκαοκτώ',
        19: 'δεκαεννέα', 20: 'είκοσι'
    }
    
    # Десятки 30-90
    tens = {
        30: 'τριάντα', 40: 'σαράντα', 50: 'πενήντα', 60: 'εξήντα',
        70: 'εβδομήντα', 80: 'ογδόντα', 90: 'ενενήντα'
    }
    
    # Сотни 100-900
    hundreds = {
        100: 'εκατό', 200: 'διακόσια', 300: 'τριακόσια', 400: 'τετρακόσια',
        500: 'πεντακόσια', 600: 'εξακόσια', 700: 'επτακόσια',
        800: 'οκτακόσια', 900: 'εννιακόσια'
    }
    
    # 1000
    if num == 1000:
        return 'χίλια'
    
    # Точное совпадение в базовых числах
    if num in basic_numbers:
        return basic_numbers[num]
    
    # Точное совпадение в десятках
    if num in tens:
        return tens[num]
    
    # Точное совпадение в сотнях
    if num in hundreds:
        return hundreds[num]
    
    # Составные числа 21-99
    if 21 <= num <= 99:
        tens_part = (num // 10) * 10
        ones_part = num % 10
        
        # Для 21-29 используем 20 из basic_numbers
        if 21 <= num <= 29:
            if ones_part == 0:
                return basic_numbers[20]
            return f"{basic_numbers[20]} {basic_numbers[ones_part]}"
        # Для 30-99 используем tens
        elif tens_part in tens and ones_part in basic_numbers:
            if ones_part == 0:
                return tens[tens_part]
            return f"{tens[tens_part]} {basic_numbers[ones_part]}"
    
    # Составные числа с сотнями (101-999)
    if 101 <= num <= 999:
        hundreds_part = (num // 100) * 100
        remainder = num % 100
        
        if hundreds_part in hundreds:
            if remainder == 0:
                return hundreds[hundreds_part]
            elif remainder in basic_numbers:
                return f"{hundreds[hundreds_part]} {basic_numbers[remainder]}"
            elif remainder in tens:
                return f"{hundreds[hundreds_part]} {tens[remainder]}"
            elif 21 <= remainder <= 29:
                # Для 21-29 используем 20 из basic_numbers
                ones_part = remainder % 10
                if ones_part == 0:
                    return f"{hundreds[hundreds_part]} {basic_numbers[20]}"
                return f"{hundreds[hundreds_part]} {basic_numbers[20]} {basic_numbers[ones_part]}"
            elif 30 <= remainder <= 99:
                tens_part = (remainder // 10) * 10
                ones_part = remainder % 10
                if tens_part in tens:
                    if ones_part == 0:
                        return f"{hundreds[hundreds_part]} {tens[tens_part]}"
                    elif ones_part in basic_numbers:
                        return f"{hundreds[hundreds_part]} {tens[tens_part]} {basic_numbers[ones_part]}"
    
    # Для чисел больше 1000 возвращаем None (не поддерживаем)
    return None

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
    Более строгая версия для точной оценки произношения
    """
    if word1 == word2:
        return 1.0
    
    # Убираем ударения для сравнения
    word1_no_accents = remove_greek_accents(word1)
    word2_no_accents = remove_greek_accents(word2)
    
    if word1_no_accents == word2_no_accents:
        return 0.95  # Почти совпадает, только ударения разные
    
    # Нормализуем варианты звука "и" для более гибкого сравнения
    word1_normalized_i = normalize_greek_i_sound(word1_no_accents)
    word2_normalized_i = normalize_greek_i_sound(word2_no_accents)
    
    if word1_normalized_i == word2_normalized_i:
        return 0.92  # Совпадает после нормализации вариантов "и" - правильное произношение
    
    # Строгая проверка: если слова отличаются критичными буквами, это разные слова
    # Например, "φίλος" (друг, м.р.) и "φίλη" (подруга, ж.р.) - разные слова
    # "φίλος" и "φίλοι" (друзья) - разные формы
    min_len = min(len(word1_no_accents), len(word2_no_accents))
    if min_len >= 3:
        # Проверяем последние 2 символа - если они сильно отличаются, это разные слова/формы
        suffix1 = word1_no_accents[-2:] if len(word1_no_accents) >= 2 else word1_no_accents
        suffix2 = word2_no_accents[-2:] if len(word2_no_accents) >= 2 else word2_no_accents
        
        if suffix1 != suffix2:
            # Если окончания разные, это может быть другая форма или другое слово
            # Проверяем корень
            root1 = word1_no_accents[:-2] if len(word1_no_accents) > 2 else word1_no_accents
            root2 = word2_no_accents[:-2] if len(word2_no_accents) > 2 else word2_no_accents
            
            if root1 == root2:
                # Корни совпадают, но окончания разные - это разные формы
                # Для обучения произношению это должно считаться неправильным
                # Снижаем похожесть значительно
                return 0.65  # Снизили с 0.75 до 0.65 для более строгой оценки
    
    # Проверяем критические различия в середине слова
    # Если слова отличаются в середине (не только в начале/конце), это серьезная ошибка
    min_len = min(len(word1_no_accents), len(word2_no_accents))
    if min_len >= 4:
        # Проверяем среднюю часть слова (исключая первый и последний символ)
        mid1 = word1_no_accents[1:-1] if len(word1_no_accents) > 2 else word1_no_accents
        mid2 = word2_no_accents[1:-1] if len(word2_no_accents) > 2 else word2_no_accents
        
        # Если средние части сильно отличаются, это разные слова
        if mid1 and mid2:
            mid_distance = levenshtein_distance(mid1, mid2)
            mid_similarity = 1.0 - (mid_distance / max(len(mid1), len(mid2)))
            if mid_similarity < 0.7:  # Средняя часть сильно отличается
                # Это разные слова, снижаем похожесть
                base_similarity = levenshtein_distance(word1_no_accents, word2_no_accents)
                max_len = max(len(word1_no_accents), len(word2_no_accents))
                return max(0.0, 1.0 - (base_similarity / max_len) - 0.2)  # Штраф за различия в середине
    
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
        
        if common_prefix >= min_len * 0.8:  # Если 80%+ символов совпадают в начале
            similarity = max(similarity, 0.7)
    
    # Дополнительная проверка: если слова отличаются критичными буквами в середине
    # (например, λ vs κ в καλώς vs κακός), это разные слова
    if min_len >= 4:
        # Проверяем первые 3 символа - если они сильно отличаются, это разные слова
        prefix1 = word1_no_accents[:3]
        prefix2 = word2_no_accents[:3]
        if prefix1 != prefix2:
            prefix_sim = 1.0 - (levenshtein_distance(prefix1, prefix2) / 3.0)
            if prefix_sim < 0.67:  # Первые 3 символа сильно отличаются
                similarity *= 0.6  # Значительно снижаем похожесть
    
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
    
    # Проверяем, является ли user_text числом, и преобразуем его в греческое числительное
    user_stripped = user_text.strip()
    if user_stripped.isdigit():
        greek_num = number_to_greek(user_stripped)
        if greek_num:
            user_text = greek_num
            logger.debug(f"Преобразовано число {user_stripped} в греческое: {greek_num}")
    
    # Нормализуем оба текста
    user_normalized = normalize_text(user_text)
    correct_normalized = normalize_text(correct_text)
    
    # Точное совпадение
    if user_normalized == correct_normalized:
        return True, 1.0, []
    
    # Нормализуем варианты звука "и" для более гибкого сравнения при распознавании речи
    user_normalized_i = normalize_greek_i_sound(user_normalized)
    correct_normalized_i = normalize_greek_i_sound(correct_normalized)
    
    # Проверяем совпадение после нормализации вариантов "и"
    if user_normalized_i == correct_normalized_i:
        return True, 0.98, []  # Почти идеальное совпадение, только разные буквы для звука "и"
    
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
        
        # Если похожесть достаточна (>= 0.8), считаем совпадением
        # Повысили порог для более строгой оценки
        if best_similarity >= 0.8 and best_match_idx is not None:
            user_idx = best_match_idx + 1  # Переходим к следующему слову
        else:
            # Ошибка: слово не распознано или распознано неправильно
            if best_match_idx is not None and best_similarity > 0.5:
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
            
            if best_sim < 0.8:
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
    
    # Повысили порог для более строгой оценки
    is_correct = similarity >= 0.85 and len(mistakes) == 0
    
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
    
    # Проверяем, является ли user_text числом, и преобразуем его в греческое числительное
    user_stripped = user_text.strip()
    if user_stripped.isdigit():
        greek_num = number_to_greek(user_stripped)
        if greek_num:
            user_text = greek_num
            logger.debug(f"Преобразовано число {user_stripped} в греческое: {greek_num}")
    
    # Нормализуем оба текста (ударения уже убраны в normalize_text)
    user_normalized = normalize_text(user_text)
    correct_normalized = normalize_text(correct_text)
    
    # Нормализуем варианты звука "и" для более гибкого сравнения при распознавании речи
    user_normalized_i = normalize_greek_i_sound(user_normalized)
    correct_normalized_i = normalize_greek_i_sound(correct_normalized)
    
    # Точное совпадение (сначала проверяем без нормализации "и", потом с нормализацией)
    if user_normalized == correct_normalized:
        return True, 1.0
    
    # Проверяем совпадение после нормализации вариантов "и"
    if user_normalized_i == correct_normalized_i:
        return True, 0.98  # Почти идеальное совпадение, только разные буквы для звука "и"
    
    # Разбиваем на слова
    user_words = user_normalized.split()
    correct_words = correct_normalized.split()
    
    if len(user_words) == 0 or len(correct_words) == 0:
        # Сравниваем как целые строки
        similarity = word_similarity(user_normalized, correct_normalized)
        # Еще больше повысили порог для более строгой оценки
        return similarity >= 0.8, similarity
    
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
        
        # Проверяем артикли строго - они должны совпадать
        articles_match = user_articles == correct_articles
        
        # Если основные слова очень похожи (>0.85) И артикли совпадают, считаем правильным
        if main_similarity >= 0.85 and articles_match:
            final_similarity = main_similarity
            is_correct = True
        elif main_similarity >= 0.85 and not articles_match:
            # Основные слова правильные, но артикли не совпадают - это неправильно
            final_similarity = main_similarity * 0.7  # Штраф за неправильный артикль
            is_correct = False
        else:
            # Если основные слова сильно отличаются (<0.7), это неправильно
            # даже если артикли совпадают
            if main_similarity < 0.7:
                final_similarity = main_similarity
                is_correct = False
            else:
                # Учитываем артикли строго
                # ВАЖНО: если основное слово имеет похожесть < 0.75, это неправильно
                # даже если артикли совпадают
                if main_similarity < 0.75:
                    final_similarity = main_similarity
                    is_correct = False
                else:
                    # Артикли должны совпадать для правильного ответа
                    if articles_match:
                        final_similarity = main_similarity
                        is_correct = final_similarity >= 0.85
                    else:
                        # Артикли не совпадают - это неправильно
                        final_similarity = main_similarity * 0.7  # Штраф за неправильный артикль
                        is_correct = False
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
        # Еще больше повысили порог для более строгой оценки
        is_correct = final_similarity >= 0.8
    
    # Также проверяем общую похожесть строки (как запасной вариант)
    # Но НЕ используем её для повышения, если основные слова сильно отличаются
    string_similarity = word_similarity(user_normalized, correct_normalized)
    # Используем строковую похожесть только если она очень высокая (>0.92)
    # и если она не противоречит результату сравнения по словам
    # Если основные слова имеют низкую похожесть (<0.7), игнорируем строковую похожесть
    if user_main_words and correct_main_words:
        main_sim_check = word_similarity(user_main_words[0], correct_main_words[0])
        if main_sim_check >= 0.7 and string_similarity > 0.92:
            final_similarity = max(final_similarity, string_similarity * 0.95)
    else:
        # Если нет основных слов, используем строковую похожесть
        if string_similarity > 0.9:
            final_similarity = max(final_similarity, string_similarity * 0.95)
    
    # Дополнительная проверка: если хотя бы одно слово очень похоже (>0.92), повышаем общую похожесть
    # Еще больше повысили пороги для более строгой оценки
    # ВАЖНО: не переопределяем is_correct, если артикли не совпадают или основные слова сильно отличаются
    if len(user_words) > 0 and len(correct_words) > 0:
        # Проверяем похожесть основных слов (без артиклей)
        if user_main_words and correct_main_words:
            # Проверяем артикли строго
            articles_match = user_articles == correct_articles
            
            main_max_sim = max(
                word_similarity(uw, cw) 
                for uw in user_main_words 
                for cw in correct_main_words
            )
            # Только если основные слова очень похожи (>0.92) И артикли совпадают, можем повысить оценку
            if main_max_sim > 0.92:
                final_similarity = max(final_similarity, main_max_sim * 0.95)
                if main_max_sim >= 0.92 and articles_match:
                    is_correct = True
                elif main_max_sim >= 0.92 and not articles_match:
                    # Основные слова правильные, но артикли не совпадают - неправильно
                    is_correct = False
        else:
            # Если нет основных слов, проверяем все слова
            max_word_sim = max(
                word_similarity(uw, cw) 
                for uw in user_words 
                for cw in correct_words
            )
            if max_word_sim > 0.92:
                final_similarity = max(final_similarity, max_word_sim * 0.95)
                if max_word_sim >= 0.92:
                    is_correct = True
    
    # Для греческого языка делаем более строгое сравнение
    # Повышаем порог до 0.82 для более точной оценки
    # Учитываем особенности распознавания греческого, но не слишком мягко
    # ВАЖНО: не переопределяем is_correct, если он уже False из-за низкой похожести основных слов
    if is_correct:  # Только если еще не определено как неправильное
        is_correct = final_similarity >= 0.82
    
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

def recognize_voice_command(audio_path, language='ru-RU'):
    """
    Распознает голосовую команду из аудио файла
    
    Args:
        audio_path: путь к аудио файлу
        language: код языка для распознавания (по умолчанию русский)
    
    Returns:
        str: распознанная команда или None
    """
    try:
        recognizer = sr.Recognizer()
        
        # Конвертируем OGG в WAV если нужно
        import os
        import subprocess
        
        wav_path = audio_path
        if audio_path.endswith('.ogg'):
            wav_path = audio_path.replace('.ogg', '.wav')
            try:
                result = subprocess.run(
                    ['ffmpeg', '-i', audio_path, '-ar', '16000', '-ac', '1', '-y', wav_path],
                    check=True,
                    capture_output=True,
                    timeout=10
                )
            except FileNotFoundError:
                try:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_ogg(audio_path)
                    audio = audio.set_frame_rate(16000).set_channels(1)
                    audio.export(wav_path, format="wav")
                except Exception:
                    wav_path = audio_path
            except Exception:
                wav_path = audio_path
        
        # Читаем аудио файл
        with sr.AudioFile(wav_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.record(source)
        
        # Распознаем речь
        try:
            text = recognizer.recognize_google(audio, language=language)
            return text.lower().strip()
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.error(f"Ошибка сервиса распознавания команд: {e}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при распознавании голосовой команды: {e}", exc_info=True)
        return None
    finally:
        # Удаляем временный WAV файл если он был создан
        if 'wav_path' in locals() and wav_path != audio_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить временный WAV файл {wav_path}: {e}")

def match_voice_command(recognized_text, command_map):
    """
    Сопоставляет распознанный текст с командой из словаря
    
    Args:
        recognized_text: распознанный текст
        command_map: словарь {команда: функция}
    
    Returns:
        str: найденная команда или None
    """
    if not recognized_text:
        return None
    
    recognized_lower = recognized_text.lower().strip()
    
    # Прямое совпадение
    if recognized_lower in command_map:
        return recognized_lower
    
    # Проверяем частичное совпадение (команда может быть частью фразы)
    for command in command_map.keys():
        if command in recognized_lower or recognized_lower in command:
            return command
    
    return None

def text_to_speech_file(text, language='el', output_path=None):
    """
    Преобразует текст в голосовое сообщение (аудио файл)
    
    Args:
        text: текст для преобразования
        language: код языка (по умолчанию 'el' для греческого)
        output_path: путь для сохранения файла (если None, создается временный файл)
    
    Returns:
        str: путь к созданному аудио файлу (OGG) или None в случае ошибки
    """
    try:
        from gtts import gTTS
        import os
        import tempfile
        
        if not text or not text.strip():
            logger.warning("Пустой текст для преобразования в речь")
            return None
        
        # Создаем временный файл, если путь не указан
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix='.mp3', prefix='tts_')
            os.close(fd)
        
        # Генерируем аудио
        tts = gTTS(text=text, lang=language, slow=False)
        tts.save(output_path)
        
        logger.debug(f"Сгенерировано голосовое сообщение: {output_path}")
        return output_path
        
    except ImportError:
        logger.error("gTTS не установлен! Установите: pip install gtts")
        return None
    except Exception as e:
        logger.error(f"Ошибка при генерации голосового сообщения: {e}", exc_info=True)
        return None

