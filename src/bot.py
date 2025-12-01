"""
Gheezy Crypto - Telegram Bot

Основной бот для взаимодействия с пользователями.
Поддерживает команды: /start, /help, /price, /signal, /defi, /whale, /portfolio, /alerts

Заработай на крипто без потерь. Учимся, торгуем, растём вместе
"""

from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties
import aiohttp
import structlog

from src.config import settings
from src.signals import SignalAnalyzer
from src.defi import DeFiAggregator
from src.whale import WhaleTracker
from src.copy_trading import CopyTradingSystem

logger = structlog.get_logger()

# Создаём роутер для обработчиков
router = Router()

# Инициализация сервисов
signal_analyzer = SignalAnalyzer()
defi_aggregator = DeFiAggregator()
whale_tracker = WhaleTracker()
copy_trading = CopyTradingSystem()

# Маппинг символов для CoinGecko
SYMBOL_MAPPING = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "SOL": "solana",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "SHIB": "shiba-inu",
    "LTC": "litecoin",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
}


def get_coingecko_id(symbol: str) -> str:
    """Получение ID для CoinGecko API."""
    symbol_upper = symbol.upper()
    return SYMBOL_MAPPING.get(symbol_upper, symbol.lower())


# ==================== ПРИВЕТСТВИЕ ====================


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Обработчик команды /start.
    
    Приветствует пользователя и показывает главное меню.
    """
    welcome_text = f"""
🚀 **Добро пожаловать в Gheezy Crypto!**

_Заработай на крипто без потерь. Учимся, торгуем, растём вместе_

Привет, {message.from_user.first_name}! 👋

Я — твой персональный крипто-помощник с AI-аналитикой.

📊 **Мои возможности:**

🤖 **AI Signals** — торговые сигналы с объяснениями
🏦 **DeFi** — лучшие APY по протоколам
🐋 **Whale Tracker** — отслеживание китов
📈 **Copy-Trading** — копируй лучших трейдеров

⌨️ **Команды:**

/price <symbol> — цена криптовалюты
/signal <symbol> — AI сигнал с анализом
/defi — лучшие DeFi ставки
/whale — движения китов
/portfolio — твой портфель
/alerts — настройка уведомлений
/help — справка

💡 Начни с команды /price btc или /signal eth
"""
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)


# ==================== СПРАВКА ====================


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """
    Обработчик команды /help.
    
    Показывает подробную справку по командам.
    """
    help_text = """
📚 **Справка по командам Gheezy Crypto**

━━━━━━━━━━━━━━━━━━━━━━

💰 **/price <symbol>**
Получить текущую цену криптовалюты
Примеры: `/price BTC`, `/price ETH`, `/price SOL`

🎯 **/signal <symbol>**
Получить AI торговый сигнал с техническим анализом
Включает: RSI, MACD, Bollinger Bands
Примеры: `/signal bitcoin`, `/signal ethereum`

🏦 **/defi**
Показать лучшие DeFi ставки (APY)
Протоколы: Aave, Lido, Compound, Curve и другие

🐋 **/whale**
Отслеживание крупных транзакций китов
Депозиты и выводы с бирж

📊 **/portfolio**
Управление вашим виртуальным портфелем
(в разработке)

🔔 **/alerts**
Настройка уведомлений о ценах
(в разработке)

📈 **/traders**
Топ трейдеров для копирования

━━━━━━━━━━━━━━━━━━━━━━

⚠️ *Отказ от ответственности:*
_Это не финансовый совет. Все решения об инвестициях вы принимаете самостоятельно._
"""
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)


# ==================== ЦЕНА ====================


@router.message(Command("price"))
async def cmd_price(message: Message) -> None:
    """
    Обработчик команды /price.
    
    Показывает текущую цену криптовалюты.
    """
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            "❌ Укажите символ криптовалюты\n"
            "Пример: `/price BTC` или `/price ethereum`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    symbol = args[1].upper()
    coin_id = get_coingecko_id(symbol)

    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": coin_id,
                "vs_currencies": "usd,rub",
                "include_24hr_change": "true",
                "include_market_cap": "true",
            }

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    await message.answer(f"❌ Не удалось получить данные для {symbol}")
                    return

                data = await response.json()

                if coin_id not in data:
                    await message.answer(
                        f"❌ Криптовалюта {symbol} не найдена\n"
                        "Попробуйте полное название (bitcoin, ethereum и т.д.)"
                    )
                    return

                coin_data = data[coin_id]
                price_usd = coin_data.get("usd", 0)
                price_rub = coin_data.get("rub", 0)
                change_24h = coin_data.get("usd_24h_change", 0)
                market_cap = coin_data.get("usd_market_cap", 0)

                # Определяем эмодзи изменения
                if change_24h > 0:
                    change_emoji = "📈"
                    change_text = f"+{change_24h:.2f}%"
                else:
                    change_emoji = "📉"
                    change_text = f"{change_24h:.2f}%"

                # Форматируем market cap
                if market_cap >= 1_000_000_000:
                    cap_text = f"${market_cap / 1_000_000_000:.2f}B"
                elif market_cap >= 1_000_000:
                    cap_text = f"${market_cap / 1_000_000:.2f}M"
                else:
                    cap_text = f"${market_cap:,.0f}"

                response_text = f"""
💰 **{symbol.upper()}**

