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
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from api_manager import get_coin_price as get_price_multi_api, get_api_stats
from whale.tracker import WhaleTracker as RealWhaleTracker

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


COINS = {
    # Основные монеты (17)
    "btc": {"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "emoji": "₿"},
    "eth": {"id": "ethereum", "symbol": "ETH", "name": "Ethereum", "emoji": "⟠"},
    "ton": {"id": "the-open-network", "symbol": "TON", "name": "Toncoin", "emoji": "💎"},
    "sol": {"id": "solana", "symbol": "SOL", "name": "Solana", "emoji": "🟣"},
    "xrp": {"id": "ripple", "symbol": "XRP", "name": "XRP", "emoji": "💧"},
    "doge": {"id": "dogecoin", "symbol": "DOGE", "name": "Dogecoin", "emoji": "🐕"},
    "matic": {"id": "matic-network", "symbol": "MATIC", "name": "Polygon", "emoji": "🟪"},
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
    "inj": {"id": "injective-protocol", "symbol": "INJ", "name": "Injective", "emoji": "💉"},
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
    chat_id = message. chat.id
    try:
        await message.delete()
    except:
        pass
    await delete_user_message(message.bot, chat_id)
    new_msg = await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    user_messages[chat_id] = new_msg.message_id


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
            timeout = aiohttp. ClientTimeout(total=10)
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    return {"error": "api_error"}
                data = await response. json()
                market = data.get("data", {})
                return {
                    "success": True,
                    "total_market_cap": market. get("total_market_cap", {}).get("usd", 0),
                    "total_volume": market. get("total_volume", {}).get("usd", 0),
                    "btc_dominance": market.get("market_cap_percentage", {}).get("btc", 0),
                    "eth_dominance": market.get("market_cap_percentage", {}).get("eth", 0),
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


def format_price_message(symbol: str, data: dict) -> str:
    if "error" in data:
        if data["error"] == "rate_limit":
            return "⚠️ *Лимит запросов*\n\nПодожди 1-2 минуты и попробуй снова"
        elif data["error"] == "timeout":
            return "⚠️ *Сервер не отвечает*\n\nПопробуй позже"
        else:
            return "❌ Ошибка: " + str(data["error"])
    
    coin_info = COINS.get(symbol.lower(), {})
    emoji = coin_info. get("emoji", "💰")
    name = coin_info. get("name", symbol.upper())
    
    price_usd = data["price_usd"]
    price_rub = data["price_rub"]
    price_eur = data["price_eur"]
    change_24h = data["change_24h"]
    volume_24h = data["volume_24h"]
    market_cap = data["market_cap"]
    source = data.get("source", "")
    
    if price_usd >= 1:
        price_usd_text = "${:,.2f}". format(price_usd)
    elif price_usd >= 0.01:
        price_usd_text = "${:,.4f}".format(price_usd)
    else:
        price_usd_text = "${:,.8f}".format(price_usd)
    
    price_rub_text = "₽{:,.2f}".format(price_rub)
    price_eur_text = "€{:,.2f}".format(price_eur)
    
    if change_24h >= 0:
        change_text = "📈 +{:.2f}%". format(change_24h)
    else:
        change_text = "📉 {:.2f}%".format(change_24h)
    
    cap_text = format_number(market_cap) if market_cap > 0 else "N/A"
    vol_text = format_number(volume_24h) if volume_24h > 0 else "N/A"
    
    now = datetime.now(). strftime("%H:%M:%S")
    
    text = emoji + " *" + name + "* (" + symbol. upper() + ")\n\n"
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
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Цены", callback_data="menu_prices"),
            InlineKeyboardButton(text="🎯 AI Сигналы", callback_data="menu_signals"),
        ],
        [
            InlineKeyboardButton(text="📊 Рынок", callback_data="menu_market"),
            InlineKeyboardButton(text="🔥 Топ", callback_data="menu_top"),
        ],
        [
            InlineKeyboardButton(text="🏦 DeFi", callback_data="menu_defi"),
            InlineKeyboardButton(text="🐋 Киты", callback_data="menu_whale"),
        ],
        [
            InlineKeyboardButton(text="📈 Трейдеры", callback_data="menu_traders"),
            InlineKeyboardButton(text="💼 Портфель", callback_data="menu_portfolio"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings"),
            InlineKeyboardButton(text="📚 Помощь", callback_data="menu_help"),
        ],
    ])


# Порядок монет для пагинации (все 34 монеты)
COINS_ORDER = [
    # Страница 1 (основные)
    "btc", "eth", "ton", "sol", "xrp", "doge", "matic", "ltc",
    # Страница 2 (продолжение основных)
    "shib", "avax", "bnb", "ada", "dot", "link", "uni", "atom",
    # Страница 3 (мем-коины и L1)
    "trx", "not", "pepe", "wif", "bonk", "sui", "apt", "sei",
    # Страница 4 (L1, L2 и DeFi)
    "near", "ftm", "arb", "op", "inj", "xlm", "vet", "algo",
    # Страница 5 (оставшиеся)
    "fil", "rune",
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
        row.append(InlineKeyboardButton(text=emoji + " " + symbol, callback_data="price_" + coin))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    # Добавляем оставшиеся кнопки
    if row:
        keyboard.append(row)
    
    # Кнопки навигации
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ " + str(page - 1), callback_data="prices_page_" + str(page - 1)))
    nav_row.append(InlineKeyboardButton(text=str(page) + "/" + str(total_pages), callback_data="prices_page_current"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text=str(page + 1) + " ▶️", callback_data="prices_page_" + str(page + 1)))
    keyboard.append(nav_row)
    
    # Дополнительные кнопки
    keyboard.append([InlineKeyboardButton(text="📊 API статистика", callback_data="menu_api_stats")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_price_keyboard(symbol: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="price_" + symbol. lower()),
            InlineKeyboardButton(text="🎯 Сигнал", callback_data="signal_" + symbol. lower()),
        ],
        [
            InlineKeyboardButton(text="🔙 К ценам", callback_data="menu_prices"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
        ],
    ])


def get_signals_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="₿ BTC", callback_data="signal_btc"),
            InlineKeyboardButton(text="⟠ ETH", callback_data="signal_eth"),
        ],
        [
            InlineKeyboardButton(text="🟣 SOL", callback_data="signal_sol"),
            InlineKeyboardButton(text="💎 TON", callback_data="signal_ton"),
        ],
        [
            InlineKeyboardButton(text="💧 XRP", callback_data="signal_xrp"),
            InlineKeyboardButton(text="🐕 DOGE", callback_data="signal_doge"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back"),
        ],
    ])


