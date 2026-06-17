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

DATA_DIR.mkdir(exist_ok=True)
