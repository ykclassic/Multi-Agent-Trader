"""Deterministic, LLM-independent market analytics and risk controls."""

from .contracts import MarketDataProvider, MarketDataRequest
from .engine import Candle, MarketSnapshot, RiskAssessment, assess_position_risk, build_market_snapshot
from .ingestion import IngestionResult, ingest_candles
from .persistence import CandlePersistenceError, SupabaseRestCandleRepository
from .providers import BinanceSpotProvider, MarketDataProviderError, TwelveDataForexProvider
from .quality import MarketDataQuality, score_candle_batch

__all__ = [
    "BinanceSpotProvider",
    "Candle",
    "CandlePersistenceError",
    "IngestionResult",
    "MarketDataProvider",
    "MarketDataProviderError",
    "MarketDataQuality",
    "MarketDataRequest",
    "MarketSnapshot",
    "RiskAssessment",
    "SupabaseRestCandleRepository",
    "TwelveDataForexProvider",
    "assess_position_risk",
    "build_market_snapshot",
    "ingest_candles",
    "score_candle_batch",
]
