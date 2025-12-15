"""
Обработчики команд бота
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from vocabulary import Vocabulary
from utils import compare_texts, recognize_voice_from_file
from ai_generator import generate_sentences_with_ai
from user_state import get_user_state, get_user_stats, send_next_training_word

logger = logging.getLogger(__name__)

# Ограничения
MAX_WORDS_PER_BATCH = 100  # Максимальное количество слов за раз
MAX_TEXT_LENGTH = 10000  # Максимальная длина текста
MAX_AUDIO_SIZE_MB = 20  # Максимальный размер аудио файла в МБ

async def handle_add_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /add_words"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    
    state['mode'] = 'add_word'
    state['data'] = {'format': None}
    
    await update.message.reply_text(
        "📝 Добавление слов в словарь\n\n"
        "Можно добавить несколько слов за раз!\n\n"
        "Формат 1 (CSV, несколько строк):\n"
        "<code>слово1,перевод1\nслово2,перевод2\nслово3,перевод3</code>\n\n"
        "Формат 2 (многострочный):\n"
        "<code>слово1\nперевод1\n\nслово2\nперевод2</code>\n\n"
        "Или /cancel для отмены",
        parse_mode='HTML'
    )

async def handle_add_word(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Обработка добавления слов (несколько слов за раз)"""
    user_id = update.effective_user.id
    
    # Валидация длины текста
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(
            f"❌ Текст слишком длинный (максимум {MAX_TEXT_LENGTH} символов). "
            f"Отправлено: {len(text)} символов."
        )
        return
    
    logger.debug(f"handle_add_word вызван для user_id={user_id}, text length={len(text)}")
    vocab = Vocabulary(user_id=user_id)
    words_to_add = []
    errors = []
    
    # Определяем формат более умно
    # Проверяем первые несколько непустых строк на наличие запятой
    lines_for_check = [line.strip() for line in text.split('\n') if line.strip()][:5]
    csv_lines_count = sum(1 for line in lines_for_check if ',' in line and line.count(',') == 1)
    
    # Если большинство строк содержит запятую (CSV формат)
    is_csv_format = len(lines_for_check) > 0 and csv_lines_count >= len(lines_for_check) * 0.6
    
    if is_csv_format:
        # Формат CSV - может быть несколько строк
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        for line in lines:
            if ',' in line:
                parts = line.split(',', 1)
                if len(parts) == 2:
                    greek = parts[0].strip()
                    russian = parts[1].strip()
                    if greek and russian:
                        words_to_add.append((greek, russian))
                    else:
                        errors.append(f"Пустое значение в строке: {line}")
                else:
                    errors.append(f"Неверный формат в строке: {line}")
            # Не добавляем ошибку для строк без запятой - возможно это не CSV формат
    else:
        # Многострочный формат - может быть несколько пар
        # Формат: слово\nперевод\n\nслово\nперевод
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Греческое слово
            greek = line
            
            # Ищем перевод на следующей непустой строке
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            
            if i < len(lines):
                russian = lines[i].strip()
                if greek and russian:
                    words_to_add.append((greek, russian))
                else:
                    errors.append(f"Пустое значение для слова: {greek}")
                i += 1
            else:
                # Последнее слово без перевода - не добавляем ошибку, просто пропускаем
                break
    
    # Валидация количества слов
    if len(words_to_add) > MAX_WORDS_PER_BATCH:
        await update.message.reply_text(
            f"❌ Слишком много слов за раз (максимум {MAX_WORDS_PER_BATCH}). "
            f"Найдено: {len(words_to_add)} слов.\n\n"
            f"Разделите добавление на несколько частей."
        )
        return
    
    # Добавляем слова пакетом
    logger.debug(f"Найдено слов для добавления: {len(words_to_add)}")
    if words_to_add:
        logger.debug(f"Слова для добавления: {words_to_add[:3]}...")  # Показываем первые 3
        try:
            added, skipped = vocab.add_words_batch(words_to_add)
            logger.debug(f"Результат: added={added}, skipped={skipped}")
            
            response = f"✅ Добавлено слов: {added}"
            if skipped > 0:
                response += f"\n⚠️ Пропущено дубликатов: {skipped}"
            response += f"\n\nВсего слов в словаре: {vocab.count()}"
            
            if errors:
                response += f"\n\n⚠️ Ошибок при разборе: {len(errors)}"
                if len(errors) <= 3:
                    for error in errors:
                        response += f"\n  - {error}"
            
            await update.message.reply_text(response)
        except Exception as e:
            import traceback
            error_msg = f"❌ Ошибка при добавлении слов: {str(e)}"
            logger.error(f"Ошибка в handle_add_word: {e}", exc_info=True)
            await update.message.reply_text(error_msg)
        
        # Выходим из режима добавления после успешного добавления
        state = get_user_state(update.effective_user.id)
        state['mode'] = None
    else:
        logger.debug(f"words_to_add пуст, errors={len(errors)}")
        if errors:
            error_msg = "❌ Не удалось разобрать слова:\n\n"
            for error in errors[:5]:  # Показываем максимум 5 ошибок
                error_msg += f"• {error}\n"
            await update.message.reply_text(error_msg)
        else:
            logger.debug("Отправляем сообщение о неверном формате")
            await update.message.reply_text(
                "❌ Неверный формат.\n\n"
                "Формат 1 (CSV, несколько строк):\n"
                "слово1,перевод1\n"
                "слово2,перевод2\n\n"
                "Формат 2 (многострочный):\n"
                "слово1\n"
                "перевод1\n\n"
                "слово2\n"
                "перевод2"
            )

