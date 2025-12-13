"""
Telegram бот для тренировки греческого языка
"""
import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ChatAction

from config import TELEGRAM_BOT_TOKEN
from user_state import get_user_state, get_user_stats

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать свой user_id"""
    from database import add_user as db_add_user, is_tracked_user
    
    user = update.effective_user
    user_id = user.id
    username = user.username
    
    # Обновляем username в БД, если пользователь отслеживается
    if is_tracked_user(user_id):
        db_add_user(user_id, username=username, is_tracked=True)
    
    message = f"🆔 Ваш User ID: <code>{user_id}</code>\n\n"
    
    if username:
        message += f"👤 Username: @{username}\n\n"
    else:
        message += "👤 Username: не установлен\n\n"
    
    message += (
        "💡 Для добавления в список отслеживаемых используйте:\n"
        f"<code>/add_user {user_id}</code>\n\n"
        "📝 Примечание: User ID - это число, которое не меняется. "
        "Username (@имя) может меняться или отсутствовать."
    )
    
    await update.message.reply_text(message, parse_mode='HTML')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    from database import is_superuser
    
    user_id = update.effective_user.id
    is_super = is_superuser(user_id)
    
    welcome_message = """
👋 Привет! Я бот для тренировки греческого языка.

📚 Доступные команды:

/add_words - Добавить слова в словарь
/training - Начать тренировку слов
/read_text - Чтение текста
/ai_generate - Генерация предложений с помощью ИИ
/stats - Показать статистику
/reset_stats - Сбросить статистику по словам (для отслеживаемых пользователей)
/my_id - Показать свой User ID
"""
    
    if is_super:
        welcome_message += """/add_user - Добавить пользователя в список отслеживаемых
/remove_user - Удалить пользователя из списка отслеживаемых
/list_users - Показать список отслеживаемых пользователей
/add_admin - Добавить администратора
/remove_admin - Убрать права администратора
"""
    
    welcome_message += """/help - Помощь

Выберите команду для начала!
    """
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    from database import is_superuser
    
    user_id = update.effective_user.id
    is_super = is_superuser(user_id)
    
    help_text = """
📖 Помощь по командам:

1️⃣ /add_words - Добавление слов в словарь
   Формат 1: отправьте "слово,перевод"
   Формат 2: отправьте многострочный текст (слово\\nперевод\\n\\n)

2️⃣ /training - Тренировка слов
   Бот будет показывать слова из словаря, вы произносите их на греческом

3️⃣ /read_text - Чтение текста
   Отправьте текст на греческом, затем произнесите его голосом

4️⃣ /ai_generate - Генерация предложений
   Опишите задание (например: "сгенери 50 предложений с винительным падежом")
   Бот сгенерирует предложения и начнет тренировку

5️⃣ /stats - Показать статистику тренировок

6️⃣ /reset_stats - Сбросить статистику по словам (только для отслеживаемых пользователей)

7️⃣ /my_id - Показать свой User ID (для добавления в список отслеживаемых)
"""
    
    # Команды управления пользователями только для администраторов
    if is_super:
        help_text += """
8️⃣ /add_user - Добавить пользователя в список отслеживаемых

9️⃣ /remove_user - Удалить пользователя из списка

🔟 /list_users - Показать список отслеживаемых пользователей

1️⃣1️⃣ /add_admin - Добавить администратора

1️⃣2️⃣ /remove_admin - Убрать права администратора

1️⃣3️⃣ /cancel - Отменить текущую операцию
"""
    else:
        help_text += """
