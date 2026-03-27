# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A collection of LangGraph-based AI agent examples, currently featuring **PortfolioBuddy** — a Telegram bot that tracks stock portfolios, analyzes market data, and provides investment insights using Google Gemini and LangGraph.

## Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run the PortfolioBuddy Telegram bot
cd PortfolioBuddy && python agent.py

# Formatting and linting
black PortfolioBuddy/
flake8 PortfolioBuddy/

# Tests
pytest
```

## Environment Variables

Requires a `.env` file (see `PortfolioBuddy/.env.example`):
- `GEMINI_API_KEY` — Google Gemini API key
- `TELEGRAM_BOT_TOKEN` — Telegram bot token
- `PORTFOLIO_CSV_PATH` — path to portfolio CSV (defaults to `portfolio.csv`)
- `NEWS_API_KEY` — optional, falls back to Yahoo Finance news

## Architecture

### PortfolioBuddy

LangGraph `StateGraph` with 4 nodes and conditional routing:

```
process_message → [fetch_portfolio | analyze_portfolio | generate_response]
fetch_portfolio → analyze_portfolio → generate_response → END
```

- **`agent.py`** — `PortfolioBuddyAgent` class: builds the LangGraph workflow, handles Telegram commands (`/start`, `/portfolio`, `/analyze`), manages user sessions (in-memory dict keyed by Telegram user ID)
- **`tools.py`** — Data layer: `CSVPortfolioManager` (reads portfolio from CSV), `YahooFinanceManager` (yfinance market data), `NewsManager` (NewsAPI + Yahoo Finance fallback, TextBlob sentiment), `PortfolioAnalyzer` (combines market data + news into buy/sell/hold recommendations)
- **`portfolio_types.py`** — All TypedDict definitions and enums (`AgentState`, `PortfolioHolding`, `MarketData`, `SentimentIndicator`, `ActionType`, etc.)

### Key patterns

- State is a `TypedDict` (`AgentState`) — not Pydantic. All data types in `portfolio_types.py` are TypedDicts accessed with bracket notation (`holding['symbol']`), not attribute access.
- LLM intent classification returns JSON parsed with regex extraction (`re.search(r'\{.*\}', ...)`).
- Portfolio CSV format: columns `Symbol`, `Quantity`, `Average Cost`.
- The repo is structured for multiple example agents (one per subdirectory), though only PortfolioBuddy exists currently.
