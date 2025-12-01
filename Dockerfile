# Gheezy Crypto - Docker образ
# Мультистадийная сборка для оптимизации размера

# Базовый образ
FROM python:3.11-slim as base

# Установка переменных окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Стадия зависимостей
FROM base as dependencies

# Копируем файл зависимостей
COPY requirements.txt .

# Установка Python зависимостей (без ta-lib, так как требует системную библиотеку)
RUN pip install --no-cache-dir -r requirements.txt || \
    pip install --no-cache-dir $(grep -v ta-lib requirements.txt)

# Финальный образ
FROM base as production

# Копируем установленные пакеты
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash appuser

# Копируем исходный код
COPY --chown=appuser:appuser . .

# Переключаемся на пользователя
USER appuser

# Порт для API
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Запуск приложения
CMD ["python", "-m", "src.main"]
