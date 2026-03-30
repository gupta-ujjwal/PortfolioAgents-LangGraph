"""Quick integration tests for PortfolioBuddy v2 agent."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from agent import create_agent


async def run_tests():
    agent = await create_agent(":memory:")
    config = {"configurable": {"thread_id": "test-user-1"}}

    tests = [
        ("Greeting (no tools)", "Hey whats up"),
        ("Single stock analysis", "Tell me about AAPL"),
        ("Memory recall", "What stock did I just ask about?"),
        ("Add stock", "I just bought 10 shares of AMZN at 185 dollars"),
        ("Compare stocks", "Compare AAPL and MSFT"),
        ("News", "Whats the latest news on TSLA"),
    ]

    for name, message in tests:
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print(f"USER: {message}")
        print("-" * 60, flush=True)
        try:
            result = await agent.ainvoke(
                {"messages": [("human", message)]}, config=config
            )
            ai_msg = result["messages"][-1].content
            # Truncate for readability
            if len(ai_msg) > 500:
                ai_msg = ai_msg[:500] + "...[truncated]"
            print(f"AI: {ai_msg}", flush=True)
        except Exception as e:
            print(f"ERROR: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(run_tests())
