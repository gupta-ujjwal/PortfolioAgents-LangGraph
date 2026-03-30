from typing import TypedDict, List, Optional, Dict, Any, Annotated
from datetime import datetime
from enum import Enum
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


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
    notes: str
    last_updated: str


class PortfolioData(TypedDict):
    holdings: List[PortfolioHolding]
    total_value: float
    total_cost: float
    total_gain_loss: float
    total_gain_loss_percent: float
    last_updated: Optional[datetime]


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
    fifty_two_week_high: Optional[float]
    fifty_two_week_low: Optional[float]


class NewsItem(TypedDict):
    title: str
    source: str
    url: str
    published_at: str
    sentiment: str


class AgentState(TypedDict):
    """State for the PortfolioBuddy agent.

    Uses LangGraph's message annotation so the graph automatically
    accumulates messages across turns instead of overwriting them.
    """
    messages: Annotated[list[BaseMessage], add_messages]
