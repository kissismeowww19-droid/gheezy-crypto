# Развёртывание Gheezy Crypto

## 📋 Требования

- Docker 24.0+
- Docker Compose 2.0+
- 2GB RAM минимум
- 10GB свободного места

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/your-username/gheezy-crypto.git
cd gheezy-crypto
```

### 2. Настройка переменных окружения

```bash
# Копируем пример конфигурации
cp .env.example .env

# Редактируем .env файл
nano .env
```

Обязательные переменные:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_botfather
POSTGRES_PASSWORD=надёжный_пароль
```

### 3. Запуск через Docker Compose

```bash
# Сборка и запуск всех сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f app
```

### 4. Проверка работоспособности

```bash
# API health check
curl http://localhost:8000/health

# Проверка бота
# Отправьте /start в Telegram боту
```

## 🔧 Конфигурация

### Переменные окружения

| Переменная | Описание | Обязательно |
|------------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | ✅ |
| `DATABASE_URL` | URL подключения к PostgreSQL | ⚪ |
| `REDIS_URL` | URL подключения к Redis | ⚪ |
| `COINGECKO_API_KEY` | API ключ CoinGecko | ⚪ |
| `ETHERSCAN_API_KEY` | API ключ Etherscan | ⚪ |

### Получение токена Telegram бота

1. Откройте @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте полученный токен в `.env`

### Получение API ключей

#### CoinGecko (бесплатный)
1. Зарегистрируйтесь на https://www.coingecko.com/
2. Перейдите в раздел API
3. Создайте ключ (бесплатный план)

#### Etherscan
1. Зарегистрируйтесь на https://etherscan.io/
2. Создайте API ключ в настройках

## 🐳 Docker команды

```bash
# Пересборка образа
docker-compose build --no-cache

# Остановка сервисов
docker-compose down

# Удаление с данными
docker-compose down -v

# Просмотр логов конкретного сервиса
docker-compose logs -f app
docker-compose logs -f db
docker-compose logs -f redis

# Вход в контейнер
docker-compose exec app bash
docker-compose exec db psql -U postgres -d gheezy_crypto

# Масштабирование (только для stateless сервисов)
docker-compose up -d --scale app=3
```

## 🗄️ База данных

### Миграции

```bash
# Создание миграции
docker-compose exec app alembic revision --autogenerate -m "описание"

# Применение миграций
docker-compose exec app alembic upgrade head

# Откат миграции
docker-compose exec app alembic downgrade -1
```

### Бэкап и восстановление

```bash
# Создание бэкапа
docker-compose exec db pg_dump -U postgres gheezy_crypto > backup.sql

# Восстановление из бэкапа
docker-compose exec -T db psql -U postgres gheezy_crypto < backup.sql
```

## 📊 Мониторинг

### Логи

Логи хранятся в директории `./logs/`

```bash
# Просмотр логов приложения
tail -f logs/app.log

# Поиск ошибок
grep -i error logs/app.log
```

### Health Checks

```bash
# API
curl http://localhost:8000/health

# База данных
docker-compose exec db pg_isready -U postgres

# Redis
docker-compose exec redis redis-cli ping
```

## 🔒 Безопасность в Production

### 1. Смените пароли по умолчанию

```env
POSTGRES_PASSWORD=очень_сложный_пароль_123!
```

### 2. Настройте firewall

```bash
# Разрешите только необходимые порты
ufw allow 22    # SSH
ufw allow 443   # HTTPS (если используется)
ufw allow 8000  # API (если нужен внешний доступ)
ufw enable
```

### 3. Используйте HTTPS

Рекомендуется использовать nginx или Traefik как reverse proxy с SSL сертификатами от Let's Encrypt.

### 4. Регулярные обновления

```bash
# Обновление образов
docker-compose pull
docker-compose up -d
```

## 🐛 Решение проблем

### Бот не отвечает

1. Проверьте токен: `echo $TELEGRAM_BOT_TOKEN`
2. Проверьте логи: `docker-compose logs app`
3. Убедитесь, что бот запущен: `docker-compose ps`

### Ошибка подключения к БД

1. Проверьте, что PostgreSQL запущен: `docker-compose ps db`
2. Проверьте логи БД: `docker-compose logs db`
3. Проверьте подключение: `docker-compose exec db pg_isready`

### Нет данных о ценах

1. Проверьте интернет в контейнере: `docker-compose exec app curl -I https://api.coingecko.com`
2. Проверьте лимиты API (бесплатный план CoinGecko: 10-30 запросов/минуту)

## 📚 Дополнительные ресурсы

- [Документация aiogram](https://docs.aiogram.dev/)
- [FastAPI документация](https://fastapi.tiangolo.com/)
- [CoinGecko API](https://www.coingecko.com/api/documentation)
- [DefiLlama API](https://defillama.com/docs/api)
