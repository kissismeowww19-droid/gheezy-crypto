"""
Gheezy Crypto - DeFi Агрегатор

Анализ лучших APY по протоколам (Aave, Lido, Compound и другие).
Использует DefiLlama API для получения данных.
"""

from dataclasses import dataclass
from typing import List, Optional

import aiohttp
import structlog

from config import settings

logger = structlog.get_logger()


@dataclass
class DeFiPool:
    """
    Пул ликвидности DeFi.

    Attributes:
        pool_id: Уникальный идентификатор пула
        chain: Блокчейн (Ethereum, BSC и т.д.)
        project: Название проекта
        symbol: Символ токена/пары
        tvl: Total Value Locked (USD)
        apy: Годовая процентная доходность
        apy_base: Базовая доходность
        apy_reward: Доходность от наград
        stable: Является ли стейблкоин пулом
    """

    pool_id: str
    chain: str
    project: str
    symbol: str
    tvl: float
    apy: float
    apy_base: Optional[float] = None
    apy_reward: Optional[float] = None
    stable: bool = False

    @property
    def formatted_apy(self) -> str:
        """Форматированная APY."""
        return f"{self.apy:.2f}%"

    @property
    def formatted_tvl(self) -> str:
        """Форматированный TVL."""
        if self.tvl >= 1_000_000_000:
            return f"${self.tvl / 1_000_000_000:.2f}B"
        elif self.tvl >= 1_000_000:
            return f"${self.tvl / 1_000_000:.2f}M"
        elif self.tvl >= 1_000:
            return f"${self.tvl / 1_000:.2f}K"
        return f"${self.tvl:.2f}"


@dataclass
class DeFiProtocol:
    """
    DeFi протокол.

    Attributes:
        name: Название протокола
        symbol: Символ токена
        chain: Основной блокчейн
        tvl: Total Value Locked (USD)
        change_1h: Изменение TVL за 1 час (%)
        change_1d: Изменение TVL за 1 день (%)
        change_7d: Изменение TVL за 7 дней (%)
    """

    name: str
    symbol: Optional[str]
    chain: str
    tvl: float
    change_1h: Optional[float] = None
    change_1d: Optional[float] = None
    change_7d: Optional[float] = None

    @property
    def formatted_tvl(self) -> str:
        """Форматированный TVL."""
        if self.tvl >= 1_000_000_000:
            return f"${self.tvl / 1_000_000_000:.2f}B"
        elif self.tvl >= 1_000_000:
            return f"${self.tvl / 1_000_000:.2f}M"
        elif self.tvl >= 1_000:
            return f"${self.tvl / 1_000:.2f}K"
        return f"${self.tvl:.2f}"


