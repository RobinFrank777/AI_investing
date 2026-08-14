import unittest
from pathlib import Path

import pandas as pd

import order_draft
import order_review
import portfolio_action_report
import portfolio_risk
import position_sizing
import report_artifact_consistency as reports
from current_run_status import load_current_run_status
from market_session import latest_completed_session_date
from portfolio_candidate_adapter import (
    build_validated_portfolio_candidates, load_production_candidates,
)
from portfolio_risk_calculator import (
    NO_PORTFOLIO_ELIGIBLE_CANDIDATES, calculate_portfolio_risk_inputs,
)


class NoActionRegressionTests(unittest.TestCase):
    def current_no_action_chain(self):
        candidate = load_production_candidates()
        validated = build_validated_portfolio_candidates(candidate)
        risk = calculate_portfolio_risk_inputs(
            validated, calculation_timestamp="2026-08-14T00:00:00+00:00"
        )
        portfolio = portfolio_risk.build_model_portfolio(risk)
        enriched = portfolio.copy()
        enriched["FundamentalScore"] = pd.Series(dtype="float64")
        enriched["CombinedScore"] = pd.Series(dtype="float64")
        enriched["FundamentalRating"] = pd.Series(dtype="object")
        sizing = position_sizing.add_share_sizing(
            position_sizing.add_target_dollar_amount(enriched, 100_000)
        )
        draft = order_draft.build_order_draft(sizing)
        review = order_review.build_order_review(draft)
        return candidate, risk, portfolio, sizing, draft, review

    def test_current_zero_eligible_chain_is_stable_no_action(self):
        candidate, risk, portfolio, sizing, draft, review = self.current_no_action_chain()
        self.assertEqual(int((candidate.TradeSignal == "BUY").sum()), 0)
        self.assertEqual(risk.attrs["RiskBuildStatus"], NO_PORTFOLIO_ELIGIBLE_CANDIDATES)
        self.assertTrue(risk.empty)
        self.assertEqual(portfolio.attrs["PortfolioStatus"], portfolio_risk.NO_QUALIFIED_CANDIDATES)
        self.assertTrue(sizing.empty)
        self.assertEqual(draft.attrs["OrderDraftStatus"], order_draft.NO_DRAFT_ORDERS)
        self.assertEqual(review.attrs["ReviewStatus"], order_review.NO_ORDERS_TO_REVIEW)
        self.assertEqual(review.attrs["PortfolioReviewFlag"], "NOT_APPLICABLE")

    def test_current_no_action_is_deterministic(self):
        first = self.current_no_action_chain()
        second = self.current_no_action_chain()
        for left, right in zip(first, second):
            pd.testing.assert_frame_equal(left.reset_index(drop=True), right.reset_index(drop=True))

    def test_current_authority_and_reports_are_truthful(self):
        context = load_current_run_status()
        candidate = load_production_candidates()
        assessment = reports.assess_current_report()
        if context["OverallRunStatus"] == "PASS":
            self.assertEqual(context["CurrentRunId"], candidate.RunId.iloc[0])
            self.assertEqual(context["AsOfDate"], candidate.AsOfDate.iloc[0])
            self.assertEqual(candidate.AsOfDate.iloc[0], latest_completed_session_date().isoformat())
            self.assertEqual(assessment.status, reports.NO_ACTION)
            text = portfolio_action_report.build_action_report_text(
                pd.read_csv("results/order_review.csv"), assessment
            )
            self.assertIn("Report Status          : NO_ACTION", text)
            self.assertIn("Portfolio Decision     : NO_ACTION", text)
        else:
            self.assertEqual(context["OverallRunStatus"], "FAILED")
            self.assertEqual(assessment.status, reports.FAILED)
            self.assertEqual(assessment.metadata["RunId"], context["CurrentRunId"])
            self.assertIn(context["FailedStage"], " ".join(assessment.reasons))

    def test_production_path_has_no_legacy_or_broker_fallback(self):
        sources = "\n".join(
            Path(module.__file__).read_text(encoding="utf-8")
            for module in (portfolio_risk, position_sizing, order_draft, order_review)
        )
        self.assertNotIn("backtest_qualified_20d.csv", sources)
        self.assertNotIn("BACKTEST_QUALIFIED_20D_OUTPUT_PATH", sources)
        self.assertNotIn("broker", sources.lower())


if __name__ == "__main__":
    unittest.main()
