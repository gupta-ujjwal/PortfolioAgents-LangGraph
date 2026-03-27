"""
PortfolioBuddy v2 — Tools

All tools are decorated with @tool so the LLM can discover and call them.
Each tool returns a human-readable string (the LLM reads the output to
formulate its response). Errors are caught and returned as descriptive
messages so the LLM can reason about failures and retry or inform the user.
"""

import os
import csv
import json
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from functools import wraps

import yfinance as yf
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

CSV_PATH = os.getenv("PORTFOLIO_CSV_PATH", "portfolio.csv")

# ---------------------------------------------------------------------------
# Retry helper for flaky external APIs
# ---------------------------------------------------------------------------

def retry(max_attempts: int = 3, delay: float = 1.0):
    """Retry decorator for transient failures (e.g. Yahoo Finance timeouts)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    logger.warning(f"{fn.__name__} attempt {attempt}/{max_attempts} failed: {e}")
                    if attempt < max_attempts:
                        time.sleep(delay * attempt)
            raise last_err
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Internal helpers (not exposed to the LLM)
# ---------------------------------------------------------------------------

def _read_csv() -> List[Dict]:
    """Read portfolio CSV and return list of row dicts."""
    path = CSV_PATH
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            if not row.get("Symbol", "").strip():
                continue
            rows.append({
                "symbol": row["Symbol"].upper().strip(),
                "quantity": float(row["Quantity"]),
                "avg_cost": float(row["Average Cost"]),
                "notes": row.get("Notes", ""),
                "last_updated": row.get("Last Updated", ""),
            })
        return rows


def _write_csv(rows: List[Dict]) -> None:
    """Write rows back to the portfolio CSV."""
    path = CSV_PATH
    fieldnames = ["Symbol", "Quantity", "Average Cost", "Notes", "Last Updated"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "Symbol": row["symbol"],
                "Quantity": row["quantity"],
                "Average Cost": row["avg_cost"],
                "Notes": row.get("notes", ""),
                "Last Updated": row.get("last_updated", datetime.now().strftime("%Y-%m-%d")),
            })


@retry(max_attempts=3, delay=1.0)
def _fetch_market_data(symbol: str) -> Optional[Dict]:
    """Fetch current market data for a single symbol from Yahoo Finance."""
    ticker = yf.Ticker(symbol)
    info = ticker.info
    history = ticker.history(period="5d")

    if history.empty:
        return None

    current_price = float(history["Close"].iloc[-1])
    previous_close = float(info.get("previousClose", current_price))
    change = current_price - previous_close
    change_pct = (change / previous_close * 100) if previous_close else 0.0

    return {
        "symbol": symbol.upper(),
        "price": round(current_price, 2),
        "change": round(change, 2),
        "change_percent": round(change_pct, 2),
        "volume": int(info.get("volume", 0)),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "day_high": round(float(history["High"].iloc[-1]), 2) if not history.empty else None,
        "day_low": round(float(history["Low"].iloc[-1]), 2) if not history.empty else None,
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
    }


@retry(max_attempts=2, delay=0.5)
def _fetch_news(symbol: str) -> List[Dict]:
    """Fetch recent news for a symbol via yfinance.

    yfinance >=0.2.36 changed the news format to:
        [{"id": "...", "content": {"title": "...", "provider": {...}, ...}}, ...]
    Older versions used:
        [{"title": "...", "publisher": "...", "link": "...", ...}]
    We handle both.
    """
    ticker = yf.Ticker(symbol)
    raw_news = ticker.news or []
    items = []
    for article in raw_news[:5]:
        # New format: nested under "content"
        content = article.get("content", {})
        if content:
            title = content.get("title", "")
            provider = content.get("provider", {})
            source = provider.get("displayName", "") if isinstance(provider, dict) else ""
            url = content.get("canonicalUrl", {}).get("url", "") if isinstance(content.get("canonicalUrl"), dict) else ""
            pub_date = content.get("pubDate", "")
            # pubDate is ISO format like "2026-03-25T18:30:00Z"
            if pub_date:
                try:
                    published_at = datetime.fromisoformat(pub_date.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
                except (ValueError, AttributeError):
                    published_at = pub_date[:16] if len(pub_date) >= 16 else pub_date
            else:
                published_at = ""
        else:
            # Old format: flat dict
            title = article.get("title", "")
            source = article.get("publisher", "")
            url = article.get("link", "")
            ts = article.get("providerPublishTime", 0)
            published_at = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""

        if title:
            items.append({
                "title": title,
                "source": source,
                "url": url,
                "published_at": published_at,
            })
    return items


def _format_currency(val: float) -> str:
    return f"${val:,.2f}"


def _format_percent(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%"


# ---------------------------------------------------------------------------
# LLM-callable tools
# ---------------------------------------------------------------------------

@tool
def get_portfolio_summary() -> str:
    """Get a complete summary of the user's stock portfolio with current market prices, total value, and gain/loss for each holding. Use this when the user asks about their portfolio, holdings, or overall performance."""
    try:
        rows = _read_csv()
        if not rows:
            return "Portfolio is empty. No stocks found. The user can ask me to add stocks."

        results = []
        total_value = 0.0
        total_cost = 0.0
        failed_symbols = []

        for row in rows:
            symbol = row["symbol"]
            qty = row["quantity"]
            avg_cost = row["avg_cost"]
            cost_basis = qty * avg_cost

            mkt = _fetch_market_data(symbol)
            if mkt is None:
                failed_symbols.append(symbol)
                continue

            current_value = qty * mkt["price"]
            gain_loss = current_value - cost_basis
            gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis else 0

            total_value += current_value
            total_cost += cost_basis

            results.append({
                "symbol": symbol,
                "quantity": qty,
                "avg_cost": avg_cost,
                "current_price": mkt["price"],
                "current_value": round(current_value, 2),
                "gain_loss": round(gain_loss, 2),
                "gain_loss_percent": round(gain_loss_pct, 2),
                "day_change_percent": mkt["change_percent"],
            })

        # Sort by gain/loss % descending
        results.sort(key=lambda x: x["gain_loss_percent"], reverse=True)

        total_gain = total_value - total_cost
        total_gain_pct = (total_gain / total_cost * 100) if total_cost else 0

        lines = [
            f"Portfolio Summary (as of {datetime.now().strftime('%Y-%m-%d %H:%M')})",
            f"Total Value: {_format_currency(total_value)}",
            f"Total Cost Basis: {_format_currency(total_cost)}",
            f"Total Gain/Loss: {_format_currency(total_gain)} ({_format_percent(total_gain_pct)})",
            f"Number of Holdings: {len(results)}",
            "",
            "Holdings (sorted by gain/loss %):",
        ]

        for r in results:
            lines.append(
                f"  {r['symbol']}: {r['quantity']} shares @ {_format_currency(r['avg_cost'])} "
                f"| Now {_format_currency(r['current_price'])} "
                f"| Value {_format_currency(r['current_value'])} "
                f"| P&L {_format_currency(r['gain_loss'])} ({_format_percent(r['gain_loss_percent'])}) "
                f"| Today {_format_percent(r['day_change_percent'])}"
            )

        if failed_symbols:
            lines.append(f"\nCould not fetch data for: {', '.join(failed_symbols)}. These may be delisted or temporarily unavailable.")

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching portfolio: {e}. Please try again."


