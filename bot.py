"""
Telegram бот для тренировки греческого языка
"""
import logging
import os
import subprocess
from datetime import datetime
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

# Время запуска бота
BOT_START_TIME = datetime.now()

def require_tracked_user(func):
    """
    Декоратор для проверки, является ли пользователь отслеживаемым.
    Если нет - возвращает сообщение о необходимости обратиться к админу.
    """
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from database import is_tracked_user, is_superuser
        
        user_id = update.effective_user.id
        
        # Супер-пользователи всегда имеют доступ
        if is_superuser(user_id):
            return await func(update, context)
        
        # Проверяем, отслеживается ли пользователь
        if not is_tracked_user(user_id):
            message = (
                "⚠️ Вы не зарегистрированы в системе.\n\n"
                "Для использования бота необходимо обратиться к администратору "
                "для добавления вас в список отслеживаемых пользователей.\n\n"
                "Используйте команду /my_id чтобы узнать свой User ID и передать его администратору."
            )
            await update.message.reply_text(message)
            return
        
        # Пользователь отслеживается - выполняем команду
        return await func(update, context)
    
    return wrapper

def require_admin(func):
    """
    Декоратор для проверки, является ли пользователь администратором.
    Если нет - возвращает сообщение об отсутствии прав.
    """
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from database import is_superuser
        
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь администратором
        if not is_superuser(user_id):
            await update.message.reply_text(
                "❌ У вас нет прав для выполнения этой команды.\n\n"
                "Только администраторы могут использовать эту команду."
            )
            return
        
        # Пользователь администратор - выполняем команду
        return await func(update, context)
    
    return wrapper

async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать свой user_id (доступно всем для получения ID для регистрации)"""
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
    
    if not is_tracked_user(user_id):
        message += (
            "⚠️ Вы не зарегистрированы в системе.\n\n"
            "Для использования бота необходимо обратиться к администратору "
            "для добавления вас в список отслеживаемых пользователей.\n\n"
            "Передайте администратору ваш User ID, указанный выше."
        )
    else:
        message += (
            "✅ Вы зарегистрированы в системе.\n\n"
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
/info - Показать информацию о версии и статистику
/reset_stats - Сбросить статистику по словам
/get_words - Экспортировать словарь в CSV
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

5️⃣ /info - Показать информацию о версии бота и статистику

6️⃣ /get_words - Экспортировать все слова из словаря в формате CSV

7️⃣ /reset_stats - Сбросить статистику по словам (только для отслеживаемых пользователей)

8️⃣ /my_id - Показать свой User ID (для добавления в список отслеживаемых)
"""
    
    # Команды управления пользователями только для администраторов
    if is_super:
        help_text += """
--- Команды администратора ---
9️⃣ /add_user - Добавить пользователя в список отслеживаемых
🔟 /remove_user - Удалить пользователя из списка
1️⃣1️⃣ /list_users - Показать список отслеживаемых пользователей
1️⃣2️⃣ /add_admin - Назначить пользователя администратором
1️⃣3️⃣ /remove_admin - Снять права администратора
"""
    help_text += "\n1️⃣4️⃣ /cancel - Отменить текущую операцию"
    
    await update.message.reply_text(help_text)

@require_tracked_user
async def reset_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить статистику по словам для пользователя"""
    from vocabulary import Vocabulary
    
    user_id = update.effective_user.id
    
    vocab = Vocabulary(user_id=user_id)
    deleted_count = vocab.reset_user_statistics(user_id)
    
    await update.message.reply_text(
        f"✅ Статистика по словам сброшена!\n\n"
        f"Обновлено записей: {deleted_count}\n\n"
        f"Теперь все слова будут доступны для тренировки."
    )

@require_admin
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить пользователя в список отслеживаемых (только для администраторов)"""
    from database import add_user as db_add_user, is_tracked_user
    
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

@require_admin
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить пользователя из списка отслеживаемых (только для администраторов)"""
    from database import remove_user as db_remove_user, is_tracked_user
    
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

@require_admin
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список отслеживаемых пользователей (только для администраторов)"""
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

@require_admin
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить пользователя в список администраторов (только для администраторов)"""
    from database import add_admin as db_add_admin
    
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

@require_admin
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Убрать права администратора у пользователя (только для администраторов)"""
    from database import remove_admin as db_remove_admin
    
    current_user_id = update.effective_user.id
    
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

