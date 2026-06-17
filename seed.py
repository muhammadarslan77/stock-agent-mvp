"""Populate the database with a demo profile + a few sample trades.

Run from the project root:

    python seed.py

You'll see a couple of Streamlit "missing ScriptRunContext" warnings —
they come from the cache decorators in `market_data.py` and are harmless
when called outside `streamlit run`.
"""
from datetime import date

from database.schema import init_db
from services.portfolio import PortfolioError, buy
from services.profile import profile_exists, save_profile


SAMPLE_TRADES = [("AAPL", 5), ("MSFT", 3), ("GOOGL", 2)]


def seed() -> None:
    init_db()

    if profile_exists():
        print("Profile already exists — skipping profile seed.")
    else:
        save_profile(
            name="Demo User",
            goal="Wealth growth",
            target_amount=100_000.0,
            target_date=date.today().replace(year=date.today().year + 5).isoformat(),
            risk_tolerance="medium",
            starting_cash=10_000.0,
        )
        print("Created demo profile (starting cash: $10,000).")

    for ticker, qty in SAMPLE_TRADES:
        try:
            result = buy(ticker, qty)
            print(f"Bought {result['quantity']} × {result['ticker']} "
                  f"@ ${result['price']:.2f} = ${result['total']:.2f}")
        except PortfolioError as e:
            print(f"Skipped {ticker}: {e}")


if __name__ == "__main__":
    seed()