@tool
def analyze_stock(symbol: str) -> str:
    """Perform a detailed analysis of a specific stock including price, fundamentals, news, and a recommendation. Use this when the user asks about a specific stock, wants analysis, or asks 'should I buy/sell X'."""
    symbol = symbol.upper().strip()
    try:
        mkt = _fetch_market_data(symbol)
        if mkt is None:
            return f"Could not fetch market data for {symbol}. The symbol may be invalid or the market data service is temporarily down. Please verify the ticker symbol."

        news = _fetch_news(symbol)

        # Check if user holds this stock
        rows = _read_csv()
        holding = next((r for r in rows if r["symbol"] == symbol), None)

        lines = [
            f"Analysis for {symbol}",
            f"Current Price: {_format_currency(mkt['price'])}",
            f"Day Change: {_format_currency(mkt['change'])} ({_format_percent(mkt['change_percent'])})",
            f"Day Range: {_format_currency(mkt['day_low'] or 0)} - {_format_currency(mkt['day_high'] or 0)}",
        ]

        if mkt["fifty_two_week_high"]:
            lines.append(f"52-Week Range: {_format_currency(mkt['fifty_two_week_low'] or 0)} - {_format_currency(mkt['fifty_two_week_high'])}")

        if mkt["pe_ratio"]:
            lines.append(f"P/E Ratio: {mkt['pe_ratio']:.2f}")

        if mkt["market_cap"]:
            cap = mkt["market_cap"]
            if cap >= 1e12:
                lines.append(f"Market Cap: ${cap/1e12:.2f}T")
            elif cap >= 1e9:
                lines.append(f"Market Cap: ${cap/1e9:.2f}B")
            else:
                lines.append(f"Market Cap: ${cap/1e6:.2f}M")

        if mkt["volume"]:
            lines.append(f"Volume: {mkt['volume']:,}")

        if holding:
            qty = holding["quantity"]
            avg = holding["avg_cost"]
            value = qty * mkt["price"]
            gain = value - (qty * avg)
            gain_pct = (gain / (qty * avg) * 100) if avg else 0
            lines.append("")
            lines.append(f"Your Position: {qty} shares @ {_format_currency(avg)}")
            lines.append(f"Position Value: {_format_currency(value)}")
            lines.append(f"Position P&L: {_format_currency(gain)} ({_format_percent(gain_pct)})")

        if news:
            lines.append("")
            lines.append("Recent News:")
            for n in news:
                lines.append(f"  - [{n['published_at']}] {n['title']} ({n['source']})")
        else:
            lines.append("\nNo recent news found.")

        return "\n".join(lines)

    except Exception as e:
        return f"Error analyzing {symbol}: {e}. Please try again."