async def handle_training_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /training"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    
    vocab = Vocabulary(user_id=user_id)
    if vocab.count() == 0:
        await update.message.reply_text(
            "❌ Словарь пуст! Сначала добавьте слова командой /add_words"
        )
        return
    
    state['mode'] = 'training'
    state['data'] = {}
    
    logger.info(f"Тренировка начата для user_id={user_id}, mode={state['mode']}")
    
    await update.message.reply_text(
        "🎯 Тренировка слов начата!\n\n"
        "Бот будет показывать слова на русском.\n"
        "Вы произносите их на греческом голосом.\n\n"
        "💡 Чтобы пропустить слово, скажите: <b>δεν ξέρω</b> (не знаю)\n\n"
        "Используйте /cancel для выхода из режима тренировки.",
        parse_mode='HTML'
    )
    
    # Отправляем первое слово
    await send_next_training_word(update, context)

async def handle_read_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /read_text"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    
    state['mode'] = 'read_text_waiting'
    state['data'] = {}
    
    await update.message.reply_text(
        "📖 Режим чтения текста\n\n"
        "Отправьте текст на греческом языке.\n"
        "Затем произнесите его голосом.\n\n"
        "Используйте /cancel для отмены."
    )

async def handle_ai_generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /ai_generate"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    
    state['mode'] = 'ai_generate'
    state['data'] = {}
    
    await update.message.reply_text(
        "🤖 Генерация предложений с помощью ИИ\n\n"
        "Опишите задание в свободной форме.\n"
        "Например:\n"
        "• 'сгенери 50 предложений с винительным падежом'\n"
        "• 'создай 30 фраз используя словарь'\n"
        "• '50 предложений с предлогами με и σε'\n\n"
        "После генерации начнется тренировка.\n\n"
        "Используйте /cancel для отмены."
    )

