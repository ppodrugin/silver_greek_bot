# Настройка Git для коммита под другим именем

## Вариант 1: Локальные настройки для этого репозитория (Рекомендуется)

Если вы хотите использовать другое имя/email только для этого репозитория:

```bash
cd telegram_bot

# Установите локальные настройки (только для этого репозитория)
git config user.name "Ваше имя для GitHub"
git config user.email "ваш-email@example.com"

# Проверьте настройки
git config user.name
git config user.email
```

Эти настройки будут применяться только к этому репозиторию и не затронут другие проекты.

## Вариант 2: Использование HTTPS с другим аккаунтом

Если у вас другой аккаунт на GitHub:

### Шаг 1: Настройте локальные настройки (как в варианте 1)

### Шаг 2: Используйте HTTPS вместо SSH

```bash
# Удалите существующий remote (если есть)
git remote remove origin

# Добавьте remote с HTTPS
git remote add origin https://github.com/ваш-username/название-репозитория.git

# При push GitHub попросит ввести логин/пароль или токен
git push -u origin main
```

### Шаг 3: Используйте Personal Access Token

GitHub больше не принимает пароли через HTTPS. Нужен токен:

1. Перейдите на https://github.com/settings/tokens
2. "Generate new token" → "Generate new token (classic)"
3. Выберите права: `repo` (полный доступ к репозиториям)
4. Скопируйте токен
5. При `git push` используйте токен вместо пароля:
   - Username: ваш GitHub username
   - Password: токен (не пароль!)

## Вариант 3: Использование SSH ключа для другого аккаунта

Если у вас есть SSH ключ для другого аккаунта:

### Шаг 1: Проверьте существующие SSH ключи
```bash
ls -la ~/.ssh/
```

### Шаг 2: Используйте другой SSH ключ для этого репозитория

Создайте файл `~/.ssh/config` (если его нет):

```
# Основной аккаунт (по умолчанию)
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_rsa

# Другой аккаунт
Host github-other
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_rsa_other
```

### Шаг 3: Используйте другой Host для remote

```bash
git remote remove origin
git remote add origin git@github-other:ваш-username/название-репозитория.git
```

## Вариант 4: Временное изменение глобальных настроек

Если нужно временно изменить настройки для всех репозиториев:

```bash
# Сохраните текущие настройки
git config --global user.name > /tmp/git_name_backup.txt
git config --global user.email > /tmp/git_email_backup.txt

# Измените настройки
git config --global user.name "Новое имя"
git config --global user.email "новый-email@example.com"

# Сделайте коммит и push
git add .
git commit -m "Initial commit"
git push

# Восстановите настройки
git config --global user.name "$(cat /tmp/git_name_backup.txt)"
git config --global user.email "$(cat /tmp/git_email_backup.txt)"
```

## Рекомендация

**Используйте Вариант 1** - это самый простой и безопасный способ. Локальные настройки не затронут другие ваши проекты.

## Проверка перед коммитом

Перед коммитом проверьте настройки:

```bash
# Проверьте локальные настройки (для этого репозитория)
git config user.name
git config user.email

# Проверьте глобальные настройки
git config --global user.name
git config --global user.email
```

## Пример полного процесса

```bash
cd telegram_bot

# 1. Настройте локальные настройки
git config user.name "Имя для GitHub"
git config user.email "email@example.com"

# 2. Инициализируйте репозиторий (если еще не сделано)
git init

# 3. Добавьте файлы
git add .

# 4. Сделайте первый коммит
git commit -m "Initial commit: Greek language learning bot"

# 5. Добавьте remote (используйте HTTPS для простоты)
git remote add origin https://github.com/ваш-username/название-репозитория.git

# 6. Push (GitHub попросит логин и токен)
git push -u origin main
```

