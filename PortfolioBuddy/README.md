# PortfolioBuddy 🤖

A sophisticated AI-powered portfolio management assistant that helps you track your investments, analyze market trends, and make informed decisions through natural conversation via Telegram.

## Features 🚀

- **💬 Natural Conversation**: Chat with your portfolio via Telegram using simple language
- **📊 Real-time Portfolio Tracking**: Reads from local CSV file for live portfolio data
- **📈 Market Analysis**: Yahoo Finance integration for current market data
- **📰 News Sentiment Analysis**: Aggregates and analyzes news for your holdings
- **🎯 Smart Recommendations**: AI-powered buy/sell/hold suggestions with confidence scores
- **🟢🟡🔴 Visual Indicators**: Clear sentiment and action indicators
- **🔒 Secure**: Uses local CSV file - no cloud dependencies

## Architecture

Built with:
- **LangGraph**: For conversational AI workflow management
- **Gemini**: Google's LLM for intelligent analysis
- **Telegram**: User interface and messaging
- **Yahoo Finance**: Real-time market data
- **Local CSV**: Simple portfolio data storage
- **TextBlob**: News sentiment analysis

## Setup Instructions

### 1. Environment Variables

Create a `.env` file in the PortfolioBuddy directory with the following:

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Optional - path to your portfolio CSV file (defaults to 'portfolio.csv')
PORTFOLIO_CSV_PATH=portfolio.csv

# Optional - for enhanced news
NEWS_API_KEY=your_news_api_key_here
```

### 2. Generate API Keys

#### Gemini API Key
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key and add to your `.env` file

#### Telegram Bot Token
1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/start` then `/newbot`
3. Follow the prompts to create your bot
4. Copy the bot token and add to your `.env` file

#### News API Key (Optional)
1. Go to [NewsAPI.org](https://newsapi.org/)
2. Sign up for a free account
3. Get your API key from the dashboard

### 3. Portfolio CSV Setup

Create a `portfolio.csv` file in the PortfolioBuddy directory with the following format:

```csv
Symbol,Quantity,Average Cost,Notes,Last Updated
AAPL,50,150.25,Core tech holding,2024-10-13
GOOGL,20,2800.00,Long term growth,2024-10-13
MSFT,30,350.75,Cloud computing play,2024-10-13
TSLA,15,220.50,High growth potential,2024-10-13
AMZN,25,3200.00,E-commerce leader,2024-10-13
```

**Important**: The CSV must have these exact column headers (case-sensitive):
- `Symbol` - Stock ticker symbol
- `Quantity` - Number of shares owned
- `Average Cost` - Average purchase price per share
- `Notes` - Optional notes about the holding
- `Last Updated` - Date of last update

### 4. Quick Start with Sample Data

Use the provided sample portfolio:

```bash
# Copy the sample portfolio
cp sample_portfolio.csv portfolio.csv

# Or create your own portfolio.csv with your actual holdings
```

### 5. Install Dependencies

```bash
cd PortfolioBuddy
pip install -r requirements.txt
```

### 6. Run the Bot

```bash
python agent.py
```

## Usage Examples

### Basic Commands
- `/start` - Welcome message and help
- `/portfolio` - View your portfolio summary
- `/analyze AAPL` - Analyze a specific stock

### Natural Language Queries
- "How is my portfolio doing today?"
- "What's happening with Tesla stock?"
- "Should I buy more Apple shares?"
- "Show me my worst performing stocks"
- "What's the news about NVIDIA?"
- "Is it time to sell my Meta shares?"

## Response Format

The bot provides responses with clear indicators:

**Sentiment Indicators:**
- 🟢 Positive news/sentiment
- 🟡 Neutral news/sentiment  
- 🔴 Negative news/sentiment

**Action Recommendations:**
- 📈 BUY - Consider buying more
- 📉 SELL - Consider selling
- ⏸️ HOLD - Keep current position
- 👀 WATCH - Monitor closely

## CSV File Management

### Updating Your Portfolio
Simply edit the `portfolio.csv` file:
- Add new holdings by appending rows
- Update quantities or average costs
- Remove holdings by deleting rows
- Changes are reflected immediately on next query

### CSV Format Rules
- Use comma-separated values
- First row must contain headers
- Symbol must be valid Yahoo Finance ticker
- Quantity and Average Cost must be numbers
- Empty rows are automatically skipped

### Sample Portfolio Breakdown

The included sample portfolio contains:
- **Total Value**: ~$258,000
- **Diversification**: 15 stocks across sectors
- **Focus**: Tech-heavy with some defensive positions

**Sectors Represented:**
- Technology (60%): AAPL, GOOGL, MSFT, NVDA, META, NFLX
- Consumer Discretionary (20%): TSLA, AMZN, DIS, UBER
- Financials (13%): JPM, V
- Healthcare (7%): JNJ
- Consumer Staples (7%): WMT
- International (3%): BABA

## Security Notes

- Portfolio data stored locally in CSV file
- No cloud storage dependencies
- API keys stored in environment variables
- Never share your API keys or CSV file

## Troubleshooting

### Common Issues

**Bot doesn't respond:**
- Check TELEGRAM_BOT_TOKEN is correct
- Ensure the bot is running without errors
- Verify internet connection

**CSV file not found:**
- Ensure `portfolio.csv` exists in the PortfolioBuddy directory
- Check PORTFOLIO_CSV_PATH environment variable
- Verify file permissions

**No market data:**
- Check Yahoo Finance API access
- Verify stock symbols are correct
- Check internet connection

**Gemini API errors:**
- Verify GEMINI_API_KEY is valid
- Check API quota limits
- Ensure proper billing is set up

**CSV parsing errors:**
- Check column headers match exactly
- Ensure proper CSV format
- Verify no special characters in data

### Debug Mode

Enable debug logging by modifying the logging level in `agent.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Development

### Project Structure
```
PortfolioBuddy/
├── agent.py              # Main LangGraph agent and Telegram bot
├── types.py              # Type definitions and data models
├── tools.py              # Portfolio analysis and data fetching tools
├── portfolio.csv         # Your portfolio data (create this)
├── sample_portfolio.csv  # Sample portfolio for testing
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
└── README.md             # This file
```

### Extending the Agent

To add new features:
1. Add new tools in `tools.py`
2. Update types in `types.py` if needed
3. Modify the LangGraph workflow in `agent.py`
4. Update the prompt templates for better responses

## Advantages of CSV Approach

- **Simple**: No complex setup or authentication
- **Fast**: Direct file access, no API calls for portfolio data
- **Secure**: Local storage, no cloud dependencies
- **Portable**: Easy backup and share
- **Version Control**: Can track changes with Git
- **Flexible**: Easy to edit manually or programmatically

## License

This project is for educational and personal use. Please ensure compliance with all API terms of service.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Verify all environment variables are set
3. Ensure portfolio.csv is properly formatted
4. Check the logs for detailed error messages

---

**Disclaimer**: This tool provides analysis and information for educational purposes only. It's not financial advice. Always do your own research before making investment decisions.