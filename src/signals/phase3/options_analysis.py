import aiohttp
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class OptionsAnalyzer:
    """
    Анализ опционов с Deribit (бесплатный API, работает в РФ)
    
    Put/Call Ratio интерпретация (contrarian):
    - PCR > 1.2: много путов = толпа ждёт падения = contrarian bullish
    - PCR < 0.8: много коллов = толпа ждёт роста = contrarian bearish
    """
    
    BASE_URL = "https://www.deribit.com/api/v2/public"
    
    async def get_options_data(self, symbol: str = "BTC") -> Optional[Dict]:
        """Получить данные по опционам"""
        currency = symbol.upper()
        if currency not in ['BTC', 'ETH']:
            logger.debug(f"Options not available for {currency}")
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/get_book_summary_by_currency"
                params = {'currency': currency, 'kind': 'option'}
                
                async with session.get(url, params=params, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        options = data.get('result', [])
                        
                        if options:
                            return self._analyze_options(options, currency)
                    else:
                        logger.warning(f"Deribit returned {resp.status}")
        except Exception as e:
            logger.warning(f"Deribit fetch failed: {e}")
        
        return None
    
    def _analyze_options(self, options: list, currency: str) -> Dict:
        """Анализ Put/Call Ratio"""
        call_oi = 0
        put_oi = 0
        
        for opt in options:
            instrument = opt.get('instrument_name', '')
            oi = opt.get('open_interest', 0) or 0
            
            if '-C' in instrument:
                call_oi += oi
            elif '-P' in instrument:
                put_oi += oi
        
        # Put/Call Ratio
        pcr = put_oi / call_oi if call_oi > 0 else 1.0
        
        # Contrarian интерпретация
        if pcr > 1.3:
            verdict = 'bullish'
            interpretation = "Высокий PCR — толпа в путах (contrarian bullish)"
            score = 10
        elif pcr > 1.1:
            verdict = 'slightly_bullish'
            interpretation = "Умеренно высокий PCR"
            score = 5
        elif pcr < 0.7:
            verdict = 'bearish'
            interpretation = "Низкий PCR — толпа в коллах (contrarian bearish)"
            score = -10
        elif pcr < 0.9:
            verdict = 'slightly_bearish'
            interpretation = "Умеренно низкий PCR"
            score = -5
        else:
            verdict = 'neutral'
            interpretation = "Сбалансированный PCR"
            score = 0
        
        logger.info(f"Options {currency}: PCR={pcr:.2f}, verdict={verdict}")
        
        return {
            'put_call_ratio': round(pcr, 3),
            'call_oi': call_oi,
            'put_oi': put_oi,
            'total_options': len(options),
            'verdict': verdict,
            'interpretation': interpretation,
            'score': max(min(score, 12), -12)
        }
    
    async def analyze(self, symbol: str = "BTC") -> Dict:
        """Главный метод"""
        data = await self.get_options_data(symbol)
        
        if data:
            return data
        
        return {
            'score': 0,
            'verdict': 'neutral',
            'interpretation': 'Данные недоступны',
            'put_call_ratio': None
        }
