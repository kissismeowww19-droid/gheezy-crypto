"""
Gheezy Crypto - Точка входа

Запуск Telegram бота и FastAPI сервера.

Заработай на крипто без потерь. Учимся, торгуем, растём вместе
"""

import asyncio
import sys
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.bot import create_bot, on_shutdown, on_startup
from src.config import settings
from src.database.db import close_db, init_db

# Настройка логирования
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
        if settings.debug
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup
    logger.info("Запуск приложения", app_name=settings.app_name)

    try:
        await init_db()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.warning(f"Не удалось подключиться к БД: {e}")

    yield

    # Shutdown
    logger.info("Остановка приложения")
    await close_db()


# Создаём FastAPI приложение
app = FastAPI(
    title=settings.app_name,
    description="Платформа для крипто-трейдинга с AI сигналами",
    version="1.0.0",
    lifespan=lifespan,
)

# Настройка CORS
# В production рекомендуется ограничить allow_origins конкретными доменами
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Корневой эндпоинт."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "slogan": "Заработай на крипто без потерь. Учимся, торгуем, растём вместе",
    }


@app.get("/health")
async def health():
    """Проверка здоровья сервиса."""
    return {"status": "healthy"}


@app.get("/api/v1/price/{symbol}")
async def get_price(symbol: str):
    """
    Получение цены криптовалюты.

    Args:
        symbol: Символ криптовалюты (bitcoin, ethereum и т.д.)
    """
    from src.signals import SignalAnalyzer

    analyzer = SignalAnalyzer()
    try:
        price = await analyzer.get_current_price(symbol)
        if price:
            return {"symbol": symbol, "price_usd": price}
        return {"error": "Криптовалюта не найдена"}
    finally:
        await analyzer.close()


@app.get("/api/v1/signal/{symbol}")
async def get_signal(symbol: str):
    """
    Получение торгового сигнала.

    Args:
        symbol: Символ криптовалюты
    """
    from src.signals import SignalAnalyzer

    analyzer = SignalAnalyzer()
    try:
        signal = await analyzer.analyze(symbol)
        if signal:
            return {
                "symbol": signal.symbol,
                "signal_type": signal.signal_type,
                "confidence": signal.confidence,
                "current_price": signal.current_price,
                "target_price": signal.target_price,
                "stop_loss": signal.stop_loss,
                "explanation": signal.explanation,
            }
        return {"error": "Не удалось получить сигнал"}
    finally:
        await analyzer.close()


async def run_bot():
    """Запуск Telegram бота."""
    bot, dp = create_bot()

    # Регистрируем хуки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Запуск Telegram бота")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def run_api():
    """Запуск FastAPI сервера."""
    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """
    Главная функция запуска.

    Запускает одновременно Telegram бота и FastAPI сервер.
    """
    logger.info(
        "Gheezy Crypto запускается",
        app_name=settings.app_name,
        env=settings.app_env,
        debug=settings.debug,
    )

    # Проверяем наличие токена бота
    if (
        not settings.telegram_bot_token
        or settings.telegram_bot_token == "your_bot_token_here"
    ):
        logger.error("TELEGRAM_BOT_TOKEN не настроен!")
        logger.info("Запускаем только API сервер...")
        await run_api()
        return

    # Запускаем бота и API параллельно
    try:
        await asyncio.gather(
            run_bot(),
            run_api(),
        )
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error("Ошибка при запуске", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение остановлено")
