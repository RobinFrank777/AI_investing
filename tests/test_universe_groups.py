import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import pandas as pd

import universe_groups


class UniverseGroupsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.root_patch = patch("universe_groups.PROJECT_ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def write_config(self, rows, columns=None):
        path = self.root / "config.csv"
        pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
        return path

    def write_universe(self, relative_path, tickers, column="Ticker"):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({column: tickers}).to_csv(path, index=False)
        return path

    def test_loads_normal_config_in_order(self):
        config = self.write_config(
            [
                {"Universe": "ai", "Enabled": "yes", "File": "data/ai.csv"},
                {"Universe": "space", "Enabled": "no", "File": "data/space.csv"},
            ]
        )
        groups = universe_groups.load_universe_config(config)
        self.assertEqual([group["name"] for group in groups], ["ai", "space"])
        self.assertEqual(groups[0]["file_path"], (self.root / "data/ai.csv").resolve())

    def test_normalizes_universe_names(self):
        config = self.write_config(
            [
                {"Universe": "AI", "Enabled": "no", "File": "data/ai.csv"},
                {"Universe": " Semiconductor ", "Enabled": "no", "File": "data/semi.csv"},
            ]
        )
        self.assertEqual(
            [group["name"] for group in universe_groups.load_universe_config(config)],
            ["ai", "semiconductor"],
        )

    def test_parses_all_enabled_values_and_warns_for_unknown(self):
        values = ["yes", "no", True, False, 1, 0, "active", "inactive", "maybe"]
        rows = [
            {"Universe": f"g{index}", "Enabled": value, "File": f"data/g{index}.csv"}
            for index, value in enumerate(values)
        ]
        config = self.write_config(rows)
        with patch("universe_groups.load_universe", return_value=[]):
            summary = universe_groups.validate_universe_config(config)
        self.assertEqual(
            [group["enabled"] for group in summary["groups"]],
            [True, False, True, False, True, False, True, False, False],
        )
        self.assertTrue(any("unrecognized" in item for item in summary["warnings"]))

    def test_rejects_each_missing_required_column(self):
        for missing in universe_groups.REQUIRED_COLUMNS:
            with self.subTest(missing=missing):
                columns = [column for column in universe_groups.REQUIRED_COLUMNS if column != missing]
                config = self.write_config([], columns=columns)
                with self.assertRaisesRegex(ValueError, missing):
                    universe_groups.load_universe_config(config)

    def test_duplicate_normalized_name_is_invalid(self):
        config = self.write_config(
            [
                {"Universe": "AI", "Enabled": "no", "File": "data/a.csv"},
                {"Universe": "ai", "Enabled": "no", "File": "data/b.csv"},
            ]
        )
        summary = universe_groups.validate_universe_config(config)
        self.assertEqual(summary["duplicates"], ["ai"])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            universe_groups.load_universe_config(config)

    def test_invalid_universe_names_are_reported(self):
        config = self.write_config(
            [
                {"Universe": "AI Stocks", "Enabled": "no", "File": "data/a.csv"},
                {"Universe": "<script>", "Enabled": "no", "File": "data/b.csv"},
                {"Universe": "中国", "Enabled": "no", "File": "data/c.csv"},
            ]
        )
        summary = universe_groups.validate_universe_config(config)
        self.assertEqual(summary["invalid_groups"], 3)

    def test_rejects_unsafe_paths(self):
        unsafe = [
            "/absolute/path.csv",
            "../../outside.csv",
            "data/../outside.csv",
            "https://example.com/file.csv",
            "file://outside.csv",
            "data/group.txt",
        ]
        for index, file_path in enumerate(unsafe):
            with self.subTest(file_path=file_path):
                config = self.write_config(
                    [{"Universe": f"g{index}", "Enabled": "no", "File": file_path}]
                )
                with self.assertRaises(ValueError):
                    universe_groups.load_universe_config(config)

    def test_missing_disabled_group_file_is_valid(self):
        config = self.write_config(
            [{"Universe": "ai", "Enabled": "no", "File": "data/missing.csv"}]
        )
        summary = universe_groups.validate_universe_config(config)
        self.assertEqual(summary["invalid_groups"], 0)

    def test_missing_enabled_group_file_is_invalid_and_load_raises(self):
        config = self.write_config(
            [{"Universe": "ai", "Enabled": "yes", "File": "data/missing.csv"}]
        )
        summary = universe_groups.validate_universe_config(config)
        self.assertEqual(summary["invalid_groups"], 1)
        with self.assertRaisesRegex(FileNotFoundError, "ai"):
            universe_groups.load_combined_universe(config)

    def test_combines_two_groups_and_deduplicates_in_order(self):
        self.write_universe("data/a.csv", ["AAPL", "NVDA", "AMD"])
        self.write_universe("data/b.csv", ["NVDA", "GOOGL"])
        config = self.write_config(
            [
                {"Universe": "a", "Enabled": "yes", "File": "data/a.csv"},
                {"Universe": "b", "Enabled": "yes", "File": "data/b.csv"},
            ]
        )
        self.assertEqual(
            universe_groups.load_combined_universe(config),
            ["AAPL", "NVDA", "AMD", "GOOGL"],
        )

    def test_combined_order_follows_config_order(self):
        self.write_universe("data/a.csv", ["AAPL"])
        self.write_universe("data/b.csv", ["NVDA"])
        config = self.write_config(
            [
                {"Universe": "b", "Enabled": "yes", "File": "data/b.csv"},
                {"Universe": "a", "Enabled": "yes", "File": "data/a.csv"},
            ]
        )
        self.assertEqual(universe_groups.load_combined_universe(config), ["NVDA", "AAPL"])

    def test_calls_manager_once_for_each_enabled_group_only(self):
        config = self.write_config(
            [
                {"Universe": "a", "Enabled": "yes", "File": "data/a.csv"},
                {"Universe": "off", "Enabled": "no", "File": "data/off.csv"},
                {"Universe": "b", "Enabled": "yes", "File": "data/b.csv"},
            ]
        )
        with patch("universe_groups.load_universe", side_effect=[["AAPL"], ["AMD"]]) as mocked:
            self.assertEqual(universe_groups.load_combined_universe(config), ["AAPL", "AMD"])
        self.assertEqual(
            mocked.call_args_list,
            [
                call((self.root / "data/a.csv").resolve()),
                call((self.root / "data/b.csv").resolve()),
            ],
        )

    def test_no_enabled_groups_returns_empty_list_and_validation_warning(self):
        config = self.write_config(
            [{"Universe": "off", "Enabled": "no", "File": "data/off.csv"}]
        )
        self.assertEqual(universe_groups.load_combined_universe(config), [])
        self.assertTrue(universe_groups.validate_universe_config(config)["warnings"])

    def test_enabled_group_without_ticker_column_is_not_silently_ignored(self):
        self.write_universe("data/bad.csv", ["AAPL"], column="Symbol")
        config = self.write_config(
            [{"Universe": "bad", "Enabled": "yes", "File": "data/bad.csv"}]
        )
        with self.assertRaisesRegex(ValueError, "bad"):
            universe_groups.load_combined_universe(config)

    def test_empty_enabled_group_can_merge_with_valid_group(self):
        self.write_universe("data/empty.csv", [])
        self.write_universe("data/valid.csv", ["AMD"])
        config = self.write_config(
            [
                {"Universe": "empty", "Enabled": "yes", "File": "data/empty.csv"},
                {"Universe": "valid", "Enabled": "yes", "File": "data/valid.csv"},
            ]
        )
        self.assertEqual(universe_groups.load_combined_universe(config), ["AMD"])

    def test_repeated_load_is_deterministic(self):
        self.write_universe("data/a.csv", ["AAPL", "AMD", "AAPL"])
        config = self.write_config(
            [{"Universe": "a", "Enabled": "yes", "File": "data/a.csv"}]
        )
        self.assertEqual(
            universe_groups.load_combined_universe(config),
            universe_groups.load_combined_universe(config),
        )

    def test_missing_config_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            universe_groups.load_universe_config(self.root / "missing.csv")


if __name__ == "__main__":
    unittest.main()
