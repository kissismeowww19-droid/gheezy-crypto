"""
Gheezy Crypto - Анализатор сигналов

AI-генерация торговых сигналов с объяснениями на основе
технического анализа (RSI, MACD, Bollinger Bands).
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import aiohttp
import structlog

from src.config import settings
from src.signals.indicators import (
    BollingerBands,
    MACD,
    RSI,
    calculate_all_indicators,
)

logger = structlog.get_logger()


@dataclass
class TradingSignal:
    """
    Торговый сигнал с полным анализом.

    Attributes:
        symbol: Символ криптовалюты (BTC, ETH и т.д.)
        signal_type: Тип сигнала (buy/sell/hold)
        confidence: Уверенность в сигнале (0-100%)
        current_price: Текущая цена
        target_price: Целевая цена
        stop_loss: Уровень стоп-лосса
        rsi: Индикатор RSI
        macd: Индикатор MACD
        bollinger: Полосы Боллинджера
        explanation: Полное объяснение сигнала
    """

    symbol: str
    signal_type: str
    confidence: float
    current_price: float
    target_price: Optional[float]
    stop_loss: Optional[float]
    rsi: Optional[RSI]
    macd: Optional[MACD]
    bollinger: Optional[BollingerBands]
    explanation: str


class SignalAnalyzer:
    """
    Анализатор для генерации торговых сигналов.

    Использует технический анализ (RSI, MACD, Bollinger Bands)
    для генерации AI-сигналов с человекочитаемыми объяснениями.
    """

    def __init__(self):
        """Инициализация анализатора."""
        self.coingecko_url = "https://api.coingecko.com/api/v3"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение HTTP сессии."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Закрытие HTTP сессии."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_price_history(
        self,
        symbol: str,
        days: int = 30,
    ) -> Optional[List[float]]:
        """
        Получение истории цен криптовалюты.

        Args:
            symbol: Символ криптовалюты (bitcoin, ethereum и т.д.)
            days: Количество дней истории

        Returns:
            List[float]: Список цен закрытия или None при ошибке
        """
        try:
            session = await self._get_session()
            url = f"{self.coingecko_url}/coins/{symbol.lower()}/market_chart"
            params = {
                "vs_currency": "usd",
                "days": days,
            }

            if settings.coingecko_api_key:
                params["x_cg_demo_api_key"] = settings.coingecko_api_key

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # Извлекаем цены закрытия
                    prices = [point[1] for point in data.get("prices", [])]
                    return prices
                else:
                    logger.warning(
                        "Ошибка получения истории цен",
                        symbol=symbol,
                        status=response.status,
                    )
                    return None

        except Exception as e:
            logger.error("Ошибка при запросе истории цен", error=str(e))
            return None

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Получение текущей цены криптовалюты.

        Args:
            symbol: Символ криптовалюты

        Returns:
            float: Текущая цена или None при ошибке
        """
        try:
            session = await self._get_session()
            url = f"{self.coingecko_url}/simple/price"
            params = {
                "ids": symbol.lower(),
                "vs_currencies": "usd",
            }

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get(symbol.lower(), {}).get("usd")
                return None

        except Exception as e:
            logger.error("Ошибка получения текущей цены", error=str(e))
            return None

    def _calculate_signal(
        self,
        rsi: Optional[RSI],
        macd: Optional[MACD],
        bb: Optional[BollingerBands],
    ) -> Tuple[str, float]:
        """
        Расчёт итогового сигнала на основе индикаторов.

        Args:
            rsi: Индикатор RSI
            macd: Индикатор MACD
            bb: Полосы Боллинджера

        Returns:
            tuple: (signal_type, confidence)
        """
        buy_score = 0
        sell_score = 0
        total_weight = 0

        # RSI анализ (вес 35%)
        if rsi:
            total_weight += 35
            if rsi.signal == "oversold":
                buy_score += 35
            elif rsi.signal == "overbought":
                sell_score += 35
            else:
                # Нейтральный - распределяем
                buy_score += 17.5
                sell_score += 17.5

        # MACD анализ (вес 35%)
        if macd:
            total_weight += 35
            if macd.signal == "bullish":
                buy_score += 35
            elif macd.signal == "bearish":
                sell_score += 35
            else:
                buy_score += 17.5
                sell_score += 17.5

        # Bollinger Bands анализ (вес 30%)
        if bb:
            total_weight += 30
            position = bb.position
            if position == "below_lower":
                buy_score += 30
            elif position == "above_upper":
                sell_score += 30
            elif position == "lower_half":
                buy_score += 15
                sell_score += 15
            else:
                buy_score += 15
                sell_score += 15

        if total_weight == 0:
            return "hold", 0.0

        # Нормализуем скоры
        buy_score = (buy_score / total_weight) * 100
        sell_score = (sell_score / total_weight) * 100

        # Определяем сигнал
        if buy_score > 60:
            return "buy", buy_score
        elif sell_score > 60:
            return "sell", sell_score
        return "hold", max(buy_score, sell_score)

    def _generate_explanation(
        self,
        signal_type: str,
        rsi: Optional[RSI],
        macd: Optional[MACD],
        bb: Optional[BollingerBands],
    ) -> str:
        """
        Генерация объяснения сигнала на русском языке.

        Args:
            signal_type: Тип сигнала
            rsi: Индикатор RSI
            macd: Индикатор MACD
            bb: Полосы Боллинджера

        Returns:
            str: Полное объяснение сигнала
        """
        parts = []

        # Заголовок
        if signal_type == "buy":
            parts.append("🟢 **СИГНАЛ: ПОКУПКА**\n")
        elif signal_type == "sell":
            parts.append("🔴 **СИГНАЛ: ПРОДАЖА**\n")
        else:
            parts.append("⚪ **СИГНАЛ: ДЕРЖАТЬ**\n")

        parts.append("📊 **Технический анализ:**\n")

        # RSI
        if rsi:
            parts.append(f"• {rsi.explanation}")

        # MACD
        if macd:
            parts.append(f"• {macd.explanation}")

        # Bollinger Bands
        if bb:
            parts.append(f"• {bb.explanation}")

        # Рекомендации
        parts.append("\n💡 **Рекомендация:**")
        if signal_type == "buy":
            parts.append(
                "Индикаторы показывают потенциал роста. "
                "Рассмотрите покупку с установкой стоп-лосса."
            )
        elif signal_type == "sell":
            parts.append(
                "Индикаторы показывают возможную коррекцию. "
                "Рассмотрите фиксацию прибыли или сокращение позиции."
            )
        else:
            parts.append(
                "Рынок в нейтральной зоне. Рекомендуем дождаться более чёткого сигнала."
            )

        return "\n".join(parts)

    async def analyze(self, symbol: str) -> Optional[TradingSignal]:
        """
        Полный анализ криптовалюты с генерацией торгового сигнала.

        Args:
            symbol: Символ криптовалюты (bitcoin, ethereum и т.д.)

        Returns:
            TradingSignal: Сигнал с полным анализом или None при ошибке
        """
        # Получаем историю цен
        prices = await self.get_price_history(symbol)
        if not prices or len(prices) < 30:
            logger.warning("Недостаточно данных для анализа", symbol=symbol)
            return None

        current_price = prices[-1]

        # Рассчитываем индикаторы
        rsi, macd, bb = calculate_all_indicators(prices)

        # Генерируем сигнал
        signal_type, confidence = self._calculate_signal(rsi, macd, bb)

        # Рассчитываем целевую цену и стоп-лосс
        target_price = None
        stop_loss = None

        if signal_type == "buy":
            target_price = current_price * 1.05  # +5%
            stop_loss = current_price * 0.97  # -3%
        elif signal_type == "sell":
            target_price = current_price * 0.95  # -5%
            stop_loss = current_price * 1.03  # +3%

        # Генерируем объяснение
        explanation = self._generate_explanation(signal_type, rsi, macd, bb)

        return TradingSignal(
            symbol=symbol.upper(),
            signal_type=signal_type,
            confidence=confidence,
            current_price=current_price,
            target_price=target_price,
            stop_loss=stop_loss,
            rsi=rsi,
            macd=macd,
            bollinger=bb,
            explanation=explanation,
        )

    async def get_signal_message(self, symbol: str) -> str:
        """
        Получение форматированного сообщения с сигналом для Telegram.

        Args:
            symbol: Символ криптовалюты

        Returns:
            str: Форматированное сообщение
        """
        signal = await self.analyze(symbol)

        if not signal:
            return f"❌ Не удалось получить сигнал для {symbol.upper()}"

        message = [
            f"🎯 **Сигнал для {signal.symbol}**",
            f"💰 Текущая цена: ${signal.current_price:,.2f}",
            f"📈 Уверенность: {signal.confidence:.1f}%",
            "",
            signal.explanation,
        ]

        if signal.target_price:
            message.append(f"\n🎯 Целевая цена: ${signal.target_price:,.2f}")
        if signal.stop_loss:
            message.append(f"🛡️ Стоп-лосс: ${signal.stop_loss:,.2f}")

        message.append("\n⚠️ *Это не финансовый совет. Инвестируйте ответственно!*")

        return "\n".join(message)
