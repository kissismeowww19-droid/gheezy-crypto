"""
Gheezy Crypto - Точка входа

Запуск Telegram бота. 

Заработай на крипто без потерь. Учимся, торгуем, растём вместе
"""

import asyncio
import logging

from bot import create_bot, on_shutdown, on_startup
from config import settings

logging.basicConfig(
    level=logging. INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_bot():
    """Запуск Telegram бота."""
    bot, dp = create_bot()

    dp.startup.register(on_startup)
    dp.shutdown. register(on_shutdown)

    logger. info("Запуск Telegram бота...")
  

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session. close()


async def main():
    """Главная функция запуска."""
    logger.info("=" * 50)
    logger.info("GHEEZY CRYPTO BOT")
    logger.info("=" * 50)

    if not settings.telegram_bot_token or settings.telegram_bot_token == "your_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN не настроен!")
        logger.error("Добавь токен в файл . env")
        return

    try:
        await run_bot()
    except KeyboardInterrupt:
        logger. info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение остановлено")