async def handle_ai_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Обработка генерации предложений через ИИ"""
    # Валидация длины текста
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(
            f"❌ Текст слишком длинный (максимум {MAX_TEXT_LENGTH} символов). "
            f"Отправлено: {len(text)} символов."
        )
        state = get_user_state(update.effective_user.id)
        state['mode'] = None
        return
    
    await update.message.reply_chat_action(ChatAction.TYPING)
    
    try:
        # Генерируем предложения
        user_id = update.effective_user.id
        sentences = await generate_sentences_with_ai(text, user_id)
        
        if not sentences:
            await update.message.reply_text(
                "❌ Не удалось сгенерировать предложения. "
                "Проверьте, что OPENAI_API_KEY установлен в .env файле."
            )
            state = get_user_state(update.effective_user.id)
            state['mode'] = None
            return
        
        # Сохраняем предложения в состояние
        user_id = update.effective_user.id
        state = get_user_state(user_id)
        state['mode'] = 'ai_training'
        state['data'] = {
            'sentences': sentences,
            'current_index': 0
        }
        
        await update.message.reply_text(
            f"✅ Сгенерировано {len(sentences)} предложений!\n\n"
            "Начинаем тренировку..."
        )
        
        # Отправляем первое предложение
        await send_next_ai_sentence(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка при генерации предложений: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Ошибка при генерации: {str(e)}"
        )
        state = get_user_state(update.effective_user.id)
        state['mode'] = None

async def send_next_ai_sentence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет следующее предложение из ИИ генерации"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    
    sentences = state['data'].get('sentences', [])
    current_index = state['data'].get('current_index', 0)
    
    if current_index >= len(sentences):
        await update.message.reply_text(
            "🎉 Все предложения пройдены! Тренировка завершена."
        )
        state['mode'] = None
        state['data'] = {}
        return
    
    russian, greek = sentences[current_index]
    state['data']['current_greek'] = greek
    state['data']['current_russian'] = russian
    
    await update.message.reply_text(
        f"📝 Переведите на греческий:\n\n"
        f"<b>{russian}</b>\n\n"
        f"({current_index + 1}/{len(sentences)})",
        parse_mode='HTML'
    )

async def handle_ai_training_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка голоса в режиме ИИ тренировки"""
    import os
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    stats = get_user_stats(user_id)
    
    await update.message.reply_chat_action(ChatAction.TYPING)
    
    # Получаем аудио файл
    voice_file = await context.bot.get_file(update.message.voice.file_id)
    
    # Проверяем размер файла
    if voice_file.file_size and voice_file.file_size > MAX_AUDIO_SIZE_MB * 1024 * 1024:
        await update.message.reply_text(
            f"❌ Аудио файл слишком большой (максимум {MAX_AUDIO_SIZE_MB} МБ). "
            f"Размер файла: {voice_file.file_size / 1024 / 1024:.1f} МБ"
        )
        return
    
    # Скачиваем аудио
    audio_path = f"temp_audio_{user_id}.ogg"
    try:
        await voice_file.download_to_drive(audio_path)
    except Exception as e:
        logger.error(f"Ошибка при скачивании аудио: {e}", exc_info=True)
        await update.message.reply_text("❌ Ошибка при загрузке аудио файла")
        return
    
    try:
        # Распознаем речь
        recognized_text = recognize_voice_from_file(audio_path, language='el-GR')
        
        if not recognized_text:
            await update.message.reply_text(
                "❌ Не удалось распознать речь. Попробуйте еще раз."
            )
            return
        
        # Получаем правильный ответ
        correct_greek = state['data'].get('current_greek')
        correct_russian = state['data'].get('current_russian')
        
        if not correct_greek:
            await update.message.reply_text("Ошибка: не найдено текущее предложение")
            return
        
        # Сравниваем
        is_correct, similarity = compare_texts(recognized_text, correct_greek)
        
        stats['total_attempts'] += 1
        
        if is_correct:
            stats['correct_attempts'] += 1
            await update.message.reply_text(
                f"🎉 ПРАВИЛЬНО!\n\n"
                f"Вы сказали: {recognized_text}\n"
                f"Правильный ответ: {correct_greek}"
            )
            # Переходим к следующему предложению
            state['data']['current_index'] += 1
            await send_next_ai_sentence(update, context)
        else:
            await update.message.reply_text(
                f"❌ Не совсем правильно\n\n"
                f"Вы сказали: {recognized_text}\n"
                f"Правильный ответ: {correct_greek}\n"
                f"Похожесть: {similarity*100:.1f}%\n\n"
                f"Попробуйте еще раз!"
            )
    
    finally:
        # Удаляем временный файл
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл {audio_path}: {e}")

