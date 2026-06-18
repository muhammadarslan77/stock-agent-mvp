"""Central configuration for Stock Agent MVP.

All shared constants live here so other modules never hardcode paths,
model names, or risk thresholds.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "portfolio.db"

OPENAI_MODEL = "gpt-4o-mini"

# Maximum share of total portfolio value any single stock may occupy,
# enforced by services/risk.py (wired up in Phase 3).
RISK_TIERS = {
    "low": 0.10,
    "medium": 0.25,
    "high": 0.50,
}

PRICE_CACHE_TTL = 300       # seconds — live price freshness
HISTORY_CACHE_TTL = 3600    # seconds — historical OHLCV freshness

DEFAULT_STARTING_CASH = 10_000.00

# Curated shortlist shown in the Buy picker. Users can still type any
# Yahoo-listed ticker via the "Other…" fallback.
POPULAR_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD",
    "NFLX", "DIS", "JPM", "BAC", "V", "MA", "WMT", "COST", "HD",
    "KO", "PEP", "MCD", "NKE", "PFE", "JNJ", "UNH", "XOM", "CVX",
    "BA", "CAT", "GE", "F", "GM", "T", "VZ", "INTC", "ORCL", "CRM",
    "ADBE", "CSCO", "IBM", "QCOM", "PYPL", "SHOP", "UBER", "ABNB",
    "SPY", "QQQ", "VOO", "VTI", "DIA", "IWM",
]

DATA_DIR.mkdir(exist_ok=True)
