#!/usr/bin/env python3
"""
Backtesting Script - проверка сигналов на исторических данных.

Использование:
    python scripts/run_backtest.py --symbol BTC --days 30
    python scripts/run_backtest.py --symbol ETH --days 7
    python scripts/run_backtest.py --all --days 14
"""

import argparse
import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from signals.ai_signals import AISignalAnalyzer
from api_manager import get_coin_price

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


@dataclass
class BacktestResult:
    """Результат бэктеста."""
    symbol: str
    total_signals: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    max_drawdown: float
    best_trade: float
    worst_trade: float


class Backtester:
    """
    Бэктестер для проверки сигналов на исторических данных.
    """
    
    SUPPORTED_SYMBOLS = ["BTC", "ETH", "TON", "SOL", "XRP"]
    
    def __init__(self):
        """Initialize backtester with mock whale tracker."""
        # Create a mock whale tracker for the analyzer
        from unittest.mock import Mock, AsyncMock
        mock_whale_tracker = Mock()
        mock_whale_tracker.get_transactions_by_blockchain = AsyncMock(return_value=[])
        self.analyzer = AISignalAnalyzer(mock_whale_tracker)
    
    async def fetch_historical_data(self, symbol: str, days: int) -> List[Dict]:
        """
        Получить исторические данные.
        
        Returns:
            List[Dict]: [{"timestamp": datetime, "price": float, "ohlcv": {...}}, ...]
        """
        logger.info(f"Fetching historical data for {symbol} over {days} days...")
        
        # Use Bybit to fetch historical 4h candles
        # For simplicity, we'll use the existing get_price_history_bybit method
        # 4h interval, limit based on days (6 candles per day for 4h)
        candles_needed = days * 6
        
        try:
            bybit_symbol = self.analyzer.bybit_mapping.get(symbol, f"{symbol}USDT")
            prices_data = await self.analyzer.get_price_history_bybit(
                symbol, interval="240", limit=min(candles_needed, 200)
            )
            
            if not prices_data or len(prices_data) < 10:
                logger.error(f"Insufficient historical data for {symbol}")
                return []
            
            # Get OHLCV data as well
            ohlcv_data = await self.analyzer.get_ohlcv_data(symbol, interval="4h", limit=min(candles_needed, 200))
            
            if not ohlcv_data:
                logger.error(f"Failed to fetch OHLCV data for {symbol}")
                return []
            
            # Combine price and OHLCV data
            historical_data = []
            for i, candle in enumerate(ohlcv_data):
                historical_data.append({
                    "timestamp": datetime.fromtimestamp(candle.get("time", 0)),
                    "price": candle.get("close", 0),
                    "ohlcv": candle
                })
            
            logger.info(f"Fetched {len(historical_data)} data points for {symbol}")
            return historical_data
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []
    
    async def _generate_signal_at_point(self, symbol: str, data_point: Dict) -> Optional[Dict]:
        """
        Симулировать генерацию сигнала в определенной точке времени.
        
        Returns:
            Dict with signal information or None if signal generation failed
        """
        try:
            # Get market data at this point
            current_price = data_point["price"]
            
            # Simulate minimal signal calculation
            # For backtesting, we'll use a simplified version
            signal_params = {
                "direction": "sideways",  # Default
                "entry_price": current_price,
                "target1_price": current_price * 1.015,
                "target2_price": current_price * 1.025,
                "stop_loss_price": current_price * 0.994,
                "probability": 50.0
            }
            
            # Try to get actual signal params (this may fail due to API limits in backtest)
            try:
                actual_params = await self.analyzer.get_signal_params(symbol)
                if actual_params:
                    signal_params = actual_params
            except Exception as e:
                logger.debug(f"Using default signal params for {symbol}: {e}")
            
            return signal_params
            
        except Exception as e:
            logger.error(f"Error generating signal at point for {symbol}: {e}")
            return None
    
    async def simulate_signals(self, symbol: str, historical_data: List[Dict]) -> List[Dict]:
        """
        Симулировать сигналы на исторических данных.
        
        Для каждой точки данных:
        1. Генерируем сигнал
        2. Проверяем достигла ли цена Target1 или Stop Loss
        3. Записываем результат
        """
        results = []
        
        logger.info(f"Simulating signals for {symbol}...")
        
        # Sample every 2 candles to avoid too many signals
        for i in range(0, len(historical_data) - 5, 2):
            data_point = historical_data[i]
            
            # Generate signal at this point
            signal = await self._generate_signal_at_point(symbol, data_point)
            
            if not signal or signal["direction"] == "sideways":
                continue  # Пропускаем боковик
            
            # Проверяем результат на следующих 4 часах данных (next 4 candles = 16 hours for 4h candles)
            outcome = self._check_outcome(
                signal=signal,
                future_data=historical_data[i+1:min(i+5, len(historical_data))]
            )
            
            results.append({
                "symbol": symbol,
                "timestamp": data_point["timestamp"],
                "direction": signal["direction"],
                "entry_price": signal["entry_price"],
                "target1": signal["target1_price"],
                "stop_loss": signal["stop_loss_price"],
                "outcome": outcome["result"],  # "win" or "loss"
                "exit_price": outcome["exit_price"],
                "pnl_percent": outcome["pnl_percent"]
            })
            
            # Limit number of signals to avoid overwhelming
            if len(results) >= 50:
                break
        
        logger.info(f"Generated {len(results)} signals for {symbol}")
        return results
    
    def _check_outcome(self, signal: Dict, future_data: List[Dict]) -> Dict:
        """Проверить исход сигнала."""
        entry = signal["entry_price"]
        target1 = signal["target1_price"]
        stop_loss = signal["stop_loss_price"]
        direction = signal["direction"]
        
        if not future_data:
            return {"result": "loss", "exit_price": entry, "pnl_percent": 0}
        
        for data in future_data:
            ohlcv = data.get("ohlcv", {})
            high = ohlcv.get("high", data["price"])
            low = ohlcv.get("low", data["price"])
            
            if direction == "long":
                # Проверяем Target1 (цена выросла)
                if high >= target1:
                    pnl = ((target1 - entry) / entry) * 100
                    return {"result": "win", "exit_price": target1, "pnl_percent": pnl}
                # Проверяем Stop Loss (цена упала)
                if low <= stop_loss:
                    pnl = ((stop_loss - entry) / entry) * 100
                    return {"result": "loss", "exit_price": stop_loss, "pnl_percent": pnl}
            
            elif direction == "short":
                # Проверяем Target1 (цена упала)
                if low <= target1:
                    pnl = ((entry - target1) / entry) * 100
                    return {"result": "win", "exit_price": target1, "pnl_percent": pnl}
                # Проверяем Stop Loss (цена выросла)
                if high >= stop_loss:
                    pnl = ((entry - stop_loss) / entry) * 100
                    return {"result": "loss", "exit_price": stop_loss, "pnl_percent": pnl}
        
        # Не достигли ни Target, ни Stop за период
        last_price = future_data[-1]["price"]
        if direction == "long":
            pnl = ((last_price - entry) / entry) * 100
        else:
            pnl = ((entry - last_price) / entry) * 100
        
        # Consider it a loss if we didn't hit target
        return {"result": "loss", "exit_price": last_price, "pnl_percent": pnl}
    
    def calculate_stats(self, results: List[Dict]) -> Optional[BacktestResult]:
        """Рассчитать статистику бэктеста."""
        if not results:
            return None
        
        symbol = results[0]["symbol"]
        wins = [r for r in results if r["outcome"] == "win"]
        losses = [r for r in results if r["outcome"] == "loss"]
        
        win_rate = len(wins) / len(results) * 100 if results else 0
        total_pnl = sum(r["pnl_percent"] for r in results)
        avg_win = sum(r["pnl_percent"] for r in wins) / len(wins) if wins else 0
        avg_loss = sum(r["pnl_percent"] for r in losses) / len(losses) if losses else 0
        
        # Max drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for r in results:
            cumulative += r["pnl_percent"]
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        
        best_trade = max(r["pnl_percent"] for r in results) if results else 0
        worst_trade = min(r["pnl_percent"] for r in results) if results else 0
        
        return BacktestResult(
            symbol=symbol,
            total_signals=len(results),
            wins=len(wins),
            losses=len(losses),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_drawdown=max_dd,
            best_trade=best_trade,
            worst_trade=worst_trade
        )
    
    async def run(self, symbol: str, days: int) -> Optional[BacktestResult]:
        """Запустить бэктест для одной монеты."""
        print(f"📊 Запуск бэктеста для {symbol} за {days} дней...")
        
        # Получаем исторические данные
        historical_data = await self.fetch_historical_data(symbol, days)
        
        if not historical_data:
            print(f"❌ Не удалось получить исторические данные для {symbol}")
            return None
        
        # Симулируем сигналы
        results = await self.simulate_signals(symbol, historical_data)
        
        if not results:
            print(f"⚠️  Не сгенерировано ни одного сигнала для {symbol}")
            return None
        
        # Рассчитываем статистику
        stats = self.calculate_stats(results)
        
        return stats
    
    async def run_all(self, days: int) -> List[BacktestResult]:
        """Запустить бэктест для всех монет."""
        results = []
        for symbol in self.SUPPORTED_SYMBOLS:
            result = await self.run(symbol, days)
            if result:
                results.append(result)
            # Small delay between coins to avoid rate limiting
            await asyncio.sleep(2)
        return results


