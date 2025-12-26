"""
Gheezy Crypto Telegram Bot - Minimalist Design
С подключением Multi-API Manager (CoinGecko + CoinPaprika + MEXC + Kraken)
"""

import logging
from typing import Tuple
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

from config import settings
from api_manager import get_coin_price as get_price_multi_api, get_api_stats
from whale.tracker import WhaleTracker as RealWhaleTracker
from signals.ai_signals import AISignalAnalyzer
from signals.signal_tracker import SignalTracker
from signals.super_signals import SuperSignals
from signals.gem_scanner import GemScanner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()
user_messages = {}

# Хранение подписок пользователей на whale alerts
whale_subscriptions: set[int] = set()


class SignalAnalyzer:
    async def close(self):
        pass


class DeFiAggregator:
    async def close(self):
        pass


signal_analyzer = SignalAnalyzer()
defi_aggregator = DeFiAggregator()
whale_tracker = RealWhaleTracker()
ai_signal_analyzer = AISignalAnalyzer(whale_tracker)
signal_tracker = SignalTracker()


COINS = {
    # Основные монеты (17)
    "btc": {"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "emoji": "₿"},
    "eth": {"id": "ethereum", "symbol": "ETH", "name": "Ethereum", "emoji": "⟠"},
    "ton": {
        "id": "the-open-network",
        "symbol": "TON",
        "name": "Toncoin",
        "emoji": "💎",
    },
    "sol": {"id": "solana", "symbol": "SOL", "name": "Solana", "emoji": "🟣"},
    "xrp": {"id": "ripple", "symbol": "XRP", "name": "XRP", "emoji": "💧"},
    "doge": {"id": "dogecoin", "symbol": "DOGE", "name": "Dogecoin", "emoji": "🐕"},
    "matic": {
        "id": "matic-network",
        "symbol": "MATIC",
        "name": "Polygon",
        "emoji": "🟪",
    },
    "ltc": {"id": "litecoin", "symbol": "LTC", "name": "Litecoin", "emoji": "🪙"},
    "shib": {"id": "shiba-inu", "symbol": "SHIB", "name": "Shiba Inu", "emoji": "🐕"},
    "avax": {"id": "avalanche-2", "symbol": "AVAX", "name": "Avalanche", "emoji": "🔺"},
    "bnb": {"id": "binancecoin", "symbol": "BNB", "name": "BNB", "emoji": "🔶"},
    "ada": {"id": "cardano", "symbol": "ADA", "name": "Cardano", "emoji": "🔵"},
    "dot": {"id": "polkadot", "symbol": "DOT", "name": "Polkadot", "emoji": "⚪"},
    "link": {"id": "chainlink", "symbol": "LINK", "name": "Chainlink", "emoji": "🔗"},
    "uni": {"id": "uniswap", "symbol": "UNI", "name": "Uniswap", "emoji": "🦄"},
    "atom": {"id": "cosmos", "symbol": "ATOM", "name": "Cosmos", "emoji": "⚛️"},
    "trx": {"id": "tron", "symbol": "TRX", "name": "Tron", "emoji": "🔴"},
    # Мем-коины (4)
    "not": {"id": "notcoin", "symbol": "NOT", "name": "Notcoin", "emoji": "⬛"},
    "pepe": {"id": "pepe", "symbol": "PEPE", "name": "Pepe", "emoji": "🐸"},
    "wif": {"id": "dogwifcoin", "symbol": "WIF", "name": "dogwifhat", "emoji": "🐕"},
    "bonk": {"id": "bonk", "symbol": "BONK", "name": "Bonk", "emoji": "🦴"},
    # Новые L1 блокчейны (5)
    "sui": {"id": "sui", "symbol": "SUI", "name": "Sui", "emoji": "🌊"},
    "apt": {"id": "aptos", "symbol": "APT", "name": "Aptos", "emoji": "🔷"},
    "sei": {"id": "sei-network", "symbol": "SEI", "name": "Sei", "emoji": "🌀"},
    "near": {"id": "near", "symbol": "NEAR", "name": "NEAR Protocol", "emoji": "🌐"},
    "ftm": {"id": "fantom", "symbol": "FTM", "name": "Fantom", "emoji": "👻"},
    # L2 Ethereum (2)
    "arb": {"id": "arbitrum", "symbol": "ARB", "name": "Arbitrum", "emoji": "🔵"},
    "op": {"id": "optimism", "symbol": "OP", "name": "Optimism", "emoji": "🔴"},
    # DeFi и другие (6)
    "inj": {
        "id": "injective-protocol",
        "symbol": "INJ",
        "name": "Injective",
        "emoji": "💉",
    },
    "xlm": {"id": "stellar", "symbol": "XLM", "name": "Stellar", "emoji": "⭐"},
    "vet": {"id": "vechain", "symbol": "VET", "name": "VeChain", "emoji": "✔️"},
    "algo": {"id": "algorand", "symbol": "ALGO", "name": "Algorand", "emoji": "⬡"},
    "fil": {"id": "filecoin", "symbol": "FIL", "name": "Filecoin", "emoji": "📁"},
    "rune": {"id": "thorchain", "symbol": "RUNE", "name": "THORChain", "emoji": "⚡"},
}


async def delete_user_message(bot: Bot, chat_id: int):
    if chat_id in user_messages:
        try:
            await bot.delete_message(chat_id, user_messages[chat_id])
        except:
            pass


async def clean_send(message: Message, text: str, keyboard: InlineKeyboardMarkup):
    chat_id = message.chat.id
    try:
        await message.delete()
    except:
        pass
    await delete_user_message(message.bot, chat_id)
    new_msg = await message.answer(
        text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
    )
    user_messages[chat_id] = new_msg.message_id


async def safe_send_message(message_method, text: str, **kwargs):
    """
    Safely send/edit a message with fallback to no parse_mode on parsing error.

    This implements a "fail-soft" approach for Markdown parsing:
    1. First tries to send with the specified parse_mode (if provided)
    2. If Telegram returns "can't parse entities" error, retries without parse_mode
    3. Ensures messages are always delivered even if formatting fails
    4. For TON signals, logs raw text when Telegram markdown errors occur

    Args:
        message_method: The async method to call (e.g., message.answer)
        text: The message text
        **kwargs: Additional arguments (reply_markup, parse_mode, etc.)

    Returns:
        The message object returned by Telegram
    """
    try:
        # Try with the original parse_mode (if specified)
        return await message_method(text, **kwargs)
    except TelegramBadRequest as e:
        error_str = str(e).lower()
        if "can't parse entities" in error_str or "can't find end of" in error_str:
            # Markdown parsing failed - retry without parse_mode
            logger.error(f"Markdown parsing error: {e}")

            # Special logging for TON signals to help debug markdown issues
            if "TON" in text or "💎" in text:
                logger.error(f"TON Telegram error: {str(e)}\nRAW SIGNAL: {text}")

            # Remove parse_mode from kwargs
            kwargs_no_parse = {k: v for k, v in kwargs.items() if k != "parse_mode"}
            try:
                return await message_method(text, **kwargs_no_parse)
            except Exception as retry_error:
                logger.error(
                    f"Failed to send message even without parse_mode: {retry_error}"
                )
                raise
        else:
            # Different error - re-raise
            raise


async def get_coin_price(symbol: str) -> dict:
    """Получить цену через Multi-API Manager (CoinGecko + CoinPaprika + MEXC + Kraken)"""
    try:
        data = await get_price_multi_api(symbol.upper())

        if data.get("success"):
            return {
                "success": True,
                "price_usd": data.get("price_usd", 0),
                "price_rub": data.get("price_rub", 0),
                "price_eur": data.get("price_eur", 0),
                "change_24h": data.get("change_24h", 0),
                "volume_24h": data.get("volume_24h", 0),
                "market_cap": data.get("market_cap", 0),
                "source": data.get("source", "Unknown"),
            }
        else:
            return {"error": data.get("message", "API Error")}
    except Exception as e:
        logger.error(f"Price error: {e}")
        return {"error": str(e)}


async def get_market_data() -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/global"
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    return {"error": "api_error"}
                data = await response.json()
                market = data.get("data", {})
                return {
                    "success": True,
                    "total_market_cap": market.get("total_market_cap", {}).get(
                        "usd", 0
                    ),
                    "total_volume": market.get("total_volume", {}).get("usd", 0),
                    "btc_dominance": market.get("market_cap_percentage", {}).get(
                        "btc", 0
                    ),
                    "eth_dominance": market.get("market_cap_percentage", {}).get(
                        "eth", 0
                    ),
                    "active_coins": market.get("active_cryptocurrencies", 0),
                }
    except:
        return {"error": "failed"}


def format_number(num: float) -> str:
    if num >= 1000000000000:
        return "$" + str(round(num / 1000000000000, 2)) + "T"
    elif num >= 1000000000:
        return "$" + str(round(num / 1000000000, 2)) + "B"
    elif num >= 1000000:
        return "$" + str(round(num / 1000000, 2)) + "M"
    else:
        return "$" + str(round(num, 2))


def generate_progress_bar(percentage: float, length: int = 10) -> str:
    """Генерирует прогресс-бар для отображения процентов."""
    filled = int(percentage / 100 * length)
    empty = length - filled
    return "█" * filled + "░" * empty


def escape_markdown_v2(text: str) -> str:
    """Экранирует специальные символы для MarkdownV2."""
    special_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]
    for char in special_chars:
        text = text.replace(char, "\\" + char)
    return text


