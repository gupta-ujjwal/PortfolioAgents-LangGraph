import os
import csv
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import yfinance as yf
from textblob import TextBlob

from portfolio_types import (
    PortfolioData, PortfolioHolding, MarketData, NewsItem, 
    SentimentIndicator, AnalysisResult, ActionType
)

class CSVPortfolioManager:
    def __init__(self, csv_file_path: str = None):
        self.csv_file_path = csv_file_path or os.getenv('PORTFOLIO_CSV_PATH', 'portfolio.csv')
    
    def get_portfolio_data(self) -> PortfolioData:
        try:
            if not os.path.exists(self.csv_file_path):
                print(f"Portfolio CSV file not found: {self.csv_file_path}")
                return PortfolioData(
                    holdings=[],
                    total_value=0.0,
                    total_gain_loss=0.0,
                    total_gain_loss_percent=0.0,
                    last_updated=datetime.now()
                )
            
            holdings = []
            
            with open(self.csv_file_path, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    try:
                        # Skip empty rows
                        if not row.get('Symbol', '').strip():
                            continue
                        
                        holding = PortfolioHolding(
                            symbol=row['Symbol'].upper().strip(),
                            quantity=float(row['Quantity']),
                            avg_cost=float(row['Average Cost']),
                            current_price=None,
                            value=None,
                            gain_loss=None,
                            gain_loss_percent=None
                        )
                        holdings.append(holding)
                        
                    except (ValueError, KeyError) as e:
                        print(f"Error parsing row {row}: {e}")
                        continue
            
            return PortfolioData(
                holdings=holdings,
                total_value=0.0,
                total_gain_loss=0.0,
                total_gain_loss_percent=0.0,
                last_updated=datetime.now()
            )
            
        except Exception as e:
            print(f"Error reading portfolio CSV: {e}")
            return PortfolioData(
                holdings=[],
                total_value=0.0,
                total_gain_loss=0.0,
                total_gain_loss_percent=0.0,
                last_updated=datetime.now()
            )

class YahooFinanceManager:
    def get_market_data(self, symbol: str) -> Optional[MarketData]:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            history = ticker.history(period="1d")
            
            if history.empty:
                return None
            
            current_price = history['Close'].iloc[-1]
            previous_close = info.get('previousClose', current_price)
            change = current_price - previous_close
            change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
            
            return MarketData(
                symbol=symbol.upper(),
                price=current_price,
                change=change,
                change_percent=change_percent,
                volume=int(info.get('volume', 0)),
                market_cap=info.get('marketCap'),
                pe_ratio=info.get('trailingPE'),
                day_high=history['High'].iloc[-1],
                day_low=history['Low'].iloc[-1]
            )
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None
    
    def get_multiple_market_data(self, symbols: List[str]) -> Dict[str, MarketData]:
        data = {}
        for symbol in symbols:
            market_data = self.get_market_data(symbol)
            if market_data:
                data[symbol] = market_data
        return data

class NewsManager:
    def __init__(self, news_api_key: str = None):
        self.api_key = news_api_key or os.getenv('NEWS_API_KEY')
        self.base_url = "https://newsapi.org/v2"
    
    def get_stock_news(self, symbol: str, days_back: int = 7) -> List[NewsItem]:
        if not self.api_key:
            # Fallback to Yahoo Finance news
            return self._get_yahoo_news(symbol)
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            url = f"{self.base_url}/everything"
            params = {
                'q': f'"{symbol}" stock OR "{symbol}" shares OR "{symbol}" trading',
                'language': 'en',
                'sortBy': 'relevancy',
                'from': start_date.strftime('%Y-%m-%d'),
                'to': end_date.strftime('%Y-%m-%d'),
                'pageSize': 10,
                'apiKey': self.api_key
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            articles = response.json().get('articles', [])
            news_items = []
            
            for article in articles:
                sentiment = self._analyze_sentiment(article.get('title', '') + ' ' + article.get('description', ''))
                relevance = self._calculate_relevance(article.get('title', '') + ' ' + article.get('description', ''), symbol)
                
                news_items.append(NewsItem(
                    title=article.get('title', ''),
                    content=article.get('description', ''),
                    source=article.get('source', {}).get('name', ''),
                    url=article.get('url', ''),
                    published_at=datetime.fromisoformat(article.get('publishedAt', '').replace('Z', '+00:00')),
                    sentiment=sentiment,
                    relevance_score=relevance
                ))
            
            return news_items
            
        except Exception as e:
            print(f"Error fetching news for {symbol}: {e}")
            return self._get_yahoo_news(symbol)
    
    def _get_yahoo_news(self, symbol: str) -> List[NewsItem]:
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            
            news_items = []
            for item in news[:10]:  # Limit to 10 most recent
                title = item.get('title', '')
                content = item.get('summary', '')
                
                sentiment = self._analyze_sentiment(title + ' ' + content)
                relevance = self._calculate_relevance(title + ' ' + content, symbol)
                
                news_items.append(NewsItem(
                    title=title,
                    content=content,
                    source=item.get('publisher', ''),
                    url=item.get('link', ''),
                    published_at=datetime.fromtimestamp(item.get('providerPublishTime', 0)),
                    sentiment=sentiment,
                    relevance_score=relevance
                ))
            
            return news_items
            
        except Exception as e:
            print(f"Error fetching Yahoo news for {symbol}: {e}")
            return []
    
    def _analyze_sentiment(self, text: str) -> SentimentIndicator:
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            
            if polarity > 0.1:
                return SentimentIndicator.POSITIVE
            elif polarity < -0.1:
                return SentimentIndicator.NEGATIVE
            else:
                return SentimentIndicator.NEUTRAL
        except:
            return SentimentIndicator.NEUTRAL
    
    def _calculate_relevance(self, text: str, symbol: str) -> float:
        text_lower = text.lower()
        symbol_lower = symbol.lower()
        
        # Count mentions of the symbol
        symbol_count = text_lower.count(symbol_lower)
        
        # Look for financial keywords
        financial_keywords = ['stock', 'share', 'trading', 'market', 'price', 'investment', 'portfolio']
        keyword_count = sum(1 for keyword in financial_keywords if keyword in text_lower)
        
        # Calculate relevance score
        relevance = (symbol_count * 0.6) + (keyword_count * 0.4)
        return min(relevance, 1.0)  # Cap at 1.0

class PortfolioAnalyzer:
    def __init__(self):
        self.yahoo_manager = YahooFinanceManager()
        self.news_manager = NewsManager()
    
    def analyze_symbol(self, symbol: str, holding: Optional[PortfolioHolding] = None) -> AnalysisResult:
        # Get market data
        market_data = self.yahoo_manager.get_market_data(symbol)
        if not market_data:
            return AnalysisResult(
                symbol=symbol,
                current_price=0.0,
                sentiment=SentimentIndicator.NEUTRAL,
                news_summary=[],
                technical_indicators={},
                recommendation=ActionType.WATCH,
                confidence=0.0,
                reasoning="Unable to fetch market data"
            )
        
        # Get news
        news_items = self.news_manager.get_stock_news(symbol)
        
        # Analyze sentiment
        if news_items:
            positive_count = sum(1 for item in news_items if item['sentiment'] == SentimentIndicator.POSITIVE)
            negative_count = sum(1 for item in news_items if item['sentiment'] == SentimentIndicator.NEGATIVE)
            
            if positive_count > negative_count:
                overall_sentiment = SentimentIndicator.POSITIVE
            elif negative_count > positive_count:
                overall_sentiment = SentimentIndicator.NEGATIVE
            else:
                overall_sentiment = SentimentIndicator.NEUTRAL
        else:
            overall_sentiment = SentimentIndicator.NEUTRAL
        
        # Generate recommendation
        recommendation, confidence, reasoning = self._generate_recommendation(
            market_data, overall_sentiment, news_items, holding
        )
        
        return AnalysisResult(
            symbol=symbol,
            current_price=market_data['price'],
            sentiment=overall_sentiment,
            news_summary=news_items[:3],  # Top 3 news items
            technical_indicators={
                'change_percent': market_data['change_percent'],
                'volume': market_data['volume'],
                'pe_ratio': market_data['pe_ratio']
            },
            recommendation=recommendation,
            confidence=confidence,
            reasoning=reasoning
        )
    
    def _generate_recommendation(
        self, 
        market_data: MarketData, 
        sentiment: SentimentIndicator, 
        news: List[NewsItem],
        holding: Optional[PortfolioHolding] = None
    ) -> tuple[ActionType, float, str]:
        
        change_percent = market_data['change_percent']
        reasoning_parts = []
        
        # Base recommendation on price change
        if change_percent > 5:
            base_action = ActionType.BUY
            base_confidence = 0.7
            reasoning_parts.append(f"Price is up {change_percent:.1f}%")
        elif change_percent < -5:
            base_action = ActionType.SELL
            base_confidence = 0.7
            reasoning_parts.append(f"Price is down {abs(change_percent):.1f}%")
        else:
            base_action = ActionType.HOLD
            base_confidence = 0.5
            reasoning_parts.append("Price is relatively stable")
        
        # Adjust based on sentiment
        if sentiment == SentimentIndicator.POSITIVE:
            if base_action == ActionType.BUY:
                base_confidence = min(base_confidence + 0.2, 1.0)
            elif base_action == ActionType.SELL:
                base_confidence = max(base_confidence - 0.2, 0.1)
                base_action = ActionType.HOLD
            reasoning_parts.append("Positive news sentiment")
        elif sentiment == SentimentIndicator.NEGATIVE:
            if base_action == ActionType.SELL:
                base_confidence = min(base_confidence + 0.2, 1.0)
            elif base_action == ActionType.BUY:
                base_confidence = max(base_confidence - 0.2, 0.1)
                base_action = ActionType.HOLD
            reasoning_parts.append("Negative news sentiment")
        
        # Consider holding performance
        if holding and holding.get('gain_loss_percent') is not None:
            gain_loss_percent = holding['gain_loss_percent']
            if gain_loss_percent > 20:
                reasoning_parts.append(f"You have {gain_loss_percent:.1f}% gains")
                if base_action == ActionType.BUY:
                    base_action = ActionType.HOLD
                    base_confidence = max(base_confidence - 0.1, 0.3)
            elif gain_loss_percent < -20:
                reasoning_parts.append(f"You have {abs(gain_loss_percent):.1f}% losses")
        
        reasoning = ". ".join(reasoning_parts) + "."
        
        return base_action, base_confidence, reasoning
    
    def update_portfolio_with_market_data(self, portfolio: PortfolioData) -> PortfolioData:
        symbols = [holding['symbol'] for holding in portfolio['holdings']]
        market_data_dict = self.yahoo_manager.get_multiple_market_data(symbols)
        
        total_value = 0.0
        total_gain_loss = 0.0
        
        for holding in portfolio['holdings']:
            symbol = holding['symbol']
            if symbol in market_data_dict:
                market_data = market_data_dict[symbol]
                holding['current_price'] = market_data['price']
                holding['value'] = holding['quantity'] * market_data['price']
                holding['gain_loss'] = (market_data['price'] - holding['avg_cost']) * holding['quantity']
                holding['gain_loss_percent'] = ((market_data['price'] - holding['avg_cost']) / holding['avg_cost']) * 100
                
                total_value += holding['value']
                total_gain_loss += holding['gain_loss']
        
        portfolio['total_value'] = total_value
        portfolio['total_gain_loss'] = total_gain_loss
        portfolio['total_gain_loss_percent'] = (total_gain_loss / (total_value - total_gain_loss)) * 100 if total_value != total_gain_loss else 0
        portfolio['last_updated'] = datetime.now()
        
        return portfolio