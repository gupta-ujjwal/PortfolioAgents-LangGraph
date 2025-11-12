from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class SentimentIndicator(Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"

class ActionType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WATCH = "watch"

class PortfolioHolding(TypedDict):
    symbol: str
    quantity: float
    avg_cost: float
    current_price: Optional[float]
    value: Optional[float]
    gain_loss: Optional[float]
    gain_loss_percent: Optional[float]

class PortfolioData(TypedDict):
    holdings: List[PortfolioHolding]
    total_value: Optional[float]
    total_gain_loss: Optional[float]
    total_gain_loss_percent: Optional[float]
    last_updated: Optional[datetime]

class NewsItem(TypedDict):
    title: str
    content: str
    source: str
    url: str
    published_at: datetime
    sentiment: SentimentIndicator
    relevance_score: float

class MarketData(TypedDict):
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: Optional[float]
    pe_ratio: Optional[float]
    day_high: Optional[float]
    day_low: Optional[float]

class AnalysisResult(TypedDict):
    symbol: str
    current_price: float
    sentiment: SentimentIndicator
    news_summary: List[NewsItem]
    technical_indicators: Dict[str, Any]
    recommendation: ActionType
    confidence: float
    reasoning: str

class AgentState(TypedDict):
    messages: List[Dict[str, Any]]
    portfolio_data: Optional[PortfolioData]
    current_analysis: Optional[AnalysisResult]
    user_context: Dict[str, Any]
    last_action: Optional[str]

class TelegramMessage(TypedDict):
    message_id: int
    user_id: int
    username: str
    text: str
    timestamp: datetime

class AgentResponse(TypedDict):
    text: str
    sentiment: Optional[SentimentIndicator]
    recommendation: Optional[ActionType]
    data: Optional[Dict[str, Any]]
    follow_up_questions: List[str]