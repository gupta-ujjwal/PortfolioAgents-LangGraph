"""
PortfolioBuddy v2 — A truly agentic portfolio assistant.

Key upgrades over v1:
  - LLM tool-calling: Gemini decides which tools to invoke (no hardcoded routing)
  - Persistent memory: SQLite-backed checkpointer so conversations survive restarts
  - Error recovery: Tools return descriptive errors; LLM reasons about failures
  - Portfolio management: Add/remove/update stocks via natural language
  - Stock comparison: Side-by-side analysis of multiple stocks
"""

import os
import logging
from datetime import datetime

import aiosqlite
from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from tools import ALL_TOOLS

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — the agent's personality and rules
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are PortfolioBuddy, a friendly and knowledgeable stock portfolio assistant on Telegram.

Your capabilities:
- View and analyze the user's stock portfolio
- Analyze individual stocks (price, fundamentals, news)
- Compare multiple stocks side by side
- Add, remove, or update stocks in the portfolio
- Fetch latest stock news

Personality:
- Friendly and conversational, like a smart friend who happens to know finance
- Use emojis to make responses scannable: 🟢 positive, 🔴 negative, 🟡 neutral, 📈 buy, 📉 sell, ⏸️ hold
- Keep responses concise — this is Telegram, not a research report
- When showing numbers, round to 2 decimal places and use $ and % signs

Formatting (CRITICAL — you are on Telegram):
- Use ONLY Telegram HTML tags: <b>bold</b>, <i>italic</i>, <code>monospace</code>, <pre>preformatted</pre>, <a href="url">link</a>
- NEVER use markdown syntax like **bold**, *italic*, or ```code```. Telegram does not render markdown.
- NEVER use markdown tables (|---|---|). Instead use aligned <pre> blocks or simple line-by-line comparisons.
- For lists, use plain bullet characters like • or emojis, not markdown dashes.

Scope (IMPORTANT):
- You are ONLY a stock/finance assistant. You must REFUSE any non-financial requests politely.
- If the user asks about cooking, homework, coding, trivia, or anything unrelated to stocks, markets, or their portfolio, say something like: "I'm just a stock buddy — I only know finance stuff! 📊 Ask me about stocks, your portfolio, or markets."
- Simple greetings ("hi", "thanks") are fine — respond warmly, but steer back to finance.

Rules:
- ALWAYS use the available tools to get real data. Never make up stock prices or portfolio data.
- If the user refers to a company by name (e.g. "Apple", "Tesla", "Reliance") instead of a ticker, use lookup_symbol FIRST to find the correct ticker, then use that ticker with the other tools.
- If a tool fails, tell the user honestly and suggest trying again or checking the symbol.
- When comparing stocks, use compare_stocks — don't call analyze_stock multiple times.
- End responses with a relevant follow-up question or suggestion when appropriate.

Portfolio modifications (CRITICAL — always confirm first):
- Before calling add_stock, remove_stock, clear_portfolio, or update_stock, you MUST first summarize what you're about to do and ask the user to confirm. For example: "Got it — I'll add 10 shares of AAPL at $185. Should I go ahead? ✅"
- When the user wants to delete/remove ALL stocks, use clear_portfolio (not remove_stock in a loop).
- Only call the tool AFTER the user explicitly confirms (e.g. "yes", "go ahead", "do it").
- If the user says "no" or "wait", do NOT proceed. Ask what they'd like to change.

Financial advice disclaimer:
- For "should I buy/sell X?" questions, use analyze_stock to get real data, then give a balanced view with pros and cons.
- ALWAYS include a brief disclaimer that you're not a licensed financial advisor and this is not professional investment advice.
- NEVER predict specific future prices (e.g. "AAPL will hit $250"). You can discuss trends, analyst consensus, and fundamentals, but don't make price target claims.
"""

# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------


def _create_llm():
    """Create the LLM based on LLM_PROVIDER env var.

    Supported providers: gemini (default), perplexity, litellm.
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower().strip()

    if provider == "perplexity":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("PERPLEXITY_MODEL", "sonar"),
            api_key=os.getenv("PERPLEXITY_API_KEY"),
            base_url="https://api.perplexity.ai",
            temperature=0.3,
        )
    elif provider == "litellm":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("LITELLM_MODEL", "gpt-4o"),
            api_key=os.getenv("LITELLM_API_KEY"),
            base_url=os.getenv("LITELLM_API_BASE"),
            temperature=0.3,
        )
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.3,
        )


async def create_agent(db_path: str = "portfoliobuddy_memory.db"):
    """Build the ReAct agent with tools and persistent memory."""

    llm = _create_llm()
    provider = os.getenv("LLM_PROVIDER", "gemini").lower().strip()
    logger.info("LLM provider: %s | model: %s", provider, llm.model_name if hasattr(llm, 'model_name') else llm.model)

    memory = AsyncSqliteSaver(await aiosqlite.connect(db_path))
    await memory.setup()

    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        checkpointer=memory,
        prompt=SYSTEM_PROMPT,
    )

    return agent


# ---------------------------------------------------------------------------
# Telegram bot
# ---------------------------------------------------------------------------


