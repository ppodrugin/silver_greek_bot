"""
Управление состоянием пользователей
"""
import logging
from vocabulary import Vocabulary
from database import is_tracked_user as db_is_tracked_user, get_connection, return_connection, get_param, USE_POSTGRES

logger = logging.getLogger(__name__)

# Глобальный словарь для хранения состояния пользователей
user_states = {}
# Статистика чтения текста хранится в памяти
text_reading_stats = {}

def is_tracked_user(user_id):
    """
    Проверяет, ведется ли статистика для данного пользователя
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        bool: True если пользователь в списке отслеживаемых
    """
    return db_is_tracked_user(user_id)

def get_user_state(user_id):
    """Получает состояние пользователя"""
    if user_id not in user_states:
        user_states[user_id] = {'mode': None, 'data': {}}
    return user_states[user_id]

def get_user_stats(user_id, lesson_id=None):
    """
    Получает статистику пользователя.
    Статистика тренировки слов берется из базы данных.
    Статистика чтения текста хранится в памяти.
    
    Args:
        user_id: ID пользователя
        lesson_id: ID урока (опционально). Если указан, статистика фильтруется по уроку
    """
    # Инициализируем статистику чтения текста в памяти
    if user_id not in text_reading_stats:
        text_reading_stats[user_id] = {'total': 0, 'correct': 0}
    
    # Получаем статистику тренировки слов из базы данных
    training_total = 0
    training_correct = 0
    
    try:
        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            param = get_param()
            
            # Формируем условия WHERE
            where_conditions = [f"user_id = {param}"]
            query_params = [user_id]
            
            # Добавляем фильтр по уроку, если указан
            if lesson_id is not None:
                where_conditions.append(f"lesson_id = {param}")
                query_params.append(lesson_id)
            
            where_clause = " AND ".join(where_conditions)
            
            # Суммируем successful и unsuccessful для слов пользователя (с учетом урока, если указан)
            query = f"""
            SELECT 
                COALESCE(SUM(successful), 0) as total_successful,
                COALESCE(SUM(unsuccessful), 0) as total_unsuccessful
            FROM vocabulary
            WHERE {where_clause}
            """
            cursor.execute(query, tuple(query_params))
            result = cursor.fetchone()
            
            if result:
                if USE_POSTGRES:
                    training_correct = result[0] if result[0] else 0
                    training_unsuccessful = result[1] if result[1] else 0
                else:
                    training_correct = result['total_successful'] if result['total_successful'] else 0
                    training_unsuccessful = result['total_unsuccessful'] if result['total_unsuccessful'] else 0
                
                training_total = training_correct + training_unsuccessful
            
            return_connection(conn)
    except Exception as e:
        logger.error(f"Ошибка при получении статистики тренировки слов из БД: {e}", exc_info=True)
    
    # Статистика чтения текста из памяти (не фильтруется по уроку)
    reading_stats = text_reading_stats[user_id]
    
    # Общая статистика (тренировка + чтение)
    total_attempts = training_total + reading_stats['total']
    correct_attempts = training_correct + reading_stats['correct']
    
    return {
        'total_attempts': total_attempts,
        'correct_attempts': correct_attempts,
        'training_words': {
            'total': training_total,
            'correct': training_correct
        },
        'text_reading': reading_stats
    }

async def send_next_training_word(update, context):
    """Отправляет следующее слово для тренировки"""
    import logging
    logger = logging.getLogger(__name__)
    
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    logger.debug(f"send_next_training_word: user_id={user_id}, mode={state.get('mode')}")
    
    # Убеждаемся, что режим установлен
    if state.get('mode') != 'training':
        logger.warning(f"Режим не установлен! Устанавливаем mode='training' для user_id={user_id}")
        state['mode'] = 'training'
    
    vocab = Vocabulary(user_id=user_id)
    
    # Проверяем количество слов перед выбором
    word_count = vocab.count()
    logger.info(f"Попытка получить слово для user_id={user_id}, слов в словаре: {word_count}")
    
    if word_count == 0:
        await update.message.reply_text(
            "❌ Словарь пуст! Добавьте слова командой /add_words"
        )
        state = get_user_state(user_id)
        state['mode'] = None
        return
    
    # Получаем lesson_id из state, если он есть
    lesson_id = state.get('data', {}).get('lesson_id')
    
    # Если пользователь в списке отслеживаемых, используем умный выбор слов
    is_tracked = is_tracked_user(user_id)
    logger.debug(f"Пользователь отслеживается: {is_tracked}, lesson_id={lesson_id}")
    
    if is_tracked:
        word = vocab.get_random_word(stats_user_id=user_id, lesson_id=lesson_id)
    else:
        word = vocab.get_random_word(lesson_id=lesson_id)
    
    if not word:
        logger.warning(f"Не удалось получить слово для user_id={user_id}, хотя count={word_count}")
        await update.message.reply_text(
            f"❌ Не удалось выбрать слово из словаря.\n\n"
            f"В словаре {word_count} слов, но произошла ошибка при выборе.\n"
            f"Попробуйте еще раз или добавьте слова командой /add_words"
        )
        state = get_user_state(user_id)
        state['mode'] = None
        return
    
    greek, russian = word
    
    state = get_user_state(user_id)
    # Убеждаемся, что режим установлен
    if state.get('mode') != 'training':
        logger.warning(f"⚠️ Режим не установлен в send_next_training_word! Устанавливаем mode='training' для user_id={user_id}")
        state['mode'] = 'training'
    
    # Убеждаемся, что data существует
    if 'data' not in state:
        state['data'] = {}
    
    state['data']['current_greek'] = greek
    state['data']['current_russian'] = russian
    
    logger.info(f"📝 Отправлено слово для тренировки: user_id={user_id}, greek={greek}, russian={russian}, mode={state.get('mode')}, data_keys={list(state.get('data', {}).keys())}")
    
    await update.message.reply_text(
        f"📝 Переведите на греческий:\n\n"
        f"<b>{russian}</b>",
        parse_mode='HTML'
    )

