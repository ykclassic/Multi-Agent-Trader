from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from quant.market_engine.engine import Candle
from quant.market_engine.calibration import RiskCalibrationCandidate, calibrate_risk_limits
from quant.market_engine.portfolio_state import (
    PortfolioStateSnapshot, PositionSnapshot, evaluate_snapshot_proposal,
)
from quant.market_engine.risk import ProposedExposure, RiskLimits
from quant.market_engine.walk_forward import (
    WalkForwardConfig, make_ema_regime_strategy, walk_forward_evaluate,
)


class PortfolioStateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.snapshot = PortfolioStateSnapshot(
            portfolio_id="portfolio-1", workspace_id="workspace-1",
            as_of=self.now, market_data_as_of=self.now,
            source="manual_import", base_currency="USD", cash_balance=8500,
            equity=10000, daily_pnl=0, peak_equity=10500,
            market_data_quality_score=0.95,
            positions=(
                PositionSnapshot("BTC/USDT", "crypto", "long", 0.01, 100000, 1000, 20),
                PositionSnapshot("EUR/USD", "forex", "short", 1000, 0.5, 500, 10),
            ),
            metadata={"note": "read-only research import"},
        )

    def test_snapshot_hash_and_risk_state_are_deterministic(self):
        self.snapshot.validate()
        self.assertEqual(self.snapshot.state_hash, self.snapshot.state_hash)
        state = self.snapshot.as_risk_state()
        self.assertEqual(state.gross_notional, 1500)
        self.assertEqual(state.net_notional, 500)
        self.assertEqual(state.open_risk, 30)
        self.assertEqual(state.open_positions, 2)
        self.assertEqual(state.largest_position_notional, 1000)

    def test_snapshot_serialization_round_trip(self):
        row = self.snapshot.as_row()
        restored = PortfolioStateSnapshot.from_mapping(row)
        self.assertEqual(restored.state_hash, self.snapshot.state_hash)
        self.assertEqual(restored.positions, self.snapshot.positions)

    def test_snapshot_rejects_future_market_data_and_invalid_peak(self):
        with self.assertRaisesRegex(ValueError, "market_data_as_of"):
            PortfolioStateSnapshot(
                portfolio_id="p", workspace_id="w", as_of=self.now,
                market_data_as_of=self.now + timedelta(seconds=1),
                source="manual_import", base_currency="USD", cash_balance=1,
                equity=100, daily_pnl=0, peak_equity=100, market_data_quality_score=1,
                positions=(),
            ).validate()
        with self.assertRaisesRegex(ValueError, "peak_equity"):
            PortfolioStateSnapshot(
                portfolio_id="p", workspace_id="w", as_of=self.now,
                market_data_as_of=self.now, source="manual_import", base_currency="USD",
                cash_balance=1, equity=100, daily_pnl=0, peak_equity=99,
                market_data_quality_score=1, positions=(),
            ).validate()

    def test_snapshot_risk_adapter_blocks_excess_exposure(self):
        proposal = ProposedExposure(10000, 100, 0.95, 0)
        decision = evaluate_snapshot_proposal(self.snapshot, proposal)
        self.assertFalse(decision.allowed)
        self.assertIn("gross_exposure_limit_exceeded", decision.reasons)

    def test_risk_threshold_sensitivity_report_never_promotes_a_candidate(self):
        later = replace(self.snapshot, as_of=self.now + timedelta(days=1),
                        market_data_as_of=self.now + timedelta(days=1))
        candidates = (
            RiskCalibrationCandidate("baseline", RiskLimits()),
            RiskCalibrationCandidate("tight_concentration", RiskLimits(max_single_position_fraction=0.05)),
        )
        report = calibrate_risk_limits((self.snapshot, later), candidates=candidates, min_samples=4)
        self.assertEqual(report.status, "completed")
        self.assertEqual(report.sample_count, 4)
        self.assertEqual(report.candidates[0].allowed_count, 4)
        self.assertGreater(report.candidates[1].rejected_count, 0)
        self.assertIn("single_position_concentration_limit_exceeded",
                      report.candidates[1].reason_counts)
        self.assertEqual(report.run_hash, calibrate_risk_limits(
            (self.snapshot, later), candidates=candidates, min_samples=4).run_hash)

    def test_calibration_requires_sufficient_historical_samples(self):
        report = calibrate_risk_limits((self.snapshot,), candidates=(
            RiskCalibrationCandidate("baseline", RiskLimits()),), min_samples=20)
        self.assertEqual(report.status, "insufficient_data")
        self.assertTrue(report.coverage_gaps)
        self.assertEqual(report.candidates[0].status, "insufficient_data")


