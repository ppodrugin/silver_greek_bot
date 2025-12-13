"""
Модуль для генерации предложений с помощью OpenAI API
"""
import logging
from openai import OpenAI
from config import OPENAI_API_KEY
from vocabulary import Vocabulary

logger = logging.getLogger(__name__)

async def generate_sentences_with_ai(prompt: str, user_id: int):
    """
    Генерирует предложения на греческом языке с помощью OpenAI API
    
    Args:
        prompt: Запрос пользователя (например, "сгенери 50 предложений с винительным падежом")
        user_id: ID пользователя для получения его словаря
    
    Returns:
        list: Список кортежей (русский_перевод, греческий_текст)
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY не установлен!")
        return None
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Загружаем словарь пользователя для контекста
        vocab = Vocabulary(user_id=user_id)
        words = vocab.get_all_words()
        
        # Формируем контекст из словаря
        vocab_context = ""
        if words:
            vocab_context = "\nСловарь содержит следующие слова:\n"
            for greek, russian in words[:50]:  # Берем первые 50 слов для контекста
                vocab_context += f"- {greek} ({russian})\n"
        
        # Формируем системный промпт
        system_prompt = """Ты помощник для изучения греческого языка. 
Твоя задача - генерировать предложения на греческом языке с переводами на русский.

Требования:
1. Используй только слова из предоставленного словаря
2. Предложения должны быть грамматически правильными
3. Формат ответа: каждая строка должна быть в формате "Русский перевод | Греческий текст"
4. Не добавляй нумерацию и другие символы
5. Предложения должны быть простыми и понятными для изучения

Пример формата:
Я вижу друга | Εγώ βλέπω τον φίλο.
Мать читает книгу | η μητέρα διαβάζει το βιβλίο."""
        
        # Формируем пользовательский промпт
        user_prompt = f"""{prompt}

{vocab_context}

Сгенерируй предложения в формате: Русский перевод | Греческий текст
Каждое предложение на отдельной строке."""
        
        # Вызываем API с таймаутом
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Используем более дешевую модель
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2000,
                timeout=30.0  # Таймаут 30 секунд
            )
        except Exception as api_error:
            logger.error(f"Ошибка при вызове OpenAI API: {api_error}", exc_info=True)
            return None
        
        # Парсим ответ
        content = response.choices[0].message.content
        sentences = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or '|' not in line:
                continue
            
            # Убираем нумерацию если есть
            if line[0].isdigit() and (line[1] == '.' or line[1] == ')'):
                line = line[2:].strip()
            
            parts = line.split('|', 1)
            if len(parts) == 2:
                russian = parts[0].strip().rstrip('.')
                greek = parts[1].strip().rstrip('.')
                if russian and greek:
                    sentences.append((russian, greek))
        
        return sentences if sentences else None
        
    except Exception as e:
        logger.error(f"Ошибка при генерации предложений: {e}", exc_info=True)
        return None