💵 Цена USD: **${price_usd:,.2f}**
🇷🇺 Цена RUB: **₽{price_rub:,.2f}**

{change_emoji} Изменение 24ч: **{change_text}**
📊 Market Cap: **{cap_text}**

⏰ _Данные в реальном времени_
"""
                await message.answer(response_text, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error("Ошибка получения цены", error=str(e), symbol=symbol)
        await message.answer(f"❌ Ошибка при получении данных: {str(e)}")


# ==================== СИГНАЛЫ ====================


@router.message(Command("signal"))
async def cmd_signal(message: Message) -> None:
    """
    Обработчик команды /signal.
    
    Генерирует AI торговый сигнал с техническим анализом.
    """
    args = message.text.split()

    if len(args) < 2:
        await message.answer(
            "❌ Укажите символ криптовалюты\n"
            "Пример: `/signal bitcoin` или `/signal ethereum`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    symbol = args[1].lower()
    coin_id = get_coingecko_id(symbol)

    # Отправляем уведомление о загрузке
    loading_msg = await message.answer("⏳ Анализирую данные...")

    try:
        signal_message = await signal_analyzer.get_signal_message(coin_id)
        await loading_msg.edit_text(signal_message, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error("Ошибка генерации сигнала", error=str(e), symbol=symbol)
        await loading_msg.edit_text(f"❌ Ошибка анализа: {str(e)}")


# ==================== DEFI ====================


@router.message(Command("defi"))
async def cmd_defi(message: Message) -> None:
    """
    Обработчик команды /defi.
    
    Показывает лучшие DeFi ставки.
    """
    loading_msg = await message.answer("⏳ Загружаю DeFi данные...")

    try:
        defi_message = await defi_aggregator.format_defi_message()
        await loading_msg.edit_text(defi_message, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error("Ошибка получения DeFi данных", error=str(e))
        await loading_msg.edit_text(f"❌ Ошибка загрузки DeFi данных: {str(e)}")


# ==================== WHALE TRACKER ====================


@router.message(Command("whale"))
async def cmd_whale(message: Message) -> None:
    """
    Обработчик команды /whale.
    
    Показывает движения китов.
    """
    loading_msg = await message.answer("⏳ Отслеживаю китов...")

    try:
        whale_message = await whale_tracker.format_whale_message()
        await loading_msg.edit_text(whale_message, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error("Ошибка отслеживания китов", error=str(e))
        await loading_msg.edit_text(f"❌ Ошибка: {str(e)}")


# ==================== COPY-TRADING ====================


@router.message(Command("traders"))
async def cmd_traders(message: Message) -> None:
    """
    Обработчик команды /traders.
    
    Показывает топ трейдеров для копирования.
    """
    try:
        traders_message = await copy_trading.format_traders_message()
        await message.answer(traders_message, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error("Ошибка получения трейдеров", error=str(e))
        await message.answer(f"❌ Ошибка: {str(e)}")


# ==================== ПОРТФЕЛЬ ====================


@router.message(Command("portfolio"))
async def cmd_portfolio(message: Message) -> None:
    """
    Обработчик команды /portfolio.
    
    Показывает портфель пользователя (заглушка).
    """
    portfolio_text = """
📊 **Ваш портфель**

🚧 _Функция в разработке_

Скоро вы сможете:
• 📝 Добавлять криптовалюты в портфель
• 📈 Отслеживать прибыль/убытки
• 📊 Видеть распределение активов
• 🔔 Получать уведомления о изменениях

Следите за обновлениями! 🚀
"""
    await message.answer(portfolio_text, parse_mode=ParseMode.MARKDOWN)


# ==================== УВЕДОМЛЕНИЯ ====================


@router.message(Command("alerts"))
async def cmd_alerts(message: Message) -> None:
    """
    Обработчик команды /alerts.
    
    Настройка уведомлений (заглушка).
    """
    alerts_text = """
🔔 **Уведомления**

🚧 _Функция в разработке_

Скоро вы сможете настроить:
• 💰 Уведомления о достижении цены
• 🎯 Оповещения о новых сигналах
• 🐋 Алерты о движениях китов
• 📊 Ежедневные отчёты

Следите за обновлениями! 🚀
"""
    await message.answer(alerts_text, parse_mode=ParseMode.MARKDOWN)


# ==================== СОЗДАНИЕ БОТА ====================


def create_bot() -> tuple[Bot, Dispatcher]:
    """
    Создание и настройка бота.
    
    Returns:
        tuple: (Bot, Dispatcher)
    """
    # Создаём бота с настройками по умолчанию
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.MARKDOWN,
        ),
    )

    # Создаём диспетчер
    dp = Dispatcher()
    
    # Регистрируем роутер
    dp.include_router(router)

    logger.info("Бот создан и настроен")

    return bot, dp


async def on_startup(bot: Bot) -> None:
    """Действия при запуске бота."""
    logger.info("Бот запущен")
    
    # Можно отправить уведомление админам
    for admin_id in settings.telegram_admin_ids:
        try:
            await bot.send_message(
                admin_id,
                "🚀 Gheezy Crypto Bot запущен!",
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа {admin_id}: {e}")


async def on_shutdown(bot: Bot) -> None:
    """Действия при остановке бота."""
    logger.info("Бот остановлен")
    
    # Закрываем сессии
    await signal_analyzer.close()
    await defi_aggregator.close()
    await whale_tracker.close()
