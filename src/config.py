"""
Gheezy Crypto - Конфигурация приложения

Загрузка настроек из переменных окружения с валидацией через Pydantic.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Основные настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot
    telegram_bot_token: str = Field(
        ...,
        description="Токен Telegram бота от @BotFather",
    )
    telegram_admin_ids: List[int] = Field(
        default_factory=list,
        description="Список ID администраторов бота",
    )

    # База данных
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/gheezy_crypto",
        description="URL подключения к PostgreSQL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="URL подключения к Redis",
    )

    # API ключи криптовалют
    coingecko_api_key: str = Field(
        default="",
        description="API ключ CoinGecko",
    )
    cryptocompare_api_key: str = Field(
        default="",
        description="API ключ CryptoCompare",
    )
    binance_api_key: str = Field(
        default="",
        description="API ключ Binance",
    )
    binance_secret_key: str = Field(
        default="",
        description="Секретный ключ Binance",
    )

    # DeFi APIs
    defillama_api_url: str = Field(
        default="https://api.llama.fi",
        description="URL API DefiLlama",
    )
    etherscan_api_key: str = Field(
        default="",
        description="API ключ Etherscan",
    )

    # Настройки приложения
    app_name: str = Field(
        default="Gheezy Crypto",
        description="Название приложения",
    )
    app_env: str = Field(
        default="development",
        description="Окружение (development/production)",
    )
    debug: bool = Field(
        default=False,
        description="Режим отладки",
    )
    log_level: str = Field(
        default="INFO",
        description="Уровень логирования",
    )

    # API сервер
    api_port: int = Field(
        default=8000,
        description="Порт API сервера",
    )
    api_host: str = Field(
        default="0.0.0.0",
        description="Хост API сервера",
    )

    # Whale Tracker
    whale_min_transaction: int = Field(
        default=100000,
        description="Минимальная сумма транзакции для отслеживания (USD)",
    )

    # Сигналы
    signal_update_interval: int = Field(
        default=300,
        description="Интервал обновления сигналов (секунды)",
    )

    @field_validator("telegram_admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        """Парсинг списка ID администраторов из строки."""
        if isinstance(v, str):
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v

    @property
    def is_production(self) -> bool:
        """Проверка на production окружение."""
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Получение настроек приложения.
    
    Кэшируется для повторного использования.
    """
    return Settings()


# Экспортируем настройки для удобства импорта
settings = get_settings()
