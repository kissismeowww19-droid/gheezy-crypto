import aiohttp
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class MacroAnalyzer:
    """
    Анализ макро-факторов: DXY, S&P500, Gold
    - DXY растёт → медвежье для крипты
    - S&P500 растёт → бычье для крипты (risk-on)
    """
    
    async def get_dxy_data(self) -> Optional[Dict]:
        """DXY через Yahoo Finance (работает в РФ)"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB"
                params = {'interval': '1h', 'range': '2d'}
                headers = {'User-Agent': 'Mozilla/5.0'}
                
                async with session.get(url, params=params, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = data.get('chart', {}).get('result', [])
                        if result:
                            quotes = result[0].get('indicators', {}).get('quote', [{}])[0]
                            closes = [c for c in quotes.get('close', []) if c is not None]
                            
                            if len(closes) >= 2:
                                current = closes[-1]
                                prev = closes[-24] if len(closes) >= 24 else closes[0]
                                change = ((current - prev) / prev) * 100
                                
                                logger.info(f"DXY: {current:.2f}, change: {change:+.2f}%")
                                return {
                                    'value': round(current, 2),
                                    'change_24h': round(change, 2),
                                    'trend': 'bullish' if change > 0.3 else 'bearish' if change < -0.3 else 'neutral'
                                }
        except Exception as e:
            logger.warning(f"DXY fetch failed: {e}")
        return None
    
    async def get_sp500_data(self) -> Optional[Dict]:
        """S&P500 через Yahoo Finance"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC"
                params = {'interval': '1h', 'range': '2d'}
                headers = {'User-Agent': 'Mozilla/5.0'}
                
                async with session.get(url, params=params, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = data.get('chart', {}).get('result', [])
                        if result:
                            quotes = result[0].get('indicators', {}).get('quote', [{}])[0]
                            closes = [c for c in quotes.get('close', []) if c is not None]
                            
                            if len(closes) >= 2:
                                current = closes[-1]
                                prev = closes[-24] if len(closes) >= 24 else closes[0]
                                change = ((current - prev) / prev) * 100
                                
                                logger.info(f"S&P500: {current:.2f}, change: {change:+.2f}%")
                                return {
                                    'value': round(current, 2),
                                    'change_24h': round(change, 2),
                                    'trend': 'bullish' if change > 0.5 else 'bearish' if change < -0.5 else 'neutral'
                                }
        except Exception as e:
            logger.warning(f"S&P500 fetch failed: {e}")
        return None
    
    async def get_gold_data(self) -> Optional[Dict]:
        """Gold через Yahoo Finance"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
                params = {'interval': '1h', 'range': '2d'}
                headers = {'User-Agent': 'Mozilla/5.0'}
                
                async with session.get(url, params=params, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = data.get('chart', {}).get('result', [])
                        if result:
                            quotes = result[0].get('indicators', {}).get('quote', [{}])[0]
                            closes = [c for c in quotes.get('close', []) if c is not None]
                            
                            if len(closes) >= 2:
                                current = closes[-1]
                                prev = closes[-24] if len(closes) >= 24 else closes[0]
                                change = ((current - prev) / prev) * 100
                                
                                logger.info(f"Gold: ${current:.2f}, change: {change:+.2f}%")
                                return {
                                    'value': round(current, 2),
                                    'change_24h': round(change, 2),
                                    'trend': 'bullish' if change > 0.3 else 'bearish' if change < -0.3 else 'neutral'
                                }
        except Exception as e:
            logger.warning(f"Gold fetch failed: {e}")
        return None
    
    async def analyze(self) -> Dict:
        """Комплексный макро анализ"""
        dxy = await self.get_dxy_data()
        sp500 = await self.get_sp500_data()
        gold = await self.get_gold_data()
        
        score = 0
        factors = []
        
        # DXY (ОБРАТНАЯ корреляция)
        if dxy:
            if dxy['trend'] == 'bullish':
                score -= 8
                factors.append(f"DXY ↑{dxy['change_24h']:+.2f}% (медвежье)")
            elif dxy['trend'] == 'bearish':
                score += 8
                factors.append(f"DXY ↓{dxy['change_24h']:+.2f}% (бычье)")
        
        # S&P500 (ПРЯМАЯ корреляция)
        if sp500:
            if sp500['trend'] == 'bullish':
                score += 6
                factors.append(f"S&P500 ↑{sp500['change_24h']:+.2f}% (бычье)")
            elif sp500['trend'] == 'bearish':
                score -= 6
                factors.append(f"S&P500 ↓{sp500['change_24h']:+.2f}% (медвежье)")
        
        # Gold
        if gold:
            if gold['trend'] == 'bullish':
                score += 3
                factors.append(f"Gold ↑{gold['change_24h']:+.2f}% (бычье)")
            elif gold['trend'] == 'bearish':
                score -= 3
                factors.append(f"Gold ↓{gold['change_24h']:+.2f}% (медвежье)")
        
        score = max(min(score, 15), -15)
        verdict = 'bullish' if score > 4 else 'bearish' if score < -4 else 'neutral'
        
        logger.info(f"Macro analysis: score={score}, verdict={verdict}")
        
        return {
            'score': score,
            'verdict': verdict,
            'factors': factors,
            'dxy': dxy,
            'sp500': sp500,
            'gold': gold
        }
