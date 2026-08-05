import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import report_terminal


class ReportTerminalTests(unittest.TestCase):
    def test_terminal_report_contains_sections_and_stock_card_link(self):
        report_data = [
            ("Top Opportunities", pd.DataFrame([{"Ticker": "NVDA", "Score": 90}])),
            ("Model Portfolio", pd.DataFrame([{"Ticker": "NVDA"}])),
            ("Order Review", pd.DataFrame([{"Ticker": "NVDA"}])),
            ("Combined Score", pd.DataFrame([{"Ticker": "NVDA"}])),
        ]

        with tempfile.TemporaryDirectory() as temp_directory:
            output_path = Path(temp_directory) / "ai_terminal_report.html"
            with (
                mock.patch.object(report_terminal, "OUTPUT_PATH", output_path),
                mock.patch.object(
                    report_terminal,
                    "load_report_data",
                    return_value=report_data,
                ),
            ):
                generated_path = report_terminal.generate_terminal_report()

            self.assertEqual(generated_path, output_path)
            self.assertTrue(output_path.exists())
            html = output_path.read_text(encoding="utf-8")

        self.assertIn("AI_investing Daily Research Terminal", html)
        self.assertIn("Top Opportunities", html)
        self.assertIn("Model Portfolio", html)
        self.assertIn("Order Review", html)
        self.assertIn("Research Card", html)
        self.assertIn('href="cards/NVDA.html"', html)


if __name__ == "__main__":
    unittest.main()
