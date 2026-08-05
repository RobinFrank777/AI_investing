import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import universe_source


class UniverseSourceTests(unittest.TestCase):
    @patch("universe_source.universe_groups.load_combined_universe")
    @patch("universe_source.universe_manager.load_universe", return_value=["AAPL"])
    def test_default_mode_uses_single_universe(self, mock_single, mock_groups):
        with patch.object(universe_source.config, "UNIVERSE_MODE", "single"):
            self.assertEqual(universe_source.load_active_universe(), ["AAPL"])
        mock_single.assert_called_once_with()
        mock_groups.assert_not_called()

    @patch("universe_source.universe_groups.load_combined_universe")
    @patch("universe_source.universe_manager.load_universe", return_value=["AMD"])
    def test_explicit_mode_overrides_config(self, mock_single, mock_groups):
        with patch.object(universe_source.config, "UNIVERSE_MODE", "groups"):
            self.assertEqual(
                universe_source.load_active_universe(mode="single"), ["AMD"]
            )
        mock_single.assert_called_once_with()
        mock_groups.assert_not_called()

    def test_mode_is_case_and_whitespace_insensitive(self):
        with patch(
            "universe_source.universe_manager.load_universe", return_value=["AAPL"]
        ) as mock_single:
            universe_source.load_active_universe(mode=" SINGLE ")
            mock_single.assert_called_once_with()

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "groups.csv"
            config_path.touch()
            with patch(
                "universe_source.universe_groups.load_combined_universe",
                return_value=["AMD"],
            ) as mock_groups:
                universe_source.load_active_universe(
                    mode=" Groups ", groups_config_path=config_path
                )
                mock_groups.assert_called_once_with(config_path)

    def test_invalid_modes_raise_with_allowed_values(self):
        for mode in ("auto", "watchlist", "", "maybe", 123):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(
                    ValueError, "Unsupported universe mode.*single, groups"
                ):
                    universe_source.load_active_universe(mode=mode)

    @patch("universe_source.universe_groups.load_combined_universe")
    @patch(
        "universe_source.universe_manager.load_universe",
        return_value=["NVDA", "AAPL", "AMD"],
    )
    def test_single_calls_only_manager_once_and_preserves_order(
        self, mock_single, mock_groups
    ):
        result = universe_source.load_active_universe(mode="single")
        self.assertEqual(result, ["NVDA", "AAPL", "AMD"])
        mock_single.assert_called_once_with()
        mock_groups.assert_not_called()

    @patch("universe_source.universe_manager.load_universe", return_value=["AAPL"])
    def test_single_custom_path_is_forwarded(self, mock_single):
        path = Path("custom.csv")
        universe_source.load_active_universe(mode="single", watchlist_path=path)
        mock_single.assert_called_once_with(path)

    @patch("universe_source.universe_groups.load_combined_universe")
    @patch(
        "universe_source.universe_manager.load_universe",
        side_effect=FileNotFoundError("missing"),
    )
    def test_single_missing_file_does_not_fallback(self, _, mock_groups):
        with self.assertRaises(FileNotFoundError):
            universe_source.load_active_universe(mode="single")
        mock_groups.assert_not_called()

    @patch("universe_source.universe_groups.load_combined_universe")
    @patch(
        "universe_source.universe_manager.load_universe",
        side_effect=ValueError("invalid"),
    )
    def test_single_invalid_csv_does_not_fallback(self, _, mock_groups):
        with self.assertRaises(ValueError):
            universe_source.load_active_universe(mode="single")
        mock_groups.assert_not_called()

    @patch("universe_source.universe_manager.load_universe")
    def test_groups_calls_only_combiner_once_and_preserves_order(self, mock_single):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.csv"
            path.touch()
            with patch(
                "universe_source.universe_groups.load_combined_universe",
                return_value=["NVDA", "AMD", "AAPL"],
            ) as mock_groups:
                result = universe_source.load_active_universe(
                    mode="groups", groups_config_path=path
                )
        self.assertEqual(result, ["NVDA", "AMD", "AAPL"])
        mock_groups.assert_called_once_with(path)
        mock_single.assert_not_called()

    def test_groups_explicit_config_path_is_forwarded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.csv"
            path.touch()
            with patch(
                "universe_source.universe_groups.load_combined_universe",
                return_value=[],
            ) as mocked:
                universe_source.load_active_universe(
                    mode="groups", groups_config_path=path
                )
            mocked.assert_called_once_with(path)

    def test_groups_missing_default_config_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "universe_config.csv"
            with patch.object(universe_source.config, "UNIVERSE_CONFIG_PATH", path):
                with self.assertRaisesRegex(
                    FileNotFoundError,
                    "Groups mode requires a universe configuration file",
                ) as raised:
                    universe_source.load_active_universe(mode="groups")
        self.assertIn(str(path), str(raised.exception))

    @patch("universe_source.universe_manager.load_universe")
    def test_groups_invalid_config_does_not_fallback(self, mock_single):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.csv"
            path.touch()
            with patch(
                "universe_source.universe_groups.load_combined_universe",
                side_effect=ValueError("invalid groups"),
            ):
                with self.assertRaisesRegex(ValueError, "invalid groups"):
                    universe_source.load_active_universe(
                        mode="groups", groups_config_path=path
                    )
        mock_single.assert_not_called()

    @patch("universe_source.universe_manager.load_universe", return_value=[])
    def test_empty_single_universe_returns_empty(self, _):
        self.assertEqual(universe_source.load_active_universe(mode="single"), [])

    def test_empty_groups_universe_returns_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.csv"
            path.touch()
            with patch(
                "universe_source.universe_groups.load_combined_universe",
                return_value=[],
            ):
                self.assertEqual(
                    universe_source.load_active_universe(
                        mode="groups", groups_config_path=path
                    ),
                    [],
                )

    @patch("universe_source.universe_manager.validate_universe")
    def test_validate_single_returns_stable_summary(self, mock_validate):
        path = Path("watchlist.csv")
        mock_validate.return_value = {
            "source_path": path,
            "symbols": ["AAPL", "AMD"],
            "warnings": [],
        }
        summary = universe_source.validate_active_universe(mode="single")
        self.assertEqual(summary["mode"], "single")
        self.assertEqual(summary["source_path"], path)
        self.assertEqual(summary["symbol_count"], 2)
        self.assertEqual(summary["symbols"], ["AAPL", "AMD"])
        mock_validate.assert_called_once_with()

    def test_validate_groups_reports_symbol_and_group_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "groups.csv"
            path.touch()
            group_summary = {
                "source_path": path,
                "total_rows": 3,
                "enabled_groups": 2,
                "invalid_groups": 0,
                "invalid_entries": [],
                "warnings": [],
            }
            with patch(
                "universe_source.universe_groups.validate_universe_config",
                return_value=group_summary,
            ), patch(
                "universe_source.universe_groups.load_combined_universe",
                return_value=["AAPL", "AMD", "NVDA"],
            ):
                summary = universe_source.validate_active_universe(
                    mode="groups", groups_config_path=path
                )
        self.assertEqual(summary["symbol_count"], 3)
        self.assertEqual(summary["group_count"], 3)
        self.assertEqual(summary["enabled_group_count"], 2)

    @patch("universe_source.universe_manager.validate_universe")
    def test_empty_active_universe_adds_warning(self, mock_validate):
        mock_validate.return_value = {
            "source_path": Path("empty.csv"),
            "symbols": [],
            "warnings": [],
        }
        summary = universe_source.validate_active_universe(mode="single")
        self.assertIn(universe_source.EMPTY_UNIVERSE_WARNING, summary["warnings"])

    @patch(
        "universe_source.universe_manager.load_universe",
        return_value=["AAPL", "AMD"],
    )
    def test_repeated_load_is_deterministic(self, _):
        first = universe_source.load_active_universe(mode="single")
        second = universe_source.load_active_universe(mode="single")
        self.assertEqual(first, second)

    @patch("universe_source.validate_active_universe")
    def test_main_success_and_validation_error_exit_codes(self, mock_validate):
        mock_validate.return_value = {
            "mode": "single",
            "source_path": Path("watchlist.csv"),
            "symbol_count": 1,
            "symbols": ["AAPL"],
            "warnings": [],
        }
        self.assertEqual(universe_source.main([]), 0)
        mock_validate.side_effect = ValueError("bad mode")
        self.assertEqual(universe_source.main(["--mode", "auto"]), 1)


if __name__ == "__main__":
    unittest.main()
