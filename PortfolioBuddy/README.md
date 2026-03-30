# PortfolioBuddy

The AI-powered stock portfolio assistant built with LangGraph. This is the core agent — see the [root README](../README.md) for the article series overview and setup instructions.

## Architecture (v2)

PortfolioBuddy v2 uses a **ReAct agent** — the LLM observes, reasons, picks a tool, observes the result, and decides what's next. No hardcoded routing.

```
User message → LLM reasons → picks tool(s) → reads result → responds (or picks another tool)
```

Built with:
- **LangGraph** `create_react_agent` — ReAct loop with tool-calling
- **Google Gemini** — LLM (swappable via `LLM_PROVIDER`)
- **SQLite** — persistent conversation memory + portfolio storage
- **Yahoo Finance** — real-time market data and news
- **Telegram** — user interface

## Tools

The LLM has 9 tools it can call freely based on what the user asks:

| Tool | What it does |
|------|-------------|
| `get_portfolio_summary` | Full portfolio with current prices, P&L, day changes |
| `analyze_stock` | Deep dive — price, fundamentals, news, user position |
| `compare_stocks` | Side-by-side comparison table for 2+ stocks |
| `add_stock` | Add holding (or average up/down if exists) |
| `remove_stock` | Remove a holding entirely |
| `update_stock` | Modify quantity, cost, or notes |
| `clear_portfolio` | Wipe all holdings at once |
| `get_stock_news` | Recent news articles for a symbol |
| `lookup_symbol` | Find ticker by company name ("Apple" → AAPL) |

Each tool returns a string the LLM reads to formulate its response. Errors are returned as descriptive messages (not exceptions) so the LLM can reason about failures.

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Optional — switch LLM provider
LLM_PROVIDER=gemini              # gemini | perplexity | litellm
GEMINI_MODEL=gemini-2.5-flash-lite
PERPLEXITY_API_KEY=...
PERPLEXITY_MODEL=sonar
LITELLM_API_KEY=...
LITELLM_API_BASE=...
LITELLM_MODEL=gpt-4o

# Optional — enhanced news
NEWS_API_KEY=your_newsapi_key
```

## Running

```bash
python agent.py
```

### Telegram Commands
- `/start` — welcome message
- `/help` — list of capabilities
- `/reset` — clear conversation memory

Or just talk naturally — no commands needed.

## Files

```
PortfolioBuddy/
├── agent.py              # ReAct agent, system prompt, Telegram bot
├── tools.py              # 9 @tool-decorated functions
├── portfolio_types.py    # TypedDict definitions and enums
├── .env.example          # Environment variable template
├── sample_portfolio.csv  # Sample data to get started
└── requirements.txt      # Python dependencies
```

## Key Design Decisions

- **Tool docstrings are routing.** The LLM reads each tool's docstring to decide when to call it. No intent classifier, no conditional edges. Adding a new capability = adding a new `@tool` function.
- **Errors go to the LLM, not the user.** Tools return error strings like "Could not fetch data for XYZFAKE. Symbol may be invalid." The LLM reads this and responds in context — suggesting alternatives, asking the user to check the symbol, etc.
- **Retry before failing.** Transient Yahoo Finance failures get retried (3 attempts with exponential backoff) before surfacing an error.
- **Confirmation before mutations.** The system prompt instructs the LLM to always confirm before adding, removing, or updating holdings.
- **One thread per user.** Each Telegram user gets their own SQLite-backed conversation thread. Memory persists across bot restarts.

## Disclaimer

Educational project. Not financial advice. Always do your own research.