@tool
def compare_stocks(symbols: list[str]) -> str:
    """Compare two or more stocks side by side on price, performance, fundamentals, and the user's holdings. Use this when the user asks to compare stocks like 'compare AAPL and GOOGL' or 'AAPL vs MSFT'."""
    if len(symbols) < 2:
        return "Please provide at least 2 stock symbols to compare."

    symbols = [s.upper().strip() for s in symbols]
    rows = _read_csv()
    holdings_map = {r["symbol"]: r for r in rows}

    data = []
    failed = []
    for sym in symbols:
        try:
            mkt = _fetch_market_data(sym)
            if mkt is None:
                failed.append(sym)
                continue
            data.append(mkt)
        except Exception:
            failed.append(sym)

    if not data:
        return f"Could not fetch data for any of the symbols: {', '.join(symbols)}."

    lines = [f"Stock Comparison: {' vs '.join(s['symbol'] for s in data)}", ""]

    # Table header
    lines.append(f"{'Metric':<20} " + " ".join(f"{d['symbol']:>14}" for d in data))
    lines.append("-" * (20 + 15 * len(data)))

    # Price
    lines.append(f"{'Price':<20} " + " ".join(f"{_format_currency(d['price']):>14}" for d in data))

    # Day Change
    lines.append(f"{'Day Change':<20} " + " ".join(f"{_format_percent(d['change_percent']):>14}" for d in data))

    # P/E
    pe_vals = []
    for d in data:
        pe_vals.append(f"{d['pe_ratio']:.2f}" if d.get("pe_ratio") else "N/A")
    lines.append(f"{'P/E Ratio':<20} " + " ".join(f"{v:>14}" for v in pe_vals))

    # Market Cap
    cap_vals = []
    for d in data:
        cap = d.get("market_cap")
        if cap and cap >= 1e12:
            cap_vals.append(f"${cap/1e12:.2f}T")
        elif cap and cap >= 1e9:
            cap_vals.append(f"${cap/1e9:.2f}B")
        elif cap:
            cap_vals.append(f"${cap/1e6:.0f}M")
        else:
            cap_vals.append("N/A")
    lines.append(f"{'Market Cap':<20} " + " ".join(f"{v:>14}" for v in cap_vals))

    # Volume
    vol_vals = []
    for d in data:
        v = d.get("volume", 0)
        if v >= 1e6:
            vol_vals.append(f"{v/1e6:.1f}M")
        else:
            vol_vals.append(f"{v:,}")
    lines.append(f"{'Volume':<20} " + " ".join(f"{v:>14}" for v in vol_vals))

    # 52-week range
    range_vals = []
    for d in data:
        lo = d.get("fifty_two_week_low")
        hi = d.get("fifty_two_week_high")
        if lo and hi:
            range_vals.append(f"${lo:.0f}-${hi:.0f}")
        else:
            range_vals.append("N/A")
    lines.append(f"{'52-Week Range':<20} " + " ".join(f"{v:>14}" for v in range_vals))

    # User holdings
    has_holdings = any(s["symbol"] in holdings_map for s in data)
    if has_holdings:
        lines.append("")
        lines.append("Your Holdings:")
        for d in data:
            sym = d["symbol"]
            if sym in holdings_map:
                h = holdings_map[sym]
                value = h["quantity"] * d["price"]
                gain = value - (h["quantity"] * h["avg_cost"])
                gain_pct = (gain / (h["quantity"] * h["avg_cost"]) * 100) if h["avg_cost"] else 0
                lines.append(f"  {sym}: {h['quantity']} shares | Value {_format_currency(value)} | P&L {_format_currency(gain)} ({_format_percent(gain_pct)})")
            else:
                lines.append(f"  {sym}: Not in portfolio")

    if failed:
        lines.append(f"\nCould not fetch data for: {', '.join(failed)}")

    return "\n".join(lines)


