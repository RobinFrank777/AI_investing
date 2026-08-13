import unittest
from unittest.mock import patch

import universe_source
import universe_manager
import watchlist


class PrimaryUniverseContractTests(unittest.TestCase):
    def test_production_consumers_share_primary_loader(self):
        expected = ["NVDA", "AAPL"]
        with patch.object(universe_manager, "load_universe", return_value=expected):
            self.assertEqual(universe_source.load_active_universe(), expected)
        with patch.object(watchlist, "get_primary_tickers", return_value=expected):
            self.assertEqual(watchlist.load_watchlist(), expected)

    def test_update_consumer_uses_unified_universe(self):
        import update_data
        with patch("update_data.load_active_universe", return_value=["A", "B"]) as loader, patch(
            "update_data.update_one_stock", return_value={"status": "success"}
        ):
            result = update_data.update_all_stocks()
        loader.assert_called_once_with()
        self.assertEqual(result["total"], 2)


if __name__ == "__main__":
    unittest.main()
