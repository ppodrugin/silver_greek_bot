# Telegram бот для тренировки греческого языка

Бот для изучения греческого языка с поддержкой распознавания речи и генерации предложений через ИИ.

## Быстрый старт

1. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Настройте переменные окружения:**
   ```bash
   cp .env.example .env
   # Отредактируйте .env и добавьте TELEGRAM_BOT_TOKEN
   ```

3. **Запустите бота:**
   ```bash
   python3 bot.py
   ```

## Документация

Вся документация находится в папке [`doc/`](doc/):

- [`README.md`](doc/README.md) - Полная документация
- [`QUICKSTART.md`](doc/QUICKSTART.md) - Быстрый старт
- [`DEPLOYMENT.md`](doc/DEPLOYMENT.md) - Инструкции по деплою на Render
- [`USER_STATISTICS.md`](doc/USER_STATISTICS.md) - Система статистики пользователей
- [`OPENAI_SETUP.md`](doc/OPENAI_SETUP.md) - Настройка OpenAI API
- [`GIT_SETUP.md`](doc/GIT_SETUP.md) - Настройка Git для коммита под другим именем

## Основные команды бота

- `/start` - Начать работу с ботом
- `/help` - Показать справку
- `/add_words` - Добавить слова в словарь
- `/training` - Начать тренировку слов
- `/read_text` - Режим чтения текста
- `/ai_generate` - Генерация предложений через ИИ
- `/stats` - Показать статистику
- `/version` - Информация о версии бота

## Структура проекта

```
telegram_bot/
├── bot.py              # Основной файл бота
├── commands.py         # Обработчики команд
├── vocabulary.py       # Работа со словарем
├── utils.py            # Утилиты (распознавание речи, сравнение)
├── ai_generator.py     # Генерация через OpenAI
├── config.py           # Конфигурация
├── database.py         # Работа с БД (SQLite/PostgreSQL)
├── user_state.py       # Управление состоянием пользователей
├── requirements.txt    # Зависимости
├── Procfile           # Для деплоя на Render
├── runtime.txt        # Версия Python
├── deploy.sh          # Скрипт для деплоя
└── doc/               # Документация
    ├── README.md
    ├── QUICKSTART.md
    ├── DEPLOYMENT.md
    └── ...
```

## Развертывание

Для развертывания на бесплатном хостинге см. [`doc/DEPLOYMENT.md`](doc/DEPLOYMENT.md).

## Примечания

- Бот использует Google Speech Recognition API для распознавания речи
- Для команды `/ai_generate` требуется OpenAI API ключ
- Словарь хранится в базе данных (SQLite локально, PostgreSQL на Render)
- Команда `/add_words` поддерживает добавление нескольких слов за раз в обоих форматах
