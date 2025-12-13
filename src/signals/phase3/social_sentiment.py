import aiohttp
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

class SocialSentimentAnalyzer:
    """
    Анализ социального настроения через Reddit
    Без API ключа — парсим публичный JSON
    """
    
    SUBREDDITS = {
        'BTC': ['bitcoin', 'cryptocurrency'],
        'ETH': ['ethereum', 'cryptocurrency'],
        'TON': ['ton_blockchain'],
        'SOL': ['solana', 'cryptocurrency'],
        'XRP': ['ripple', 'cryptocurrency']
    }
    
    BULLISH_KEYWORDS = [
        'bull', 'moon', 'buy', 'long', 'pump', 'breakout', 'ath', 
        'bullish', 'accumulate', 'hodl', 'rocket', 'up', 'green',
        '🚀', '📈', '💎', '🟢'
    ]
    
    BEARISH_KEYWORDS = [
        'bear', 'crash', 'sell', 'short', 'dump', 'drop', 'bearish',
        'collapse', 'fear', 'panic', 'rekt', 'down', 'red',
        '📉', '💀', '🔻', '🔴'
    ]
    
    async def get_reddit_sentiment(self, symbol: str) -> Optional[Dict]:
        """Получить sentiment с Reddit"""
        subreddits = self.SUBREDDITS.get(symbol.upper(), ['cryptocurrency'])
        
        total_bullish = 0
        total_bearish = 0
        total_engagement = 0
        posts_analyzed = 0
        
        for subreddit in subreddits[:2]:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"https://www.reddit.com/r/{subreddit}/hot.json"
                    headers = {'User-Agent': 'CryptoSignalBot/1.0 (Educational)'}
                    
                    async with session.get(url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            posts = data.get('data', {}).get('children', [])
                            
                            result = self._analyze_posts(posts)
                            total_bullish += result['bullish_score']
                            total_bearish += result['bearish_score']
                            total_engagement += result['engagement']
                            posts_analyzed += result['posts_count']
                        elif resp.status == 429:
                            logger.warning(f"Reddit rate limited for r/{subreddit}")
                        else:
                            logger.warning(f"Reddit returned {resp.status}")
            except Exception as e:
                logger.warning(f"Reddit r/{subreddit} failed: {e}")
        
        if posts_analyzed == 0:
            return None
        
        # Рассчитываем соотношение
        total = total_bullish + total_bearish
        bullish_ratio = total_bullish / total if total > 0 else 0.5
        
        # Verdict и score
        if bullish_ratio > 0.65:
            verdict = 'bullish'
            score = 8
        elif bullish_ratio > 0.55:
            verdict = 'slightly_bullish'
            score = 4
        elif bullish_ratio < 0.35:
            verdict = 'bearish'
            score = -8
        elif bullish_ratio < 0.45:
            verdict = 'slightly_bearish'
            score = -4
        else:
            verdict = 'neutral'
            score = 0
        
        logger.info(f"Reddit sentiment {symbol}: {bullish_ratio:.0%} bullish, verdict={verdict}")
        
        return {
            'bullish_ratio': round(bullish_ratio, 2),
            'bearish_ratio': round(1 - bullish_ratio, 2),
            'total_engagement': total_engagement,
            'posts_analyzed': posts_analyzed,
            'verdict': verdict,
            'score': max(min(score, 10), -10)
        }
    
    def _analyze_posts(self, posts: list) -> Dict:
        """Анализ постов"""
        bullish_score = 0
        bearish_score = 0
        engagement = 0
        count = 0
        
        for post in posts[:25]:
            post_data = post.get('data', {})
            title = post_data.get('title', '').lower()
            selftext = post_data.get('selftext', '').lower()
            score = post_data.get('score', 0) or 0
            comments = post_data.get('num_comments', 0) or 0
            
            full_text = title + ' ' + selftext
            post_engagement = score + comments * 2
            engagement += post_engagement
            count += 1
            
            # Bullish
            for keyword in self.BULLISH_KEYWORDS:
                if keyword in full_text:
                    bullish_score += post_engagement
                    break
            
            # Bearish
            for keyword in self.BEARISH_KEYWORDS:
                if keyword in full_text:
                    bearish_score += post_engagement
                    break
        
        return {
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'engagement': engagement,
            'posts_count': count
        }
    
    async def analyze(self, symbol: str = "BTC") -> Dict:
        """Главный метод"""
        reddit = await self.get_reddit_sentiment(symbol)
        
        if reddit:
            return reddit
        
        return {
            'score': 0,
            'verdict': 'neutral',
            'bullish_ratio': None,
            'posts_analyzed': 0
        }
