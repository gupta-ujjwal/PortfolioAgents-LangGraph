import os
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage

from portfolio_types import AgentState, TelegramMessage, AgentResponse, SentimentIndicator, ActionType
from tools import CSVPortfolioManager, PortfolioAnalyzer, PortfolioData

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PortfolioBuddyAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.3
        )
        
        # Initialize tools
        self.csv_manager = CSVPortfolioManager()
        self.portfolio_analyzer = PortfolioAnalyzer()
        
        # User sessions storage (in production, use a proper database)
        self.user_sessions: Dict[int, AgentState] = {}
        
        # Build LangGraph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("process_message", self._process_message)
        workflow.add_node("fetch_portfolio", self._fetch_portfolio)
        workflow.add_node("analyze_portfolio", self._analyze_portfolio)
        workflow.add_node("generate_response", self._generate_response)
        
        # Add edges
        workflow.set_entry_point("process_message")
        workflow.add_conditional_edges(
            "process_message",
            self._should_fetch_portfolio,
            {
                "fetch_portfolio": "fetch_portfolio",
                "analyze_portfolio": "analyze_portfolio",
                "generate_response": "generate_response"
            }
        )
        workflow.add_edge("fetch_portfolio", "analyze_portfolio")
        workflow.add_edge("analyze_portfolio", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()
    
    async def _process_message(self, state: AgentState) -> AgentState:
        """Process the incoming user message and determine intent"""
        latest_message = state["messages"][-1]["content"]
        
        # Use LLM to classify the message intent
        prompt = f"""
        Analyze this user message about their investment portfolio:
        "{latest_message}"
        
        Classify the intent as one of:
        1. "portfolio_query" - User wants to know about their portfolio performance
        2. "stock_analysis" - User wants analysis of specific stocks
        3. "general_question" - General investment question
        4. "greeting" - Simple greeting
        
        Also extract any stock symbols mentioned (format: AAPL, GOOGL, etc.)
        
        Respond in JSON format:
        {{
            "intent": "intent_type",
            "symbols": ["SYMBOL1", "SYMBOL2"],
            "requires_portfolio": true/false
        }}
        """
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            import json
            import re
            
            # Extract JSON from response (handle cases where LLM adds extra text)
            content = response.content.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                analysis = json.loads(json_str)
            else:
                # Fallback: try parsing the entire response as JSON
                analysis = json.loads(content)
            
            state["user_context"]["intent"] = analysis.get("intent", "general_question")
            state["user_context"]["symbols"] = analysis.get("symbols", [])
            state["user_context"]["requires_portfolio"] = analysis.get("requires_portfolio", False)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            state["user_context"]["intent"] = "general_question"
            state["user_context"]["symbols"] = []
            state["user_context"]["requires_portfolio"] = False
        
        return state
    
    def _should_fetch_portfolio(self, state: AgentState) -> str:
        """Determine if we need to fetch portfolio data"""
        if state["user_context"].get("requires_portfolio", False):
            return "fetch_portfolio"
        elif state["user_context"].get("intent") in ["portfolio_query", "stock_analysis"]:
            return "fetch_portfolio"
        else:
            return "generate_response"
    
    async def _fetch_portfolio(self, state: AgentState) -> AgentState:
        """Fetch portfolio data from CSV file"""
        try:
            portfolio = self.csv_manager.get_portfolio_data()
            # Update with current market data
            portfolio = self.portfolio_analyzer.update_portfolio_with_market_data(portfolio)
            
            state["portfolio_data"] = portfolio
            
        except Exception as e:
            logger.error(f"Error fetching portfolio: {e}")
            state["portfolio_data"] = None
        
        return state
    
    async def _analyze_portfolio(self, state: AgentState) -> AgentState:
        """Analyze portfolio and generate insights"""
        if not state["portfolio_data"]:
            return state
        
        try:
            portfolio = state["portfolio_data"]
            symbols_to_analyze = state["user_context"].get("symbols", [])
            
            # If no specific symbols mentioned, analyze all holdings
            if not symbols_to_analyze:
                symbols_to_analyze = [holding["symbol"] for holding in portfolio["holdings"]]
            
            analyses = []
            for symbol in symbols_to_analyze:
                # Find the holding if it exists
                holding = next((h for h in portfolio["holdings"] if h["symbol"] == symbol), None)
                analysis = self.portfolio_analyzer.analyze_symbol(symbol, holding)
                analyses.append(analysis)
            
            if analyses:
                state["current_analysis"] = analyses[0]  # Primary analysis
                state["user_context"]["all_analyses"] = analyses
            
        except Exception as e:
            logger.error(f"Error analyzing portfolio: {e}")
            state["current_analysis"] = None
        
        return state
    
    async def _generate_response(self, state: AgentState) -> AgentState:
        """Generate the final response to the user"""
        try:
            latest_message = state["messages"][-1]["content"]
            intent = state["user_context"].get("intent", "general_question")
            
            # Build context for the LLM
            context_parts = []
            
            # Add portfolio context if available
            if state["portfolio_data"]:
                portfolio = state["portfolio_data"]
                context_parts.append(f"""
                Portfolio Summary:
                - Total Value: ${portfolio['total_value']:,.2f}
                - Total Gain/Loss: ${portfolio['total_gain_loss']:,.2f} ({portfolio['total_gain_loss_percent']:.1f}%)
                - Holdings: {len(portfolio['holdings'])} stocks
                """)
                
                # Add top performers
                if portfolio["holdings"]:
                    top_performers = sorted(portfolio["holdings"], key=lambda x: x.get("gain_loss_percent", 0), reverse=True)[:3]
                    worst_performers = sorted(portfolio["holdings"], key=lambda x: x.get("gain_loss_percent", 0))[:3]
                    
                    context_parts.append("Top Performers:")
                    for holding in top_performers:
                        context_parts.append(f"- {holding['symbol']}: {holding.get('gain_loss_percent', 0):.1f}%")
                    
                    context_parts.append("Worst Performers:")
                    for holding in worst_performers:
                        context_parts.append(f"- {holding['symbol']}: {holding.get('gain_loss_percent', 0):.1f}%")
            
            # Add analysis context if available
            if state["current_analysis"]:
                analysis = state["current_analysis"]
                sentiment_emoji = {
                    SentimentIndicator.POSITIVE: "🟢",
                    SentimentIndicator.NEUTRAL: "🟡", 
                    SentimentIndicator.NEGATIVE: "🔴"
                }
                
                action_emoji = {
                    ActionType.BUY: "📈",
                    ActionType.SELL: "📉",
                    ActionType.HOLD: "⏸️",
                    ActionType.WATCH: "👀"
                }
                
                context_parts.append(f"""
                Analysis for {analysis['symbol']}:
                - Current Price: ${analysis['current_price']:.2f}
                - Sentiment: {sentiment_emoji[analysis['sentiment']]} {analysis['sentiment'].value}
                - Recommendation: {action_emoji[analysis['recommendation']]} {analysis['recommendation'].value.upper()}
                - Confidence: {analysis['confidence']:.1%}
                - Reasoning: {analysis['reasoning']}
                """)
                
                if analysis['news_summary']:
                    context_parts.append("Recent News:")
                    for news in analysis['news_summary'][:2]:
                        context_parts.append(f"- {news['title']}")
            
            # Create the prompt
            context = "\n".join(context_parts)
            
            prompt = f"""
            You are PortfolioBuddy, a friendly and knowledgeable investment assistant. You help users understand their portfolio performance and make informed decisions.

            User Message: "{latest_message}"
            User Intent: {intent}

            {context if context else "No portfolio data available."}

            Instructions:
            1. Respond in a friendly, conversational tone
            2. Keep responses concise but informative
            3. Use emojis to indicate sentiment (🟢 positive, 🟡 neutral, 🔴 negative)
            4. Use action emojis for recommendations (📈 BUY, 📉 SELL, ⏸️ HOLD, 👀 WATCH)
            5. Focus on the most important information
            6. End with a helpful question or suggestion
            7. Never give financial advice, only provide analysis and information

            Response:
            """
            
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            # Add the AI response to messages
            state["messages"].append({
                "role": "assistant",
                "content": response.content,
                "timestamp": datetime.now()
            })
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            error_response = "Sorry, I encountered an error processing your request. Please try again."
            state["messages"].append({
                "role": "assistant", 
                "content": error_response,
                "timestamp": datetime.now()
            })
        
        return state
    
    def get_or_create_session(self, user_id: int) -> AgentState:
        """Get or create a user session"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "messages": [],
                "portfolio_data": None,
                "current_analysis": None,
                "user_context": {},
                "last_action": None
            }
        return self.user_sessions[user_id]
    
    async def process_telegram_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process incoming Telegram message"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Get or create user session
        session = self.get_or_create_session(user_id)
        
        # Add user message to session
        session["messages"].append({
            "role": "user",
            "content": message_text,
            "timestamp": datetime.now()
        })
        
        try:
            # Process through LangGraph
            result = await self.graph.ainvoke(session)
            
            # Update session with result
            self.user_sessions[user_id] = result
            
            # Send the latest AI response back to user
            if result["messages"]:
                latest_message = result["messages"][-1]
                if latest_message["role"] == "assistant":
                    await update.message.reply_text(latest_message["content"])
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text("Sorry, I encountered an error. Please try again.")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        welcome_message = """
        🤖 Welcome to PortfolioBuddy!

        I'm your personal investment assistant that helps you:
        • Track your portfolio performance
        • Analyze individual stocks
        • Get market insights and news
        • Receive actionable recommendations

        Commands:
        /start - Show this welcome message
        /portfolio - View your portfolio summary
        /analyze SYMBOL - Analyze a specific stock

        Just ask me questions like:
        • "How is my portfolio doing?"
        • "What's happening with AAPL?"
        • "Should I buy more TSLA?"
        • "Show me my worst performers"

        Let's get started! 📈
        """
        await update.message.reply_text(welcome_message)
    
    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /portfolio command"""
        user_id = update.effective_user.id
        session = self.get_or_create_session(user_id)
        
        # Add portfolio request as a user message
        session["messages"].append({
            "role": "user",
            "content": "Show me my portfolio summary",
            "timestamp": datetime.now()
        })
        
        # Process through the graph
        await self.process_telegram_message(update, context)
    
    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /analyze command"""
        user_id = update.effective_user.id
        session = self.get_or_create_session(user_id)
        
        if not context.args:
            await update.message.reply_text("Please provide a stock symbol. Usage: /analyze AAPL")
            return
        
        symbol = context.args[0].upper()
        
        # Add analysis request as a user message
        session["messages"].append({
            "role": "user",
            "content": f"Analyze {symbol}",
            "timestamp": datetime.now()
        })
        
        # Process through the graph
        await self.process_telegram_message(update, context)

def run_bot():
    """Run the Telegram bot"""
    # Get environment variables
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    
    # Create the agent
    agent = PortfolioBuddyAgent()
    
    # Create the Telegram application
    application = Application.builder().token(telegram_token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", agent.start_command))
    application.add_handler(CommandHandler("portfolio", agent.portfolio_command))
    application.add_handler(CommandHandler("analyze", agent.analyze_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, agent.process_telegram_message))
    
    # Run the bot
    logger.info("Starting PortfolioBuddy bot...")
    application.run_polling()

if __name__ == "__main__":
    run_bot()