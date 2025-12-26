"""
💎 Gem Scanner - Поиск новых токенов на DEX
"""

import aiohttp
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GemScanner:
    """Сканер для поиска новых токенов (гемов) на DEX."""

    # Константы
    UNKNOWN_TOKEN_AGE_HOURS = (
        999  # Значение по умолчанию для токенов с неизвестным возрастом
    )

    # Фильтры для гемов
    DEFAULT_FILTERS = {
        "max_market_cap": 2_000_000,  # Макс. капитализация < $2M
        "min_liquidity": 10_000,  # Мин. ликвидность > $10K
        "max_liquidity": 500_000,  # Макс. ликвидность < $500K (иначе уже не гем)
        "max_token_age_hours": 168,  # Возраст токена < 7 дней (168 часов)
        "min_volume_24h": 5_000,  # Мин. объём 24ч > $5K
        "min_holders": 50,  # Мин. держателей > 50
        "min_volume_growth": 50,  # Рост объёма > 50%
    }

    # Сети и их ID для DEX Screener
    NETWORKS = {
        "solana": "solana",
        "base": "base",
        "ethereum": "ethereum",
        "bsc": "bsc",
    }

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.filters = self.DEFAULT_FILTERS.copy()

    async def _ensure_session(self):
        """Создаёт сессию если её нет."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Закрывает сессию."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def scan(self, network: str, limit: int = 10) -> List[Dict]:
        """
        Сканирует DEX на выбранной сети и возвращает топ гемов.

        Args:
            network: Сеть (solana, base, ethereum, bsc)
            limit: Максимальное количество результатов

        Returns:
            Список токенов с данными
        """
        await self._ensure_session()

        logger.info(f"GemScanner: Starting scan on {network}")

        try:
            # 1. Получаем новые пары с DEX Screener
            pairs = await self._fetch_new_pairs(network)
            logger.info(f"GemScanner: Fetched {len(pairs)} pairs from DEX Screener")

            if not pairs:
                return []

            # 2. Фильтруем по базовым критериям
            filtered = self._apply_filters(pairs)
            logger.info(f"GemScanner: {len(filtered)} pairs passed filters")

            if not filtered:
                return []

            # 3. Рассчитываем скор для каждого токена
            scored = []
            for token in filtered[:30]:  # Анализируем максимум 30
                score_data = self._calculate_gem_score(token)
                token["_gem_score"] = score_data["score"]
                token["_gem_signal"] = score_data["signal"]
                token["_gem_reasons"] = score_data["reasons"]
                scored.append(token)

            # 4. Сортируем по скору и возвращаем топ
            scored.sort(key=lambda x: x.get("_gem_score", 0), reverse=True)

            result = scored[:limit]
            logger.info(f"GemScanner: Found {len(result)} gems on {network}")

            return result

        except Exception as e:
            logger.error(f"GemScanner error: {e}")
            return []

    async def _fetch_new_pairs(self, network: str) -> List[Dict]:
        """
        Получает новые пары с DEX Screener API.

        API: https://api.dexscreener.com/token-profiles/latest/v1
        Note: This endpoint returns the latest token profiles across all chains.
        """
        chain = self.NETWORKS.get(network.lower(), network)

        # DEX Screener API для новых пар
        url = "https://api.dexscreener.com/token-profiles/latest/v1"

        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # Ensure data is a list
                    if not isinstance(data, list):
                        logger.warning(
                            f"DEX Screener API returned non-list data: {type(data)}"
                        )
                        return []

                    # Фильтруем по сети - используем list comprehension для производительности
                    pairs = [
                        item
                        for item in data
                        if isinstance(item, dict)
                        and item.get("chainId", "").lower() == chain.lower()
                    ]

                    return pairs
                else:
                    logger.warning(f"DEX Screener API returned {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching from DEX Screener: {e}")
            return []

    async def _fetch_pair_details(self, network: str, address: str) -> Optional[Dict]:
        """Получает детальную информацию о паре."""
        chain = self.NETWORKS.get(network.lower(), network)
        url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{address}"

        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    return pairs[0] if pairs else None
        except Exception as e:
            logger.debug(f"Error fetching pair details: {e}")
            return None

    def _apply_filters(self, pairs: List[Dict]) -> List[Dict]:
        """Применяет фильтры к списку пар."""
        filtered = []

        for pair in pairs:
            try:
                # Получаем метрики
                liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                market_cap = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)
                volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)

                # Возраст токена
                created_at = pair.get("pairCreatedAt")
                if created_at:
                    age_hours = (datetime.now().timestamp() * 1000 - created_at) / (
                        1000 * 60 * 60
                    )
                else:
                    age_hours = self.UNKNOWN_TOKEN_AGE_HOURS

                # Применяем фильтры
                if market_cap > self.filters["max_market_cap"]:
                    continue
                if liquidity < self.filters["min_liquidity"]:
                    continue
                if liquidity > self.filters["max_liquidity"]:
                    continue
                if age_hours > self.filters["max_token_age_hours"]:
                    continue
                if volume_24h < self.filters["min_volume_24h"]:
                    continue

                filtered.append(pair)

            except Exception as e:
                logger.debug(f"Error filtering pair: {e}")
                continue

        return filtered

    def _calculate_gem_score(self, token: Dict) -> Dict:
        """
        Рассчитывает "гем-скор" для токена.

        Returns:
            {
                "score": 85,
                "signal": "🟢 ВЫСОКИЙ ПОТЕНЦИАЛ",
                "reasons": ["Свежий токен", "Хорошая ликвидность", ...]
            }
        """
        score = 0
        reasons = []

        # Получаем метрики
        liquidity = float(token.get("liquidity", {}).get("usd", 0) or 0)
        market_cap = float(token.get("marketCap", 0) or token.get("fdv", 0) or 0)
        volume_24h = float(token.get("volume", {}).get("h24", 0) or 0)
        price_change_24h = float(token.get("priceChange", {}).get("h24", 0) or 0)

        # Возраст токена
        created_at = token.get("pairCreatedAt")
        if created_at:
            age_hours = (datetime.now().timestamp() * 1000 - created_at) / (
                1000 * 60 * 60
            )
        else:
            age_hours = self.UNKNOWN_TOKEN_AGE_HOURS

        # === ВОЗРАСТ (max 25) ===
        if age_hours < 24:
            score += 25
            reasons.append(f"🔥 Очень свежий ({age_hours:.0f}ч)")
        elif age_hours < 72:
            score += 20
            reasons.append(f"✨ Свежий ({age_hours:.0f}ч)")
        elif age_hours < 168:
            score += 10
            reasons.append(f"📅 Новый ({age_hours / 24:.0f}д)")

        # === ЛИКВИДНОСТЬ (max 20) ===
        if 30_000 <= liquidity <= 100_000:
            score += 20
            reasons.append(f"💧 Идеальная ликвидность (${liquidity / 1000:.0f}K)")
        elif 10_000 <= liquidity < 30_000:
            score += 15
            reasons.append(f"💧 Хорошая ликвидность (${liquidity / 1000:.0f}K)")
        elif 100_000 < liquidity <= 300_000:
            score += 10
            reasons.append(f"💧 Высокая ликвидность (${liquidity / 1000:.0f}K)")

        # === ОБЪЁМ (max 20) ===
        if volume_24h > 100_000:
            score += 20
            reasons.append(f"📊 Отличный объём (${volume_24h / 1000:.0f}K)")
        elif volume_24h > 50_000:
            score += 15
            reasons.append(f"📊 Хороший объём (${volume_24h / 1000:.0f}K)")
        elif volume_24h > 10_000:
            score += 10
            reasons.append(f"📊 Есть объём (${volume_24h / 1000:.0f}K)")

        # === РОСТ ЦЕНЫ (max 20) ===
        if 10 < price_change_24h < 100:
            score += 20
            reasons.append(f"📈 Здоровый рост (+{price_change_24h:.0f}%)")
        elif 0 < price_change_24h <= 10:
            score += 15
            reasons.append(f"📈 Стабильный рост (+{price_change_24h:.0f}%)")
        elif 100 <= price_change_24h < 500:
            score += 10
            reasons.append(f"🚀 Сильный рост (+{price_change_24h:.0f}%)")
        elif price_change_24h >= 500:
            score += 5
            reasons.append(f"⚠️ Возможный памп (+{price_change_24h:.0f}%)")

        # === MARKET CAP (max 15) ===
        if market_cap < 100_000:
            score += 15
            reasons.append(f"💎 Микрокап (${market_cap / 1000:.0f}K)")
        elif market_cap < 500_000:
            score += 12
            reasons.append(f"💎 Низкий кап (${market_cap / 1000:.0f}K)")
        elif market_cap < 1_000_000:
            score += 8
            reasons.append("📊 Кап < $1M")

        # Определяем сигнал
        if score >= 70:
            signal = "🟢 ВЫСОКИЙ ПОТЕНЦИАЛ"
        elif score >= 50:
            signal = "🟡 СРЕДНИЙ ПОТЕНЦИАЛ"
        elif score >= 30:
            signal = "🟠 НИЗКИЙ ПОТЕНЦИАЛ"
        else:
            signal = "🔴 ВЫСОКИЙ РИСК"

        return {"score": min(100, score), "signal": signal, "reasons": reasons}

    def format_gems_message(self, gems: List[Dict], network: str) -> str:
        """Форматирует сообщение с найденными гемами."""

        network_emoji = {"solana": "☀️", "base": "🔵", "ethereum": "💎", "bsc": "🟡"}

        emoji = network_emoji.get(network.lower(), "🌐")

        lines = [
            f"💎 НОВЫЕ ГЕМЫ {emoji} {network.upper()}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"⏰ Обновлено: {datetime.now().strftime('%H:%M:%S')}",
            "",
        ]

        if not gems:
            lines.append("❌ Гемы не найдены по текущим фильтрам")
            lines.append("")
            lines.append("Попробуйте другую сеть или подождите")
        else:
            for i, gem in enumerate(gems, 1):
                # Получаем данные
                base_token = gem.get("baseToken", {})
                symbol = base_token.get("symbol", gem.get("symbol", "???"))
                name = base_token.get("name", gem.get("name", "Unknown"))

                price = float(gem.get("priceUsd", 0) or 0)
                market_cap = float(gem.get("marketCap", 0) or gem.get("fdv", 0) or 0)
                liquidity = float(gem.get("liquidity", {}).get("usd", 0) or 0)
                volume_24h = float(gem.get("volume", {}).get("h24", 0) or 0)
                price_change = float(gem.get("priceChange", {}).get("h24", 0) or 0)

                score = gem.get("_gem_score", 0)
                signal = gem.get("_gem_signal", "")
                reasons = gem.get("_gem_reasons", [])

                # Возраст
                created_at = gem.get("pairCreatedAt")
                if created_at:
                    age_hours = (datetime.now().timestamp() * 1000 - created_at) / (
                        1000 * 60 * 60
                    )
                    if age_hours < 24:
                        age_str = f"{age_hours:.0f}ч"
                    else:
                        age_str = f"{age_hours / 24:.0f}д"
                else:
                    age_str = "?"

                # Форматируем цену
                if price < 0.00001:
                    price_str = f"${price:.8f}"
                elif price < 0.01:
                    price_str = f"${price:.6f}"
                elif price < 1:
                    price_str = f"${price:.4f}"
                else:
                    price_str = f"${price:.2f}"

                lines.append(f"💎 #{i} {symbol}")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append(f"📛 {name}")
                lines.append(f"💰 Цена: {price_str}")
                lines.append(f"📊 Кап: ${market_cap / 1000:.0f}K")
                lines.append(f"💧 Ликвидность: ${liquidity / 1000:.0f}K")
                lines.append(f"📈 Объём 24ч: ${volume_24h / 1000:.0f}K")
                lines.append(
                    f"📊 Изменение: {'+' if price_change > 0 else ''}{price_change:.1f}%"
                )
                lines.append(f"⏰ Возраст: {age_str}")
                lines.append("")
                lines.append(f"🎯 Потенциал: {score}% {signal}")

                if reasons:
                    lines.append("")
                    lines.append("🔮 Почему:")
                    for reason in reasons[:4]:
                        lines.append(f"• {reason}")

                # Ссылки
                lines.append("")
                lines.append("🔗 DEX Screener | Contract")
                lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ DYOR! Высокий риск!")

        return "\n".join(lines)
