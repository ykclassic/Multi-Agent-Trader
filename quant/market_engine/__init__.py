"""Deterministic, LLM-independent market analytics and risk controls."""

from .calibration import (
    RiskCalibrationCandidate, RiskCalibrationCandidateResult, RiskCalibrationReport,
    calibrate_risk_limits,
)
from .contracts import MarketDataProvider, MarketDataRequest
from .engine import Candle, MarketSnapshot, RiskAssessment, assess_position_risk, build_market_snapshot
from .ingestion import IngestionResult, ingest_candles
from .market_state import MarketState, classify_market_state
from .persistence import CandlePersistenceError, SupabaseRestCandleRepository
from .portfolio_state import PortfolioStateSnapshot, PositionSnapshot, evaluate_snapshot_proposal
from .providers import BinanceSpotProvider, MarketDataProviderError, TwelveDataForexProvider
from .quality import MarketDataQuality, score_candle_batch
from .research_persistence import PointInTimeCandle, ResearchPersistenceError, SupabaseRestResearchRepository
from .risk import PortfolioRiskState, ProposedExposure, RiskLimits, RiskPolicyDecision, evaluate_portfolio_risk
from .walk_forward import FoldResult, WalkForwardConfig, WalkForwardResult, make_ema_regime_strategy, walk_forward_evaluate

__all__ = [
    "BinanceSpotProvider", "Candle", "CandlePersistenceError", "FoldResult",
    "IngestionResult", "MarketDataProvider", "MarketDataProviderError",
    "MarketDataQuality", "MarketDataRequest", "MarketSnapshot", "MarketState",
    "PointInTimeCandle", "PortfolioRiskState", "PortfolioStateSnapshot",
    "PositionSnapshot", "ProposedExposure", "ResearchPersistenceError",
    "RiskAssessment", "RiskCalibrationCandidate", "RiskCalibrationCandidateResult",
    "RiskCalibrationReport", "RiskLimits", "RiskPolicyDecision",
    "SupabaseRestCandleRepository", "SupabaseRestResearchRepository",
    "TwelveDataForexProvider", "WalkForwardConfig", "WalkForwardResult",
    "assess_position_risk", "build_market_snapshot", "calibrate_risk_limits",
    "classify_market_state", "evaluate_portfolio_risk", "evaluate_snapshot_proposal",
    "ingest_candles", "make_ema_regime_strategy", "score_candle_batch",
    "walk_forward_evaluate",
]