def format_previous_result(result: dict) -> str:
    """Форматирует результат предыдущего сигнала."""
    direction_emoji = (
        "📈"
        if result["direction"] == "long"
        else "📉"
        if result["direction"] == "short"
        else "➡️"
    )

    # Форматирование цен
    def format_price(price: float) -> str:
        if price >= 1000:
            return f"${price:,.0f}"
        elif price >= 1:
            return f"${price:,.2f}"
        else:
            return f"${price:.6f}"

    # Статусы целей
    t1_status = "✅ Достигнута" if result["target1_reached"] else "❌ Не достигнута"
    t2_status = "✅ Достигнута" if result["target2_reached"] else "⏳ Не достигнута"
    sl_status = "❌ Задет" if result["stop_hit"] else "✅ Не задет"

    # Результат
    if result["result"] == "win":
        result_text = f"✅ УСПЕХ (+{result['pnl_percent']:.1f}%)"
    elif result["result"] == "loss":
        result_text = f"❌ УБЫТОК ({result['pnl_percent']:.1f}%)"
    else:
        result_text = "⏳ В процессе"

    # Для sideways другой формат
    if result["direction"] == "sideways":
        text = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *ПРЕДЫДУЩИЙ СИГНАЛ* ({result["time_elapsed"]} назад)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{direction_emoji} Направление: *БОКОВИК*
💰 Вход: {format_price(result["entry_price"])}
📊 Диапазон: ±1.0%

📊 Результат: {result_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    else:
        text = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *ПРЕДЫДУЩИЙ СИГНАЛ* ({result["time_elapsed"]} назад)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{direction_emoji} Направление: *{result["direction"].upper()}*
💰 Вход: {format_price(result["entry_price"])}
🎯 Цель 1: {format_price(result["target1_price"])} — {t1_status}
🎯 Цель 2: {format_price(result["target2_price"])} — {t2_status}
🛑 Стоп: {sl_status}

📊 Результат: {result_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return text


def format_price_message(symbol: str, data: dict) -> str:
    if "error" in data:
        if data["error"] == "rate_limit":
            return "⚠️ *Лимит запросов*\n\nПодожди 1-2 минуты и попробуй снова"
        elif data["error"] == "timeout":
            return "⚠️ *Сервер не отвечает*\n\nПопробуй позже"
        else:
            return "❌ Ошибка: " + str(data["error"])

    coin_info = COINS.get(symbol.lower(), {})
    emoji = coin_info.get("emoji", "💰")
    name = coin_info.get("name", symbol.upper())

    price_usd = data["price_usd"]
    price_rub = data["price_rub"]
    price_eur = data["price_eur"]
    change_24h = data["change_24h"]
    volume_24h = data["volume_24h"]
    market_cap = data["market_cap"]
    source = data.get("source", "")

    if price_usd >= 1:
        price_usd_text = "${:,.2f}".format(price_usd)
    elif price_usd >= 0.01:
        price_usd_text = "${:,.4f}".format(price_usd)
    else:
        price_usd_text = "${:,.8f}".format(price_usd)

    price_rub_text = "₽{:,.2f}".format(price_rub)
    price_eur_text = "€{:,.2f}".format(price_eur)

    if change_24h >= 0:
        change_text = "📈 +{:.2f}%".format(change_24h)
    else:
        change_text = "📉 {:.2f}%".format(change_24h)

    cap_text = format_number(market_cap) if market_cap > 0 else "N/A"
    vol_text = format_number(volume_24h) if volume_24h > 0 else "N/A"

    now = datetime.now().strftime("%H:%M:%S")

    text = emoji + " *" + name + "* (" + symbol.upper() + ")\n\n"
    text = text + "💵 USD: *" + price_usd_text + "*\n"
    text = text + "🇷🇺 RUB: *" + price_rub_text + "*\n"
    text = text + "🇪🇺 EUR: *" + price_eur_text + "*\n\n"
    text = text + change_text + " за 24ч\n"
    text = text + "📊 Cap: " + cap_text + "\n"
    text = text + "📈 Vol: " + vol_text + "\n\n"
    if source:
        text = text + "📡 _" + source + "_\n"
    text = text + "⏰ _" + now + "_"

    return text


def get_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Цены", callback_data="menu_prices"),
                InlineKeyboardButton(text="🎯 Сигналы", callback_data="menu_signals"),
                InlineKeyboardButton(text="🐋 Киты", callback_data="menu_whale"),
            ],
            [
                InlineKeyboardButton(text="📊 Рынок", callback_data="menu_market"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings"),
                InlineKeyboardButton(
                    text="💼 Портфель", callback_data="menu_portfolio"
                ),
            ],
        ]
    )


# Порядок монет для пагинации (все 34 монеты)
COINS_ORDER = [
    # Страница 1 (основные)
    "btc",
    "eth",
    "ton",
    "sol",
    "xrp",
    "doge",
    "matic",
    "ltc",
    # Страница 2 (продолжение основных)
    "shib",
    "avax",
    "bnb",
    "ada",
    "dot",
    "link",
    "uni",
    "atom",
    # Страница 3 (мем-коины и L1)
    "trx",
    "not",
    "pepe",
    "wif",
    "bonk",
    "sui",
    "apt",
    "sei",
    # Страница 4 (L1, L2 и DeFi)
    "near",
    "ftm",
    "arb",
    "op",
    "inj",
    "xlm",
    "vet",
    "algo",
    # Страница 5 (оставшиеся)
    "fil",
    "rune",
]

COINS_PER_PAGE = 8


