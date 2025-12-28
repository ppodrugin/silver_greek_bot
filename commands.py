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

async def check_tracked_user(update: Update) -> bool:
    """
    Проверяет, является ли пользователь отслеживаемым.
    Если нет - отправляет сообщение и возвращает False.
    """
    from database import is_tracked_user, is_superuser
    
    user_id = update.effective_user.id
    
    # Супер-пользователи всегда имеют доступ
    if is_superuser(user_id):
        return True
    
    # Проверяем, отслеживается ли пользователь
    if not is_tracked_user(user_id):
        message = (
            "⚠️ Вы не зарегистрированы в системе.\n\n"
            "Для использования бота необходимо обратиться к администратору "
            "для добавления вас в список отслеживаемых пользователей.\n\n"
            "Используйте команду /add_me Ваше имя для запроса добавления в систему."
        )
        await update.message.reply_text(message)
        return False
    
    return True

# Ограничения
MAX_WORDS_PER_BATCH = 100  # Максимальное количество слов за раз
MAX_TEXT_LENGTH = 10000  # Максимальная длина текста
MAX_AUDIO_SIZE_MB = 20  # Максимальный размер аудио файла в МБ

async def handle_add_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /add_words"""
    if not await check_tracked_user(update):
        return
    
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    
    # Проверяем, передан ли параметр урока
    lesson_name = None
    if context.args and len(context.args) > 0:
        lesson_name = ' '.join(context.args).strip()
    
    state['mode'] = 'add_word'
    state['data'] = {'format': None, 'lesson_name': lesson_name}
    
    if lesson_name:
        await update.message.reply_text(
            f"📝 Добавление слов в словарь\n\n"
            f"📚 Урок: <b>{lesson_name}</b>\n\n"
            "Можно добавить несколько слов за раз!\n\n"
            "Формат 1 (CSV, несколько строк):\n"
            "<code>слово1,перевод1\nслово2,перевод2\nслово3,перевод3</code>\n\n"
            "Формат 2 (многострочный):\n"
            "<code>слово1\nперевод1\n\nслово2\nперевод2</code>\n\n"
            "Или /cancel для отмены",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "📝 Добавление слов в словарь\n\n"
            "⚠️ Не указан урок! Используйте команду так:\n"
            "<code>/add_words Название урока</code>\n\n"
            "Например: <code>/add_words Урок 1</code>\n\n"
            "Или /cancel для отмены",
            parse_mode='HTML'
        )
        state['mode'] = None

async def handle_add_word(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Обработка добавления слов (несколько слов за раз)"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    lesson_name = state.get('data', {}).get('lesson_name')
    
    # Проверяем, что урок указан
    if not lesson_name:
        await update.message.reply_text(
            "❌ Не указан урок! Используйте команду так:\n"
            "<code>/add_words Название урока</code>\n\n"
            "Например: <code>/add_words Урок 1</code>",
            parse_mode='HTML'
        )
        state['mode'] = None
        return
    
    # Валидация длины текста
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(
            f"❌ Текст слишком длинный (максимум {MAX_TEXT_LENGTH} символов). "
            f"Отправлено: {len(text)} символов."
        )
        return
    
    logger.debug(f"handle_add_word вызван для user_id={user_id}, lesson_name={lesson_name}, text length={len(text)}")
    
    # Создаем урок (если уже существует - ошибка)
    from database import create_lesson
    try:
        lesson_id = create_lesson(lesson_name, user_id)
        if lesson_id is None:
            await update.message.reply_text(
                f"❌ Ошибка при создании урока '{lesson_name}'"
            )
            state['mode'] = None
            return
    except ValueError as e:
        # Урок уже существует
        await update.message.reply_text(
            f"❌ {str(e)}\n\n"
            "Используйте другое название урока или отмените операцию командой /cancel"
        )
        state['mode'] = None
        return
    
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
            added, skipped = vocab.add_words_batch(words_to_add, lesson_id=lesson_id)
            logger.debug(f"Результат: added={added}, skipped={skipped}")
            
            response = f"✅ Урок '{lesson_name}' создан\n"
            response += f"✅ Добавлено слов: {added}"
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
    if not await check_tracked_user(update):
        return
    
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    
    # Проверяем, передан ли параметр урока
    lesson_name = None
    lesson_id = None
    if context.args and len(context.args) > 0:
        lesson_name = ' '.join(context.args).strip()
        from database import get_lesson_id
        lesson_id = get_lesson_id(lesson_name, user_id)
        
        if lesson_id is None:
            await update.message.reply_text(
                f"❌ Урок '{lesson_name}' не найден!\n\n"
                "Используйте команду без параметра для тренировки всех слов или укажите существующий урок."
            )
            return
    
    vocab = Vocabulary(user_id=user_id)
    
    # Проверяем наличие слов (с учетом урока, если указан)
    if lesson_id is not None:
        # Проверяем количество слов в уроке
        from database import get_connection, return_connection, get_param
        conn = get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                param = get_param()
                count_query = f"SELECT COUNT(*) FROM vocabulary WHERE user_id = {param} AND lesson_id = {param}"
                cursor.execute(count_query, (user_id, lesson_id))
                count_result = cursor.fetchone()
                word_count = count_result[0] if count_result else 0
                return_connection(conn)
                
                if word_count == 0:
                    await update.message.reply_text(
                        f"❌ В уроке '{lesson_name}' нет слов!\n\n"
                        "Добавьте слова в этот урок командой /add_words"
                    )
                    return
            except Exception as e:
                logger.error(f"Ошибка при проверке слов урока: {e}", exc_info=True)
                return_connection(conn)
        else:
            await update.message.reply_text("❌ Ошибка подключения к базе данных")
            return
    else:
        if vocab.count() == 0:
            await update.message.reply_text(
                "❌ Словарь пуст! Сначала добавьте слова командой /add_words"
            )
            return
    
    state['mode'] = 'training'
    state['data'] = {'lesson_id': lesson_id, 'lesson_name': lesson_name}
    
    logger.info(f"Тренировка начата для user_id={user_id}, lesson_id={lesson_id}, lesson_name={lesson_name}")
    
    message = "🎯 Тренировка слов начата!\n\n"
    if lesson_name:
        message += f"📚 Урок: <b>{lesson_name}</b>\n\n"
    message += (
        "Бот будет показывать слова на русском.\n"
        "Вы произносите их на греческом голосом.\n\n"
        "💡 Чтобы пропустить слово:\n"
        "   • Скажите: <b>δεν ξέρω</b> (не знаю)\n"
        "   • Или отправьте в чат: <b>-</b>\n\n"
        "Используйте /cancel для выхода из режима тренировки."
    )
    
    await update.message.reply_text(message, parse_mode='HTML')
    
    # Отправляем первое слово
    await send_next_training_word(update, context)

async def handle_read_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /read_text"""
    if not await check_tracked_user(update):
        return
    
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
    """Обработчик команды /ai (ранее /ai_generate)"""
    if not await check_tracked_user(update):
        return
    
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
        
        # Получаем порог похожести из состояния пользователя (по умолчанию 0.85 = 85%)
        threshold = state.get('similarity_threshold', 85) / 100.0  # Конвертируем проценты в 0.0-1.0
        
        # Сравниваем (используем более гибкую функцию для предложений)
        from utils import compare_texts_sentences
        is_correct, similarity = compare_texts_sentences(recognized_text, correct_greek, threshold=threshold)
        
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
            # Отправляем текстовое сообщение
            await update.message.reply_text(
                f"❌ Не совсем правильно\n\n"
                f"Вы сказали: {recognized_text}\n"
                f"Правильный ответ: {correct_greek}\n"
                f"Похожесть: {similarity*100:.1f}%\n\n"
                f"Попробуйте еще раз!"
            )
            
            # Генерируем и отправляем голосовое сообщение с правильным произношением
            try:
                from utils import text_to_speech_file
                
                tts_file = text_to_speech_file(correct_greek, language='el')
                if tts_file and os.path.exists(tts_file):
                    try:
                        with open(tts_file, 'rb') as audio_file:
                            await update.message.reply_voice(
                                voice=audio_file,
                                caption="🎤 Правильное произношение:"
                            )
                    finally:
                        # Удаляем временный файл
                        try:
                            os.remove(tts_file)
                        except Exception as e:
                            logger.warning(f"Не удалось удалить временный TTS файл {tts_file}: {e}")
            except Exception as e:
                logger.warning(f"Ошибка при генерации голосового сообщения: {e}", exc_info=True)
                # Не прерываем выполнение, если не удалось отправить голосовое сообщение
    
    finally:
        # Удаляем временный файл
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл {audio_path}: {e}")

