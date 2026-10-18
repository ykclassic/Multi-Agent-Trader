"""Deterministic, LLM-independent market analytics and risk controls."""

from .contracts import MarketDataProvider, MarketDataRequest
from .engine import Candle, MarketSnapshot, RiskAssessment, assess_position_risk, build_market_snapshot
from .ingestion import IngestionResult, ingest_candles
from .market_state import MarketState, classify_market_state
from .persistence import CandlePersistenceError, SupabaseRestCandleRepository
from .providers import BinanceSpotProvider, MarketDataProviderError, TwelveDataForexProvider
from .quality import MarketDataQuality, score_candle_batch
from .risk import (
    PortfolioRiskState, ProposedExposure, RiskLimits, RiskPolicyDecision,
    evaluate_portfolio_risk,
)

__all__ = [
    "BinanceSpotProvider", "Candle", "CandlePersistenceError", "IngestionResult",
    "MarketDataProvider", "MarketDataProviderError", "MarketDataQuality",
    "MarketDataRequest", "MarketSnapshot", "MarketState", "PortfolioRiskState",
    "ProposedExposure", "RiskAssessment", "RiskLimits", "RiskPolicyDecision",
    "SupabaseRestCandleRepository", "TwelveDataForexProvider",
    "assess_position_risk", "build_market_snapshot", "classify_market_state",
    "evaluate_portfolio_risk", "ingest_candles", "score_candle_batch",
]