def get_prices_keyboard(page: int = 1) -> InlineKeyboardMarkup:
    """Клавиатура с ценами монет с пагинацией."""
    total_pages = (len(COINS_ORDER) + COINS_PER_PAGE - 1) // COINS_PER_PAGE

    # Ограничиваем страницу
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    # Вычисляем индексы для текущей страницы
    start_idx = (page - 1) * COINS_PER_PAGE
    end_idx = min(start_idx + COINS_PER_PAGE, len(COINS_ORDER))
    page_coins = COINS_ORDER[start_idx:end_idx]

    keyboard = []

    # Создаем кнопки для монет (по 3 в ряд)
    row = []
    for coin in page_coins:
        coin_info = COINS.get(coin, {})
        emoji = coin_info.get("emoji", "💰")
        symbol = coin_info.get("symbol", coin.upper())
        row.append(
            InlineKeyboardButton(
                text=emoji + " " + symbol, callback_data="price_" + coin
            )
        )
        if len(row) == 3:
            keyboard.append(row)
            row = []

    # Добавляем оставшиеся кнопки
    if row:
        keyboard.append(row)

    # Кнопки навигации
    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️ " + str(page - 1), callback_data="prices_page_" + str(page - 1)
            )
        )
    nav_row.append(
        InlineKeyboardButton(
            text=str(page) + "/" + str(total_pages), callback_data="prices_page_current"
        )
    )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text=str(page + 1) + " ▶️", callback_data="prices_page_" + str(page + 1)
            )
        )
    keyboard.append(nav_row)

    # Дополнительные кнопки
    keyboard.append(
        [InlineKeyboardButton(text="📊 API статистика", callback_data="menu_api_stats")]
    )
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_price_keyboard(symbol: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить", callback_data="price_" + symbol.lower()
                ),
                InlineKeyboardButton(
                    text="🎯 Сигнал", callback_data="signal_" + symbol.lower()
                ),
            ],
            [
                InlineKeyboardButton(text="🔙 К ценам", callback_data="menu_prices"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
            ],
        ]
    )


def get_signals_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа сигналов."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Обычные сигналы", callback_data="signals_normal"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚡ Супер Сигналы", callback_data="super_signals"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💎 Новые гемы", callback_data="gems"
                ),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu"),
            ],
        ]
    )


def get_super_signals_mode_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора режима сканирования для супер сигналов."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Все монеты", callback_data="signals_all"),
                InlineKeyboardButton(
                    text="📈 Фьючерсы", callback_data="signals_futures"
                ),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="menu_signals"),
            ],
        ]
    )


def get_gems_network_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора сети для сканирования гемов."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="☀️ Solana", callback_data="gems_solana"),
                InlineKeyboardButton(text="🔵 Base", callback_data="gems_base"),
            ],
            [
                InlineKeyboardButton(text="💎 Ethereum", callback_data="gems_ethereum"),
                InlineKeyboardButton(text="🟡 BSC", callback_data="gems_bsc"),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="menu_signals"),
            ],
        ]
    )


def get_signals_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для AI-сигналов по 5 монетам: BTC, ETH, TON, SOL, XRP."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="₿ BTC", callback_data="signal_btc"),
                InlineKeyboardButton(text="⟠ ETH", callback_data="signal_eth"),
                InlineKeyboardButton(text="💎 TON", callback_data="signal_ton"),
            ],
            [
                InlineKeyboardButton(text="🟣 SOL", callback_data="signal_sol"),
                InlineKeyboardButton(text="💧 XRP", callback_data="signal_xrp"),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика", callback_data="show_stats_menu"
                ),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="menu_signals"),
            ],
        ]
    )


def get_stats_coins_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора монеты для статистики."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="₿ BTC", callback_data="stats_BTC"),
                InlineKeyboardButton(text="⟠ ETH", callback_data="stats_ETH"),
                InlineKeyboardButton(text="💎 TON", callback_data="stats_TON"),
            ],
            [
                InlineKeyboardButton(text="🟣 SOL", callback_data="stats_SOL"),
                InlineKeyboardButton(text="💧 XRP", callback_data="stats_XRP"),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_signals"),
            ],
        ]
    )


def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def get_welcome_text(name: str) -> str:
    text = "🚀 *GHEEZY CRYPTO*\n\n"
    text = text + "Привет, *" + name + "*!  👋\n\n"
    text = text + "Я — Gheezy, твой проводник в крипто вселенной💫\n"
    text = text + "Давай вместе учиться и зарабатывать 🤩\n\n"
    text = text + "📊 *Мои возможности:*\n\n"
    text = text + "• 💰 Цены — самые популярные криптовалюты\n"
    text = text + "• 🎯 Сигналы — торговые сигналы + новые гемы\n"
    text = text + "• 🐋 Киты — движения китов\n"
    text = text + "• 📊 Рынок — капитализация и статистика\n"
    text = text + "• ⚙️ Настройки — настройки бота\n"
    text = text + "• 💼 Портфель — твой портфель\n\n"
    text = text + "Ну что, взлетаем! 🚀🚀🚀\n\n"
    text = text + "👇 *Выбери раздел:*"
    return text


