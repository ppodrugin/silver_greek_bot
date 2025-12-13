# Быстрый старт

## 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

Для macOS может потребоваться:
```bash
brew install portaudio
```

## 2. Настройка токенов

Создайте файл `.env`:
```bash
cp .env.example .env
```

Отредактируйте `.env` и добавьте токены:
- `TELEGRAM_BOT_TOKEN` - получите у @BotFather в Telegram
- `OPENAI_API_KEY` - получите на https://platform.openai.com (опционально, для команды /ai_generate)

## 3. Запуск

```bash
python3 bot.py
```

## Тестирование

1. Найдите вашего бота в Telegram
2. Отправьте `/start`
3. Попробуйте команды:
   - `/add_words` - добавьте несколько слов
   - `/training` - начните тренировку
   - `/read_text` - попробуйте чтение текста
   - `/ai_generate` - генерация через ИИ (требует API ключ)

## Примечания

- Бот использует Google Speech Recognition API (бесплатно)
- Для команды `/ai_generate` нужен OpenAI API ключ (платный, но есть бесплатный кредит)
- Словарь сохраняется в `vocabulary.txt`
