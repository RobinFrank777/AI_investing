import tempfile
import unittest
from pathlib import Path
from unittest import mock

import stock_card_builder


class StockCardBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.results_dir = Path(self.temp_directory.name) / "results"
        self.results_dir.mkdir()

        self.sources = {
            "top_opportunity": self.results_dir / "top10.csv",
            "model_portfolio": self.results_dir / "model_portfolio.csv",
            "order_review": self.results_dir / "order_review.csv",
            "combined_score": self.results_dir / "combined_score.csv",
        }

        self.sources["top_opportunity"].write_text(
            "Ticker,TradeSignal,FinalScore\nGOOGL,BUY,82.5\n",
            encoding="utf-8",
        )
        self.sources["model_portfolio"].write_text(
            "Ticker,BacktestScore,PortfolioRole\nGOOGL,77.9,candidate\n",
            encoding="utf-8",
        )
        self.sources["order_review"].write_text(
            "Ticker,Action,ReviewStatus\nGOOGL,BUY,PASS\n",
            encoding="utf-8",
        )
        self.sources["combined_score"].write_text(
            "Ticker,CombinedScore,FundamentalRating\nGOOGL,76.62,GOOD\n",
            encoding="utf-8",
        )

        self.sources_patch = mock.patch.object(
            stock_card_builder,
            "CARD_SOURCES",
            self.sources,
        )
        self.sources_patch.start()

    def tearDown(self):
        self.sources_patch.stop()
        self.temp_directory.cleanup()

    def test_normal_symbol_matches_available_sources(self):
        card = stock_card_builder.build_stock_card("GOOGL")

        self.assertIsInstance(card, dict)
        self.assertEqual(card["symbol"], "GOOGL")
        self.assertEqual(card["model_portfolio"]["BacktestScore"], 77.9)
        self.assertEqual(card["model_portfolio"]["PortfolioRole"], "candidate")
        self.assertEqual(card["order_review"]["Action"], "BUY")
        self.assertEqual(card["order_review"]["ReviewStatus"], "PASS")
        self.assertEqual(card["combined_score"]["CombinedScore"], 76.62)
        self.assertEqual(
            card["combined_score"]["FundamentalRating"],
            "GOOD",
        )

    def test_symbol_missing_from_one_source_returns_none_for_that_source(self):
        self.sources["top_opportunity"].write_text(
            "Ticker,TradeSignal,FinalScore\nAAPL,BUY,80.0\n",
            encoding="utf-8",
        )

        card = stock_card_builder.build_stock_card("GOOGL")

        self.assertIsNone(card["top_opportunity"])
        self.assertIsNotNone(card["model_portfolio"])
        self.assertIsNotNone(card["order_review"])
        self.assertIsNotNone(card["combined_score"])

    def test_unknown_symbol_returns_none_for_all_data_sources(self):
        card = stock_card_builder.build_stock_card("MSFT")

        self.assertEqual(card["symbol"], "MSFT")
        for source_name in self.sources:
            self.assertIsNone(card[source_name])

    def test_missing_csv_returns_none_without_raising(self):
        missing_path = self.results_dir / "missing_order_review.csv"
        self.sources["order_review"] = missing_path

        card = stock_card_builder.build_stock_card("GOOGL")

        self.assertIsNone(card["order_review"])
        self.assertIsNotNone(card["model_portfolio"])

    def test_csv_without_ticker_column_returns_none_without_raising(self):
        self.sources["combined_score"].write_text(
            "Symbol,CombinedScore\nGOOGL,76.62\n",
            encoding="utf-8",
        )

        card = stock_card_builder.build_stock_card("GOOGL")

        self.assertIsNone(card["combined_score"])
        self.assertIsNotNone(card["model_portfolio"])

    def test_lowercase_symbol_is_normalized_and_matched(self):
        card = stock_card_builder.build_stock_card("googl")

        self.assertEqual(card["symbol"], "GOOGL")
        self.assertEqual(card["model_portfolio"]["Ticker"], "GOOGL")
        self.assertEqual(card["order_review"]["Ticker"], "GOOGL")
        self.assertEqual(card["combined_score"]["Ticker"], "GOOGL")


if __name__ == "__main__":
    unittest.main()
