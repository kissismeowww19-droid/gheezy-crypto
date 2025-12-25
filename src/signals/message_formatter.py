"""
Compact Message Formatter - форматирует сигналы в компактном виде (15-20 строк).

Создаёт краткие и информативные сообщения о торговых сигналах.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CompactMessageFormatter:
    """
    Форматирует торговые сигналы в компактное сообщение (15-20 строк).
    
    Включает:
    - Направление и точку входа
    - TP1, TP2, SL, R:R
    - Прогноз и уверенность
    - Ключевые уровни (POC, сопротивление, поддержка)
    - Топ-4 причины для входа
    """
    
    def format_signal(
        self,
        coin: str,
        direction: str,
        entry_price: float,
        targets: Dict,
        confidence: float,
        timeframe: str = "4H",
        levels: Optional[Dict] = None,
        reasons: Optional[List[Dict]] = None,
        enhancer_data: Optional[Dict] = None
    ) -> str:
        """
        Форматирует сигнал в компактное сообщение.
        
        Args:
            coin: Символ монеты (BTC, ETH, etc.)
            direction: Направление сигнала ("long" или "short" или "sideways")
            entry_price: Цена входа
            targets: Dict с ключами tp1, tp2, sl, rr (R:R соотношение)
            confidence: Уверенность в сигнале (0-100)
            timeframe: Временной фрейм прогноза (по умолчанию "4H")
            levels: Dict с ключевыми уровнями (poc, resistance, support)
            reasons: Список причин для входа [{icon, name, value}, ...]
            enhancer_data: Данные от enhancers для автоматического извлечения причин
            
        Returns:
            Отформатированное сообщение для Telegram
        """
        # Нормализуем direction
        direction = direction.lower()
        
        # Определяем эмодзи и текст направления
        if direction == "long":
            direction_emoji = "🚀"
            direction_text = "LONG"
        elif direction == "short":
            direction_emoji = "📉"
            direction_text = "SHORT"
        else:  # sideways
            direction_emoji = "➡️"
            direction_text = "SIDEWAYS"
        
        # Начинаем сообщение
        lines = []
        lines.append(f"{direction_emoji} *{direction_text} {coin}*\n")
        
        # Блок цен
        lines.append(f"💰 *Вход:* {self._format_price(entry_price)}")
        
        # TP и SL
        tp1 = targets.get("tp1")
        tp2 = targets.get("tp2")
        sl = targets.get("sl")
        rr = targets.get("rr")
        
        if direction == "sideways":
            # Для боковика показываем диапазон
            lines.append(f"🎯 *Диапазон:* {self._format_price(tp1)} - {self._format_price(sl)}")
        else:
            # Для LONG/SHORT показываем цели
            tp1_label = targets.get("tp1_label", "")
            tp2_label = targets.get("tp2_label", "")
            sl_label = targets.get("sl_label", "")
            
            lines.append(f"🎯 *TP1:* {self._format_price(tp1)}{f' ({tp1_label})' if tp1_label else ''}")
            lines.append(f"🎯 *TP2:* {self._format_price(tp2)}{f' ({tp2_label})' if tp2_label else ''}")
            lines.append(f"🛑 *SL:* {self._format_price(sl)}{f' ({sl_label})' if sl_label else ''}")
            
            # R:R только для LONG/SHORT
            if rr is not None:
                lines.append(f"📈 *R:R:* 1:{rr:.1f}")
        
        lines.append("")  # Пустая строка
        
        # Прогноз и уверенность
        lines.append(f"⏱️ *Прогноз:* {timeframe}")
        lines.append(f"📊 *Уверенность:* {confidence:.0f}%")
        lines.append("")  # Пустая строка
        
        # Ключевые уровни (новый компактный формат)
        if levels:
            resistance = levels.get("resistance")
            resistance2 = levels.get("resistance2")
            support = levels.get("support")
            support2 = levels.get("support2")
            
            # Проверяем, есть ли хотя бы один уровень
            has_levels = resistance or support
            
            if has_levels:
                lines.append("📍 *Уровни:*")
                
                # Сопротивления (если есть)
                if resistance or resistance2:
                    resistances_str = " | ".join(filter(None, [
                        self._format_price(resistance) if resistance else None,
                        self._format_price(resistance2) if resistance2 else None
                    ]))
                    lines.append(f"├ 🔴 Сопр: {resistances_str}")
                
                # Поддержки (если есть)
                if support or support2:
                    supports_str = " | ".join(filter(None, [
                        self._format_price(support) if support else None,
                        self._format_price(support2) if support2 else None
                    ]))
                    lines.append(f"└ 🟢 Подд: {supports_str}")
                
                lines.append("")  # Пустая строка
        
        # Причины для входа
        # Используем переданные reasons или извлекаем из enhancer_data
        if reasons is None and enhancer_data is not None:
            reasons = self._get_top_reasons(enhancer_data, limit=6)  # Увеличиваем до 6
        
        if reasons:
            lines.append("🔥 *Сигналы:*")
            for i, reason in enumerate(reasons[:6]):  # Максимум 6 причин
                icon = reason.get("icon", "•")
                name = reason.get("name", "")
                value = reason.get("value", "")
                
                # Используем правильный символ для дерева
                if i < len(reasons) - 1 and i < 5:  # Не последний элемент
                    lines.append(f"├ {icon} *{name}:* {value}")
                else:  # Последний элемент
                    lines.append(f"└ {icon} *{name}:* {value}")
        
        return "\n".join(lines)
    
    def _format_price(self, price: float) -> str:
        """
        Форматирует цену с правильной точностью.
        
        Args:
            price: Цена для форматирования
            
        Returns:
            Отформатированная строка цены
        """
        if price >= 1000:
            # Для больших чисел - без десятичных, с разделителями
            return f"${price:,.0f}"
        elif price >= 1:
            # Для средних чисел - 2 десятичных знака
            return f"${price:,.2f}"
        elif price >= 0.01:
            # Для маленьких чисел - 4 десятичных знака
            return f"${price:.4f}"
        else:
            # Для очень маленьких чисел - 6 десятичных знаков
            return f"${price:.6f}"
    
    def _format_rr(self, entry: float, tp: float, sl: float) -> float:
        """
        Рассчитывает и форматирует соотношение Risk:Reward.
        
        Args:
            entry: Цена входа
            tp: Take Profit цена
            sl: Stop Loss цена
            
        Returns:
            R:R соотношение (например 2.3 для 1:2.3)
        """
        if entry == 0 or sl == 0:
            return 0.0
        
        # Рассчитываем прибыль и риск
        profit = abs(tp - entry)
        risk = abs(entry - sl)
        
        if risk == 0:
            return 0.0
        
        # R:R соотношение
        rr = profit / risk
        return rr
    
    def _get_top_reasons(self, enhancer_data: Dict, limit: int = 4) -> List[Dict]:
        """
        Выбирает топ самых важных факторов для отображения.
        
        Приоритет факторов:
        1. Wyckoff фаза (если определена)
        2. Активность китов (если есть сигнал)
        3. Магнит ликвидации (ближайшая зона)
        4. Funding rate (если значимый)
        5. SMC Order Block (если есть)
        6. Fear & Greed Index
        7. RSI значение
        8. MACD направление (bullish/bearish)
        9. TradingView рейтинг
        
        Args:
            enhancer_data: Данные от EnhancerManager и technical indicators
            limit: Максимальное количество причин (по умолчанию 4)
            
        Returns:
            Список причин [{icon, name, value}, ...]
        """
        reasons = []
        
        # 1. Wyckoff фаза
        wyckoff = enhancer_data.get("wyckoff", {})
        if wyckoff.get("phase"):
            phase = wyckoff["phase"]
            confidence = wyckoff.get("confidence", 0) * 100
            
            # Переводим фазу на русский
            phase_ru = {
                "accumulation": "Накопление",
                "markup": "Разгон",
                "distribution": "Распределение",
                "markdown": "Падение"
            }.get(phase.lower(), phase.title())
            
            reasons.append({
                "icon": "🌊",
                "name": "Wyckoff",
                "value": f"{phase_ru} ({confidence:.0f}%)"
            })
        
        # 2. Whale Activity
        whale = enhancer_data.get("whale_activity", {})
        if whale.get("signal"):
            signal = whale["signal"]
            action = "накапливают" if signal == "bullish" else "распродают"
            reasons.append({
                "icon": "🐋",
                "name": "Киты",
                "value": action
            })
        
        # 3. Liquidation Magnet
        liq = enhancer_data.get("liquidation_zones", {})
        nearest_short = liq.get("nearest_short")
        nearest_long = liq.get("nearest_long")
        
        # Выбираем ближайшую зону
        if nearest_short and nearest_long:
            # Берём ту что ближе
            current_price = enhancer_data.get("current_price", 0)
            if current_price > 0:
                dist_short = abs(nearest_short.get("price", 0) - current_price)
                dist_long = abs(nearest_long.get("price", 0) - current_price)
                nearest = nearest_short if dist_short < dist_long else nearest_long
                zone_type = "short liq" if dist_short < dist_long else "long liq"
            else:
                nearest = nearest_short
                zone_type = "short liq"
        elif nearest_short:
            nearest = nearest_short
            zone_type = "short liq"
        elif nearest_long:
            nearest = nearest_long
            zone_type = "long liq"
        else:
            nearest = None
            zone_type = None
        
        if nearest:
            price = nearest.get("price", 0)
            # Умный формат цены вместо всегда делить на 1000
            if price >= 1000:
                price_k = price / 1000
                price_formatted = f"${price_k:.1f}K"
            elif price >= 1:
                price_formatted = f"${price:.2f}"
            else:
                price_formatted = f"${price:.4f}"
            
            reasons.append({
                "icon": "💧",
                "name": "Магнит",
                "value": f"{price_formatted} ({zone_type})"
            })
        
        # 4. Funding Rate
        funding = enhancer_data.get("funding", {})
        if funding.get("current_funding") is not None:
            rate = funding["current_funding"] * 100
            
            # Определяем статус
            if abs(rate) < 0.05:
                status = "норма"
            elif rate > 0:
                status = "высокий"
            else:
                status = "отрицательный"
            
            reasons.append({
                "icon": "🔄",
                "name": "Funding",
                "value": f"{status} ({rate:.2f}%)"
            })
        
        # 5. SMC Order Block
        smc = enhancer_data.get("smc_levels", {})
        order_blocks = smc.get("order_blocks", [])
        if order_blocks:
            ob = order_blocks[0]  # Берём первый (самый важный)
            ob_type = ob.get("type", "").title()
            ob_low = ob.get("low", 0)
            
            reasons.append({
                "icon": "🧠",
                "name": "SMC",
                "value": f"{ob_type} OB {self._format_price(ob_low)}"
            })
        
        # 6. Fear & Greed Index
        fear_greed = enhancer_data.get("fear_greed", {})
        if fear_greed.get("value") is not None:
            fg_value = fear_greed["value"]
            fg_classification = fear_greed.get("value_classification", "")
            
            # Определяем эмодзи на основе значения
            if fg_value < 25:
                emoji = "😱"
            elif fg_value < 50:
                emoji = "😰"
            elif fg_value < 75:
                emoji = "😊"
            else:
                emoji = "🤑"
            
            reasons.append({
                "icon": emoji,
                "name": "F&G",
                "value": f"{fg_value} ({fg_classification})"
            })
        
        # 7. RSI значение
        rsi = enhancer_data.get("rsi", {})
        if rsi.get("value") is not None:
            rsi_value = rsi["value"]
            reasons.append({
                "icon": "📊",
                "name": "RSI",
                "value": f"{rsi_value:.1f}"
            })
        
        # 8. MACD направление
        macd = enhancer_data.get("macd", {})
        if macd.get("signal"):
            macd_signal = macd["signal"]
            direction_text = "bullish" if macd_signal in ["bullish", "buy"] else "bearish" if macd_signal in ["bearish", "sell"] else "neutral"
            reasons.append({
                "icon": "📈",
                "name": "MACD",
                "value": direction_text
            })
        
        # 9. TradingView рейтинг
        tradingview = enhancer_data.get("tradingview", {})
        if tradingview.get("summary", {}).get("RECOMMENDATION"):
            tv_rating = tradingview["summary"]["RECOMMENDATION"]
            # Упрощаем рейтинг для краткости
            if tv_rating in ["STRONG_BUY", "BUY"]:
                rating_text = "BUY"
            elif tv_rating in ["STRONG_SELL", "SELL"]:
                rating_text = "SELL"
            else:
                rating_text = "NEUTRAL"
            
            reasons.append({
                "icon": "📺",
                "name": "TV",
                "value": rating_text
            })
        
        # Возвращаем только топ N причин
        return reasons[:limit]