class DeFiAggregator:
    """
    Агрегатор DeFi данных.

    Собирает информацию о лучших APY ставках
    по различным DeFi протоколам через DefiLlama API.
    """

    # Список отслеживаемых протоколов
    TRACKED_PROTOCOLS = [
        "aave",
        "lido",
        "compound",
        "maker",
        "uniswap",
        "curve",
        "convex",
        "yearn",
        "rocket-pool",
        "frax",
    ]

    def __init__(self):
        """Инициализация агрегатора."""
        self.base_url = settings.defillama_api_url
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

    async def get_protocols(self, limit: int = 10) -> List[DeFiProtocol]:
        """
        Получение топ DeFi протоколов по TVL.

        Args:
            limit: Максимальное количество протоколов

        Returns:
            List[DeFiProtocol]: Список протоколов
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/protocols"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error("Ошибка получения протоколов", status=response.status)
                    return []

                data = await response.json()

                protocols = []
                for item in data[:limit]:
                    protocols.append(
                        DeFiProtocol(
                            name=item.get("name", "Unknown"),
                            symbol=item.get("symbol"),
                            chain=item.get("chain", "Multi-chain"),
                            tvl=item.get("tvl", 0),
                            change_1h=item.get("change_1h"),
                            change_1d=item.get("change_1d"),
                            change_7d=item.get("change_7d"),
                        )
                    )

                return protocols

        except Exception as e:
            logger.error("Ошибка при получении протоколов", error=str(e))
            return []

    async def get_pools(
        self,
        min_tvl: float = 1_000_000,
        min_apy: float = 1.0,
        stablecoins_only: bool = False,
        limit: int = 20,
    ) -> List[DeFiPool]:
        """
        Получение пулов с лучшими APY.

        Args:
            min_tvl: Минимальный TVL (USD)
            min_apy: Минимальная APY (%)
            stablecoins_only: Только стейблкоин пулы
            limit: Максимальное количество пулов

        Returns:
            List[DeFiPool]: Список пулов, отсортированных по APY
        """
        try:
            session = await self._get_session()
            url = "https://yields.llama.fi/pools"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error("Ошибка получения пулов", status=response.status)
                    return []

                result = await response.json()
                data = result.get("data", [])

                pools = []
                for item in data:
                    tvl = item.get("tvlUsd", 0)
                    apy = item.get("apy", 0)
                    stable = item.get("stablecoin", False)

                    # Фильтрация
                    if tvl < min_tvl or apy < min_apy:
                        continue
                    if stablecoins_only and not stable:
                        continue
                    if apy > 1000:  # Пропускаем нереалистичные APY
                        continue

                    pools.append(
                        DeFiPool(
                            pool_id=item.get("pool", ""),
                            chain=item.get("chain", "Unknown"),
                            project=item.get("project", "Unknown"),
                            symbol=item.get("symbol", "Unknown"),
                            tvl=tvl,
                            apy=apy,
                            apy_base=item.get("apyBase"),
                            apy_reward=item.get("apyReward"),
                            stable=stable,
                        )
                    )

                # Сортируем по APY (от большего к меньшему)
                pools.sort(key=lambda x: x.apy, reverse=True)

                return pools[:limit]

        except Exception as e:
            logger.error("Ошибка при получении пулов", error=str(e))
            return []

    async def get_best_stablecoin_yields(self, limit: int = 10) -> List[DeFiPool]:
        """
        Получение лучших ставок для стейблкоинов.

        Args:
            limit: Максимальное количество пулов

        Returns:
            List[DeFiPool]: Список пулов со стейблкоинами
        """
        return await self.get_pools(
            min_tvl=1_000_000,
            min_apy=2.0,
            stablecoins_only=True,
            limit=limit,
        )

    async def get_protocol_pools(
        self,
        protocol: str,
        limit: int = 10,
    ) -> List[DeFiPool]:
        """
        Получение пулов конкретного протокола.

        Args:
            protocol: Название протокола
            limit: Максимальное количество пулов

        Returns:
            List[DeFiPool]: Список пулов протокола
        """
        all_pools = await self.get_pools(min_tvl=100_000, min_apy=0.1, limit=1000)

        protocol_pools = [
            pool for pool in all_pools if pool.project.lower() == protocol.lower()
        ]

        return protocol_pools[:limit]

    async def format_defi_message(self) -> str:
        """
        Форматирование сообщения с DeFi данными для Telegram.

        Returns:
            str: Форматированное сообщение
        """
        pools = await self.get_pools(limit=10)
        stablecoin_pools = await self.get_best_stablecoin_yields(limit=5)

        message = ["🏦 **DeFi Агрегатор - Лучшие APY**\n"]

        # Топ пулы
        message.append("📈 **Топ-10 по доходности:**\n")
        for i, pool in enumerate(pools, 1):
            stable_emoji = "🔵" if pool.stable else "⚪"
            message.append(
                f"{i}. {stable_emoji} **{pool.project}** - {pool.symbol}\n"
                f"   APY: {pool.formatted_apy} | TVL: {pool.formatted_tvl} | {pool.chain}"
            )

        # Стейблкоины
        if stablecoin_pools:
            message.append("\n💵 **Лучшие ставки для стейблкоинов:**\n")
            for i, pool in enumerate(stablecoin_pools, 1):
                message.append(
                    f"{i}. **{pool.project}** - {pool.symbol}\n"
                    f"   APY: {pool.formatted_apy} | TVL: {pool.formatted_tvl}"
                )

        message.append(
            "\n⚠️ *Высокий APY = высокий риск. "
            "Проводите собственное исследование (DYOR)!*"
        )

        return "\n".join(message)

    async def format_protocols_message(self) -> str:
        """
        Форматирование сообщения с топ протоколами.

        Returns:
            str: Форматированное сообщение
        """
        protocols = await self.get_protocols(limit=10)

        if not protocols:
            return "❌ Не удалось получить данные о протоколах"

        message = ["🏛️ **Топ-10 DeFi протоколов по TVL**\n"]

        for i, protocol in enumerate(protocols, 1):
            # Определяем эмодзи изменения
            if protocol.change_1d:
                if protocol.change_1d > 0:
                    change_emoji = "📈"
                    change_text = f"+{protocol.change_1d:.2f}%"
                else:
                    change_emoji = "📉"
                    change_text = f"{protocol.change_1d:.2f}%"
            else:
                change_emoji = "➡️"
                change_text = "N/A"

            message.append(
                f"{i}. **{protocol.name}** ({protocol.symbol or 'N/A'})\n"
                f"   TVL: {protocol.formatted_tvl} {change_emoji} {change_text} (24h)"
            )

        message.append("\n📊 *Данные: DefiLlama*")

        return "\n".join(message)