@router.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    name = user.first_name if user.first_name else "друг"
    await clean_send(message, get_welcome_text(name), get_main_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = "📚 *Справка*\n\n"
    text = text + "*Быстрые команды (34 монеты):*\n\n"
    text = text + "Основные: /btc /eth /ton /sol /xrp\n"
    text = text + "/doge /matic /ltc /shib /avax\n"
    text = text + "/bnb /ada /dot /link /uni /atom /trx\n\n"
    text = text + "Мем-коины: /not /pepe /wif /bonk\n\n"
    text = text + "L1: /sui /apt /sei /near /ftm\n\n"
    text = text + "L2: /arb /op\n\n"
    text = text + "Другие: /inj /xlm /vet /algo /fil /rune\n\n"
    text = text + "*Текстовые команды:*\n\n"
    text = text + "Напиши символ монеты (BTC, NOT, SUI...)\n"
    text = text + "и получи её цену!\n\n"
    text = text + "*Основные команды:*\n\n"
    text = text + "/start — главное меню\n"
    text = text + "/market — обзор рынка\n"
    text = text + "/prices — все монеты (с пагинацией)\n"
    text = text + "/help — справка\n\n"
    text = text + "*Команды Whale Tracker (2 сети):*\n\n"
    text = text + "/whale — все крупные транзакции\n"
    text = text + "/whale btc — только Bitcoin\n"
    text = text + "/whale eth — только Ethereum\n"
    text = text + "/whale on — включить оповещения\n"
    text = text + "/whale off — выключить оповещения\n"
    text = text + "/whale stats — статистика за день\n"
    text = text + "/whales — статистика всех сетей\n\n"
    text = text + "📡 _5 API: CoinGecko + CoinPaprika + MEXC + Kraken_"
    await clean_send(message, text, get_back_keyboard())


@router.message(Command("market"))
async def cmd_market(message: Message):
    chat_id = message.chat.id
    try:
        await message.delete()
    except:
        pass
    await delete_user_message(message.bot, chat_id)

    loading_msg = await message.answer(
        "⏳ *Загружаю рынок...*", parse_mode=ParseMode.MARKDOWN
    )
    user_messages[chat_id] = loading_msg.message_id

    data = await get_market_data()

    if "error" in data:
        text = "❌ Не удалось загрузить"
    else:
        cap = format_number(data["total_market_cap"])
        vol = format_number(data["total_volume"])
        btc_dom = str(round(data["btc_dominance"], 1)) + "%"
        eth_dom = str(round(data["eth_dominance"], 1)) + "%"
        coins = str(data["active_coins"])

        text = "📊 *Обзор рынка*\n\n"
        text = text + "💰 Total Cap: *" + cap + "*\n"
        text = text + "📈 24h Volume: *" + vol + "*\n\n"
        text = text + "₿ BTC Dominance: *" + btc_dom + "*\n"
        text = text + "⟠ ETH Dominance: *" + eth_dom + "*\n\n"
        text = text + "🪙 Активных монет: *" + coins + "*"

    await loading_msg.edit_text(
        text, reply_markup=get_back_keyboard(), parse_mode=ParseMode.MARKDOWN
    )


@router.message(Command("prices"))
async def cmd_prices(message: Message):
    chat_id = message.chat.id
    try:
        await message.delete()
    except:
        pass
    await delete_user_message(message.bot, chat_id)

    loading_msg = await message.answer(
        "⏳ *Загружаю все цены...*", parse_mode=ParseMode.MARKDOWN
    )
    user_messages[chat_id] = loading_msg.message_id

    # Показываем первую страницу монет
    coins_list = COINS_ORDER[:COINS_PER_PAGE]

    text = "💰 *Цены криптовалют*\n\n"

    for symbol in coins_list:
        data = await get_coin_price(symbol.upper())
        coin_info = COINS.get(symbol.lower(), {})
        emoji = coin_info.get("emoji", "💰")

        if data.get("success"):
            price = data["price_usd"]
            change = data["change_24h"]

            if price >= 1:
                price_text = "${:,.2f}".format(price)
            elif price >= 0.01:
                price_text = "${:,.4f}".format(price)
            else:
                price_text = "${:,.6f}".format(price)

            if change >= 0:
                change_text = "+{:.1f}%".format(change)
                trend = "🟢"
            else:
                change_text = "{:.1f}%".format(change)
                trend = "🔴"

            text = (
                text
                + emoji
                + " *"
                + symbol.upper()
                + "*: "
                + price_text
                + " "
                + trend
                + " "
                + change_text
                + "\n"
            )
        else:
            text = text + emoji + " *" + symbol.upper() + "*: ❌ ошибка\n"

    now = datetime.now().strftime("%H:%M:%S")
    text = text + "\n⏰ _" + now + "_"

    await loading_msg.edit_text(
        text, reply_markup=get_prices_keyboard(1), parse_mode=ParseMode.MARKDOWN
    )


async def send_quick_price(message: Message, symbol: str):
    if symbol.lower() not in COINS:
        await message.answer("❌ Монета не найдена")
        return

    chat_id = message.chat.id
    try:
        await message.delete()
    except:
        pass
    await delete_user_message(message.bot, chat_id)

    coin_info = COINS.get(symbol.lower(), {})
    emoji = coin_info.get("emoji", "💰")

    loading_msg = await message.answer(
        emoji + " *Загружаю " + symbol.upper() + "...*", parse_mode=ParseMode.MARKDOWN
    )
    user_messages[chat_id] = loading_msg.message_id

    data = await get_coin_price(symbol.upper())
    text = format_price_message(symbol, data)

    await loading_msg.edit_text(
        text, reply_markup=get_price_keyboard(symbol), parse_mode=ParseMode.MARKDOWN
    )


@router.message(Command("btc"))
async def cmd_btc(message: Message):
    await send_quick_price(message, "btc")


@router.message(Command("eth"))
async def cmd_eth(message: Message):
    await send_quick_price(message, "eth")


@router.message(Command("ton"))
async def cmd_ton(message: Message):
    await send_quick_price(message, "ton")


@router.message(Command("sol"))
async def cmd_sol(message: Message):
    await send_quick_price(message, "sol")


@router.message(Command("xrp"))
async def cmd_xrp(message: Message):
    await send_quick_price(message, "xrp")


@router.message(Command("doge"))
async def cmd_doge(message: Message):
    await send_quick_price(message, "doge")


@router.message(Command("matic"))
async def cmd_matic(message: Message):
    await send_quick_price(message, "matic")


@router.message(Command("ltc"))
async def cmd_ltc(message: Message):
    await send_quick_price(message, "ltc")


@router.message(Command("shib"))
async def cmd_shib(message: Message):
    await send_quick_price(message, "shib")


@router.message(Command("avax"))
async def cmd_avax(message: Message):
    await send_quick_price(message, "avax")


@router.message(Command("bnb"))
async def cmd_bnb(message: Message):
    await send_quick_price(message, "bnb")


@router.message(Command("ada"))
async def cmd_ada(message: Message):
    await send_quick_price(message, "ada")


@router.message(Command("dot"))
async def cmd_dot(message: Message):
    await send_quick_price(message, "dot")


@router.message(Command("link"))
async def cmd_link(message: Message):
    await send_quick_price(message, "link")


@router.message(Command("uni"))
async def cmd_uni(message: Message):
    await send_quick_price(message, "uni")


@router.message(Command("atom"))
async def cmd_atom(message: Message):
    await send_quick_price(message, "atom")


@router.message(Command("trx"))
async def cmd_trx(message: Message):
    await send_quick_price(message, "trx")


# Мем-коины
@router.message(Command("not"))
async def cmd_not(message: Message):
    await send_quick_price(message, "not")


@router.message(Command("pepe"))
async def cmd_pepe(message: Message):
    await send_quick_price(message, "pepe")


@router.message(Command("wif"))
async def cmd_wif(message: Message):
    await send_quick_price(message, "wif")


@router.message(Command("bonk"))
async def cmd_bonk(message: Message):
    await send_quick_price(message, "bonk")


# Новые L1 блокчейны
@router.message(Command("sui"))
async def cmd_sui(message: Message):
    await send_quick_price(message, "sui")


@router.message(Command("apt"))
async def cmd_apt(message: Message):
    await send_quick_price(message, "apt")


@router.message(Command("sei"))
async def cmd_sei(message: Message):
    await send_quick_price(message, "sei")


@router.message(Command("near"))
async def cmd_near(message: Message):
    await send_quick_price(message, "near")


@router.message(Command("ftm"))
async def cmd_ftm(message: Message):
    await send_quick_price(message, "ftm")


# L2 Ethereum
@router.message(Command("arb"))
async def cmd_arb(message: Message):
    await send_quick_price(message, "arb")


@router.message(Command("op"))
async def cmd_op(message: Message):
    await send_quick_price(message, "op")


# DeFi и другие
@router.message(Command("inj"))
async def cmd_inj(message: Message):
    await send_quick_price(message, "inj")


@router.message(Command("xlm"))
async def cmd_xlm(message: Message):
    await send_quick_price(message, "xlm")


@router.message(Command("vet"))
async def cmd_vet(message: Message):
    await send_quick_price(message, "vet")


@router.message(Command("algo"))
async def cmd_algo(message: Message):
    await send_quick_price(message, "algo")


@router.message(Command("fil"))
async def cmd_fil(message: Message):
    await send_quick_price(message, "fil")


@router.message(Command("rune"))
async def cmd_rune(message: Message):
    await send_quick_price(message, "rune")


# ============================================
# Whale Tracker Commands
# ============================================


def get_whale_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для whale tracker с 2 сетями: BTC, ETH."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="₿ BTC", callback_data="whale_btc")],
            [InlineKeyboardButton(text="⟠ ETH", callback_data="whale_eth")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
        ]
    )


