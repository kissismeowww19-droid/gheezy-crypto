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
                        checked_at=datetime.fromisoformat(row[3]) if row[3] else None
                    )
                raise
    
    def check_previous_signal(
        self,
        user_id: int,
        symbol: str,
        current_price: float
    ) -> Optional[Dict]:
        """
        Проверить результат предыдущего сигнала для этой монеты.
        
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
                       stop_loss_price, probability, timestamp, result
                FROM signals
                WHERE user_id = ? AND symbol = ? AND result = 'pending'
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (user_id, symbol))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            signal_id, direction, entry_price, target1_price, target2_price, \
                stop_loss_price, probability, timestamp_str, result = row
            
            timestamp = datetime.fromisoformat(timestamp_str)
            
            # Проверяем результат на основе текущей цены
            target1_reached = False
            target2_reached = False
            stop_hit = False
            final_result = 'pending'
            pnl_percent = 0.0
            
            if direction == "long":
                # Для long сигнала
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
                # Для short сигнала
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
                # Для sideways - проверяем, осталась ли цена в диапазоне
                range_percent = 1.0  # +/- 1%
                upper_bound = entry_price * (1 + range_percent / 100)
                lower_bound = entry_price * (1 - range_percent / 100)
                
                if lower_bound <= current_price <= upper_bound:
                    final_result = 'win'
                    pnl_percent = 0.5  # Небольшая прибыль за правильный прогноз
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
                logger.info(f"Updated signal {signal_id}: {final_result} with P&L {pnl_percent:.2f}%")
            
            # Расчёт времени с момента сигнала
            time_elapsed = datetime.now() - timestamp
            hours = int(time_elapsed.total_seconds() // 3600)
            minutes = int((time_elapsed.total_seconds() % 3600) // 60)
            
            if hours > 0:
                time_elapsed_str = f"{hours}ч {minutes}мин"
            else:
                time_elapsed_str = f"{minutes}мин"
            
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
                "result": final_result,
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
            
            best_symbol = symbol_stats[0][0] if symbol_stats else "N/A"
            worst_symbol = symbol_stats[-1][0] if symbol_stats else "N/A"
            
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