@tool
def add_stock(symbol: str, quantity: float, avg_cost: float, notes: str = "") -> str:
    """Add a new stock to the user's portfolio or update quantity if it already exists. Use this when the user says they bought a stock or wants to add a holding."""
    symbol = symbol.upper().strip()

    if quantity <= 0:
        return f"Quantity must be positive. Got {quantity}."
    if avg_cost <= 0:
        return f"Average cost must be positive. Got {avg_cost}."

    try:
        rows = _read_csv()
        existing = next((r for r in rows if r["symbol"] == symbol), None)

        if existing:
            # Weighted average cost
            old_total = existing["quantity"] * existing["avg_cost"]
            new_total = quantity * avg_cost
            combined_qty = existing["quantity"] + quantity
            new_avg = (old_total + new_total) / combined_qty

            existing["quantity"] = round(combined_qty, 4)
            existing["avg_cost"] = round(new_avg, 2)
            existing["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            if notes:
                existing["notes"] = notes

            _write_csv(rows)
            return (
                f"Updated {symbol} in portfolio. "
                f"New position: {existing['quantity']} shares @ {_format_currency(existing['avg_cost'])} avg cost. "
                f"(Added {quantity} shares @ {_format_currency(avg_cost)})"
            )
        else:
            rows.append({
                "symbol": symbol,
                "quantity": quantity,
                "avg_cost": avg_cost,
                "notes": notes,
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
            })
            _write_csv(rows)
            return f"Added {symbol} to portfolio: {quantity} shares @ {_format_currency(avg_cost)}."

    except Exception as e:
        return f"Error adding {symbol}: {e}. Please try again."


@tool
def remove_stock(symbol: str) -> str:
    """Remove a stock entirely from the user's portfolio. Use this when the user says they sold all shares of a stock or wants to remove a holding."""
    symbol = symbol.upper().strip()
    try:
        rows = _read_csv()
        original_len = len(rows)
        rows = [r for r in rows if r["symbol"] != symbol]

        if len(rows) == original_len:
            return f"{symbol} is not in the portfolio. No changes made."

        _write_csv(rows)
        return f"Removed {symbol} from portfolio."

    except Exception as e:
        return f"Error removing {symbol}: {e}. Please try again."


@tool
def update_stock(symbol: str, quantity: float = 0, avg_cost: float = 0, notes: str = "") -> str:
    """Update an existing stock's quantity, average cost, or notes. Use this when the user wants to correct their holdings or sold some (not all) shares."""
    symbol = symbol.upper().strip()
    try:
        rows = _read_csv()
        existing = next((r for r in rows if r["symbol"] == symbol), None)

        if not existing:
            return f"{symbol} is not in the portfolio. Use add_stock to add it first."

        changes = []
        if quantity > 0:
            existing["quantity"] = quantity
            changes.append(f"quantity to {quantity}")
        if avg_cost > 0:
            existing["avg_cost"] = avg_cost
            changes.append(f"avg cost to {_format_currency(avg_cost)}")
        if notes:
            existing["notes"] = notes
            changes.append(f"notes to '{notes}'")

        if not changes:
            return "No changes specified. Provide quantity, avg_cost, or notes to update."

        existing["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        _write_csv(rows)
        return f"Updated {symbol}: {', '.join(changes)}."

    except Exception as e:
        return f"Error updating {symbol}: {e}. Please try again."


@tool
def get_stock_news(symbol: str) -> str:
    """Get the latest news articles for a stock. Use this when the user asks about news, what's happening with a stock, or recent events."""
    symbol = symbol.upper().strip()
    try:
        news = _fetch_news(symbol)
        if not news:
            return f"No recent news found for {symbol}."

        lines = [f"Recent News for {symbol}:", ""]
        for i, n in enumerate(news, 1):
            lines.append(f"{i}. {n['title']}")
            lines.append(f"   Source: {n['source']} | {n['published_at']}")
            if n.get("url"):
                lines.append(f"   URL: {n['url']}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"Error fetching news for {symbol}: {e}. Please try again."


# Collect all tools for the agent
ALL_TOOLS = [
    get_portfolio_summary,
    analyze_stock,
    compare_stocks,
    add_stock,
    remove_stock,
    update_stock,
    get_stock_news,
]