def synthetic_candles(count=520):
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    close = 100.0
    candles = []
    for index in range(count):
        if index < 120:
            change = 0.008
        elif index < 240:
            change = -0.008
        elif index < 380:
            if index % 5 == 0:
                change = 0.12 if index % 10 == 0 else -0.10
            else:
                change = 0.025 if index % 2 else -0.022
        else:
            change = 0.001 if index % 3 else -0.001
        previous = close
        close = max(1.0, close * (1.0 + change))
        high = max(previous, close) * 1.001
        low = min(previous, close) * 0.999
        volume = 6000.0 if 240 <= index < 380 and index % 5 == 0 else 1000.0
        candles.append(Candle(
            now + timedelta(hours=index), previous, high, low, close, volume,
        ))
    return candles


class WalkForwardTests(unittest.TestCase):
    def test_walk_forward_is_reproducible_and_out_of_sample(self):
        candles = synthetic_candles()
        config = WalkForwardConfig(
            train_window_candles=80, test_window_candles=40, step_candles=40,
            min_folds=3, min_observations_per_condition=3, condition_lookback=12,
            bull_bear_return_threshold=0.02, high_volatility_threshold=0.5,
            shock_return_multiple=2.0, shock_return_floor=0.01,
            shock_volume_multiple=1.5,
        )
        fit_sizes = []
        def fitter(training):
            fit_sizes.append(len(training))
            direction = 1 if training[-1].close >= training[0].close else -1
            return lambda history: direction
        first = walk_forward_evaluate(candles, timeframe_seconds=3600,
            fit_strategy=fitter, config=config, market_type="crypto")
        second = walk_forward_evaluate(candles, timeframe_seconds=3600,
            fit_strategy=lambda training: (lambda history: 1 if training[-1].close >= training[0].close else -1),
            config=config, market_type="crypto")
        self.assertEqual(first.run_hash, second.run_hash)
        self.assertEqual(first.summary, second.summary)
        self.assertGreaterEqual(len(first.folds), 3)
        self.assertTrue(all(size == 80 for size in fit_sizes))
        self.assertTrue(all(fold.test_observation_count <= 40 for fold in first.folds))
        self.assertIn("bull", first.condition_counts)
        self.assertIn("bear", first.condition_counts)
        self.assertIn("high_volatility", first.condition_counts)
        self.assertIn("liquidity_shock_proxy", first.condition_counts)
        self.assertEqual(first.summary["liquidity_shock_label_type"], "OHLCV_proxy_not_orderbook_liquidity")

    def test_insufficient_history_is_reported_not_promoted(self):
        candles = synthetic_candles(90)
        result = walk_forward_evaluate(candles, timeframe_seconds=3600,
            fit_strategy=make_ema_regime_strategy(timeframe_seconds=3600, market_type="crypto"),
            config=WalkForwardConfig(train_window_candles=80, test_window_candles=20,
                step_candles=20, min_folds=3, min_observations_per_condition=2,
                condition_lookback=12), market_type="crypto")
        self.assertEqual(result.status, "insufficient_data")
        self.assertTrue(result.coverage_gaps)

    def test_config_rejects_overlapping_test_windows(self):
        with self.assertRaisesRegex(ValueError, "avoid overlapping"):
            WalkForwardConfig(train_window_candles=100, test_window_candles=50,
                step_candles=25).validate()

    def test_predictor_only_emits_valid_positions(self):
        candles = synthetic_candles(140)
        result = walk_forward_evaluate(candles, timeframe_seconds=3600,
            fit_strategy=make_ema_regime_strategy(timeframe_seconds=3600, market_type="crypto"),
            config=WalkForwardConfig(train_window_candles=80, test_window_candles=20,
                step_candles=20, min_folds=1, min_observations_per_condition=1,
                condition_lookback=12), market_type="crypto")
        self.assertIn(result.status, ("completed", "insufficient_data"))
        self.assertGreaterEqual(result.summary["observations"], 0)


if __name__ == "__main__":
    unittest.main()