class TelegramBot:
    def __init__(self, agent):
        self.agent = agent

    @classmethod
    async def create(cls):
        agent = await create_agent()
        return cls(agent)

    def _thread_config(self, user_id: int) -> dict:
        """Each Telegram user gets their own conversation thread."""
        return {
            "configurable": {"thread_id": str(user_id)},
            "recursion_limit": 50,
        }

    async def _invoke_agent(self, user_id: int, message: str) -> str:
        """Send a message to the agent and return the response text."""
        config = self._thread_config(user_id)
        try:
            result = await self.agent.ainvoke(
                {"messages": [("human", message)]},
                config=config,
            )
            ai_message = result["messages"][-1]
            return ai_message.content
        except Exception as e:
            logger.error(f"Agent error for user {user_id}: {e}", exc_info=True)
            return (
                "Oops, something went wrong on my end. "
                "Please try again in a moment. If it keeps happening, "
                "try rephrasing your question."
            )

    @staticmethod
    def _md_to_html(text: str) -> str:
        """Convert common Markdown patterns to Telegram-compatible HTML."""
        import re
        # Bold: **text** or __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
        # Italic: *text* or _text_ (but not inside words like don_t)
        text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'<i>\1</i>', text)
        text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<i>\1</i>', text)
        # Inline code: `text`
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        # Code blocks: ```text```
        text = re.sub(r'```(\w*)\n?(.*?)```', r'<pre>\2</pre>', text, flags=re.DOTALL)
        # Markdown tables → preformatted (simple approach)
        lines = text.split('\n')
        result = []
        in_table = False
        table_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('|') and stripped.endswith('|'):
                if not in_table:
                    in_table = True
                    table_lines = []
                # Skip separator rows like |---|---|
                if re.match(r'^\|[\s\-:|]+\|$', stripped):
                    continue
                table_lines.append(stripped)
            else:
                if in_table:
                    result.append('<pre>' + '\n'.join(table_lines) + '</pre>')
                    in_table = False
                    table_lines = []
                result.append(line)
        if in_table:
            result.append('<pre>' + '\n'.join(table_lines) + '</pre>')
        text = '\n'.join(result)
        # Markdown headings → bold
        text = re.sub(r'^#{1,3}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
        return text

    async def _send(self, update: Update, text: str) -> None:
        """Send a message with HTML parsing, falling back to plain text."""
        html = self._md_to_html(text)
        try:
            if len(html) > 4000:
                chunks = [html[i:i+4000] for i in range(0, len(html), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode="HTML")
            else:
                await update.message.reply_text(html, parse_mode="HTML")
        except Exception as e:
            # If HTML parsing fails (malformed tags), send as plain text
            logger.warning("HTML parse failed (%s), falling back to plain text", e)
            await update.message.reply_text(text)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle any text message."""
        user_id = update.effective_user.id
        text = update.message.text

        logger.info(f"User {user_id}: {text}")

        response = await self._invoke_agent(user_id, text)
        await self._send(update, response)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        welcome = (
            "Hey! I'm PortfolioBuddy 📊\n\n"
            "I can help you with:\n"
            "• Check your portfolio — \"How's my portfolio doing?\"\n"
            "• Analyze stocks — \"Tell me about AAPL\"\n"
            "• Compare stocks — \"Compare AAPL vs GOOGL vs MSFT\"\n"
            "• Manage holdings — \"I bought 10 shares of NVDA at $120\"\n"
            "• Get news — \"What's the latest on TSLA?\"\n\n"
            "Just talk to me like you'd talk to a friend who knows stocks. "
            "No special commands needed!\n\n"
            "What would you like to know? 🚀"
        )
        await self._send(update, welcome)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        help_text = (
            "Here's what I can do:\n\n"
            "📊 Portfolio: \"Show my portfolio\", \"How am I doing?\"\n"
            "🔍 Analysis: \"Analyze AAPL\", \"Should I buy TSLA?\"\n"
            "⚖️ Compare: \"Compare AAPL and GOOGL\"\n"
            "➕ Add: \"I bought 50 shares of MSFT at $400\"\n"
            "➖ Remove: \"I sold all my BABA\"\n"
            "✏️ Update: \"Update AAPL to 100 shares\"\n"
            "📰 News: \"What's happening with NVDA?\"\n\n"
            "I remember our conversations, so you can refer back to earlier messages!"
        )
        await self._send(update, help_text)

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reset command — clear conversation memory for this user."""
        user_id = update.effective_user.id
        # Reinitialize agent to clear the thread
        # (SqliteSaver doesn't have a delete method, so we note the reset in conversation)
        await self._invoke_agent(
            user_id,
            "[SYSTEM] The user has reset the conversation. Forget all prior context and start fresh."
        )
        await self._send(update, "Conversation reset! Let's start fresh. What can I help you with? 🔄")


def run_bot():
    """Start the Telegram bot."""
    import asyncio

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN not set. "
            "Get one from @BotFather on Telegram and add it to your .env file."
        )

    # Create the agent async, then hand the event loop to python-telegram-bot
    bot = asyncio.get_event_loop().run_until_complete(TelegramBot.create())

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", bot.start_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("reset", bot.reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    logger.info("PortfolioBuddy v2 starting...")
    logger.info("Tools loaded: %s", [t.name for t in ALL_TOOLS])
    app.run_polling()


if __name__ == "__main__":
    run_bot()
