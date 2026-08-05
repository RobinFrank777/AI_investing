import copy
import math
import unittest
from unittest import mock

import research_summary


def make_card(
    action="BUY",
    review_status="PASS",
    score=76.62,
    fundamental_rating="GOOD",
    portfolio_role="candidate",
    top_opportunity=True,
):
    return {
        "symbol": "GOOGL",
        "order_review": {"Action": action, "ReviewStatus": review_status},
        "combined_score": {
            "CombinedScore": score,
            "FundamentalRating": fundamental_rating,
        },
        "model_portfolio": {"PortfolioRole": portfolio_role},
        "top_opportunity": {"Ticker": "GOOGL"} if top_opportunity else None,
    }


class ResearchSummaryTests(unittest.TestCase):
    def build_with(self, card, symbol="GOOGL"):
        with mock.patch("research_summary.build_stock_card", return_value=card):
            return research_summary.build_research_summary(symbol)

    def test_buy_candidate(self):
        result = self.build_with(make_card())

        self.assertEqual(result["stance"], "BUY CANDIDATE")
        self.assertIn("Combined score is strong.", result["strengths"])
        self.assertIn("Fundamental rating is positive.", result["strengths"])
        self.assertIn("GOOGL", result["summary"])
        self.assertIs(result["manual_review_required"], True)

    def test_sell_overrides_high_score(self):
        result = self.build_with(make_card(action="SELL", score=90))
        self.assertEqual(result["stance"], "REDUCE / AVOID")

    def test_failed_review_means_reduce_or_avoid(self):
        result = self.build_with(make_card(review_status="FAIL"))
        self.assertEqual(result["stance"], "REDUCE / AVOID")

    def test_hold_action(self):
        result = self.build_with(make_card(action="HOLD"))
        self.assertEqual(result["stance"], "HOLD / REVIEW")

    def test_buy_with_score_below_threshold_requires_review(self):
        result = self.build_with(make_card(score=65))
        self.assertEqual(result["stance"], "HOLD / REVIEW")

    def test_no_data_is_insufficient(self):
        card = {name: None for name in research_summary._DATA_SECTIONS}
        result = self.build_with(card)
        self.assertEqual(result["stance"], "INSUFFICIENT DATA")

    def test_symbol_is_trimmed_and_uppercased(self):
        card = make_card()
        with mock.patch("research_summary.build_stock_card", return_value=card) as builder:
            result = research_summary.build_research_summary(" googl ")
        self.assertEqual(result["symbol"], "GOOGL")
        builder.assert_called_once_with("GOOGL")

    def test_empty_symbol_raises_value_error(self):
        with self.assertRaises(ValueError):
            research_summary.build_research_summary("   ")

    def test_nan_score_is_missing(self):
        result = self.build_with(make_card(score=math.nan))
        self.assertEqual(result["stance"], "HOLD / REVIEW")
        self.assertIn("Combined score data is unavailable.", result["risks"])

    def test_numeric_string_score_is_accepted(self):
        result = self.build_with(make_card(score="76.62"))
        self.assertEqual(result["stance"], "BUY CANDIDATE")

    def test_same_input_produces_same_dictionary(self):
        card = make_card()
        with mock.patch(
            "research_summary.build_stock_card",
            side_effect=[copy.deepcopy(card), copy.deepcopy(card)],
        ):
            first = research_summary.build_research_summary("GOOGL")
            second = research_summary.build_research_summary("GOOGL")
        self.assertEqual(first, second)

    def test_summary_avoids_prohibited_claims(self):
        summary = self.build_with(make_card())["summary"].lower()
        for phrase in ("guaranteed", "risk-free", "must buy", "certain profit"):
            self.assertNotIn(phrase, summary)

    def test_missing_sections_are_reported_as_risks(self):
        card = make_card(top_opportunity=False)
        card["combined_score"] = None
        card["order_review"] = None
        card["model_portfolio"] = None
        result = self.build_with(card)
        self.assertIn("Combined score data is unavailable.", result["risks"])
        self.assertIn("Order review data is unavailable.", result["risks"])
        self.assertIn(
            "The stock is not included in the current Top Opportunities list.",
            result["risks"],
        )
        self.assertIn(
            "The stock is not included in the current model portfolio output.",
            result["risks"],
        )

    def test_summary_stays_within_approximately_120_words(self):
        result = self.build_with(make_card(score=55, review_status="FAIL"))
        self.assertLessEqual(len(result["summary"].split()), 120)


if __name__ == "__main__":
    unittest.main()
