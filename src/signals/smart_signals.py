"""
Smart Signals - система умных сигналов для ТОП-3 монет.
"""

import logging
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import asyncio
import aiohttp
import statistics

from signals.exchanges.okx import OKXClient
from signals.exchanges.bybit import BybitClient
from signals.exchanges.gate import GateClient
from signals.scoring import (
    calculate_momentum_score, calculate_volume_score,
    calculate_trend_score, calculate_volatility_score,
    calculate_total_score, apply_score_bonuses,
    calculate_ema, calculate_adx, clamp
)
from config import settings

logger = logging.getLogger(__name__)


class SmartSignalAnalyzer:
    """
    Анализатор умных сигналов.
    
    Сканирует 500+ монет из CoinGecko, анализирует их по множеству факторов
    и выбирает ТОП-3 лучших сигналов.
    """
    
    # Настройки из конфига
    SCAN_LIMIT = getattr(settings, 'smart_signals_scan_limit', 500)
    MIN_VOLUME_USD = getattr(settings, 'smart_signals_min_volume', 5_000_000)
    MIN_MCAP_USD = getattr(settings, 'smart_signals_min_mcap', 10_000_000)
    MAX_SPREAD_PCT = getattr(settings, 'smart_signals_max_spread', 0.005) * 100  # Convert to percentage
    HYSTERESIS_TIME = getattr(settings, 'smart_signals_hysteresis_time', 900)
    HYSTERESIS_THRESHOLD = getattr(settings, 'smart_signals_hysteresis_threshold', 0.10)
    MAX_ANALYZE = getattr(settings, 'smart_signals_max_analyze', 100)
    
    # Исключенные символы (стейблкоины, wrapped токены, проблемные монеты)
    EXCLUDED_SYMBOLS = {
        # === СТЕЙБЛКОИНЫ ===
        'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'FDUSD', 'PYUSD', 'USDD', 
        'USDP', 'GUSD', 'FRAX', 'LUSD', 'USDJ', 'USDS', 'CUSD', 'SUSD',
        'USDN', 'USDX', 'USDK', 'MUSD', 'HUSD', 'OUSD', 'CEUR', 'EURS',
        'EURT', 'USDQ', 'RSV', 'PAX', 'USDL', 'USDB',
        
        # === WRAPPED ТОКЕНЫ ===
        'WETH', 'WBTC', 'WBNB', 'WSTETH', 'WBETH', 'CBBTC',
        'METH', 'EETH', 'WTRX', 'WAVAX',
        'WMATIC', 'WFTM', 'WONE', 'WCRO', 'WKCS', 'WROSE', 'WXDAI',
        'WGLMR', 'WMOVR', 'WEVMOS', 'WCANTO',
        
        # === LIQUID STAKING DERIVATIVES ===
        'STETH', 'RETH', 'CBETH', 'FRXETH', 'SFRXETH', 
        'MSOL', 'JITOSOL', 'BNSOL',
        'ANKRBNB', 'ANKRETH', 'MARINADE', 'LIDO',
        'STMATIC', 'MATICX', 'STKBNB', 'SNBNB', 'STKSOL',
        'STSOL', 'SCNSOL', 'LAINESOL', 'XSOL',
        
        # === ETHENA & СИНТЕТИКИ ===
        'SUSDE', 'SUSDS', 'USDE', 'SENA', 'ENA', 'SDAI', 'SFRAX',
        
        # === LP/YIELD ТОКЕНЫ ===
        'JLP', 'BFUSD', 'SYRUPUSDC', 
        'FIGR_HELOC', 'GLP', 'SGLP', 'MLP', 'HLP', 'PLP',
        
        # === БИРЖЕВЫЕ ТОКЕНЫ ===
        'BGB',   # Bitget
        'WBT',   # WhiteBIT
        'GT',    # Gate.io
        'MX',    # MEXC
        'KCS',   # KuCoin
        'HT',    # Huobi (HTX)
        'OKB',   # OKX - может не торговаться на конкурентах
        'BNB',   # Может быть проблемы с форматом
        'LEO',   # Bitfinex
        'CRO',   # Crypto.com
        
        # === BRIDGED ТОКЕНЫ ===
        'BTCB', 'ETHB', 'SOETH', 'SOLETH', 'ARBETH', 'OPETH',
        'BSC-USD', 'BTCST',
        
        # === REBASE/ELASTIC ТОКЕНЫ ===
        'OHM', 'OHMS', 'SOHM', 'GOHM', 'AMPL', 'FORTH', 
        'KLIMA', 'TIME', 'MEMO', 'BTRFLY',
        
        # === GOVERNANCE/VOTE-ESCROWED ===
        'VECRV', 'VEBAL', 'VELO', 'VEVELO', 'VEGNO', 'VETHE',
        
        # === ПРОБЛЕМНЫЕ ИЗ ЛОГОВ ===
        'USDT0', 'RAIN',
        
        # === ДОПОЛНИТЕЛЬНЫЕ ОБЁРТКИ ===
        'TBTC', 'HBTC', 'RENBTC', 'SBTC', 'OBTC', 'PBTC', 'IMBTC',
        'XSUSHI', 'XRUNE', 'XVOTE',
    }
    
    # Веса для скоринга
    SCORING_WEIGHTS = {
        "momentum_4h": 0.30,
        "momentum_1h": 0.20,
        "volume_ratio": 0.20,
        "trend_score": 0.15,
        "volatility_score": 0.15,
    }
    
    # Приоритет бирж для fallback
    EXCHANGE_PRIORITY = ["okx", "bybit", "gate"]
    
    # Константы для расчётов
    OI_HISTORY_WINDOW_SECONDS = 14400  # 4 часа
    ONE_HOUR_SECONDS = 3600  # 1 час
    MIN_CORRELATION_SAMPLES = 10  # Минимум точек для корреляции
    MAX_CORRELATION_SAMPLES = 20  # Максимум точек для корреляции
    MAX_ATR_MULTIPLIER = 0.05  # Максимум 5% для ATR
    MIN_ATR_MULTIPLIER = 0.01  # Минимум 1% для ATR
    
    # Пороги для определения направления
    MOMENTUM_4H_THRESHOLD = 0.5  # Порог для 4-часового momentum
    MOMENTUM_1H_THRESHOLD = 0.2  # Порог для 1-часового momentum
    TREND_BULLISH_THRESHOLD = 6  # Порог для бычьего тренда
    TREND_BEARISH_THRESHOLD = 4  # Порог для медвежьего тренда
    FUNDING_EXTREME_THRESHOLD = 0.0005  # Порог для экстремального funding
    
    # Веса сигналов для определения направления
    MOMENTUM_4H_WEIGHT = 2  # Вес для 4-часового momentum
    MOMENTUM_1H_WEIGHT = 1  # Вес для 1-часового momentum
    
    # Кэш невалидных символов
    INVALID_SYMBOL_CACHE_TTL = 3600  # 1 час
    
    def __init__(self):
        self.exchanges = {
            "okx": OKXClient(),
            "bybit": BybitClient(),
            "gate": GateClient(),
        }
        self.cache: Dict[str, Dict] = {}
        self.top3_history: List[Dict] = []
        self.last_update: float = 0
        self.session: Optional[aiohttp.ClientSession] = None
        self.oi_history: Dict[str, List[Tuple[float, float]]] = {}  # {symbol: [(timestamp, oi), ...]}
        self.invalid_symbols_cache: Dict[str, float] = {}  # {symbol: timestamp}
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close all exchange connections."""
        for exchange in self.exchanges.values():
            await exchange.close()
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _should_skip_symbol(self, symbol: str) -> bool:
        """
        Проверяет, нужно ли пропустить символ.
        
        Args:
            symbol: Символ монеты (например, "BTC", "USDT")
            
        Returns:
            True если символ нужно пропустить, False иначе
        """
        symbol_upper = symbol.upper()
        
        # Проверяем список исключений
        if symbol_upper in self.EXCLUDED_SYMBOLS:
            return True
        
        # Пропускаем символы с дефисами или подчёркиваниями (обычно проблемные)
        if '_' in symbol or '-' in symbol:
            return True
        
        # Пропускаем слишком длинные символы (обычно некорректные)
        if len(symbol) > 10:
            return True
        
        return False
    
    def _is_symbol_cached_invalid(self, symbol: str) -> bool:
        """
        Проверяет, кэширован ли символ как невалидный.
        
        Args:
            symbol: Символ для проверки (может включать exchange)
            
        Returns:
            True если символ кэширован как невалидный и кэш актуален
        """
        if symbol in self.invalid_symbols_cache:
            if time.time() - self.invalid_symbols_cache[symbol] < self.INVALID_SYMBOL_CACHE_TTL:
                return True
            else:
                del self.invalid_symbols_cache[symbol]
        return False
    
    def _cache_invalid_symbol(self, symbol: str):
        """
        Кэширует символ как невалидный.
        
        Args:
            symbol: Символ для кэширования (может включать exchange)
        """
        self.invalid_symbols_cache[symbol] = time.time()
    
    def _normalize_symbol_for_exchange(self, symbol: str, exchange: str) -> str:
        """
        Нормализует символ для конкретной биржи.
        
        Args:
            symbol: Базовый символ (напр., "BTC")
            exchange: Название биржи
            
        Returns:
            Нормализованный символ для биржи
        """
        if exchange == "okx":
            return f"{symbol}-USDT"
        elif exchange == "bybit":
            return f"{symbol}USDT"
        elif exchange == "gate":
            return f"{symbol}_USDT"
        return symbol
    
    async def scan_all_coins(self) -> List[Dict]:
        """
        Сканирует все монеты из CoinGecko API с пагинацией.
        
        Returns:
            Список монет с базовой информацией
        """
        await self._ensure_session()
        
        all_coins = []
        # CoinGecko бесплатный API ограничивает per_page до 250
        max_per_page = 250
        
        headers = {}
        if hasattr(settings, 'coingecko_api_key') and settings.coingecko_api_key:
            headers["X-CG-Pro-API-Key"] = settings.coingecko_api_key
            max_per_page = 500  # Pro API поддерживает больше
        
        total_pages = (self.SCAN_LIMIT + max_per_page - 1) // max_per_page
        max_retries = 3  # Максимум попыток для каждой страницы при rate limit
        
        try:
            page = 1
            while page <= total_pages:
                url = "https://api.coingecko.com/api/v3/coins/markets"
                
                # Рассчитываем сколько монет запросить на этой странице
                remaining = self.SCAN_LIMIT - len(all_coins)
                per_page = min(max_per_page, remaining)
                
                if per_page <= 0:
                    break
                
                params = {
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": str(per_page),
                    "page": str(page),
                    "sparkline": "false",
                }
                
                retry_count = 0
                success = False
                
                while retry_count < max_retries and not success:
                    async with self.session.get(
                        url, 
                        params=params, 
                        headers=headers, 
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status == 200:
                            coins = await resp.json()
                            all_coins.extend(coins)
                            logger.info(f"Scanned page {page}: {len(coins)} coins (total: {len(all_coins)})")
                            
                            # Если получили меньше чем запросили - значит это последняя страница
                            if len(coins) < per_page:
                                return all_coins
                            
                            success = True
                            
                        elif resp.status == 429:
                            # Rate limit - ждём и пробуем снова
                            retry_count += 1
                            if retry_count < max_retries:
                                logger.warning(f"CoinGecko rate limit hit, waiting 10 seconds... (attempt {retry_count}/{max_retries})")
                                await asyncio.sleep(10)
                            else:
                                logger.error(f"Max retries reached for page {page}, stopping scan")
                                return all_coins
                        else:
                            logger.warning(f"CoinGecko API error: {resp.status}")
                            return all_coins
                
                if not success:
                    # Не удалось получить данные после всех попыток
                    break
                
                # Переходим к следующей странице
                page += 1
                
                # Небольшая задержка между запросами чтобы не получить rate limit
                if page <= total_pages:
                    await asyncio.sleep(1)
            
            logger.info(f"Scanned {len(all_coins)} coins from CoinGecko")
            return all_coins
            
        except Exception as e:
            logger.error(f"Error scanning coins: {e}", exc_info=True)
            return all_coins  # Возвращаем то что успели собрать
    
    async def filter_coins(self, coins: List[Dict]) -> List[Dict]:
        """
        Фильтрует монеты по критериям ликвидности, объёма, возраста.
        
        Args:
            coins: Список монет от CoinGecko
            
        Returns:
            Отфильтрованный список монет
        """
        filtered = []
        
        for coin in coins:
            symbol = coin.get("symbol", "").upper()
            
            # Пропускаем исключенные символы
            if self._should_skip_symbol(symbol):
                logger.debug(f"Skipping excluded symbol: {symbol}")
                continue
            
            # Проверка объёма 24h
            volume_24h = coin.get("total_volume", 0) or 0
            if volume_24h < self.MIN_VOLUME_USD:
                continue
            
            # Проверка капитализации
            market_cap = coin.get("market_cap", 0) or 0
            if market_cap < self.MIN_MCAP_USD:
                continue
            
            # Проверка наличия цены
            if not coin.get("current_price"):
                continue
            
            # Добавляем в список
            filtered.append({
                "id": coin["id"],
                "symbol": symbol,
                "name": coin["name"],
                "price": coin["current_price"],
                "volume_24h": volume_24h,
                "market_cap": market_cap,
                "change_24h": coin.get("price_change_percentage_24h", 0) or 0,
            })
        
        logger.info(f"Filtered {len(filtered)} coins from {len(coins)}")
        return filtered
    
    async def _get_exchange_data(self, symbol: str, exchange_name: str) -> Optional[Dict]:
        """
        Получает данные с биржи с оптимизацией запросов.
        Сначала проверяет тикер (быстро), затем запрашивает OHLCV.
        
        Args:
            symbol: Символ монеты (напр., "BTC")
            exchange_name: Название биржи
            
        Returns:
            Dict с данными или None
        """
        # Проверяем кэш невалидных символов
        cache_key = f"{symbol}_{exchange_name}"
        if self._is_symbol_cached_invalid(cache_key):
            return None
        
        exchange = self.exchanges.get(exchange_name)
        if not exchange:
            return None
        
        normalized_symbol = self._normalize_symbol_for_exchange(symbol, exchange_name)
        
        try:
            # ШАГ 1: Сначала проверяем тикер (быстро, 1 запрос)
            ticker = await exchange.get_ticker(normalized_symbol)
            if not ticker:
                self._cache_invalid_symbol(cache_key)
                return None
            
            # ШАГ 2: Только если тикер есть - запрашиваем остальное
            tasks = [
                exchange.get_ohlcv(normalized_symbol, "1H", 100),
                exchange.get_ohlcv(normalized_symbol, "4H", 30),
            ]
            
            # Для фьючерсных данных нужен SWAP формат
            if exchange_name == "okx":
                swap_symbol = f"{symbol}-USDT-SWAP"
                tasks.extend([
                    exchange.get_funding_rate(swap_symbol),
                    exchange.get_open_interest(swap_symbol),
                ])
            elif exchange_name == "bybit":
                tasks.extend([
                    exchange.get_funding_rate(normalized_symbol),
                    exchange.get_open_interest(normalized_symbol),
                ])
            else:
                # Gate.io fallback
                tasks.extend([
                    asyncio.create_task(asyncio.sleep(0)),  # Placeholder
                    asyncio.create_task(asyncio.sleep(0)),  # Placeholder
                ])
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            ohlcv_1h = results[0] if not isinstance(results[0], Exception) else []
            ohlcv_4h = results[1] if not isinstance(results[1], Exception) else []
            funding_rate = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else None
            open_interest = results[3] if len(results) > 3 and not isinstance(results[3], Exception) else None
            
            if not ohlcv_1h:
                self._cache_invalid_symbol(cache_key)
                return None
            
            return {
                "ohlcv_1h": ohlcv_1h,
                "ohlcv_4h": ohlcv_4h,
                "ticker": ticker,
                "funding_rate": funding_rate,
                "open_interest": open_interest,
                "exchange": exchange_name,
            }
        except Exception as e:
            logger.warning(f"Error getting data from {exchange_name} for {symbol}: {e}")
            self._cache_invalid_symbol(cache_key)
            return None
    
    async def _get_data_with_fallback(self, symbol: str) -> Optional[Dict]:
        """
        Получает данные параллельно от всех бирж, берёт первый успешный по приоритету.
        
        Args:
            symbol: Символ монеты
            
        Returns:
            Dict с данными от первой доступной биржи
        """
        async def try_exchange(name: str):
            try:
                return await self._get_exchange_data(symbol, name)
            except Exception as e:
                logger.debug(f"Error getting data from {name} for {symbol}: {e}")
                return None
        
        # Запускаем все запросы параллельно
        tasks = [try_exchange(name) for name in self.EXCHANGE_PRIORITY]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Берём первый успешный результат по приоритету
        for result in results:
            if result and not isinstance(result, Exception):
                logger.debug(f"Got data for {symbol} from {result.get('exchange', 'unknown')}")
                return result
        
        logger.warning(f"Failed to get data for {symbol} from all exchanges")
        return None
    
    async def _calculate_oi_change(self, symbol: str, current_oi: float) -> float:
        """
        Рассчитывает изменение OI за последний час.
        
        Args:
            symbol: Символ монеты
            current_oi: Текущее значение Open Interest
            
        Returns:
            Процентное изменение OI за последний час
        """
        if current_oi <= 0:
            return 0.0
        
        now = time.time()
        history = self.oi_history.get(symbol, [])
        
        # Добавляем текущее значение
        history.append((now, current_oi))
        
        # Удаляем старые записи (старше 4 часов)
        history = [(t, oi) for t, oi in history if now - t < self.OI_HISTORY_WINDOW_SECONDS]
        self.oi_history[symbol] = history
        
        # Ищем значение час назад
        one_hour_ago = now - self.ONE_HOUR_SECONDS
        old_entries = [(t, oi) for t, oi in history if t <= one_hour_ago]
        
        if old_entries:
            old_oi = old_entries[-1][1]  # Берём ближайшее к часу назад
            if old_oi > 0:
                return ((current_oi - old_oi) / old_oi) * 100
        
        return 0.0
    
    async def _calculate_btc_correlation(self, prices: List[float]) -> float:
        """
        Рассчитывает корреляцию с BTC.
        
        Args:
            prices: Список цен монеты для расчета корреляции
            
        Returns:
            Коэффициент корреляции Пирсона (-1 до 1)
        """
        try:
            # Используем приоритет бирж для получения данных BTC
            btc_data = await self._get_data_with_fallback("BTC")
            if not btc_data or not btc_data.get("ohlcv_1h"):
                return 0.5  # Нейтральное значение при ошибке
            
            btc_prices = [c["close"] for c in btc_data["ohlcv_1h"]]
            
            # Выравниваем длину
            min_len = min(len(prices), len(btc_prices), self.MAX_CORRELATION_SAMPLES)
            if min_len < self.MIN_CORRELATION_SAMPLES:
                return 0.5
            
            prices = prices[-min_len:]
            btc_prices = btc_prices[-min_len:]
            
            # Рассчитываем корреляцию Пирсона
            mean_p = sum(prices) / len(prices)
            mean_b = sum(btc_prices) / len(btc_prices)
            
            numerator = sum((p - mean_p) * (b - mean_b) for p, b in zip(prices, btc_prices))
            denom_p = sum((p - mean_p) ** 2 for p in prices) ** 0.5
            denom_b = sum((b - mean_b) ** 2 for b in btc_prices) ** 0.5
            
            if denom_p * denom_b == 0:
                return 0.5
            
            return numerator / (denom_p * denom_b)
        except Exception as e:
            logger.warning(f"Error calculating BTC correlation: {e}")
            return 0.5
    
    def _determine_direction(self, change_1h: float, change_4h: float, 
                             trend_score: float, funding_rate: float) -> Tuple[str, str]:
        """
        Определяет направление на основе нескольких факторов.
        
        Args:
            change_1h: Изменение цены за 1 час (%)
            change_4h: Изменение цены за 4 часа (%)
            trend_score: Оценка тренда (0-10)
            funding_rate: Ставка финансирования
            
        Returns:
            Tuple (направление, эмодзи)
        """
        bullish_signals = 0
        bearish_signals = 0
        
        # Momentum (вес 2)
        if change_4h > self.MOMENTUM_4H_THRESHOLD:
            bullish_signals += self.MOMENTUM_4H_WEIGHT
        elif change_4h < -self.MOMENTUM_4H_THRESHOLD:
            bearish_signals += self.MOMENTUM_4H_WEIGHT
        
        if change_1h > self.MOMENTUM_1H_THRESHOLD:
            bullish_signals += self.MOMENTUM_1H_WEIGHT
        elif change_1h < -self.MOMENTUM_1H_THRESHOLD:
            bearish_signals += self.MOMENTUM_1H_WEIGHT
        
        # Trend (EMA crossover)
        if trend_score > self.TREND_BULLISH_THRESHOLD:
            bullish_signals += 1
        elif trend_score < self.TREND_BEARISH_THRESHOLD:
            bearish_signals += 1
        
        # Funding (контр-сигнал при экстремальных значениях)
        if funding_rate and funding_rate > self.FUNDING_EXTREME_THRESHOLD:
            bearish_signals += 1  # Много лонгов
        elif funding_rate and funding_rate < -self.FUNDING_EXTREME_THRESHOLD:
            bullish_signals += 1  # Много шортов
        
        if bullish_signals > bearish_signals:
            return "ЛОНГ", "📈"
        elif bearish_signals > bullish_signals:
            return "ШОРТ", "📉"
        return "НЕЙТРАЛЬНО", "➡️"
    
    def _calculate_levels(self, price: float, atr_pct: float, direction: str) -> Dict:
        """
        Рассчитывает уровни входа, SL и TP на основе ATR.
        
        Args:
            price: Текущая цена
            atr_pct: ATR в процентах
            direction: Направление ("ЛОНГ", "ШОРТ", или "НЕЙТРАЛЬНО")
            
        Returns:
            Dict с уровнями entry_low, entry_high, stop, tp1, tp2
        """
        # Ограничиваем ATR multiplier
        atr_mult = max(min(atr_pct / 100, self.MAX_ATR_MULTIPLIER), self.MIN_ATR_MULTIPLIER)
        
        if direction == "ЛОНГ":
            return {
                "entry_low": price * (1 - atr_mult * 0.5),
                "entry_high": price * (1 + atr_mult * 0.5),
                "stop": price * (1 - atr_mult * 1.5),
                "tp1": price * (1 + atr_mult * 2.0),
                "tp2": price * (1 + atr_mult * 4.0),
            }
        else:  # ШОРТ или НЕЙТРАЛЬНО
            return {
                "entry_low": price * (1 - atr_mult * 0.5),
                "entry_high": price * (1 + atr_mult * 0.5),
                "stop": price * (1 + atr_mult * 1.5),
                "tp1": price * (1 - atr_mult * 2.0),
                "tp2": price * (1 - atr_mult * 4.0),
            }
    
    async def _get_cached_data(self, key: str, fetch_func, ttl: int = 60):
        """
        Получает данные из кэша или выполняет запрос.
        
        Args:
            key: Ключ кэша
            fetch_func: Async функция для получения данных
            ttl: Время жизни кэша в секундах
            
        Returns:
            Данные из кэша или от fetch_func
        """
        # Check in-memory cache first
        cache_entry = self.cache.get(key)
        if cache_entry and time.time() - cache_entry.get("timestamp", 0) < ttl:
            return cache_entry.get("data")
        
        # Fetch fresh data
        data = await fetch_func()
        
        if data:
            self.cache[key] = {"data": data, "timestamp": time.time()}
        
        return data
    
    def get_top3_changes(self, new_top3: List[Dict]) -> Dict:
        """
        Возвращает изменения в ТОП-3 для уведомлений.
        
        Args:
            new_top3: Новый список ТОП-3 монет
            
        Returns:
            Dict с ключами added, removed, has_changes
        """
        old_symbols = {c["symbol"] for c in self.top3_history}
        new_symbols = {c["symbol"] for c in new_top3}
        
        added = new_symbols - old_symbols
        removed = old_symbols - new_symbols
        
        return {
            "added": [c for c in new_top3 if c["symbol"] in added],
            "removed": [c for c in self.top3_history if c["symbol"] in removed],
            "has_changes": bool(added or removed),
        }
    
    async def calculate_score(self, coin: Dict) -> Optional[Dict]:
        """
        Рассчитывает score для монеты.
        
        Args:
            coin: Данные монеты от CoinGecko
            
        Returns:
            Dict с score и метриками или None
        """
        symbol = coin["symbol"]
        
        # Получаем данные с биржи
        exchange_data = await self._get_data_with_fallback(symbol)
        if not exchange_data:
            return None
        
        ohlcv_1h = exchange_data["ohlcv_1h"]
        ohlcv_4h = exchange_data["ohlcv_4h"]
        ticker = exchange_data["ticker"]
        
        # Проверка спреда
        if ticker.get("spread_pct", 1.0) > self.MAX_SPREAD_PCT:
            logger.debug(f"Skipping {symbol} due to high spread")
            return None
        
        # Извлекаем цены для расчётов
        try:
            prices_1h = [c["close"] for c in ohlcv_1h]
            highs = [c["high"] for c in ohlcv_1h]
            lows = [c["low"] for c in ohlcv_1h]
            volumes = [c["volume"] for c in ohlcv_1h]
            
            if len(prices_1h) < 20:
                return None
            
            current_price = prices_1h[-1]
            price_1h_ago = prices_1h[-2] if len(prices_1h) >= 2 else current_price
            price_4h_ago = prices_1h[-5] if len(prices_1h) >= 5 else current_price
            
            # Рассчитываем изменения цены
            change_1h = ((current_price - price_1h_ago) / price_1h_ago) * 100 if price_1h_ago > 0 else 0
            change_4h = ((current_price - price_4h_ago) / price_4h_ago) * 100 if price_4h_ago > 0 else 0
            
            # Momentum score
            momentum_score_4h = calculate_momentum_score({"1h": 0, "4h": change_4h})
            momentum_score_1h = calculate_momentum_score({"1h": change_1h, "4h": 0})
            
            # Volume score
            avg_volume = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else volumes[-1]
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            volume_score = calculate_volume_score(current_volume, avg_volume)
            
            # Trend score (EMA + ADX)
            ema_short = calculate_ema(prices_1h, 9)
            ema_long = calculate_ema(prices_1h, 21)
            adx = calculate_adx(highs, lows, prices_1h, 14)
            trend_score = calculate_trend_score(
                {"ema_short": ema_short, "ema_long": ema_long, "price": current_price},
                adx
            )
            
            # Volatility score (упрощённый ATR + BB width)
            high_low_range = [(h - l) / l * 100 for h, l in zip(highs[-14:], lows[-14:]) if l > 0]
            atr_pct = sum(high_low_range) / len(high_low_range) if high_low_range else 2.0
            
            # BB width (упрощённо через std)
            price_std = statistics.stdev(prices_1h[-20:]) if len(prices_1h) >= 20 else 0
            bb_width_pct = (price_std * 2 / current_price) * 100 if current_price > 0 else 5.0
            
            volatility_score = calculate_volatility_score(atr_pct, bb_width_pct)
            
            # Фильтры
            if volume_ratio < 1.0:
                logger.debug(f"Skipping {symbol} due to low volume ratio")
                return None
            
            if bb_width_pct > 15:
                logger.debug(f"Skipping {symbol} due to high volatility")
                return None
            
            # Итоговый score
            metrics = {
                "momentum_4h": momentum_score_4h,
                "momentum_1h": momentum_score_1h,
                "volume_ratio": volume_score,
                "trend_score": trend_score,
                "volatility_score": volatility_score,
            }
            
            base_score = calculate_total_score(metrics, self.SCORING_WEIGHTS)
            
            # Применяем бонусы/штрафы
            funding_rate = exchange_data.get("funding_rate") or 0
            oi_data = exchange_data.get("open_interest")
            
            # Рассчитываем реальное изменение OI
            if oi_data and isinstance(oi_data, dict):
                current_oi = oi_data.get("openInterest", 0) or oi_data.get("open_interest", 0)
                oi_change_pct = await self._calculate_oi_change(symbol, current_oi)
            else:
                oi_change_pct = 0
            
            # Рассчитываем реальную корреляцию с BTC
            btc_correlation = await self._calculate_btc_correlation(prices_1h)
            
            final_score, factors = apply_score_bonuses(
                base_score,
                funding_rate,
                oi_change_pct,
                change_4h,
                btc_correlation
            )
            
            # Определяем направление с помощью улучшенной логики
            direction, direction_emoji = self._determine_direction(
                change_1h, change_4h, trend_score, funding_rate
            )
            
            return {
                "symbol": symbol,
                "name": coin["name"],
                "score": final_score,
                "price": current_price,
                "change_1h": change_1h,
                "change_4h": change_4h,
                "change_24h": coin["change_24h"],
                "volume_ratio": volume_ratio,
                "atr_pct": atr_pct,
                "bb_width_pct": bb_width_pct,
                "funding_rate": funding_rate,
                "oi_change_pct": oi_change_pct,
                "direction": direction,
                "direction_emoji": direction_emoji,
                "factors": factors,
                "adx": adx,
                "exchange": exchange_data["exchange"],
            }
        except Exception as e:
            logger.error(f"Error calculating score for {symbol}: {e}", exc_info=True)
            return None
    
    async def get_top3(self) -> Tuple[List[Dict], int, int]:
        """
        Возвращает ТОП-3 монеты с гистерезисом.
        
        Returns:
            Tuple (top3_list, scanned_count, filtered_count)
        """
        # Сканируем монеты
        coins = await self.scan_all_coins()
        scanned_count = len(coins)
        
        # Фильтруем
        filtered_coins = await self.filter_coins(coins)
        filtered_count = len(filtered_coins)
        
        # Рассчитываем scores для всех монет (с ограничением параллелизма)
        scored_coins = []
        
        # Ограничиваем количество одновременных запросов
        semaphore = asyncio.Semaphore(10)
        
        # For performance, we analyze top coins by market cap first
        # Configurable via settings.smart_signals_max_analyze
        max_coins_to_analyze = min(len(filtered_coins), self.MAX_ANALYZE)
        
        async def score_coin_with_limit(coin):
            async with semaphore:
                return await self.calculate_score(coin)
        
        tasks = [score_coin_with_limit(coin) for coin in filtered_coins[:max_coins_to_analyze]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if result and not isinstance(result, Exception):
                scored_coins.append(result)
        
        # Сортируем по score
        scored_coins.sort(key=lambda x: x["score"], reverse=True)
        
        # Применяем гистерезис
        top3 = self._apply_hysteresis(scored_coins[:10])  # Берём топ-10 для гистерезиса
        
        self.last_update = time.time()
        
        return top3[:3], scanned_count, filtered_count
    
    def _apply_hysteresis(self, candidates: List[Dict]) -> List[Dict]:
        """
        Применяет гистерезис для предотвращения "мигания" списка.
        
        Args:
            candidates: Список кандидатов, отсортированных по score
            
        Returns:
            Финальный список с учётом гистерезиса
        """
        if not self.top3_history:
            # Первый запуск - просто берём топ-3
            self.top3_history = candidates[:3]
            for coin in self.top3_history:
                coin["entry_time"] = time.time()
            return self.top3_history
        
        current_time = time.time()
        result = []
        
        for historical_coin in self.top3_history:
            symbol = historical_coin["symbol"]
            entry_time = historical_coin.get("entry_time", 0)
            time_in_top = current_time - entry_time
            
            # Монета должна остаться минимум 15 минут
            if time_in_top < self.HYSTERESIS_TIME:
                result.append(historical_coin)
                continue
            
            # Ищем эту монету в новых кандидатах
            candidate_coin = next((c for c in candidates if c["symbol"] == symbol), None)
            
            if candidate_coin:
                # Монета всё ещё в топе - обновляем данные но сохраняем entry_time
                candidate_coin["entry_time"] = entry_time
                result.append(candidate_coin)
            else:
                # Монета выпала из топа - проверяем, есть ли новая монета на 10%+ лучше
                best_new = next((c for c in candidates if c["symbol"] not in [h["symbol"] for h in self.top3_history]), None)
                
                if best_new and best_new["score"] > historical_coin["score"] * (1 + self.HYSTERESIS_THRESHOLD):
                    # Новая монета значительно лучше - заменяем
                    best_new["entry_time"] = current_time
                    result.append(best_new)
                else:
                    # Оставляем старую
                    result.append(historical_coin)
        
        # Если result содержит меньше 3 монет, добавляем из кандидатов
        existing_symbols = {c["symbol"] for c in result}
        for candidate in candidates:
            if len(result) >= 3:
                break
            if candidate["symbol"] not in existing_symbols:
                candidate["entry_time"] = current_time
                result.append(candidate)
        
        self.top3_history = result[:3]
        return result[:3]
    
    def format_message(self, top3: List[Dict], scanned_count: int, filtered_count: int) -> str:
        """
        Форматирует сообщение для Telegram.
        
        Args:
            top3: Список ТОП-3 монет
            scanned_count: Количество отсканированных монет
            filtered_count: Количество монет прошедших фильтры
            
        Returns:
            Отформатированное сообщение
        """
        now = datetime.now().strftime("%H:%M:%S")
        
        text = "📡 *УМНЫЕ СИГНАЛЫ \\(ТОП\\-3\\)*\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📊 Сканирование: {scanned_count} монет\n"
        text += f"✅ Прошли фильтры: {filtered_count} монет\n"
        text += f"⏰ Обновлено: {now}\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        
        for idx, coin in enumerate(top3):
            medal = medals[idx] if idx < len(medals) else "•"
            
            text += f"{medal} *\\#{idx + 1} {coin['symbol']}/USDT \\| {coin['direction_emoji']} {coin['direction']}*\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"💰 Цена: ${coin['price']:,.2f}\n"
            text += f"📈 Δ1h: {coin['change_1h']:+.1f}% \\| Δ4h: {coin['change_4h']:+.1f}% \\| Δ24h: {coin['change_24h']:+.1f}%\n"
            text += f"📊 Объём: {coin['volume_ratio']:.1f}x от среднего\n"
            text += f"📉 ATR: {coin['atr_pct']:.1f}% \\| BB: {coin['bb_width_pct']:.1f}%\n"
            
            if coin.get('funding_rate'):
                funding_pct = coin['funding_rate'] * 100
                text += f"💹 Funding: {funding_pct:.3f}% \\| OI: {coin['oi_change_pct']:+.1f}%\n"
            
            # Progress bar для score
            score = coin['score']
            filled = int(score)
            empty = 10 - filled
            bar = "█" * filled + "░" * empty
            text += f"🎯 Score: {score:.1f}/10 {bar}\n\n"
            
            # Факторы
            if coin.get('factors'):
                text += "✅ *Факторы:*\n"
                for factor in coin['factors']:
                    # Escape special characters
                    factor_escaped = factor.replace("_", "\\_").replace(".", "\\.").replace("-", "\\-").replace("+", "\\+").replace("(", "\\(").replace(")", "\\)").replace("%", "\\%")
                    text += f"• {factor_escaped}\n"
                text += "\n"
            
            # Уровни на основе ATR
            current_price = coin['price']
            levels = self._calculate_levels(current_price, coin['atr_pct'], coin['direction'])
            
            entry_low = levels['entry_low']
            entry_high = levels['entry_high']
            stop = levels['stop']
            tp1 = levels['tp1']
            tp2 = levels['tp2']
            
            # Рассчитываем Risk/Reward ratio
            risk = abs(stop - current_price)
            reward = abs(tp1 - current_price)
            rr_ratio = reward / risk if risk > 0 else 0
            
            text += "📍 *Уровни:*\n"
            text += f"• Вход: ${entry_low:,.2f}\\-{entry_high:,.2f}\n"
            text += f"• Стоп: ${stop:,.2f} \\({((stop - current_price) / current_price * 100):+.1f}%\\)\n"
            text += f"• TP1: ${tp1:,.2f} \\({((tp1 - current_price) / current_price * 100):+.1f}%\\)\n"
            text += f"• TP2: ${tp2:,.2f} \\({((tp2 - current_price) / current_price * 100):+.1f}%\\)\n"
            text += f"📊 R:R = 1:{rr_ratio:.1f}\n"
            
            if idx < len(top3) - 1:
                text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "⏱️ Следующее обновление: по запросу\n"
        text += "⚠️ Не является финансовым советом"
        
        return text