8️⃣ /cancel - Отменить текущую операцию
"""
    
    await update.message.reply_text(help_text)

async def reset_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить статистику по словам для пользователя"""
    from vocabulary import Vocabulary
    from user_state import is_tracked_user
    
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь отслеживаемым
    if not is_tracked_user(user_id):
        await update.message.reply_text(
            "❌ Статистика по словам ведется только для пользователей из списка.\n"
            "Ваша статистика не отслеживается."
        )
        return
    
    vocab = Vocabulary(user_id=user_id)
    deleted_count = vocab.reset_user_statistics(user_id)
    
    await update.message.reply_text(
        f"✅ Статистика по словам сброшена!\n\n"
        f"Удалено записей: {deleted_count}\n\n"
        f"Теперь все слова будут доступны для тренировки."
    )

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить пользователя в список отслеживаемых (только для администраторов)"""
    from database import add_user as db_add_user, is_tracked_user, is_superuser
    
    # Проверяем права доступа
    current_user_id = update.effective_user.id
    if not is_superuser(current_user_id):
        await update.message.reply_text(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Только супер-пользователи могут добавлять пользователей в список отслеживаемых."
        )
        return
    
    # Проверяем, есть ли reply на сообщение пользователя
    username = None
    user_id = None
    
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        # Если команда отправлена как ответ на сообщение пользователя
        replied_user = update.message.reply_to_message.from_user
        user_id = replied_user.id
        username = replied_user.username
    elif context.args:
        # Если user_id указан в аргументах
        try:
            user_id = int(context.args[0])
            # Получаем username из аргументов, если указан
            if len(context.args) > 1:
                username = context.args[1]
                if username.startswith('@'):
                    username = username[1:]  # Убираем @ если есть
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат user_id. Должно быть число.\n\n"
                "Использование:\n"
                "• Ответьте на сообщение пользователя командой /add_user\n"
                "• Или: /add_user <user_id> [username]\n\n"
                "Пример: /add_user 123456789"
            )
            return
    else:
        await update.message.reply_text(
            "❌ Использование:\n"
            "• Ответьте на сообщение пользователя командой /add_user\n"
            "• Или: /add_user <user_id> [username]\n\n"
            "Пример: /add_user 123456789\n\n"
            "💡 Используйте /my_id чтобы узнать user_id пользователя"
        )
        return
    
    if not user_id:
        await update.message.reply_text("❌ Не удалось определить user_id пользователя")
        return
    
    # Проверяем, не добавлен ли уже
    if is_tracked_user(user_id):
        await update.message.reply_text(
            f"ℹ️ Пользователь {user_id} уже в списке отслеживаемых"
        )
        return
    
    # Добавляем пользователя
    if db_add_user(user_id, username=username, is_tracked=True):
        username_text = f" (@{username})" if username else ""
        await update.message.reply_text(
            f"✅ Пользователь {user_id}{username_text} добавлен в список отслеживаемых!\n\n"
            f"Теперь для этого пользователя будет вестись статистика по словам."
        )
    else:
        await update.message.reply_text(
            f"❌ Ошибка при добавлении пользователя {user_id}"
        )

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить пользователя из списка отслеживаемых (только для администраторов)"""
    from database import remove_user as db_remove_user, is_tracked_user, is_superuser
    
    # Проверяем права доступа
    current_user_id = update.effective_user.id
    if not is_superuser(current_user_id):
        await update.message.reply_text(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Только супер-пользователи могут удалять пользователей из списка отслеживаемых."
        )
        return
    
    # Проверяем аргументы команды
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /remove_user <user_id>\n\n"
            "Пример: /remove_user 123456789"
        )
        return
    
    try:
        user_id = int(context.args[0])
        
        # Проверяем, существует ли пользователь
        if not is_tracked_user(user_id):
            await update.message.reply_text(
                f"ℹ️ Пользователь {user_id} не найден в списке отслеживаемых"
            )
            return
        
        # Удаляем пользователя
        if db_remove_user(user_id):
            await update.message.reply_text(
                f"✅ Пользователь {user_id} удален из списка отслеживаемых.\n\n"
                f"Статистика по словам для этого пользователя сохранена, но больше не будет обновляться."
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка при удалении пользователя {user_id}"
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат user_id. Должно быть число.\n\n"
            "Пример: /remove_user 123456789"
        )

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список отслеживаемых пользователей"""
    from database import get_tracked_users_with_info, add_user as db_add_user
    
    users = get_tracked_users_with_info()
    
    if not users:
        await update.message.reply_text(
            "ℹ️ Список отслеживаемых пользователей пуст.\n\n"
            "Используйте /add_user <user_id> для добавления пользователя."
        )
        return
    
    # Пытаемся обновить username для текущего пользователя, если он в списке
    current_user = update.effective_user
    if current_user.id in [u['user_id'] for u in users]:
        db_add_user(current_user.id, username=current_user.username, is_tracked=True)
        # Обновляем список после обновления
        users = get_tracked_users_with_info()
    
    users_list = []
    for user in users:
        user_id = user['user_id']
        username = user['username']
        if username:
            users_list.append(f"• {user_id} - @{username}")
        else:
            users_list.append(f"• {user_id} - (username не указан)")
    
    await update.message.reply_text(
        f"📋 Отслеживаемые пользователи ({len(users)}):\n\n" + "\n".join(users_list)
    )

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить пользователя в список администраторов (только для администраторов)"""
    from database import add_admin as db_add_admin, is_superuser
    
    # Проверяем права доступа
    current_user_id = update.effective_user.id
    if not is_superuser(current_user_id):
        await update.message.reply_text(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Только администраторы могут добавлять других администраторов."
        )
        return
    
    # Проверяем аргументы команды
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /add_admin <user_id> [username]\n\n"
            "Пример: /add_admin 123456789\n\n"
            "💡 Используйте /my_id чтобы узнать user_id пользователя"
        )
        return
    
    try:
        user_id = int(context.args[0])
        
        # Получаем username из аргументов, если указан
        username = context.args[1] if len(context.args) > 1 else None
        if username and username.startswith('@'):
            username = username[1:]  # Убираем @ если есть
        
        # Добавляем администратора
        if db_add_admin(user_id, username=username):
            username_text = f" (@{username})" if username else ""
            await update.message.reply_text(
                f"✅ Пользователь {user_id}{username_text} добавлен в список администраторов!\n\n"
                f"Теперь этот пользователь имеет права администратора."
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка при добавлении администратора {user_id}"
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат user_id. Должно быть число.\n\n"
            "Пример: /add_admin 123456789\n"
            "Или с username: /add_admin 123456789 username"
        )

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Убрать права администратора у пользователя (только для администраторов)"""
    from database import remove_admin as db_remove_admin, is_superuser
    
    # Проверяем права доступа
    current_user_id = update.effective_user.id
    if not is_superuser(current_user_id):
        await update.message.reply_text(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Только администраторы могут убирать права администратора."
        )
        return
    
    # Проверяем аргументы команды
    if not context.args:
        await update.message.reply_text(
            "❌ Использование: /remove_admin <user_id>\n\n"
            "Пример: /remove_admin 123456789"
        )
        return
    
    try:
        user_id = int(context.args[0])
        
        # Нельзя убрать права у самого себя
        if user_id == current_user_id:
            await update.message.reply_text(
                "❌ Вы не можете убрать права администратора у самого себя."
            )
            return
        
        # Убираем права администратора
        if db_remove_admin(user_id):
            await update.message.reply_text(
                f"✅ Права администратора у пользователя {user_id} убраны.\n\n"
                f"Пользователь больше не является администратором."
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка при удалении администратора {user_id}\n\n"
                f"Возможно, пользователь не является администратором."
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат user_id. Должно быть число.\n\n"
            "Пример: /remove_admin 123456789"
        )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику пользователя"""
    from vocabulary import Vocabulary
    
    user_id = update.effective_user.id
    stats = get_user_stats(user_id)
    
    # Получаем статистику словаря
    vocab = Vocabulary(user_id=user_id)
    vocab_count = vocab.count()
    
    total = stats['total_attempts']
    correct = stats['correct_attempts']
    accuracy = (correct / total * 100) if total > 0 else 0
    
    training_total = stats['training_words']['total']
    training_correct = stats['training_words']['correct']
    training_accuracy = (training_correct / training_total * 100) if training_total > 0 else 0
    
    reading_total = stats['text_reading']['total']
    reading_correct = stats['text_reading']['correct']
    reading_accuracy = (reading_correct / reading_total * 100) if reading_total > 0 else 0
    
    stats_text = f"""
📊 Ваша статистика:

📚 Словарь:
   Слов в словаре: {vocab_count}

🎯 Общая статистика:
   Всего попыток: {total}
   Правильных: {correct}
   Точность: {accuracy:.1f}%

📝 Тренировка слов:
   Попыток: {training_total}
   Правильных: {training_correct}
   Точность: {training_accuracy:.1f}%

📖 Чтение текста:
   Попыток: {reading_total}
   Правильных: {reading_correct}
   Точность: {reading_accuracy:.1f}%
    """
    await update.message.reply_text(stats_text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить текущую операцию"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    state['mode'] = None
    state['data'] = {}
    await update.message.reply_text("✅ Операция отменена")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    text = update.message.text
    
    if state['mode'] == 'add_word':
        from commands import handle_add_word
        await handle_add_word(update, context, text)
    elif state['mode'] == 'training' or state['mode'] == 'ai_training':
        # В режиме тренировки текстовые сообщения не обрабатываются
        await update.message.reply_text("Пожалуйста, отправьте голосовое сообщение")
    elif state['mode'] == 'read_text_waiting':
        # Пользователь отправил текст для чтения
        state['mode'] = 'read_text'
        state['data']['text'] = text
        await update.message.reply_text(
            f"✅ Текст получен:\n\n{text}\n\n"
            "Теперь произнесите этот текст голосом 🎤"
        )
    elif state['mode'] == 'ai_generate':
        from commands import handle_ai_generation
        await handle_ai_generation(update, context, text)
    else:
        await update.message.reply_text(
            "Используйте команды для работы с ботом. /help - для помощи"
        )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик голосовых сообщений"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    
    if state['mode'] == 'training':
        await handle_training_voice(update, context)
    elif state['mode'] == 'read_text':
        await handle_reading_voice(update, context)
    elif state['mode'] == 'ai_training':
        from commands import handle_ai_training_voice
        await handle_ai_training_voice(update, context)
    else:
        await update.message.reply_text(
            "Сначала запустите тренировку (/training), чтение текста (/read_text) или генерацию (/ai_generate)"
        )

async def handle_training_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка голоса в режиме тренировки"""
    from utils import compare_texts, recognize_voice_from_file
    from user_state import send_next_training_word, is_tracked_user
    from vocabulary import Vocabulary
    
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    stats = get_user_stats(user_id)
    vocab = Vocabulary(user_id=user_id)
    
    await update.message.reply_chat_action(ChatAction.TYPING)
    
    # Получаем аудио файл
    voice_file = await context.bot.get_file(update.message.voice.file_id)
    
    # Скачиваем аудио
    audio_path = f"temp_audio_{user_id}.ogg"
    await voice_file.download_to_drive(audio_path)
    
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
            await update.message.reply_text("Ошибка: не найдено текущее слово")
            return
        
        # Проверяем, не сказал ли пользователь "δεν ξέρω" (не знаю) для пропуска слова
        recognized_normalized = recognized_text.lower().strip()
        # Различные варианты написания "δεν ξέρω" (с ударениями и без)
        skip_phrases = ['δεν ξέρω', 'δεν ξερω', 'δεν ξέρο', 'δεν ξερο']
        
        # Проверяем, содержит ли распознанный текст одну из фраз пропуска
        # Учитываем, что распознавание может добавить лишние слова
        is_skip = any(
            phrase in recognized_normalized or 
            recognized_normalized.startswith(phrase) or
            recognized_normalized.endswith(phrase)
            for phrase in skip_phrases
        )
        
        if is_skip:
            # Пропускаем слово
            await update.message.reply_text(
                f"⏭️ Слово пропущено\n\n"
                f"Правильный ответ был: <b>{correct_greek}</b>\n"
                f"Перевод: {correct_russian}\n\n"
                f"Переходим к следующему слову...",
                parse_mode='HTML'
            )
            # Переходим к следующему слову
            await send_next_training_word(update, context)
            return
        
        # Сравниваем
        is_correct, similarity = compare_texts(recognized_text, correct_greek)
        
        stats['total_attempts'] += 1
        stats['training_words']['total'] += 1
        
        # Сохраняем статистику по слову для отслеживаемых пользователей
        if is_tracked_user(user_id):
            vocab.record_word_result(stats_user_id=user_id, greek=correct_greek, russian=correct_russian, is_successful=is_correct)
        
        if is_correct:
            stats['correct_attempts'] += 1
            stats['training_words']['correct'] += 1
            await update.message.reply_text(
                f"🎉 ПРАВИЛЬНО!\n\n"
                f"Вы сказали: {recognized_text}\n"
                f"Правильный ответ: {correct_greek}"
            )
            # Переходим к следующему слову
            await send_next_training_word(update, context)
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

async def handle_reading_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка голоса в режиме чтения текста"""
    from utils import compare_texts_detailed, recognize_voice_from_file
    
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    stats = get_user_stats(user_id)
    
    await update.message.reply_chat_action(ChatAction.TYPING)
    
    # Получаем правильный текст
    correct_text = state['data'].get('text')
    if not correct_text:
        await update.message.reply_text("Ошибка: текст не найден")
        return
    
    # Получаем аудио файл
    voice_file = await context.bot.get_file(update.message.voice.file_id)
    
    # Скачиваем аудио
    audio_path = f"temp_audio_{user_id}.ogg"
    await voice_file.download_to_drive(audio_path)
    
    try:
        # Распознаем речь
        recognized_text = recognize_voice_from_file(audio_path, language='el-GR')
        
        if not recognized_text:
            await update.message.reply_text(
                "❌ Не удалось распознать речь. Попробуйте еще раз."
            )
            return
        
        # Сравниваем с детальным анализом ошибок
        is_correct, similarity, mistakes = compare_texts_detailed(recognized_text, correct_text)
        
        stats['total_attempts'] += 1
        stats['text_reading']['total'] += 1
        
        if is_correct:
            stats['correct_attempts'] += 1
            stats['text_reading']['correct'] += 1
            await update.message.reply_text(
                f"🎉 ПРАВИЛЬНО!\n\n"
                f"Вы сказали: {recognized_text}\n"
                f"Оригинал: {correct_text}"
            )
            state['mode'] = None
            state['data'] = {}
        else:
            # Формируем сообщение с ошибками
            message = f"❌ Обнаружены ошибки\n\n"
            message += f"Похожесть: {similarity*100:.1f}%\n\n"
            
            if mistakes:
                message += f"🔍 Найдено ошибок: {len(mistakes)}\n\n"
                message += "📝 Неправильно распознанные слова:\n\n"
                
                # Показываем первые 10 ошибок
                for i, mistake in enumerate(mistakes[:10], 1):
                    recognized = mistake['recognized'] or "(не распознано)"
                    correct = mistake['correct'] or "(лишнее слово)"
                    
                    if mistake['recognized'] is None:
                        message += f"{i}. ❌ Пропущено: <b>{correct}</b>\n"
                    elif mistake['correct'] is None:
                        message += f"{i}. ➕ Лишнее: <b>{recognized}</b>\n"
                    else:
                        message += f"{i}. ❌ <b>{recognized}</b> → <b>{correct}</b>\n"
                
                if len(mistakes) > 10:
                    message += f"\n... и еще {len(mistakes) - 10} ошибок"
            
            message += f"\n\n📄 Распознанный текст:\n{recognized_text}\n\n"
            message += f"📄 Оригинальный текст:\n{correct_text}\n\n"
            message += "Попробуйте еще раз!"
            
            await update.message.reply_text(message, parse_mode='HTML')
    
    finally:
        # Удаляем временный файл
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл {audio_path}: {e}")

# Функция send_next_training_word перенесена в user_state.py

def main():
    """Запуск бота"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    # Инициализируем базу данных
    logger.info("Инициализация базы данных...")
    from database import init_database
    if not init_database():
        logger.error("Не удалось инициализировать базу данных!")
        logger.error("Проверьте права доступа к файлу vocabulary.db")
        return
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    from commands import (
        handle_add_word_command,
        handle_training_command,
        handle_read_text_command,
        handle_ai_generate_command
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("reset_stats", reset_stats))
    application.add_handler(CommandHandler("my_id", my_id))
    application.add_handler(CommandHandler("add_user", add_user))
    application.add_handler(CommandHandler("remove_user", remove_user))
    application.add_handler(CommandHandler("list_users", list_users))
    application.add_handler(CommandHandler("add_admin", add_admin))
    application.add_handler(CommandHandler("remove_admin", remove_admin))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("add_words", handle_add_word_command))
    application.add_handler(CommandHandler("training", handle_training_command))
    application.add_handler(CommandHandler("read_text", handle_read_text_command))
    application.add_handler(CommandHandler("ai_generate", handle_ai_generate_command))
    
    # Регистрируем обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

