# Команды для деплоя бота на Render

## Быстрый деплой (автоматический скрипт)

```bash
cd telegram_bot
./deploy.sh
```

Или с кастомным сообщением коммита:
```bash
./deploy.sh "Ваше сообщение коммита"
```

## Ручной деплой (пошагово)

### 1. Проверка статуса
```bash
cd telegram_bot
git status
```

### 2. Добавление изменений
```bash
# Добавить все изменения
git add .

# Или добавить конкретные файлы
git add bot.py vocabulary.py user_state.py database.py
```

### 3. Создание коммита
```bash
git commit -m "Добавлена команда /get_words для экспорта словаря в CSV"
```

### 4. Отправка в GitHub
```bash
git push origin main
```

### 5. Проверка деплоя на Render
После `git push` Render автоматически начнет деплой. Проверьте статус на:
- https://dashboard.render.com
- В разделе вашего Background Worker сервиса

## Проверка логов после деплоя

Если используете Render CLI:
```bash
render logs --service <service-name>
```

Или через веб-интерфейс Render Dashboard → ваш сервис → Logs

## Важные замечания

1. **База данных**: Файл `vocabulary.db` не коммитится (в `.gitignore`). 
   На Render база данных создается автоматически при первом запуске.

2. **Переменные окружения**: Убедитесь, что на Render настроены:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY` (если используется)

3. **Проверка после деплоя**: После деплоя проверьте бота командой `/start` или `/help`

## Откат изменений (если что-то пошло не так)

```bash
# Посмотреть последние коммиты
git log --oneline -5

# Откатить последний коммит (локально)
git reset --soft HEAD~1

# Или откатить конкретный коммит
git revert <commit-hash>
git push origin main
```

