from datetime import datetime, timedelta, timezone
import unittest
from quant.market_engine import Candle
from quant.market_engine.market_state import classify_market_state
from quant.market_engine.risk import PortfolioRiskState, ProposedExposure, RiskLimits, evaluate_portfolio_risk

class MarketStateAndRiskTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.candles = []
        for index in range(40):
            close = 100.0 + index * 0.2
            self.candles.append(Candle(self.now - timedelta(hours=39-index),
                close-0.1, close+0.3, close-0.3, close, 1000.0))
        self.portfolio = PortfolioRiskState(10_000, 0, 10_000, 2_000, 1_000, 50, 1, 2_000)
        self.proposed = ProposedExposure(1_000, 40, 0.95, 60)

    def test_market_state_ready_and_deterministic(self):
        args = dict(source="test", as_of=self.now, timeframe_seconds=3600, max_age_seconds=7200)
        result = classify_market_state(self.candles, **args)
        self.assertEqual(result, classify_market_state(self.candles, **args))
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.trend, "trend_up")
        self.assertIn("rsi_14:", result.evidence[1])

    def test_stale_market_state_fails_closed(self):
        result = classify_market_state(self.candles, source="test",
            as_of=self.now + timedelta(days=1), timeframe_seconds=3600, max_age_seconds=7200)
        self.assertEqual(result.status, "blocked")
        self.assertIn("stale_market_data", result.reasons)
        self.assertIsNone(result.snapshot)

    def test_insufficient_history_blocks_state(self):
        result = classify_market_state(self.candles[:10], source="test", as_of=self.now,
            timeframe_seconds=3600, max_age_seconds=7200)
        self.assertEqual(result.status, "blocked")
        self.assertIn("insufficient_candles:minimum_27", result.reasons)

    def test_risk_policy_allows_within_limits(self):
        result = evaluate_portfolio_risk(self.portfolio, self.proposed)
        self.assertTrue(result.allowed)
        self.assertEqual(result.reasons, ())
        self.assertAlmostEqual(result.projected_gross_exposure_fraction, 0.3)
        self.assertAlmostEqual(result.projected_open_risk_fraction, 0.009)

    def test_stale_or_low_quality_data_blocks_risk(self):
        result = evaluate_portfolio_risk(self.portfolio, ProposedExposure(1000, 40, 0.95, 601))
        self.assertFalse(result.allowed)
        self.assertIn("market_data_stale_or_future_dated", result.reasons)
        result = evaluate_portfolio_risk(self.portfolio, ProposedExposure(1000, 40, 0.2, 60))
        self.assertIn("market_data_quality_below_minimum", result.reasons)

    def test_daily_loss_drawdown_and_exposure_limits_block(self):
        portfolio = PortfolioRiskState(8_000, -250, 10_000, 8_000, 7_000, 200, 5, 3_000)
        result = evaluate_portfolio_risk(portfolio, self.proposed)
        self.assertFalse(result.allowed)
        for reason in ("daily_loss_limit_reached", "drawdown_limit_reached",
            "gross_exposure_limit_exceeded", "net_exposure_limit_exceeded",
            "maximum_open_positions_reached"):
            self.assertIn(reason, result.reasons)

    def test_non_finite_and_negative_inputs_fail_closed(self):
        result = evaluate_portfolio_risk(self.portfolio, ProposedExposure(float("nan"), 40, 0.95, 60))
        self.assertFalse(result.allowed)
        self.assertIn("non_finite_risk_input", result.reasons)
        result = evaluate_portfolio_risk(self.portfolio, ProposedExposure(-1, 40, 0.95, 60))
        self.assertFalse(result.allowed)
        self.assertIn("negative_exposure_or_risk", result.reasons)

    def test_limits_reject_invalid_configuration(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            RiskLimits(max_gross_exposure_fraction=1.2).validate()

    def test_invalid_signed_exposure_and_quality_score_fail_closed(self):
        result = evaluate_portfolio_risk(self.portfolio, self.proposed, signed_notional=float("nan"))
        self.assertFalse(result.allowed)
        self.assertIn("non_finite_risk_input", result.reasons)
        result = evaluate_portfolio_risk(self.portfolio, ProposedExposure(1000, 40, 1.5, 60))
        self.assertFalse(result.allowed)
        self.assertIn("invalid_market_data_quality_score", result.reasons)
        result = evaluate_portfolio_risk(self.portfolio, self.proposed, signed_notional=2000)
        self.assertIn("signed_notional_exceeds_proposed_notional", result.reasons)

if __name__ == "__main__":
    unittest.main()