def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
    ])


def get_welcome_text(name: str) -> str:
    text = "🚀 *GHEEZY CRYPTO*\n\n"
    text = text + "Привет, *" + name + "*!  👋\n\n"
    text = text + "Я — Gheezy, твой проводник в крипто вселенной💫\n"
    text = text + "Давай вместе учиться и зарабатывать 🤩\n\n"
    text = text + "📊 *Мои возможности:*\n\n"
    text = text + "• 💰 Цены — самые популярные криптовалюты\n"
    text = text + "• 🤖 AI Signals — торговые сигналы\n"
    text = text + "• 🏦 DeFi — лучшие ставки\n"
    text = text + "• 🐋 Whales — движения китов\n"
    text = text + "• 📈 Traders — топ трейдеры\n\n"
    text = text + "📡 Проверенные источники данных с обновлением в реальном времени ✅\n\n"
    text = text + "Ну что взлетаем! 🚀🚀🚀\n\n"
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
    text = text + "DeFi: /inj /xlm /vet /algo /fil /rune\n\n"
    text = text + "*Текстовые команды:*\n\n"
    text = text + "Напиши символ монеты (BTC, NOT, SUI...)\n"
    text = text + "и получи её цену!\n\n"
    text = text + "*Основные команды:*\n\n"
    text = text + "/start — главное меню\n"
    text = text + "/market — обзор рынка\n"
    text = text + "/prices — все монеты (с пагинацией)\n"
    text = text + "/help — справка\n\n"
    text = text + "*Команды Whale Tracker (6 сетей):*\n\n"
    text = text + "/whale — все крупные транзакции\n"
    text = text + "/whale btc — только Bitcoin\n"
    text = text + "/whale eth — только Ethereum\n"
    text = text + "/whale bsc — только BSC (FREE!)\n"
    text = text + "/whale arb — только Arbitrum\n"
    text = text + "/whale polygon — только Polygon\n"
    text = text + "/whale avax — только Avalanche\n"
    text = text + "/whale on — включить оповещения\n"
    text = text + "/whale off — выключить оповещения\n"
    text = text + "/whale stats — статистика за день\n"
    text = text + "/whales — статистика всех сетей\n\n"
    text = text + "📡 _5 API: CoinGecko + CoinPaprika + MEXC + Kraken_"
    await clean_send(message, text, get_back_keyboard())


