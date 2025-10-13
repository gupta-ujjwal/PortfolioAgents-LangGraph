# LangGraph Trading Bot Series

A comprehensive tutorial series for building automated trading bots using LangGraph and Google's Gemini API. This repository contains code examples and resources for a three-article series that progresses from basic agent concepts to a full-scale multi-agent trading system.

## Article Series Overview

### Article 1: Introduction to LangGraph and Basic Agents
- Understanding LangGraph fundamentals
- Building simple agents with state management
- Introduction to Gemini API integration
- Basic decision-making patterns

### Article 2: Multi-Agent Systems and Market Integration
- Coordinating multiple specialized agents
- Market data integration and processing
- Basic trading logic and signal generation
- Agent communication patterns

### Article 3: Advanced Trading System
- Complete multi-agent trading architecture
- Risk management and portfolio optimization
- Backtesting framework and performance analysis
- Production-ready deployment considerations

## Prerequisites

- Python 3.8 or higher
- Google Gemini API key (free tier available)
- Basic understanding of Python and trading concepts

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ExampleAgents
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

## Getting Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Create a new API key
4. Copy the key to your `.env` file

The Gemini API offers a generous free tier, making it perfect for development and learning without upfront costs.

## Project Structure

As you progress through the articles, new folders will be created:
- `article-1-intro/` - Basic LangGraph concepts and simple agents
- `article-2-intermediate/` - Multi-agent coordination and market data
- `article-3-advanced/` - Complete trading system with risk management

## Dependencies

- **LangGraph**: Framework for building stateful, multi-actor applications
- **LangChain**: Core framework for LLM applications
- **Google Generative AI**: Gemini API integration
- **Pandas/NumPy**: Data manipulation and analysis
- **YFinance**: Market data retrieval
- **Matplotlib**: Visualization for analysis

## Contributing

This repository is designed as a learning resource. Feel free to fork and modify the examples for your own trading strategies and research.

## Disclaimer

This educational content is for learning purposes only. Trading financial markets involves substantial risk. Always conduct thorough research and consider consulting with financial professionals before implementing real trading strategies.

## License

MIT License - feel free to use this code for educational and development purposes.