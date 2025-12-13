"""
Управление состоянием пользователей
"""
from vocabulary import Vocabulary
from database import is_tracked_user as db_is_tracked_user

# Глобальный словарь для хранения состояния пользователей
user_states = {}
user_stats = {}

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

def get_user_stats(user_id):
    """Получает статистику пользователя"""
    if user_id not in user_stats:
        user_stats[user_id] = {
            'total_attempts': 0,
            'correct_attempts': 0,
            'training_words': {'total': 0, 'correct': 0},
            'text_reading': {'total': 0, 'correct': 0}
        }
    return user_stats[user_id]

async def send_next_training_word(update, context):
    """Отправляет следующее слово для тренировки"""
    user_id = update.effective_user.id
    vocab = Vocabulary(user_id=user_id)
    
    # Если пользователь в списке отслеживаемых, используем умный выбор слов
    if is_tracked_user(user_id):
        word = vocab.get_random_word(stats_user_id=user_id)
    else:
        word = vocab.get_random_word()
    
    if not word:
        await update.message.reply_text(
            "❌ Словарь пуст! Добавьте слова командой /add_words"
        )
        state = get_user_state(user_id)
        state['mode'] = None
        return
    
    greek, russian = word
    
    state = get_user_state(user_id)
    state['data']['current_greek'] = greek
    state['data']['current_russian'] = russian
    
    await update.message.reply_text(
        f"📝 Переведите на греческий:\n\n"
        f"<b>{russian}</b>",
        parse_mode='HTML'
    )