def print_report(result: BacktestResult):
    """Вывести отчёт бэктеста."""
    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 BACKTEST REPORT: {result.symbol}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 Всего сигналов: {result.total_signals}
✅ Успешных: {result.wins}
❌ Убыточных: {result.losses}

🎯 Win Rate: {result.win_rate:.1f}%
{"█" * int(result.win_rate / 10)}{"░" * (10 - int(result.win_rate / 10))}

💰 Общий P/L: {result.total_pnl:+.2f}%
📈 Средний выигрыш: +{result.avg_win:.2f}%
📉 Средний убыток: {result.avg_loss:.2f}%

🏆 Лучшая сделка: +{result.best_trade:.2f}%
💀 Худшая сделка: {result.worst_trade:.2f}%
📉 Макс. просадка: -{result.max_drawdown:.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


async def main():
    parser = argparse.ArgumentParser(description="Backtest trading signals")
    parser.add_argument("--symbol", type=str, help="Symbol to backtest (BTC, ETH, etc.)")
    parser.add_argument("--all", action="store_true", help="Backtest all symbols")
    parser.add_argument("--days", type=int, default=30, help="Number of days to backtest (default: 30)")
    
    args = parser.parse_args()
    
    backtester = Backtester()
    
    if args.all:
        results = await backtester.run_all(args.days)
        for result in results:
            print_report(result)
        
        # Общая статистика
        if results:
            total_signals = sum(r.total_signals for r in results)
            total_wins = sum(r.wins for r in results)
            total_pnl = sum(r.total_pnl for r in results)
            
            print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ОБЩАЯ СТАТИСТИКА
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Всего сигналов: {total_signals}
🎯 Общий Win Rate: {total_wins / total_signals * 100:.1f}%
💰 Общий P/L: {total_pnl:+.2f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    elif args.symbol:
        result = await backtester.run(args.symbol.upper(), args.days)
        if result:
            print_report(result)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
