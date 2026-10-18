"""Deterministic, LLM-independent market analytics and risk controls."""

from .contracts import MarketDataProvider, MarketDataRequest
from .engine import Candle, MarketSnapshot, RiskAssessment, assess_position_risk, build_market_snapshot
from .ingestion import IngestionResult, ingest_candles
from .market_state import MarketState, classify_market_state
from .persistence import CandlePersistenceError, SupabaseRestCandleRepository\nfrom .portfolio_state import (\n    PortfolioStateSnapshot, PositionSnapshot, evaluate_snapshot_proposal,\n)\nfrom .research_persistence import (\n    PointInTimeCandle, ResearchPersistenceError, SupabaseRestResearchRepository,\n)\nfrom .walk_forward import (\n    FoldResult, WalkForwardConfig, WalkForwardResult, make_ema_regime_strategy,\n    walk_forward_evaluate,\n)
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
    "PointInTimeCandle", "PortfolioStateSnapshot", "PositionSnapshot", "ProposedExposure",\n    "ResearchPersistenceError", "RiskAssessment", "RiskLimits", "RiskPolicyDecision",\n    "SupabaseRestResearchRepository", "FoldResult", "WalkForwardConfig", "WalkForwardResult",
    "SupabaseRestCandleRepository", "TwelveDataForexProvider",
    "assess_position_risk", "build_market_snapshot", "classify_market_state",
    "evaluate_portfolio_risk", "evaluate_snapshot_proposal", "ingest_candles",\n    "make_ema_regime_strategy", "score_candle_batch", "walk_forward_evaluate",
]