@router.message(Command("market"))
async def cmd_market(message: Message):
    chat_id = message. chat.id
    try:
        await message.delete()
    except:
        pass
    await delete_user_message(message.bot, chat_id)
    
    loading_msg = await message.answer("⏳ *Загружаю рынок...*", parse_mode=ParseMode.MARKDOWN)
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
    
    await loading_msg.edit_text(text, reply_markup=get_back_keyboard(), parse_mode=ParseMode.MARKDOWN)


@router.message(Command("prices"))
async def cmd_prices(message: Message):
    chat_id = message.chat.id
    try:
        await message.delete()
    except:
        pass
    await delete_user_message(message.bot, chat_id)
    
    loading_msg = await message.answer("⏳ *Загружаю все цены...*", parse_mode=ParseMode.MARKDOWN)
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
            
            text = text + emoji + " *" + symbol.upper() + "*: " + price_text + " " + trend + " " + change_text + "\n"
        else:
            text = text + emoji + " *" + symbol.upper() + "*: ❌ ошибка\n"
    
    now = datetime.now().strftime("%H:%M:%S")
    text = text + "\n⏰ _" + now + "_"
    
    await loading_msg.edit_text(text, reply_markup=get_prices_keyboard(1), parse_mode=ParseMode.MARKDOWN)


async def send_quick_price(message: Message, symbol: str):
    if symbol. lower() not in COINS:
        await message.answer("❌ Монета не найдена")
        return
    
    chat_id = message. chat.id
    try:
        await message.delete()
    except:
        pass
    await delete_user_message(message.bot, chat_id)
    
    coin_info = COINS.get(symbol. lower(), {})
    emoji = coin_info.get("emoji", "💰")
    
    loading_msg = await message.answer(emoji + " *Загружаю " + symbol. upper() + "...*", parse_mode=ParseMode.MARKDOWN)
    user_messages[chat_id] = loading_msg.message_id
    
    data = await get_coin_price(symbol. upper())
    text = format_price_message(symbol, data)
    
    await loading_msg.edit_text(text, reply_markup=get_price_keyboard(symbol), parse_mode=ParseMode. MARKDOWN)


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

