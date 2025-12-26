"""
Signal Tracker - отслеживание результатов сигналов.
Сохраняет сигналы в SQLite и проверяет результаты.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path
import logging
import asyncio

# Import module for historical price checking (allows for easier mocking in tests)
import api_manager

logger = logging.getLogger(__name__)


@dataclass
class TrackedSignal:
    """Отслеживаемый сигнал."""
    id: Optional[int]
    user_id: int
    symbol: str
    direction: str  # "long", "short", "sideways"
    entry_price: float
    target1_price: float  # Цель 1 (+1.5%)
    target2_price: float  # Цель 2 (+2.0%)
    stop_loss_price: float  # Стоп (-0.6%)
    probability: float
    timestamp: datetime
    result: Optional[str] = None  # "win", "loss", "pending"
    exit_price: Optional[float] = None
    checked_at: Optional[datetime] = None


class SignalTracker:
    """
    Трекер сигналов с SQLite хранилищем.
    
    Функционал:
    - save_signal() - сохранить новый сигнал
    - check_previous_signal() - проверить результат предыдущего сигнала
    - get_user_stats() - получить статистику пользователя
    """
    
    def __init__(self, db_path: str = "data/signals.db"):
        """Инициализация с созданием БД если не существует."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Создание таблицы сигналов."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    target1_price REAL NOT NULL,
                    target2_price REAL NOT NULL,
                    stop_loss_price REAL NOT NULL,
                    probability REAL NOT NULL,
                    timestamp DATETIME NOT NULL,
                    result TEXT DEFAULT 'pending',
                    exit_price REAL,
                    checked_at DATETIME,
                    UNIQUE(user_id, symbol, timestamp)
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_user_symbol ON signals(user_id, symbol)')
            conn.commit()
    
    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Safely parse datetime string from database."""
        if not datetime_str:
            return None
        try:
            return datetime.fromisoformat(datetime_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse datetime '{datetime_str}': {e}")
            return None
    
    def save_signal(
        self,
        user_id: int,
        symbol: str,
        direction: str,
        entry_price: float,
        target1_price: float,
        target2_price: float,
        stop_loss_price: float,
        probability: float
    ) -> TrackedSignal:
        """Сохранить новый сигнал."""
        timestamp = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute('''
                    INSERT INTO signals 
                    (user_id, symbol, direction, entry_price, target1_price, target2_price, 
                     stop_loss_price, probability, timestamp, result)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                ''', (user_id, symbol, direction, entry_price, target1_price, target2_price,
                      stop_loss_price, probability, timestamp))
                conn.commit()
                signal_id = cursor.lastrowid
                
                logger.info(f"Saved signal {signal_id} for user {user_id}, {symbol} {direction}")
                
                return TrackedSignal(
                    id=signal_id,
                    user_id=user_id,
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    target1_price=target1_price,
                    target2_price=target2_price,
                    stop_loss_price=stop_loss_price,
                    probability=probability,
                    timestamp=timestamp,
                    result='pending'
                )
            except sqlite3.IntegrityError:
                # Сигнал с таким user_id, symbol и timestamp уже существует
                logger.warning(f"Signal already exists for user {user_id}, {symbol} at {timestamp}")
                # Получаем существующий сигнал
                cursor = conn.execute('''
                    SELECT id, result, exit_price, checked_at
                    FROM signals
                    WHERE user_id = ? AND symbol = ? AND timestamp = ?
                ''', (user_id, symbol, timestamp))
                row = cursor.fetchone()
                if row:
                    return TrackedSignal(
                        id=row[0],
                        user_id=user_id,
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        target1_price=target1_price,
                        target2_price=target2_price,
                        stop_loss_price=stop_loss_price,
                        probability=probability,
                        timestamp=timestamp,
                        result=row[1],
                        exit_price=row[2],
                        checked_at=self._parse_datetime(row[3])
                    )
                else:
                    # Если по какой-то причине не нашли сигнал, пробрасываем исключение
                    raise
    
    def check_previous_signal(
        self,
        user_id: int,
        symbol: str,
        current_price: float
    ) -> Optional[Dict]:
        """
        Проверить результат предыдущего сигнала для этой монеты.
        
        Теперь проверяет результат по ИСТОРИЧЕСКИМ ЦЕНАМ за 4 часа после сигнала,
        а не по текущей цене!
        
        Возвращает:
        {
            "had_signal": True,
            "direction": "long",
            "entry_price": 87500,
            "target1_price": 88812,
            "target1_reached": True,
            "target2_reached": False,
            "stop_hit": False,
            "result": "win",
            "pnl_percent": 1.5,
            "time_elapsed": "3ч 25мин"
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            # Получить последний pending сигнал для этого user+symbol
            cursor = conn.execute('''
                SELECT id, direction, entry_price, target1_price, target2_price, 
                       stop_loss_price, probability, timestamp, result, checked_at, exit_price
                FROM signals
                WHERE user_id = ? AND symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (user_id, symbol))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            signal_id, direction, entry_price, target1_price, target2_price, \
                stop_loss_price, probability, timestamp_str, result, checked_at_str, exit_price = row
            
            timestamp = datetime.fromisoformat(timestamp_str)
            checked_at = self._parse_datetime(checked_at_str)
            
            # Если сигнал уже проверен (не pending), возвращаем закэшированный результат
            if result != 'pending' and checked_at:
                # Используем сохранённую exit_price из БД, или entry_price если exit_price None
                cached_exit_price = exit_price if exit_price is not None else entry_price
                return self._format_signal_result(
                    direction, entry_price, target1_price, target2_price,
                    stop_loss_price, result, timestamp, cached_exit_price
                )
            
            # Проверяем, созрел ли сигнал (прошло ли 4 часа)
            time_elapsed = datetime.now() - timestamp
            hours_elapsed = time_elapsed.total_seconds() / 3600
            
            # Если сигнал ещё не созрел (<4 часов), возвращаем "в процессе"
            if hours_elapsed < 4:
                return self._format_signal_result(
                    direction, entry_price, target1_price, target2_price,
                    stop_loss_price, 'pending', timestamp, current_price
                )
            
            # Сигнал созрел (>4 часов) - проверяем по историческим ценам
            logger.info(f"Сигнал {signal_id} созрел, проверяем по историческим ценам")
            
            # Рассчитываем временной диапазон: created_at → created_at + 4 часа
            signal_start = timestamp
            signal_end = timestamp + timedelta(hours=4)
            
            from_ts = int(signal_start.timestamp())
            to_ts = int(signal_end.timestamp())
            
            # Получаем исторические цены
            try:
                historical_data = asyncio.run(
                    api_manager.get_historical_prices(symbol, from_ts, to_ts)
                )
            except Exception as e:
                logger.error(f"Ошибка получения исторических цен: {e}")
                historical_data = None
            
            # Если не удалось получить исторические данные, используем текущую цену
            if not historical_data or not historical_data.get("success"):
                logger.warning(
                    f"Не удалось получить исторические данные для {symbol}, "
                    f"используем текущую цену"
                )
                return self._check_with_current_price(
                    conn, signal_id, direction, entry_price, target1_price,
                    target2_price, stop_loss_price, timestamp, current_price
                )
            
            # Проверяем результат по историческим ценам
            max_price = historical_data["max_price"]
            min_price = historical_data["min_price"]
            
            logger.info(
                f"Исторические цены для {symbol}: "
                f"min=${min_price:.2f}, max=${max_price:.2f}"
            )
            
            target1_reached = False
            target2_reached = False
            stop_hit = False
            final_result = 'loss'  # По умолчанию loss если цели не достигнуты
            exit_price = entry_price
            pnl_percent = 0.0
            
            if direction == "long":
                # Для long: проверяем, был ли задет стоп ПЕРВЫМ
                if min_price <= stop_loss_price:
                    # Стоп был задет
                    stop_hit = True
                    final_result = 'loss'
                    exit_price = stop_loss_price
                    pnl_percent = ((stop_loss_price - entry_price) / entry_price) * 100
                elif max_price >= target1_price:
                    # Цель достигнута, стоп не задет
                    target1_reached = True
                    final_result = 'win'
                    exit_price = target1_price
                    pnl_percent = ((target1_price - entry_price) / entry_price) * 100
                    if max_price >= target2_price:
                        target2_reached = True
                        exit_price = target2_price
                        pnl_percent = ((target2_price - entry_price) / entry_price) * 100
                else:
                    # Ни цель, ни стоп не достигнуты за 4 часа
                    final_result = 'loss'
                    exit_price = max_price  # Используем максимальную цену
                    pnl_percent = ((max_price - entry_price) / entry_price) * 100
            
            elif direction == "short":
                # Для short: проверяем, был ли задет стоп ПЕРВЫМ
                if max_price >= stop_loss_price:
                    # Стоп был задет
                    stop_hit = True
                    final_result = 'loss'
                    exit_price = stop_loss_price
                    pnl_percent = ((entry_price - stop_loss_price) / entry_price) * 100
                elif min_price <= target1_price:
                    # Цель достигнута, стоп не задет
                    target1_reached = True
                    final_result = 'win'
                    exit_price = target1_price
                    pnl_percent = ((entry_price - target1_price) / entry_price) * 100
                    if min_price <= target2_price:
                        target2_reached = True
                        exit_price = target2_price
                        pnl_percent = ((entry_price - target2_price) / entry_price) * 100
                else:
                    # Ни цель, ни стоп не достигнуты за 4 часа
                    final_result = 'loss'
                    exit_price = min_price  # Используем минимальную цену
                    pnl_percent = ((entry_price - min_price) / entry_price) * 100
            
            elif direction == "sideways":
                # Для sideways - проверяем, осталась ли цена в диапазоне
                range_percent = 1.0  # +/- 1%
                upper_bound = entry_price * (1 + range_percent / 100)
                lower_bound = entry_price * (1 - range_percent / 100)
                
                # Проверяем, оставались ли ВСЕ цены в диапазоне
                all_in_range = min_price >= lower_bound and max_price <= upper_bound
                
                if all_in_range:
                    final_result = 'win'
                    pnl_percent = 0.5  # Небольшая прибыль за правильный прогноз
                else:
                    final_result = 'loss'
                    pnl_percent = -0.5
                
                exit_price = (min_price + max_price) / 2  # Средняя цена
            
            # Обновляем результат в БД (кэшируем)
            conn.execute('''
                UPDATE signals
                SET result = ?, exit_price = ?, checked_at = ?
                WHERE id = ?
            ''', (final_result, exit_price, datetime.now(), signal_id))
            conn.commit()
            
            logger.info(
                f"Обновлен сигнал {signal_id}: {final_result} "
                f"with P&L {pnl_percent:.2f}% (historical check)"
            )
            
            return self._format_signal_result(
                direction, entry_price, target1_price, target2_price,
                stop_loss_price, final_result, timestamp, exit_price,
                target1_reached, target2_reached, stop_hit, pnl_percent
            )
    
    def _check_with_current_price(
        self,
        conn,
        signal_id: int,
        direction: str,
        entry_price: float,
        target1_price: float,
        target2_price: float,
        stop_loss_price: float,
        timestamp: datetime,
        current_price: float
    ) -> Dict:
        """Fallback: проверка по текущей цене (старая логика)."""
        target1_reached = False
        target2_reached = False
        stop_hit = False
        final_result = 'pending'
        pnl_percent = 0.0
        
        if direction == "long":
            if current_price >= target1_price:
                target1_reached = True
                final_result = 'win'
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
                if current_price >= target2_price:
                    target2_reached = True
            elif current_price <= stop_loss_price:
                stop_hit = True
                final_result = 'loss'
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
        
        elif direction == "short":
            if current_price <= target1_price:
                target1_reached = True
                final_result = 'win'
                pnl_percent = ((entry_price - current_price) / entry_price) * 100
                if current_price <= target2_price:
                    target2_reached = True
            elif current_price >= stop_loss_price:
                stop_hit = True
                final_result = 'loss'
                pnl_percent = ((entry_price - current_price) / entry_price) * 100
        
        elif direction == "sideways":
            range_percent = 1.0
            upper_bound = entry_price * (1 + range_percent / 100)
            lower_bound = entry_price * (1 - range_percent / 100)
            
            if lower_bound <= current_price <= upper_bound:
                final_result = 'win'
                pnl_percent = 0.5
            else:
                final_result = 'loss'
                pnl_percent = -0.5
        
        # Обновляем результат в БД если изменился
        if final_result != 'pending':
            conn.execute('''
                UPDATE signals
                SET result = ?, exit_price = ?, checked_at = ?
                WHERE id = ?
            ''', (final_result, current_price, datetime.now(), signal_id))
            conn.commit()
            logger.info(
                f"Updated signal {signal_id}: {final_result} "
                f"with P&L {pnl_percent:.2f}% (current price fallback)"
            )
        
        return self._format_signal_result(
            direction, entry_price, target1_price, target2_price,
            stop_loss_price, final_result, timestamp, current_price,
            target1_reached, target2_reached, stop_hit, pnl_percent
        )
    
    def _format_signal_result(
        self,
        direction: str,
        entry_price: float,
        target1_price: float,
        target2_price: float,
        stop_loss_price: float,
        result: str,
        timestamp: datetime,
        exit_price: float,
        target1_reached: bool = False,
        target2_reached: bool = False,
        stop_hit: bool = False,
        pnl_percent: float = 0.0
    ) -> Dict:
        """Форматировать результат проверки сигнала."""
        # Расчёт времени с момента сигнала
        time_elapsed = datetime.now() - timestamp
        hours = int(time_elapsed.total_seconds() // 3600)
        minutes = int((time_elapsed.total_seconds() % 3600) // 60)
        
        if hours > 0:
            time_elapsed_str = f"{hours}ч {minutes}мин"
        else:
            time_elapsed_str = f"{minutes}мин"
        
        # Для pending сигналов пересчитываем флаги на основе текущего состояния
        if result == 'pending':
            if direction == "long":
                target1_reached = exit_price >= target1_price
                target2_reached = exit_price >= target2_price
                stop_hit = exit_price <= stop_loss_price
                if target1_reached or target2_reached or stop_hit:
                    pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            elif direction == "short":
                target1_reached = exit_price <= target1_price
                target2_reached = exit_price <= target2_price
                stop_hit = exit_price >= stop_loss_price
                if target1_reached or target2_reached or stop_hit:
                    pnl_percent = ((entry_price - exit_price) / entry_price) * 100
        
        return {
            "had_signal": True,
            "direction": direction,
            "entry_price": entry_price,
            "target1_price": target1_price,
            "target2_price": target2_price,
            "stop_loss_price": stop_loss_price,
            "target1_reached": target1_reached,
            "target2_reached": target2_reached,
            "stop_hit": stop_hit,
            "result": result,
            "pnl_percent": pnl_percent,
            "time_elapsed": time_elapsed_str
        }
    
    def get_user_stats(self, user_id: int) -> Dict:
        """
        Получить статистику пользователя.
        
        Возвращает:
        {
            "total_signals": 45,
            "wins": 28,
            "losses": 12,
            "pending": 5,
            "win_rate": 70.0,
            "total_pnl": 15.5,
            "best_symbol": "BTC",
            "worst_symbol": "XRP"
        }
        """
        with sqlite3.connect(self.db_path) as conn:
            # Общая статистика
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN result = 'pending' THEN 1 ELSE 0 END) as pending
                FROM signals
                WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            total_signals = row[0] or 0
            wins = row[1] or 0
            losses = row[2] or 0
            pending = row[3] or 0
            
            # Расчёт win rate
            completed = wins + losses
            win_rate = (wins / completed * 100) if completed > 0 else 0.0
            
            # Расчёт общего P&L
            cursor = conn.execute('''
                SELECT 
                    direction,
                    entry_price,
                    exit_price,
                    result
                FROM signals
                WHERE user_id = ? AND result IN ('win', 'loss') AND exit_price IS NOT NULL
            ''', (user_id,))
            
            total_pnl = 0.0
            for direction, entry_price, exit_price, result in cursor.fetchall():
                # Skip if entry_price is 0 to avoid division by zero
                if entry_price == 0:
                    continue
                    
                if direction == "long":
                    pnl = ((exit_price - entry_price) / entry_price) * 100
                elif direction == "short":
                    pnl = ((entry_price - exit_price) / entry_price) * 100
                elif direction == "sideways":
                    pnl = 0.5 if result == 'win' else -0.5
                else:
                    pnl = 0.0
                total_pnl += pnl
            
            # Лучшая и худшая монета
            cursor = conn.execute('''
                SELECT 
                    symbol,
                    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
                    COUNT(*) as total
                FROM signals
                WHERE user_id = ? AND result IN ('win', 'loss')
                GROUP BY symbol
                HAVING total > 0
                ORDER BY (CAST(wins AS FLOAT) / total) DESC
            ''', (user_id,))
            
            symbol_stats = cursor.fetchall()
            
            # Handle best/worst symbols
            if not symbol_stats:
                best_symbol = "N/A"
                worst_symbol = "N/A"
            elif len(symbol_stats) == 1:
                # If only one symbol, show it for best but N/A for worst
                best_symbol = symbol_stats[0][0]
                worst_symbol = "N/A"
            else:
                # Multiple symbols - show best and worst
                best_symbol = symbol_stats[0][0]
                worst_symbol = symbol_stats[-1][0]
            
            return {
                "total_signals": total_signals,
                "wins": wins,
                "losses": losses,
                "pending": pending,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "best_symbol": best_symbol,
                "worst_symbol": worst_symbol
            }
    
    def get_coin_stats(self, user_id: int, symbol: str) -> Dict:
        """
        Получить статистику по конкретной монете для пользователя.
        
        Args:
            user_id: ID пользователя
            symbol: Символ монеты (BTC, ETH, TON, SOL, XRP)
        
        Returns:
            Dictionary with coin statistics including:
            - total: общее количество сигналов
            - wins: успешных сигналов
            - losses: убыточных сигналов
            - pending: сигналов в ожидании
            - win_rate: процент успешных сигналов
            - total_pl: общий P/L в процентах
            - best_signal: лучший сигнал (% прибыли)
            - worst_signal: худший сигнал (% убытка)
            - last_signal_time: время последнего сигнала
        """
        with sqlite3.connect(self.db_path) as conn:
            # Получить все сигналы для данной монеты
            cursor = conn.execute('''
                SELECT 
                    result,
                    direction,
                    entry_price,
                    exit_price,
                    timestamp
                FROM signals
                WHERE user_id = ? AND symbol = ?
                ORDER BY timestamp DESC
            ''', (user_id, symbol.upper()))
            
            signals = cursor.fetchall()
            
            if not signals:
                return {
                    'total': 0,
                    'wins': 0,
                    'losses': 0,
                    'pending': 0,
                    'win_rate': 0.0,
                    'total_pl': 0.0,
                    'best_signal': 0.0,
                    'worst_signal': 0.0,
                    'last_signal_time': None
                }
            
            total = len(signals)
            wins = 0
            losses = 0
            pending = 0
            pnl_list = []
            
            for result, direction, entry_price, exit_price, timestamp_str in signals:
                if result == 'win':
                    wins += 1
                elif result == 'loss':
                    losses += 1
                elif result == 'pending':
                    pending += 1
                
                # Рассчитать P/L для завершенных сигналов
                if result in ['win', 'loss'] and exit_price is not None and entry_price > 0:
                    if direction == 'long':
                        pnl = ((exit_price - entry_price) / entry_price) * 100
                    elif direction == 'short':
                        pnl = ((entry_price - exit_price) / entry_price) * 100
                    elif direction == 'sideways':
                        pnl = 0.5 if result == 'win' else -0.5
                    else:
                        pnl = 0.0
                    pnl_list.append(pnl)
            
            # Расчёт метрик
            completed = wins + losses
            win_rate = (wins / completed * 100) if completed > 0 else 0.0
            total_pl = sum(pnl_list) if pnl_list else 0.0
            best_signal = max(pnl_list) if pnl_list else 0.0
            worst_signal = min(pnl_list) if pnl_list else 0.0
            
            # Время последнего сигнала
            last_signal_time = None
            if signals:
                last_timestamp_str = signals[0][4]  # timestamp из первой записи (ORDER BY DESC)
                last_signal_time = self._parse_datetime(last_timestamp_str)
            
            return {
                'total': total,
                'wins': wins,
                'losses': losses,
                'pending': pending,
                'win_rate': win_rate,
                'total_pl': total_pl,
                'best_signal': best_signal,
                'worst_signal': worst_signal,
                'last_signal_time': last_signal_time
            }
    
    def get_pending_signals(self, user_id: int, symbol: Optional[str] = None) -> List[TrackedSignal]:
        """
        Get all pending signals for a user, optionally filtered by symbol.
        
        Args:
            user_id: ID of the user
            symbol: Optional symbol to filter by (e.g., "BTC", "ETH")
        
        Returns:
            List of TrackedSignal objects with pending status
        """
        with sqlite3.connect(self.db_path) as conn:
            if symbol:
                cursor = conn.execute('''
                    SELECT id, symbol, direction, entry_price, target1_price, target2_price,
                           stop_loss_price, probability, timestamp
                    FROM signals
                    WHERE user_id = ? AND symbol = ? AND result = 'pending'
                    ORDER BY timestamp DESC
                ''', (user_id, symbol.upper()))
            else:
                cursor = conn.execute('''
                    SELECT id, symbol, direction, entry_price, target1_price, target2_price,
                           stop_loss_price, probability, timestamp
                    FROM signals
                    WHERE user_id = ? AND result = 'pending'
                    ORDER BY timestamp DESC
                ''', (user_id,))
            
            signals = []
            for row in cursor.fetchall():
                signal_id, symbol, direction, entry_price, target1_price, target2_price, \
                    stop_loss_price, probability, timestamp_str = row
                
                timestamp = datetime.fromisoformat(timestamp_str)
                
                signals.append(TrackedSignal(
                    id=signal_id,
                    user_id=user_id,
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    target1_price=target1_price,
                    target2_price=target2_price,
                    stop_loss_price=stop_loss_price,
                    probability=probability,
                    timestamp=timestamp,
                    result='pending'
                ))
            
            return signals
    
    async def check_all_pending_signals(self, user_id: int) -> Dict:
        """
        Check ALL pending signals for a user using historical prices.
        
        This method checks signals that are older than 4 hours using historical
        price data to determine if they hit their targets or stop losses.
        
        Args:
            user_id: ID of the user
        
        Returns:
            Dict with counts: {'checked': 5, 'wins': 3, 'losses': 2, 'still_pending': 1}
        """
        pending_signals = self.get_pending_signals(user_id)
        
        results = {'checked': 0, 'wins': 0, 'losses': 0, 'still_pending': 0}
        
        for signal in pending_signals:
            # Calculate age of signal
            time_elapsed = datetime.now() - signal.timestamp
            hours_elapsed = time_elapsed.total_seconds() / 3600
            
            # Check if signal is older than 4 hours
            if hours_elapsed >= 4:
                # Get historical prices for the 4h period after signal
                signal_start = signal.timestamp
                signal_end = signal.timestamp + timedelta(hours=4)
                
                from_ts = int(signal_start.timestamp())
                to_ts = int(signal_end.timestamp())
                
                try:
                    historical_data = await api_manager.get_historical_prices(
                        signal.symbol, from_ts, to_ts
                    )
                except Exception as e:
                    logger.error(f"Error getting historical prices for signal {signal.id}: {e}")
                    results['still_pending'] += 1
                    continue
                
                if not historical_data or not historical_data.get("success"):
                    logger.warning(
                        f"No historical data for signal {signal.id}, keeping as pending"
                    )
                    results['still_pending'] += 1
                    continue
                
                # Check signal result using historical prices
                max_price = historical_data["max_price"]
                min_price = historical_data["min_price"]
                
                final_result = self._evaluate_signal_result(
                    signal, max_price, min_price
                )
                
                if final_result:
                    results['checked'] += 1
                    if final_result == 'win':
                        results['wins'] += 1
                    elif final_result == 'loss':
                        results['losses'] += 1
                else:
                    results['still_pending'] += 1
            else:
                results['still_pending'] += 1
            
            # Small delay between signals to be nice to APIs
            await asyncio.sleep(0.5)
        
        return results
    
    async def check_pending_signals_for_symbol(self, user_id: int, symbol: str) -> Dict:
        """
        Check pending signals for a specific symbol using historical prices.
        
        Args:
            user_id: ID of the user
            symbol: Symbol to check (e.g., "BTC", "ETH")
        
        Returns:
            Dict with counts: {'checked': 3, 'wins': 2, 'losses': 1, 'still_pending': 0}
        """
        pending_signals = self.get_pending_signals(user_id, symbol)
        
        results = {'checked': 0, 'wins': 0, 'losses': 0, 'still_pending': 0}
        
        for signal in pending_signals:
            # Calculate age of signal
            time_elapsed = datetime.now() - signal.timestamp
            hours_elapsed = time_elapsed.total_seconds() / 3600
            
            # Check if signal is older than 4 hours
            if hours_elapsed >= 4:
                # Get historical prices for the 4h period after signal
                signal_start = signal.timestamp
                signal_end = signal.timestamp + timedelta(hours=4)
                
                from_ts = int(signal_start.timestamp())
                to_ts = int(signal_end.timestamp())
                
                try:
                    historical_data = await api_manager.get_historical_prices(
                        signal.symbol, from_ts, to_ts
                    )
                except Exception as e:
                    logger.error(f"Error getting historical prices for signal {signal.id}: {e}")
                    results['still_pending'] += 1
                    continue
                
                if not historical_data or not historical_data.get("success"):
                    logger.warning(
                        f"No historical data for signal {signal.id}, keeping as pending"
                    )
                    results['still_pending'] += 1
                    continue
                
                # Check signal result using historical prices
                max_price = historical_data["max_price"]
                min_price = historical_data["min_price"]
                
                final_result = self._evaluate_signal_result(
                    signal, max_price, min_price
                )
                
                if final_result:
                    results['checked'] += 1
                    if final_result == 'win':
                        results['wins'] += 1
                    elif final_result == 'loss':
                        results['losses'] += 1
                else:
                    results['still_pending'] += 1
            else:
                results['still_pending'] += 1
            
            # Small delay between signals to be nice to APIs
            await asyncio.sleep(0.5)
        
        return results
    
    def _evaluate_signal_result(
        self,
        signal: TrackedSignal,
        max_price: float,
        min_price: float
    ) -> Optional[str]:
        """
        Evaluate a signal's result based on historical min/max prices.
        
        Args:
            signal: The TrackedSignal to evaluate
            max_price: Maximum price during the period
            min_price: Minimum price during the period
        
        Returns:
            'win', 'loss', or None if result cannot be determined
        """
        final_result = None
        exit_price = signal.entry_price
        
        if signal.direction == "long":
            # For long: check if stop was hit FIRST
            if min_price <= signal.stop_loss_price:
                # Stop was hit
                final_result = 'loss'
                exit_price = signal.stop_loss_price
            elif max_price >= signal.target1_price:
                # Target reached, stop not hit
                final_result = 'win'
                exit_price = signal.target1_price
                if max_price >= signal.target2_price:
                    exit_price = signal.target2_price
            else:
                # Neither target nor stop reached in 4 hours
                final_result = 'loss'
                exit_price = max_price
        
        elif signal.direction == "short":
            # For short: check if stop was hit FIRST
            if max_price >= signal.stop_loss_price:
                # Stop was hit
                final_result = 'loss'
                exit_price = signal.stop_loss_price
            elif min_price <= signal.target1_price:
                # Target reached, stop not hit
                final_result = 'win'
                exit_price = signal.target1_price
                if min_price <= signal.target2_price:
                    exit_price = signal.target2_price
            else:
                # Neither target nor stop reached in 4 hours
                final_result = 'loss'
                exit_price = min_price
        
        elif signal.direction == "sideways":
            # For sideways - check if price stayed in range
            range_percent = 1.0  # +/- 1%
            upper_bound = signal.entry_price * (1 + range_percent / 100)
            lower_bound = signal.entry_price * (1 - range_percent / 100)
            
            all_in_range = min_price >= lower_bound and max_price <= upper_bound
            
            if all_in_range:
                final_result = 'win'
            else:
                final_result = 'loss'
            
            exit_price = (min_price + max_price) / 2
        
        # Update the signal in database
        if final_result:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE signals
                    SET result = ?, exit_price = ?, checked_at = ?
                    WHERE id = ?
                ''', (final_result, exit_price, datetime.now(), signal.id))
                conn.commit()
            
            logger.info(
                f"Updated signal {signal.id} ({signal.symbol} {signal.direction}): "
                f"{final_result} at ${exit_price:.2f}"
            )
        
        return final_result