def get_git_info():
    """Получает информацию о последнем коммите из Git"""
    try:
        # Получаем хеш коммита (короткий)
        commit_hash = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        
        # Получаем сообщение коммита
        commit_message = subprocess.check_output(
            ['git', 'log', '-1', '--pretty=format:%s'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        
        # Получаем дату коммита
        commit_date = subprocess.check_output(
            ['git', 'log', '-1', '--pretty=format:%ci'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        
        return commit_hash, commit_message, commit_date
    except Exception as e:
        logger.warning(f"Не удалось получить информацию о Git: {e}")
        return None, None, None

@require_tracked_user
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о версии бота и статистику"""
    from vocabulary import Vocabulary
    
    user_id = update.effective_user.id
    
    # Часть 1: Информация о версии
    commit_hash, commit_message, commit_date = get_git_info()
    start_time_str = BOT_START_TIME.strftime("%Y-%m-%d %H:%M:%S UTC")
    
    message = "📋 Информация о боте:\n\n"
    message += f"🕐 Запущен: {start_time_str}\n"
    
    if commit_hash:
        message += f"\n📝 Последний коммит:\n"
        message += f"   Хеш: <code>{commit_hash}</code>\n"
        if commit_date:
            message += f"   Дата: {commit_date}\n"
        if commit_message:
            message += f"   Сообщение: {commit_message}\n"
    else:
        message += "\n⚠️ Информация о коммите недоступна\n"
        message += "(возможно, бот запущен не из Git репозитория)"
    
    # Часть 2: Статистика
    stats = get_user_stats(user_id)
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
    
    message += f"""
    
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
    
    await update.message.reply_text(message, parse_mode='HTML')

@require_tracked_user
async def get_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт всех слов из словаря пользователя в формате CSV"""
    from vocabulary import Vocabulary
    
    user_id = update.effective_user.id
    vocab = Vocabulary(user_id=user_id)
    
    # Получаем все слова
    words = vocab.get_all_words()
    
    if not words:
        await update.message.reply_text(
            "❌ Ваш словарь пуст! Добавьте слова командой /add_words"
        )
        return
    
    # Формируем CSV формат: слово,перевод
    csv_lines = []
    for greek, russian in words:
        # Экранируем запятые и кавычки в CSV
        greek_escaped = greek.replace('"', '""')
        russian_escaped = russian.replace('"', '""')
        # Если есть запятая или кавычка, оборачиваем в кавычки
        if ',' in greek or '"' in greek or ',' in russian or '"' in russian:
            csv_lines.append(f'"{greek_escaped}","{russian_escaped}"')
        else:
            csv_lines.append(f"{greek},{russian}")
    
    csv_content = "\n".join(csv_lines)
    
    # Telegram имеет ограничение на длину сообщения (4096 символов)
    # Если словарь большой, отправляем файлом
    if len(csv_content) > 4000:
        # Отправляем как документ
        from io import BytesIO
        file_buffer = BytesIO(csv_content.encode('utf-8'))
        file_buffer.name = 'vocabulary.csv'
        
        await update.message.reply_document(
            document=file_buffer,
            filename='vocabulary.csv',
            caption=f"📚 Ваш словарь ({len(words)} слов)"
        )
    else:
        # Отправляем как текст
        message = f"📚 Ваш словарь ({len(words)} слов):\n\n"
        message += "```csv\n"
        message += csv_content
        message += "\n```"
        
        await update.message.reply_text(message, parse_mode='Markdown')


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить текущую операцию"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    state['mode'] = None
    state['data'] = {}
    await update.message.reply_text("✅ Операция отменена")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    from database import is_tracked_user, is_superuser
    
    user_id = update.effective_user.id
    
    # Проверяем доступ (кроме супер-пользователей)
    if not is_superuser(user_id) and not is_tracked_user(user_id):
        message = (
            "⚠️ Вы не зарегистрированы в системе.\n\n"
            "Для использования бота необходимо обратиться к администратору "
            "для добавления вас в список отслеживаемых пользователей.\n\n"
            "Используйте команду /my_id чтобы узнать свой User ID и передать его администратору."
        )
        await update.message.reply_text(message)
        return
    
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
    from database import is_tracked_user, is_superuser
    
    user_id = update.effective_user.id
    
    # Проверяем доступ (кроме супер-пользователей)
    if not is_superuser(user_id) and not is_tracked_user(user_id):
        message = (
            "⚠️ Вы не зарегистрированы в системе.\n\n"
            "Для использования бота необходимо обратиться к администратору "
            "для добавления вас в список отслеживаемых пользователей.\n\n"
            "Используйте команду /my_id чтобы узнать свой User ID и передать его администратору."
        )
        await update.message.reply_text(message)
        return
    
    state = get_user_state(user_id)
    
    current_mode = state.get('mode')
    logger.info(f"🎤 handle_voice: user_id={user_id}, mode={current_mode}, data_keys={list(state.get('data', {}).keys())}")
    
    if current_mode == 'training':
        logger.info(f"✅ Режим тренировки активен для user_id={user_id}")
        await handle_training_voice(update, context)
    elif current_mode == 'read_text':
        logger.info(f"✅ Режим чтения текста активен для user_id={user_id}")
        await handle_reading_voice(update, context)
    elif current_mode == 'ai_training':
        logger.info(f"✅ Режим AI тренировки активен для user_id={user_id}")
        from commands import handle_ai_training_voice
        await handle_ai_training_voice(update, context)
    else:
        logger.warning(f"❌ Неизвестный режим для user_id={user_id}: mode={current_mode}, state={state}")
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
    import os
    
    # Проверяем, не запущен ли бот локально при наличии DATABASE_URL (продакшен)
    DATABASE_URL = os.getenv('DATABASE_URL')
    if DATABASE_URL:
        logger.warning("⚠️ DATABASE_URL установлен - это продакшен окружение!")
        logger.warning("⚠️ Локальный запуск бота отключен для предотвращения конфликтов с Render")
        logger.warning("⚠️ Для локального запуска убедитесь, что DATABASE_URL не установлен")
        return
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    # Инициализируем базу данных
    logger.info("Инициализация базы данных...")
    from database import init_database
    if not init_database():
        logger.error("Не удалось инициализировать базу данных!")
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
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("get_words", get_words))
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
    
    # Добавляем обработчик ошибок
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ошибок"""
        logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
        
        # Обрабатываем конфликт нескольких экземпляров бота
        if isinstance(context.error, Exception) and "Conflict" in str(context.error):
            logger.warning("⚠️ Обнаружен конфликт: запущено несколько экземпляров бота")
            logger.warning("Убедитесь, что локальный бот остановлен, если используете Render")
    
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("Бот запущен...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main()