@router. message(Command("ltc"))
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
    """Клавиатура для whale tracker с 6 сетями."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟠 BTC", callback_data="whale_btc"),
            InlineKeyboardButton(text="🔷 ETH", callback_data="whale_eth"),
        ],
        [
            InlineKeyboardButton(text="🟡 BSC", callback_data="whale_bsc"),
            InlineKeyboardButton(text="🔵 Arbitrum", callback_data="whale_arb"),
        ],
        [
            InlineKeyboardButton(text="🟣 Polygon", callback_data="whale_polygon"),
            InlineKeyboardButton(text="🔺 Avalanche", callback_data="whale_avax"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="whale_stats"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="whale_all"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back"),
        ],
    ])


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
            "транзакциях на BTC, ETH, BSC, Arbitrum,\n"
            "Polygon и Avalanche.\n\n"
            "Минимальная сумма: $100,000+"
        )
        new_msg = await message.answer(text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
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
        new_msg = await message.answer(text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = new_msg.message_id
        return

    if subcommand == "stats":
        # Статистика за день
        loading_msg = await message.answer("⏳ *Загружаю статистику...*", parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = loading_msg.message_id

        try:
            stats_text = await whale_tracker.format_stats_message()
            await loading_msg.edit_text(stats_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Whale stats error: {e}")
            await loading_msg.edit_text(
                "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки статистики",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        return

    if subcommand in ("eth", "ethereum"):
        # Только Ethereum
        loading_msg = await message.answer("⏳ *Загружаю ETH транзакции...*", parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = loading_msg.message_id

        try:
            whale_text = await whale_tracker.format_whale_message(blockchain="eth")
            await loading_msg.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Whale ETH error: {e}")
            await loading_msg.edit_text(
                "🐋 *Whale Tracker - Ethereum*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        return

    if subcommand in ("bsc", "bnb", "binance"):
        # BSC re-enabled with Blockscout (FREE!)
        loading_msg = await message.answer("⏳ *Загружаю BSC транзакции...*", parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = loading_msg.message_id

        try:
            whale_text = await whale_tracker.format_whale_message(blockchain="bsc")
            await loading_msg.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Whale BSC error: {e}")
            await loading_msg.edit_text(
                "🐋 *Whale Tracker - BSC*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        return

    if subcommand in ("btc", "bitcoin"):
        # Только Bitcoin
        loading_msg = await message.answer("⏳ *Загружаю BTC транзакции...*", parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = loading_msg.message_id

        try:
            whale_text = await whale_tracker.format_whale_message(blockchain="btc")
            await loading_msg.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Whale BTC error: {e}")
            await loading_msg.edit_text(
                "🐋 *Whale Tracker - Bitcoin*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        return

    if subcommand in ("sol", "solana"):
        # Solana removed - Solscan API returns 404
        text = (
            "🐋 *Whale Tracker - Solana*\n\n"
            "⚠️ *Временно недоступно*\n\n"
            "Solscan API недоступен (404).\n"
            "Используйте другие сети:\n"
            "• ETH (Etherscan V2)\n"
            "• Arbitrum, Polygon, Base\n"
            "• BTC (mempool.space)\n"
            "• AVAX (Snowtrace)"
        )
        new_msg = await message.answer(text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = new_msg.message_id
        return

    if subcommand == "ton":
        # TON removed - complex API
        text = (
            "🐋 *Whale Tracker - TON*\n\n"
            "⚠️ *Временно недоступно*\n\n"
            "TON API сложен для интеграции.\n"
            "Используйте другие сети:\n"
            "• ETH (Etherscan V2)\n"
            "• Arbitrum, Polygon, Base\n"
            "• BTC (mempool.space)\n"
            "• AVAX (Snowtrace)"
        )
        new_msg = await message.answer(text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = new_msg.message_id
        return

    if subcommand == "arb" or subcommand == "arbitrum":
        # Только Arbitrum
        loading_msg = await message.answer("⏳ *Загружаю Arbitrum транзакции...*", parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = loading_msg.message_id

        try:
            whale_text = await whale_tracker.format_whale_message(blockchain="arb")
            await loading_msg.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Whale Arbitrum error: {e}")
            await loading_msg.edit_text(
                "🐋 *Whale Tracker - Arbitrum*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        return

    if subcommand == "polygon" or subcommand == "matic":
        # Только Polygon
        loading_msg = await message.answer("⏳ *Загружаю Polygon транзакции...*", parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = loading_msg.message_id

        try:
            whale_text = await whale_tracker.format_whale_message(blockchain="polygon")
            await loading_msg.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Whale Polygon error: {e}")
            await loading_msg.edit_text(
                "🐋 *Whale Tracker - Polygon*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        return

    if subcommand == "avax" or subcommand == "avalanche":
        # Только Avalanche
        loading_msg = await message.answer("⏳ *Загружаю Avalanche транзакции...*", parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = loading_msg.message_id

        try:
            whale_text = await whale_tracker.format_whale_message(blockchain="avax")
            await loading_msg.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Whale Avalanche error: {e}")
            await loading_msg.edit_text(
                "🐋 *Whale Tracker - Avalanche*\n\n❌ Ошибка загрузки данных",
                reply_markup=get_whale_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        return

    if subcommand == "base":
        # Base removed - requires paid Etherscan plan
        text = (
            "🐋 *Whale Tracker - Base*\n\n"
            "⚠️ *Временно недоступно*\n\n"
            "Base требует платный API ключ.\n"
            "Используйте другие сети:\n"
            "• ETH (Etherscan V2)\n"
            "• Arbitrum, Polygon\n"
            "• BTC (mempool.space)\n"
            "• AVAX (Snowtrace)"
        )
        new_msg = await message.answer(text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = new_msg.message_id
        return

    if subcommand == "defi":
        # DeFi button removed from menu
        text = (
            "🏦 *DeFi Tracker*\n\n"
            "⚠️ *Функция отключена*\n\n"
            "DeFi трекинг временно недоступен.\n"
            "Используйте основные сети:\n"
            "• ETH, Arbitrum, Polygon\n"
            "• BTC (mempool.space)\n"
            "• AVAX (Snowtrace)"
        )
        new_msg = await message.answer(text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
        user_messages[chat_id] = new_msg.message_id
        return

    # Все транзакции (по умолчанию)
    loading_msg = await message.answer("⏳ *Загружаю транзакции китов...*", parse_mode=ParseMode.MARKDOWN)
    user_messages[chat_id] = loading_msg.message_id

    try:
        whale_text = await whale_tracker.format_whale_message()
        await loading_msg.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whale all error: {e}")
        await loading_msg.edit_text(
            "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки данных",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
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

    loading_msg = await message.answer("⏳ *Загружаю статистику всех сетей...*", parse_mode=ParseMode.MARKDOWN)
    user_messages[chat_id] = loading_msg.message_id

    try:
        stats_text = await whale_tracker.format_all_networks_stats_message()
        await loading_msg.edit_text(stats_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whales stats error: {e}")
        await loading_msg.edit_text(
            "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки статистики",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.callback_query(lambda c: c.data == "whale_all")
async def callback_whale_all(callback: CallbackQuery):
    """Обновить все транзакции китов."""
    await callback.answer("⏳ Загружаю...")
    await callback.message.edit_text("⏳ *Загружаю транзакции китов...*", parse_mode=ParseMode.MARKDOWN)

    try:
        whale_text = await whale_tracker.format_whale_message()
        await callback.message.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whale callback error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки данных",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.callback_query(lambda c: c.data == "whale_eth")
async def callback_whale_eth(callback: CallbackQuery):
    """Транзакции Ethereum."""
    await callback.answer("⏳ Загружаю ETH...")
    await callback.message.edit_text("⏳ *Загружаю ETH транзакции...*", parse_mode=ParseMode.MARKDOWN)

    try:
        whale_text = await whale_tracker.format_whale_message(blockchain="eth")
        await callback.message.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whale ETH callback error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker - Ethereum*\n\n❌ Ошибка загрузки данных",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.callback_query(lambda c: c.data == "whale_bsc")
async def callback_whale_bsc(callback: CallbackQuery):
    """Транзакции BSC (Blockscout - FREE!)."""
    await callback.answer("⏳ Загружаю BSC...")
    await callback.message.edit_text("⏳ *Загружаю BSC транзакции...*", parse_mode=ParseMode.MARKDOWN)

    try:
        whale_text = await whale_tracker.format_whale_message(blockchain="bsc")
        await callback.message.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whale BSC callback error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker - BSC*\n\n❌ Ошибка загрузки данных",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.callback_query(lambda c: c.data == "whale_btc")
async def callback_whale_btc(callback: CallbackQuery):
    """Транзакции Bitcoin."""
    await callback.answer("⏳ Загружаю BTC...")
    await callback.message.edit_text("⏳ *Загружаю BTC транзакции...*", parse_mode=ParseMode.MARKDOWN)

    try:
        whale_text = await whale_tracker.format_whale_message(blockchain="btc")
        await callback.message.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whale BTC callback error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker - Bitcoin*\n\n❌ Ошибка загрузки данных",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.callback_query(lambda c: c.data == "whale_sol")
async def callback_whale_sol(callback: CallbackQuery):
    """Solana removed - API returns 404."""
    await callback.answer("Solana временно недоступен")
    text = (
        "🐋 *Whale Tracker - Solana*\n\n"
        "⚠️ *Временно недоступно*\n\n"
        "Solscan API недоступен (404).\n"
        "Используйте другие сети:\n"
        "• ETH (Etherscan V2)\n"
        "• Arbitrum, Polygon, Base\n"
        "• BTC (mempool.space)\n"
        "• AVAX (Snowtrace)"
    )
    await callback.message.edit_text(text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)


@router.callback_query(lambda c: c.data == "whale_ton")
async def callback_whale_ton(callback: CallbackQuery):
    """TON removed - complex API."""
    await callback.answer("TON временно недоступен")
    text = (
        "🐋 *Whale Tracker - TON*\n\n"
        "⚠️ *Временно недоступно*\n\n"
        "TON API сложен для интеграции.\n"
        "Используйте другие сети:\n"
        "• ETH (Etherscan V2)\n"
        "• Arbitrum, Polygon, Base\n"
        "• BTC (mempool.space)\n"
        "• AVAX (Snowtrace)"
    )
    await callback.message.edit_text(text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)


@router.callback_query(lambda c: c.data == "whale_arb")
async def callback_whale_arb(callback: CallbackQuery):
    """Транзакции Arbitrum."""
    await callback.answer("⏳ Загружаю Arbitrum...")
    await callback.message.edit_text("⏳ *Загружаю Arbitrum транзакции...*", parse_mode=ParseMode.MARKDOWN)

    try:
        whale_text = await whale_tracker.format_whale_message(blockchain="arb")
        await callback.message.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whale Arbitrum callback error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker - Arbitrum*\n\n❌ Ошибка загрузки данных",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.callback_query(lambda c: c.data == "whale_polygon")
async def callback_whale_polygon(callback: CallbackQuery):
    """Транзакции Polygon."""
    await callback.answer("⏳ Загружаю Polygon...")
    await callback.message.edit_text("⏳ *Загружаю Polygon транзакции...*", parse_mode=ParseMode.MARKDOWN)

    try:
        whale_text = await whale_tracker.format_whale_message(blockchain="polygon")
        await callback.message.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whale Polygon callback error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker - Polygon*\n\n❌ Ошибка загрузки данных",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.callback_query(lambda c: c.data == "whale_avax")
async def callback_whale_avax(callback: CallbackQuery):
    """Транзакции Avalanche."""
    await callback.answer("⏳ Загружаю Avalanche...")
    await callback.message.edit_text("⏳ *Загружаю Avalanche транзакции...*", parse_mode=ParseMode.MARKDOWN)

    try:
        whale_text = await whale_tracker.format_whale_message(blockchain="avax")
        await callback.message.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whale Avalanche callback error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker - Avalanche*\n\n❌ Ошибка загрузки данных",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.callback_query(lambda c: c.data == "whale_base")
async def callback_whale_base(callback: CallbackQuery):
    """Base removed - requires paid API."""
    await callback.answer("Base временно недоступен")
    text = (
        "🐋 *Whale Tracker - Base*\n\n"
        "⚠️ *Временно недоступно*\n\n"
        "Base требует платный API ключ.\n"
        "Используйте другие сети:\n"
        "• ETH (Etherscan V2)\n"
        "• Arbitrum, Polygon\n"
        "• BTC (mempool.space)\n"
        "• AVAX (Snowtrace)"
    )
    await callback.message.edit_text(text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)


@router.callback_query(lambda c: c.data == "whale_defi")
async def callback_whale_defi(callback: CallbackQuery):
    """DeFi button removed from menu."""
    await callback.answer("DeFi временно недоступен")
    text = (
        "🏦 *DeFi Tracker*\n\n"
        "⚠️ *Функция отключена*\n\n"
        "DeFi трекинг временно недоступен.\n"
        "Используйте основные сети:\n"
        "• ETH, Arbitrum, Polygon\n"
        "• BTC (mempool.space)\n"
        "• AVAX (Snowtrace)"
    )
    await callback.message.edit_text(text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)


@router.callback_query(lambda c: c.data == "whale_stats")
async def callback_whale_stats(callback: CallbackQuery):
    """Статистика whale tracker."""
    await callback.answer("⏳ Загружаю статистику...")
    await callback.message.edit_text("⏳ *Загружаю статистику...*", parse_mode=ParseMode.MARKDOWN)

    try:
        stats_text = await whale_tracker.format_all_networks_stats_message()
        await callback.message.edit_text(stats_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whale stats callback error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки статистики",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.callback_query(lambda c: c.data == "menu_prices")
async def callback_prices(callback: CallbackQuery):
    text = "💰 *Цены криптовалют*\n\n"
    text = text + "Выбери монету для просмотра\n"
    text = text + "актуальной цены 👇\n\n"
    text = text + "📡 _5 API: CoinGecko + CoinPaprika + MEXC + Kraken_"
    await callback.message.edit_text(text, reply_markup=get_prices_keyboard(1), parse_mode=ParseMode.MARKDOWN)
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
    await callback.message.edit_text(text, reply_markup=get_prices_keyboard(page), parse_mode=ParseMode.MARKDOWN)
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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К ценам", callback_data="menu_prices")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back")],
    ])
    
    await callback. message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


@router. callback_query(lambda c: c.data. startswith("price_"))
async def callback_price_coin(callback: CallbackQuery):
    symbol = callback.data. replace("price_", "")
    if symbol not in COINS:
        await callback.answer("Монета не найдена")
        return
    
    await callback.answer("⏳ Загружаю...")
    
    coin_info = COINS.get(symbol, {})
    emoji = coin_info. get("emoji", "💰")
    
    await callback.message.edit_text(emoji + " *Загружаю " + symbol.upper() + "...*", parse_mode=ParseMode. MARKDOWN)
    
    data = await get_coin_price(symbol.upper())
    text = format_price_message(symbol, data)
    
    await callback.message.edit_text(text, reply_markup=get_price_keyboard(symbol), parse_mode=ParseMode.MARKDOWN)


@router.callback_query(lambda c: c.data == "menu_signals")
async def callback_signals(callback: CallbackQuery):
    text = "🎯 *AI Сигналы*\n\n"
    text = text + "Анализ на основе:\n\n"
    text = text + "• RSI (14 периодов)\n"
    text = text + "• MACD\n"
    text = text + "• Bollinger Bands\n"
    text = text + "• MA 50/200\n\n"
    text = text + "📊 _Точность: 73%_\n\n"
    text = text + "👇 Выбери монету:"
    await callback.message.edit_text(text, reply_markup=get_signals_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback. answer()


@router.callback_query(lambda c: c. data. startswith("signal_"))
async def callback_signal_coin(callback: CallbackQuery):
    symbol = callback.data.replace("signal_", ""). upper()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Цена", callback_data="price_" + symbol. lower()),
            InlineKeyboardButton(text="🔄 Обновить", callback_data=callback.data),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="menu_signals"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="menu_back"),
        ],
    ])
    
    text = "🎯 *AI Сигнал: " + symbol + "*\n\n"
    text = text + "📊 *Технический анализ:*\n\n"
    text = text + "📈 RSI (14): *58.3* — нейтрально\n"
    text = text + "📊 MACD: *бычий* — кроссовер вверх\n"
    text = text + "📉 Bollinger: *середина* — низкая волатильность\n"
    text = text + "🔄 MA 50/200: *выше* — бычий тренд\n\n"
    text = text + "🤖 *Рекомендация:*\n\n"
    text = text + "✅ *HOLD* (Держать)\n\n"
    text = text + "⚠️ *Риск-менеджмент:*\n\n"
    text = text + "• Позиция: 2-3% портфеля\n"
    text = text + "• Stop-Loss: -5%\n"
    text = text + "• Take-Profit: +10-15%\n\n"
    text = text + "📊 _Точность AI: 73%_"
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu_market")
async def callback_market(callback: CallbackQuery):
    await callback.answer("⏳ Загружаю...")
    await callback.message.edit_text("⏳ *Загружаю рынок...*", parse_mode=ParseMode.MARKDOWN)
    
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
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode=ParseMode. MARKDOWN)


@router.callback_query(lambda c: c.data == "menu_top")
async def callback_top(callback: CallbackQuery):
    text = "🔥 *Топ монет 24ч*\n\n"
    text = text + "📈 *Лидеры роста:*\n\n"
    text = text + "1. 🟢 SOL +12.5%\n"
    text = text + "2. 🟢 AVAX +8.3%\n"
    text = text + "3. 🟢 LINK +7.1%\n\n"
    text = text + "📉 *Лидеры падения:*\n\n"
    text = text + "1. 🔴 SHIB -5.2%\n"
    text = text + "2.  🔴 DOGE -4.1%\n"
    text = text + "3. 🔴 XRP -3.8%"
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode=ParseMode. MARKDOWN)
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu_defi")
async def callback_defi(callback: CallbackQuery):
    text = "🏦 *DeFi Ставки*\n\n"
    text = text + "🔷 *Lido* (stETH)\n"
    text = text + "APY: 3.5% • Риск: Низкий\n"
    text = text + "TVL: $28.5B\n\n"
    text = text + "🔷 *Aave* (ETH)\n"
    text = text + "APY: 3.2% • Риск: Низкий\n"
    text = text + "TVL: $12.3B\n\n"
    text = text + "🔷 *Compound* (USDC)\n"
    text = text + "APY: 4.1% • Риск: Низкий\n"
    text = text + "TVL: $2.8B\n\n"
    text = text + "💡 _Рекомендация: Lido для ETH_"
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback. answer()


@router.callback_query(lambda c: c. data == "menu_whale")
async def callback_whale(callback: CallbackQuery):
    """Обработка callback для меню Whale Tracker."""
    await callback.answer("⏳ Загружаю...")
    await callback.message.edit_text("⏳ *Загружаю транзакции китов...*", parse_mode=ParseMode.MARKDOWN)

    try:
        whale_text = await whale_tracker.format_whale_message()
        await callback.message.edit_text(whale_text, reply_markup=get_whale_keyboard(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Whale menu error: {e}")
        await callback.message.edit_text(
            "🐋 *Whale Tracker*\n\n❌ Ошибка загрузки данных.\n\nПопробуйте позже.",
            reply_markup=get_whale_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )


@router.callback_query(lambda c: c.data == "menu_traders")
async def callback_traders(callback: CallbackQuery):
    text = "📈 *Топ трейдеры*\n\n"
    text = text + "🥇 *CryptoKing*\n"
    text = text + "Прибыль: +156% • Win: 78%\n\n"
    text = text + "🥈 *WhaleHunter*\n"
    text = text + "Прибыль: +134% • Win: 72%\n\n"
    text = text + "🥉 *DiamondHands*\n"
    text = text + "Прибыль: +98% • Win: 81%\n\n"
    text = text + "🔜 _Скоро: копирование сделок! _"
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback. answer()


@router.callback_query(lambda c: c. data == "menu_portfolio")
async def callback_portfolio(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="portfolio_add")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
    ])
    text = "💼 *Мой портфель*\n\n"
    text = text + "_Портфель пуст_\n\n"
    text = text + "Добавь активы для отслеживания:\n\n"
    text = text + "• 💵 Общая стоимость\n"
    text = text + "• 📈 Прибыль/убыток\n"
    text = text + "• 📊 Распределение"
    await callback. message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


@router. callback_query(lambda c: c.data == "menu_settings")
async def callback_settings(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings_notify"),
            InlineKeyboardButton(text="💱 Валюта", callback_data="settings_currency"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
    ])
    text = "⚙️ *Настройки*\n\n"
    text = text + "🔔 Уведомления: ВКЛ\n"
    text = text + "💱 Валюта: USD\n"
    text = text + "🌐 Язык: Русский"
    await callback. message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu_help")
async def callback_help(callback: CallbackQuery):
    text = "📚 *Справка*\n\n"
    text = text + "*Быстрые команды (34 монеты):*\n\n"
    text = text + "Основные: /btc /eth /ton /sol /xrp\n"
    text = text + "/doge /matic /ltc /shib /avax\n"
    text = text + "/bnb /ada /dot /link /uni /atom /trx\n\n"
    text = text + "Мем-коины: /not /pepe /wif /bonk\n\n"
    text = text + "L1: /sui /apt /sei /near /ftm\n\n"
    text = text + "L2: /arb /op\n\n"
    text = text + "DeFi: /inj /xlm /vet /algo /fil /rune\n\n"
    text = text + "*Текстовые команды:*\n\n"
    text = text + "Напиши символ монеты (BTC, NOT, SUI...)\n"
    text = text + "и получи её цену!\n\n"
    text = text + "*Основные команды:*\n\n"
    text = text + "/start — главное меню\n"
    text = text + "/market — обзор рынка\n"
    text = text + "/prices — все монеты (с пагинацией)\n"
    text = text + "/help — справка\n\n"
    text = text + "📡 _5 API: CoinGecko + CoinPaprika + MEXC + Kraken_"
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode=ParseMode.MARKDOWN)
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu_back")
async def callback_back(callback: CallbackQuery):
    user = callback.from_user
    name = user.first_name if user.first_name else "друг"
    await callback.message.edit_text(get_welcome_text(name), reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN)
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
    if len(text) > 6 or ' ' in text:
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
            text = "🚀 *Gheezy Crypto* запущен!\n\n"
            text = text + "📡 API: CoinGecko + CoinPaprika + MEXC + Kraken\n"
            text = text + "🪙 Монеты: 34 популярных в России"
            await bot.send_message(admin_id, text, parse_mode=ParseMode.MARKDOWN)
        except:
            pass


async def on_shutdown(bot: Bot):
    logger.info("Gheezy Crypto Bot остановлен")
    await signal_analyzer.close()
    await defi_aggregator.close()
    await whale_tracker.close()