@router.message(Command("whale"))
async def cmd_whale(message: Message):
    """Обработка команды /whale с аргументами."""
    chat_id = message.chat.id
    try:
        await message.delete()
    except Exception:
        pass
    await delete_user_message(message.bot, chat_id)

    # Парсим аргументы команды
    text_parts = message.text.split() if message.text else []
    subcommand = text_parts[1].lower() if len(text_parts) > 1 else None

    if subcommand == "on":
        # Включить оповещения
        whale_subscriptions.add(chat_id)
        text = (
            "🐋 *Whale Tracker*\n\n"
            "✅ *Оповещения включены!*\n\n"
            "Вы будете получать уведомления о крупных\n"
            "транзакциях на BTC и ETH.\n\n"
            "Минимальная сумма: $50,000+"
        )
        new_msg = await message.answer(
            text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
        user_messages[chat_id] = new_msg.message_id
        return

    if subcommand == "off":
        # Выключить оповещения
        whale_subscriptions.discard(chat_id)
        text = (
            "🐋 *Whale Tracker*\n\n"
            "❌ *Оповещения выключены!*\n\n"
            "Вы больше не будете получать уведомления\n"
            "о транзакциях китов."
        )
        new_msg = await message.answer(
            text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
        user_messages[chat_id] = new_msg.message_id
        return

    if subcommand == "stats":
        # Статистика за день
        loading_msg = await message.answer(
            "⏳ *Загружаю статистику...*", parse_mode=ParseMode.MARKDOWN
        )
        user_messages[chat_id] = loading_msg.message_id

        try:
            stats_text = await whale_tracker.format_stats_message()
            await loading_msg.edit_text(
                stats_text,
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error(f"Whale stats error: {e}")
            await loading_msg.edit_text(
                "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки статистики",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    if subcommand in ("eth", "ethereum"):
        # Только Ethereum
        loading_msg = await message.answer(
            "⏳ *Загружаю ETH транзакции...*", parse_mode=ParseMode.MARKDOWN
        )
        user_messages[chat_id] = loading_msg.message_id

        try:
            whale_text = await whale_tracker.format_whale_message(blockchain="eth")
            await loading_msg.edit_text(
                whale_text,
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error(f"Whale ETH error: {e}")
            await loading_msg.edit_text(
                "🐋 *Whale Tracker - Ethereum*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    if subcommand in ("btc", "bitcoin"):
        # Только Bitcoin
        loading_msg = await message.answer(
            "⏳ *Загружаю BTC транзакции...*", parse_mode=ParseMode.MARKDOWN
        )
        user_messages[chat_id] = loading_msg.message_id

        try:
            whale_text = await whale_tracker.format_whale_message(blockchain="btc")
            await loading_msg.edit_text(
                whale_text,
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error(f"Whale BTC error: {e}")
            await loading_msg.edit_text(
                "🐋 *Whale Tracker - Bitcoin*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    # Все транзакции (по умолчанию)
    loading_msg = await message.answer(
        "⏳ *Загружаю транзакции китов...*", parse_mode=ParseMode.MARKDOWN
    )
    user_messages[chat_id] = loading_msg.message_id

    try:
        whale_text = await whale_tracker.format_whale_message()
        await loading_msg.edit_text(
            whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Whale all error: {e}")
        await loading_msg.edit_text(
            "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки данных",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )


@router.message(Command("whales"))
async def cmd_whales(message: Message):
    """Команда /whales - статистика всех сетей."""
    chat_id = message.chat.id
    try:
        await message.delete()
    except Exception:
        pass
    await delete_user_message(message.bot, chat_id)

    loading_msg = await message.answer(
        "⏳ *Загружаю статистику всех сетей...*", parse_mode=ParseMode.MARKDOWN
    )
    user_messages[chat_id] = loading_msg.message_id

    try:
        stats_text = await whale_tracker.format_all_networks_stats_message()
        await loading_msg.edit_text(
            stats_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Whales stats error: {e}")
        await loading_msg.edit_text(
            "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки статистики",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Показать статистику сигналов пользователя."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    try:
        await message.delete()
    except Exception:
        pass
    await delete_user_message(message.bot, chat_id)

    try:
        stats = signal_tracker.get_user_stats(user_id)

        if stats["total_signals"] == 0:
            text = """
📊 *Ваша статистика*

_У вас пока нет отслеживаемых сигналов._

Нажмите на любую монету в разделе Сигналы, чтобы начать отслеживание!
"""
        else:
            # Прогресс-бар для win rate
            filled = int(stats["win_rate"] / 10)
            bar = "█" * filled + "░" * (10 - filled)

            # Эмодзи для P&L
            pnl_emoji = "📈" if stats["total_pnl"] >= 0 else "📉"

            text = f"""
📊 *Ваша статистика сигналов*
━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 Всего сигналов: *{stats["total_signals"]}*

✅ Успешных: *{stats["wins"]}*
❌ Убыточных: *{stats["losses"]}*
⏳ В ожидании: *{stats["pending"]}*

🎯 Win Rate: *{stats["win_rate"]:.1f}%*
{bar}

{pnl_emoji} Общий P/L: *{stats["total_pnl"]:+.1f}%*

🏆 Лучшая монета: *{stats["best_symbol"]}*
💀 Худшая монета: *{stats["worst_symbol"]}*
━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back")],
            ]
        )

        new_msg = await message.answer(
            text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
        user_messages[chat_id] = new_msg.message_id

    except Exception as e:
        logger.error(f"Stats error: {e}", exc_info=True)
        text = "❌ *Ошибка*\n\nНе удалось загрузить статистику."
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back")],
            ]
        )
        new_msg = await message.answer(
            text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
        user_messages[chat_id] = new_msg.message_id


@router.callback_query(lambda c: c.data == "whale_all")
async def callback_whale_all(callback: CallbackQuery):
    """Обновить все транзакции китов."""
    await callback.answer("⏳ Загружаю...")
    await callback.message.edit_text(
        "⏳ *Загружаю транзакции китов...*", parse_mode=ParseMode.MARKDOWN
    )

    try:
        whale_text = await whale_tracker.format_whale_message()
        await callback.message.edit_text(
            whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Whale callback error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки данных",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )


@router.callback_query(lambda c: c.data == "whale_eth")
async def callback_whale_eth(callback: CallbackQuery):
    """Транзакции Ethereum."""
    await callback.answer("⏳ Загружаю ETH...")
    await callback.message.edit_text(
        "⏳ *Загружаю ETH транзакции...*", parse_mode=ParseMode.MARKDOWN
    )

    try:
        whale_text = await whale_tracker.format_whale_message(blockchain="eth")
        try:
            await callback.message.edit_text(
                whale_text,
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramBadRequest as e:
            if "message to edit not found" in str(e):
                await callback.message.answer(
                    whale_text,
                    reply_markup=get_whale_keyboard(),
                    parse_mode=ParseMode.MARKDOWN,
                )
            elif "message is not modified" in str(e):
                pass
            else:
                raise
    except Exception as e:
        logger.error(f"Whale ETH callback error: {e}")
        try:
            await callback.message.edit_text(
                "🐋 *Whale Tracker - Ethereum*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramBadRequest:
            await callback.message.answer(
                "🐋 *Whale Tracker - Ethereum*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )


@router.callback_query(lambda c: c.data == "whale_btc")
async def callback_whale_btc(callback: CallbackQuery):
    """Транзакции Bitcoin."""
    await callback.answer("⏳ Загружаю BTC...")
    await callback.message.edit_text(
        "⏳ *Загружаю BTC транзакции...*", parse_mode=ParseMode.MARKDOWN
    )

    try:
        whale_text = await whale_tracker.format_whale_message(blockchain="btc")
        try:
            await callback.message.edit_text(
                whale_text,
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramBadRequest as e:
            if "message to edit not found" in str(e):
                await callback.message.answer(
                    whale_text,
                    reply_markup=get_whale_keyboard(),
                    parse_mode=ParseMode.MARKDOWN,
                )
            elif "message is not modified" in str(e):
                pass
            else:
                raise
    except Exception as e:
        logger.error(f"Whale BTC callback error: {e}")
        try:
            await callback.message.edit_text(
                "🐋 *Whale Tracker - Bitcoin*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramBadRequest:
            await callback.message.answer(
                "🐋 *Whale Tracker - Bitcoin*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )


@router.callback_query(lambda c: c.data == "whale_stats")
async def callback_whale_stats(callback: CallbackQuery):
    """Статистика whale tracker."""
    await callback.answer("⏳ Загружаю статистику...")
    await callback.message.edit_text(
        "⏳ *Загружаю статистику...*", parse_mode=ParseMode.MARKDOWN
    )

    try:
        stats_text = await whale_tracker.format_all_networks_stats_message()
        await callback.message.edit_text(
            stats_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Whale stats callback error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки статистики",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )


@router.callback_query(lambda c: c.data == "menu_prices")
async def callback_prices(callback: CallbackQuery):
    text = "💰 *Цены криптовалют*\n\n"
    text = text + "Выбери монету для просмотра\n"
    text = text + "актуальной цены 👇\n\n"
    text = text + "📡 _5 API: CoinGecko + CoinPaprika + MEXC + Kraken_"
    await callback.message.edit_text(
        text, reply_markup=get_prices_keyboard(1), parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("prices_page_"))
async def callback_prices_page(callback: CallbackQuery):
    """Обработка пагинации страниц с ценами."""
    page_str = callback.data.replace("prices_page_", "")

    # Если нажали на текущую страницу, ничего не делаем
    if page_str == "current":
        await callback.answer()
        return

    try:
        page = int(page_str)
    except ValueError:
        await callback.answer()
        return

    text = "💰 *Цены криптовалют*\n\n"
    text = text + "Выбери монету для просмотра\n"
    text = text + "актуальной цены 👇\n\n"
    text = text + "📡 _5 API: CoinGecko + CoinPaprika + MEXC + Kraken_"
    await callback.message.edit_text(
        text, reply_markup=get_prices_keyboard(page), parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu_api_stats")
async def callback_api_stats(callback: CallbackQuery):
    stats = get_api_stats()

    text = "📡 *Статистика API*\n\n"

    for api_name, api_stats in stats.items():
        name = api_stats["name"]
        success = api_stats["success"]
        failed = api_stats["failed"]
        rate = api_stats["success_rate"]
        avg_time = api_stats["avg_time"]
        status = api_stats["status"]

        if status == "Active":
            status_emoji = "🟢"
        else:
            status_emoji = "🟡"

        text = text + status_emoji + " *" + name + "*\n"
        text = text + "   ✅ Успехов: " + str(success) + "\n"
        text = text + "   ❌ Ошибок: " + str(failed) + "\n"
        text = text + "   📊 Rate: " + rate + "\n"
        text = text + "   ⏱ Время: " + avg_time + "\n\n"

    text = text + "_Автоматический fallback между API_"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К ценам", callback_data="menu_prices")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back")],
        ]
    )

    await callback.message.edit_text(
        text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("price_"))
async def callback_price_coin(callback: CallbackQuery):
    symbol = callback.data.replace("price_", "")
    if symbol not in COINS:
        await callback.answer("Монета не найдена")
        return

    await callback.answer("⏳ Загружаю...")

    coin_info = COINS.get(symbol, {})
    emoji = coin_info.get("emoji", "💰")

    await callback.message.edit_text(
        emoji + " *Загружаю " + symbol.upper() + "...*", parse_mode=ParseMode.MARKDOWN
    )

    data = await get_coin_price(symbol.upper())
    text = format_price_message(symbol, data)

    await callback.message.edit_text(
        text, reply_markup=get_price_keyboard(symbol), parse_mode=ParseMode.MARKDOWN
    )


@router.callback_query(lambda c: c.data == "menu_signals")
async def callback_signals(callback: CallbackQuery):
    text = "🎯 *Торговые сигналы*\n\n"
    text = text + "Выберите тип сигналов:\n\n"
    text = (
        text
        + "📊 *Обычные сигналы* — AI-анализ по конкретным монетам (BTC, ETH, TON, SOL, XRP)\n\n"
    )
    text = (
        text
        + "⚡ *Супер Сигналы* — автоматическое сканирование 3000\\+ монет и выбор ТОП-5 с вероятностью\n\n"
    )
    text = text + "👇 Выберите:"
    try:
        await safe_send_message(
            callback.message.edit_text,
            text,
            reply_markup=get_signals_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"Error editing message: {e}")
    await callback.answer()


@router.callback_query(lambda c: c.data == "signals_normal")
async def callback_signals_normal(callback: CallbackQuery):
    """Handler for normal signals - show coin selection."""
    text = "🎯 *Торговые сигналы*\n\n"
    text = text + "Анализ на основе:\n\n"
    text = text + "• Данные трекера китов\n"
    text = text + "• Депозиты vs выводы с бирж\n"
    text = text + "• Рыночные данные\n"
    text = text + "• Объём торгов\n\n"
    text = text + "🔮 _Прогноз на ближайший час_\n\n"
    text = text + "👇 Выбери монету:"
    try:
        await safe_send_message(
            callback.message.edit_text,
            text,
            reply_markup=get_signals_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"Error editing message: {e}")
    await callback.answer()


@router.callback_query(lambda c: c.data == "super_signals")
async def callback_super_signals(callback: CallbackQuery):
    """Handler for super signals - show mode selection."""
    text = "⚡ *Супер Сигналы*\n\n"
    text = text + "Выберите режим сканирования:\n\n"
    text = text + "📊 *Все монеты* — сканирование 3000\\+ монет всех типов\n\n"
    text = (
        text + "📈 *Фьючерсы* — только монеты с фьючерсными контрактами на Binance\n\n"
    )
    text = text + "👇 Выберите:"
    try:
        await safe_send_message(
            callback.message.edit_text,
            text,
            reply_markup=get_super_signals_mode_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"Error editing message: {e}")
    await callback.answer()


@router.callback_query(lambda c: c.data == "signals_all")
async def callback_signals_all(callback: CallbackQuery):
    """Handler for all coins mode - scan 3000+ coins and show TOP-5."""
    await callback.answer("⏳ Сканирую все монеты...")
    await callback.message.edit_text(
        "⏳ *Сканирование всех монет\\.\\.\\.*\n\n"
        "Анализирую 3000\\+ монет\\.\\.\\.\\.\n"
        "Это может занять 30\\-60 секунд",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        # Initialize SuperSignals
        analyzer = SuperSignals()

        # Get TOP-5 signals in "all" mode
        top5 = await analyzer.scan(mode="all")

        # Get counts for message
        scanned_count = 3000  # Approximate
        filtered_count = 30  # TOP_CANDIDATES

        # Format message
        message_text = analyzer.format_message(
            top5, scanned_count, filtered_count, mode="all"
        )

        # Close analyzer
        await analyzer.close()

        # Send result
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Обновить", callback_data="signals_all"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 К выбору", callback_data="super_signals"
                    ),
                    InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
                ],
            ]
        )

        await callback.message.edit_text(
            message_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error in super signals (all mode): {e}", exc_info=True)

        error_text = (
            "❌ *Ошибка супер сигналов*\n\n"
            "Произошла ошибка при сканировании монет\\.\n"
            "Попробуйте позже или используйте обычные сигналы\\.\n\n"
            f"_Ошибка: {str(e).replace('.', '\\.').replace('-', '\\-')}_"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="super_signals"
                    ),
                ],
            ]
        )

        try:
            await callback.message.edit_text(
                error_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass


@router.callback_query(lambda c: c.data == "signals_futures")
async def callback_signals_futures(callback: CallbackQuery):
    """Handler for futures mode - scan futures pairs and show TOP-5."""
    await callback.answer("⏳ Сканирую фьючерсные пары...")
    await callback.message.edit_text(
        "⏳ *Сканирование фьючерсов\\.\\.\\.*\n\n"
        "Анализирую фьючерсные пары на Binance\\.\\.\\.\\.\n"
        "Это может занять 30\\-60 секунд",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        # Initialize SuperSignals
        analyzer = SuperSignals()

        # Get TOP-5 signals in "futures" mode
        top5 = await analyzer.scan(mode="futures")

        # Get counts for message
        scanned_count = 200  # Approximate futures pairs count
        filtered_count = 30  # TOP_CANDIDATES

        # Format message
        message_text = analyzer.format_message(
            top5, scanned_count, filtered_count, mode="futures"
        )

        # Close analyzer
        await analyzer.close()

        # Send result
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Обновить", callback_data="signals_futures"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 К выбору", callback_data="super_signals"
                    ),
                    InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
                ],
            ]
        )

        await callback.message.edit_text(
            message_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error in super signals (futures mode): {e}", exc_info=True)

        error_text = (
            "❌ *Ошибка супер сигналов*\n\n"
            "Произошла ошибка при сканировании фьючерсных пар\\.\n"
            "Попробуйте позже или используйте режим всех монет\\.\n\n"
            f"_Ошибка: {str(e).replace('.', '\\.').replace('-', '\\-')}_"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="super_signals"
                    ),
                ],
            ]
        )

        try:
            await callback.message.edit_text(
                error_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass


# ============================================
# Message formatting constants
# ============================================

# Section divider used in signal messages
MESSAGE_SECTION_DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Maximum length for each message part (Telegram limit is 4096, we use 3900 for safety margin)
MAX_MESSAGE_PART_LENGTH = 3900


async def send_signal_in_parts(
    message_or_callback, symbol: str, signal_text: str
) -> None:
    """
    Send signal message in multiple parts to avoid MESSAGE_TOO_LONG error.
    Telegram has a 4096 character limit per message.

    Args:
        message_or_callback: Message or CallbackQuery object
        symbol: Symbol being analyzed
        signal_text: Full signal text from analyzer
    """
    # Check if message is already short enough
    if len(signal_text) <= 4000:
        # Can send in one message
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💰 Цена", callback_data="price_" + symbol.lower()
                    ),
                    InlineKeyboardButton(
                        text="🔄 Обновить", callback_data="signal_" + symbol.lower()
                    ),
                ],
                [
                    InlineKeyboardButton(text="🔙 Назад", callback_data="menu_signals"),
                    InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
                ],
            ]
        )

        try:
            if isinstance(message_or_callback, CallbackQuery):
                await safe_send_message(
                    message_or_callback.message.edit_text,
                    signal_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await safe_send_message(
                    message_or_callback.answer,
                    signal_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
        except TelegramBadRequest as e:
            if "message to edit not found" in str(e):
                # Fallback: send as new message
                bot = (
                    message_or_callback.bot
                    if isinstance(message_or_callback, CallbackQuery)
                    else message_or_callback.bot
                )
                chat_id = (
                    message_or_callback.message.chat.id
                    if isinstance(message_or_callback, CallbackQuery)
                    else message_or_callback.chat.id
                )
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=signal_text,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except TelegramBadRequest as parse_error:
                    if "can't parse entities" in str(parse_error).lower():
                        await bot.send_message(
                            chat_id=chat_id, text=signal_text, reply_markup=keyboard
                        )
        return

    # Message is too long - split into parts
    # Find natural split points based on section markers
    parts = []

    # Try to split at section boundaries
    sections = signal_text.split(MESSAGE_SECTION_DIVIDER)

    current_part = ""
    for i, section in enumerate(sections):
        # Add section divider back except for first section
        if i > 0:
            test_part = current_part + MESSAGE_SECTION_DIVIDER + section
        else:
            test_part = current_part + section

        # Check if adding this section would exceed limit
        if len(test_part) > MAX_MESSAGE_PART_LENGTH:  # Leave some margin
            if current_part:
                parts.append(current_part)
            current_part = section
        else:
            current_part = test_part

    # Add remaining content
    if current_part:
        parts.append(current_part)

    # Send parts
    bot = (
        message_or_callback.bot
        if isinstance(message_or_callback, CallbackQuery)
        else message_or_callback.bot
    )
    chat_id = (
        message_or_callback.message.chat.id
        if isinstance(message_or_callback, CallbackQuery)
        else message_or_callback.chat.id
    )

    # First part - replace original message if callback
    if isinstance(message_or_callback, CallbackQuery) and parts:
        try:
            await safe_send_message(
                message_or_callback.message.edit_text,
                parts[0],
                parse_mode=ParseMode.MARKDOWN,
            )
        except TelegramBadRequest:
            # Fallback: send as new message
            try:
                await bot.send_message(
                    chat_id=chat_id, text=parts[0], parse_mode=ParseMode.MARKDOWN
                )
            except TelegramBadRequest as parse_error:
                if "can't parse entities" in str(parse_error).lower():
                    await bot.send_message(chat_id=chat_id, text=parts[0])
        parts = parts[1:]  # Remove first part

    # Send remaining parts as separate messages
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1

        # Add keyboard to last message only
        if is_last:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💰 Цена", callback_data="price_" + symbol.lower()
                        ),
                        InlineKeyboardButton(
                            text="🔄 Обновить", callback_data="signal_" + symbol.lower()
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад", callback_data="menu_signals"
                        ),
                        InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
                    ],
                ]
            )
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=part,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except TelegramBadRequest as parse_error:
                if "can't parse entities" in str(parse_error).lower():
                    await bot.send_message(
                        chat_id=chat_id, text=part, reply_markup=keyboard
                    )
        else:
            try:
                await bot.send_message(
                    chat_id=chat_id, text=part, parse_mode=ParseMode.MARKDOWN
                )
            except TelegramBadRequest as parse_error:
                if "can't parse entities" in str(parse_error).lower():
                    await bot.send_message(chat_id=chat_id, text=part)


@router.callback_query(lambda c: c.data.startswith("signal_"))
async def callback_signal_coin(callback: CallbackQuery):
    symbol = callback.data.replace("signal_", "").upper()
    user_id = callback.from_user.id

    # Показываем индикатор загрузки
    await callback.answer("⏳ Анализирую данные...")
    await callback.message.edit_text(
        "⏳ *Анализирую данные...*\n\nПодождите несколько секунд",
        parse_mode=ParseMode.MARKDOWN,
    )

    # First, check pending signals for this symbol
    try:
        check_results = await signal_tracker.check_pending_signals_for_symbol(
            user_id, symbol
        )

        # Show notification if any signals were checked
        if check_results["checked"] > 0:
            update_msg = f"🔄 Проверено {check_results['checked']} сигналов: "
            update_msg += (
                f"✅ {check_results['wins']} win, ❌ {check_results['losses']} loss"
            )
            # Note: callback.answer was already called above, so we'll show this in the message
            logger.info(
                f"Checked {check_results['checked']} pending signals for {symbol}: {check_results}"
            )
    except Exception as e:
        logger.error(f"Error checking pending signals for {symbol}: {e}", exc_info=True)

    # Получаем текущую цену для проверки предыдущего сигнала
    try:
        price_data = await get_price_multi_api(symbol)
        current_price = (
            price_data.get("price_usd", 0) if price_data.get("success") else 0
        )
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
        current_price = 0

    # Проверяем результат предыдущего сигнала
    previous_result = None
    if current_price > 0:
        try:
            previous_result = signal_tracker.check_previous_signal(
                user_id=user_id, symbol=symbol, current_price=current_price
            )
        except Exception as e:
            logger.error(f"Error checking previous signal: {e}", exc_info=True)

    # Получаем AI сигнал
    try:
        signal_text = await ai_signal_analyzer.analyze_coin(symbol)
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
        signal_text = (
            "❌ *Ошибка анализа*\n\n"
            f"Произошла ошибка при анализе {symbol}.\n"
            "Попробуйте позже."
        )

        # Send error message
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔙 Назад", callback_data="menu_signals"),
                    InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
                ],
            ]
        )

        try:
            await callback.message.edit_text(
                signal_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass
        return

    # Note: Previous signal information is now tracked in statistics, not displayed in each message

    # Сохраняем новый сигнал
    try:
        signal_params = await ai_signal_analyzer.get_signal_params(symbol)
        if signal_params:
            signal_tracker.save_signal(
                user_id=user_id,
                symbol=symbol,
                direction=signal_params["direction"],
                entry_price=signal_params["entry_price"],
                target1_price=signal_params["target1_price"],
                target2_price=signal_params["target2_price"],
                stop_loss_price=signal_params["stop_loss_price"],
                probability=signal_params["probability"],
            )
            logger.info(f"Saved signal for user {user_id}, {symbol}")
    except Exception as e:
        logger.error(f"Error saving signal: {e}", exc_info=True)

    # Send signal (possibly in multiple parts)
    try:
        await send_signal_in_parts(callback, symbol, signal_text)
    except Exception as e:
        logger.error(f"Error sending signal: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при отправке сигнала", show_alert=True)


@router.callback_query(lambda c: c.data == "show_stats_menu")
async def show_stats_menu(callback: CallbackQuery):
    """Показать меню выбора монеты для статистики."""
    await callback.message.delete()

    text = "📊 Статистика по монете\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "Выберите монету:"

    new_msg = await callback.message.answer(
        text, reply_markup=get_stats_coins_keyboard(), parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("stats_"))
async def show_coin_statistics(callback: CallbackQuery):
    """Показать статистику по выбранной монете."""
    coin = callback.data.replace("stats_", "")
    user_id = callback.from_user.id

    await callback.message.delete()

    # Показываем индикатор загрузки
    loading_msg = await callback.message.answer(
        "⏳ Загружаю статистику...", parse_mode=ParseMode.MARKDOWN
    )

    try:
        # First, check all pending signals for this coin
        check_results = await signal_tracker.check_pending_signals_for_symbol(
            user_id, coin
        )

        # Show alert if any signals were checked
        if check_results["checked"] > 0:
            update_msg = f"🔄 Проверено {check_results['checked']} сигналов: "
            update_msg += (
                f"✅ {check_results['wins']} win, ❌ {check_results['losses']} loss"
            )
            await callback.answer(update_msg, show_alert=True)

        # Получаем статистику по монете
        stats = signal_tracker.get_coin_stats(user_id, coin)

        if stats["total"] == 0:
            text = f"""
📊 СТАТИСТИКА {coin}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

_У вас пока нет сигналов по этой монете._

Нажмите на монету в разделе Сигналы, чтобы начать отслеживание!
━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        else:
            # Используем новую функцию generate_progress_bar
            progress_bar = generate_progress_bar(stats["win_rate"])

            text = f"""
📊 СТАТИСТИКА {coin}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Всего сигналов: {stats["total"]}
✅ Успешных: {stats["wins"]}
❌ Убыточных: {stats["losses"]}
⏳ В ожидании: {stats["pending"]}

🎯 Win Rate: {stats["win_rate"]:.1f}%
{progress_bar}

📈 Общий P/L: {stats["total_pl"]:+.1f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="show_stats_menu")]
            ]
        )

        await loading_msg.edit_text(
            text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.error(f"Error getting coin stats for {coin}: {e}", exc_info=True)

        text = f"""
❌ Ошибка

Не удалось загрузить статистику для {coin}.
"""

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="show_stats_menu")]
            ]
        )

        await loading_msg.edit_text(
            text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
        )

    await callback.answer()


@router.callback_query(lambda c: c.data == "back_to_signals")
async def back_to_signals(callback: CallbackQuery):
    """Вернуться в меню сигналов из статистики."""
    await callback.message.delete()

    text = "🤖 AI Сигналы\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "Выберите монету:"

    new_msg = await callback.message.answer(
        text, reply_markup=get_signals_keyboard(), parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu_market")
async def callback_market(callback: CallbackQuery):
    await callback.answer("⏳ Загружаю...")
    await callback.message.edit_text(
        "⏳ *Загружаю рынок...*", parse_mode=ParseMode.MARKDOWN
    )

    data = await get_market_data()

    if "error" in data:
        text = "❌ Не удалось загрузить"
    else:
        cap = format_number(data["total_market_cap"])
        vol = format_number(data["total_volume"])
        btc_dom = str(round(data["btc_dominance"], 1)) + "%"
        eth_dom = str(round(data["eth_dominance"], 1)) + "%"
        coins = str(data["active_coins"])

        text = "📊 *Обзор рынка*\n\n"
        text = text + "💰 Total Cap: *" + cap + "*\n"
        text = text + "📈 24h Volume: *" + vol + "*\n\n"
        text = text + "₿ BTC Dominance: *" + btc_dom + "*\n"
        text = text + "⟠ ETH Dominance: *" + eth_dom + "*\n\n"
        text = text + "🪙 Активных монет: *" + coins + "*"

    await callback.message.edit_text(
        text, reply_markup=get_back_keyboard(), parse_mode=ParseMode.MARKDOWN
    )


@router.callback_query(lambda c: c.data == "menu_whale")
async def callback_whale(callback: CallbackQuery):
    """Обработка callback для меню Whale Tracker - показать меню выбора сети."""
    text = "🐋 *Трекер китов*\n\n"
    text = text + "Отслеживание крупных транзакций:\n\n"
    text = text + "• Депозиты на биржи\n"
    text = text + "• Выводы с бирж\n"
    text = text + "• Whale-to-whale переводы\n\n"
    text = text + "🔍 _Анализ в реальном времени_\n\n"
    text = text + "👇 Выбери монету:"
    await callback.message.edit_text(
        text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu_portfolio")
async def callback_portfolio(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data="portfolio_add")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )
    text = "💼 *Мой портфель*\n\n"
    text = text + "_Портфель пуст_\n\n"
    text = text + "Добавь активы для отслеживания:\n\n"
    text = text + "• 💵 Общая стоимость\n"
    text = text + "• 📈 Прибыль/убыток\n"
    text = text + "• 📊 Распределение"
    await callback.message.edit_text(
        text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu_settings")
async def callback_settings(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 Уведомления", callback_data="settings_notify"
                ),
                InlineKeyboardButton(
                    text="💱 Валюта", callback_data="settings_currency"
                ),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )
    text = "⚙️ *Настройки*\n\n"
    text = text + "🔔 Уведомления: ВКЛ\n"
    text = text + "💱 Валюта: USD\n"
    text = text + "🌐 Язык: Русский"
    await callback.message.edit_text(
        text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery):
    """Возврат в главное меню."""
    user = callback.from_user
    name = user.first_name if user.first_name else "друг"
    await callback.message.edit_text(
        get_welcome_text(name),
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    await callback.answer()


# ============================================
# Handlers for Gems (DEX Scanner)
# ============================================


@router.callback_query(lambda c: c.data == "gems")
async def gems_menu(callback: CallbackQuery):
    """Показывает меню выбора сети для сканирования гемов."""
    await callback.message.edit_text(
        "💎 *Новые гемы*\n\n"
        "Поиск свежих токенов на DEX\n"
        "Возраст до 7 дней, капа до $2M\n\n"
        "Выберите сеть:",
        reply_markup=get_gems_network_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("gems_"))
async def gems_network(callback: CallbackQuery):
    """Сканирует выбранную сеть на новые гемы."""
    network = callback.data.replace("gems_", "")

    network_names = {
        "solana": "☀️ Solana",
        "base": "🔵 Base",
        "ethereum": "💎 Ethereum",
        "bsc": "🟡 BSC",
    }

    await callback.message.edit_text(
        f"⏳ Сканирую {network_names.get(network, network)}...\n\n"
        "Это может занять 10-20 секунд"
    )
    await callback.answer()

    try:
        scanner = GemScanner()
        gems = await scanner.scan(network, limit=5)
        message = scanner.format_gems_message(gems, network)
        await scanner.close()

        # Отправляем без форматирования для избежания проблем с экранированием
        await callback.message.edit_text(
            message,
            parse_mode=None,  # Без форматирования для стабильности
        )
    except Exception as e:
        logger.error(f"Gems scan error: {e}")
        await callback.message.edit_text(f"❌ Ошибка сканирования: {str(e)}")


@router.callback_query(lambda c: c.data == "menu_back")
async def callback_back(callback: CallbackQuery):
    user = callback.from_user
    name = user.first_name if user.first_name else "друг"
    await callback.message.edit_text(
        get_welcome_text(name),
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    await callback.answer()


@router.callback_query()
async def callback_unknown(callback: CallbackQuery):
    await callback.answer("🔜 Скоро!")


# ============================================
# Обработка текстовых сообщений с символами монет
# ============================================


@router.message()
async def handle_text_coin(message: Message):
    """Обработка текстовых сообщений с символами монет."""
    if not message.text:
        return

    text = message.text.strip()

    # Проверяем формат: только короткие сообщения (1-6 символов) без пробелов
    # Это предотвращает обработку обычных сообщений
    if len(text) > 6 or " " in text:
        return

    # Проверяем, есть ли такой символ в COINS
    coin_key = text.lower()
    if coin_key in COINS:
        await send_quick_price(message, coin_key)


def create_bot() -> Tuple[Bot, Dispatcher]:
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Бот создан с Multi-API Manager")
    return bot, dp


async def on_startup(bot: Bot):
    logger.info("Gheezy Crypto Bot запущен с 5 API")
    for admin_id in settings.telegram_admin_ids:
        try:
            text = "🚀 *Gheezy Crypto* запущен!"
            await bot.send_message(admin_id, text, parse_mode=ParseMode.MARKDOWN)
        except:
            pass


async def on_shutdown(bot: Bot):
    logger.info("Gheezy Crypto Bot остановлен")
    await signal_analyzer.close()
    await defi_aggregator.close()
    await whale_tracker.close()
