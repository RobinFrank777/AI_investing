import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import validate_position_sizing_outputs as subject


class PositionSizingValidatorTests(unittest.TestCase):
    def test_header_only_no_action_output_is_valid(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "sizing.csv"
            pd.DataFrame(columns=subject.REQUIRED_COLUMNS).to_csv(output, index=False)
            with patch.object(subject, "POSITION_SIZING_OUTPUT", output):
                subject.validate_position_sizing_outputs()

    def test_header_only_output_still_requires_schema(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "sizing.csv"
            pd.DataFrame(columns=["Ticker"]).to_csv(output, index=False)
            with (
                patch.object(subject, "POSITION_SIZING_OUTPUT", output),
                self.assertRaisesRegex(RuntimeError, "validation failed"),
            ):
                subject.validate_position_sizing_outputs()


if __name__ == "__main__":
    unittest.main()
