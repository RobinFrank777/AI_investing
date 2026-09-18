import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from observation_workbook import (
    CANDIDATE_TRACKING_HEADERS,
    CANDIDATE_TRACKING_HEADER_ROW,
    CANDIDATE_TRACKING_SHEET,
    append_candidate_tracking,
)


class CandidateTrackingRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.path = Path(self.tempdir.name) / "observation.xlsx"

        wb = Workbook()
        ws = wb.active
        ws.title = CANDIDATE_TRACKING_SHEET

        for col, header in enumerate(CANDIDATE_TRACKING_HEADERS, start=1):
            ws.cell(
                row=CANDIDATE_TRACKING_HEADER_ROW,
                column=col,
                value=header,
            )

        wb.save(self.path)
        wb.close()

    def test_net_price_survives_excel_roundtrip_verification(self):
        row = append_candidate_tracking(
            file_path=self.path,
            date=datetime(2026, 9, 18),
            ticker="NET",
            signal="WATCH",
            rank=2,
            final_score=65.8259862485943,
            fundamental_score="MISSING",
            combined_score="MISSING",
            price=333.94000244140625,
            why_tracked=(
                "Price above MA20 | Bullish MA alignment | Weak volume | "
                "Near 52-week high | RSI not overbought"
            ),
            research_note=None,
            day_30=None,
            day_60=None,
            day_90=None,
            outcome="OPEN",
        )

        self.assertEqual(row, 5)


if __name__ == "__main__":
    unittest.main()