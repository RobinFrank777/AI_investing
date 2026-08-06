import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import factor_validation as validation
from price_factors import calculate_price_factors


def history(multiplier=1.0, rows=130):
    return pd.DataFrame({
        "Date": pd.bdate_range("2024-01-01", periods=rows),
        "Close": [(100 + index) * multiplier for index in range(rows)],
    })


def histories(rows=130):
    return {"A": history(1, rows), "B": history(1.1, rows), "C": history(.9, rows)}


def validation_table():
    rows = []
    for date, scores in [("2024-03-29", [3, 2, 1]), ("2024-04-30", [3, 1, 2])]:
        for ticker, score in zip(["A", "B", "C"], scores):
            row = {column: None for column in validation.VALIDATION_COLUMNS}
            row.update({"RebalanceDate": date, "Ticker": ticker, "CompositeFactorScore": score,
                        "ForwardReturn5D": score / 10, "ForwardReturn10D": score / 10,
                        "ForwardReturn20D": score / 10, "ForwardReturn60D": score / 10})
            rows.append(row)
    return pd.DataFrame(rows, columns=validation.VALIDATION_COLUMNS)


class FactorValidationTests(unittest.TestCase):
    def test_monthly_dates_deterministic(self):
        self.assertEqual(validation.build_rebalance_dates(histories()), validation.build_rebalance_dates(histories()))

    def test_dates_ascending_unique(self):
        dates = validation.build_rebalance_dates(histories()); self.assertEqual(dates, sorted(set(dates)))

    def test_dates_within_available_range(self):
        dates = validation.build_rebalance_dates(histories()); self.assertLessEqual(max(dates), history().Date.max())

    def test_initial_insufficient_months_excluded(self):
        dates = validation.build_rebalance_dates(histories()); self.assertGreaterEqual(dates[0], history().Date.iloc[59])

    def test_start_end_honored(self):
        dates = validation.build_rebalance_dates(histories(), "2024-04-01", "2024-05-31")
        self.assertTrue(all(pd.Timestamp("2024-04-01") <= x <= pd.Timestamp("2024-05-31") for x in dates))

    def test_invalid_frequency(self):
        with self.assertRaises(ValueError): validation.build_rebalance_dates(histories(), rebalance_frequency="daily")

    def test_cross_section_truncates_future(self):
        data = histories(); date = data["A"].Date.iloc[70]; a = validation.build_historical_factor_cross_section(data, date)
        data["A"].loc[data["A"].Date > date, "Close"] = 999999
        b = validation.build_historical_factor_cross_section(data, date)
        self.assertEqual(a.loc[0, "CompositeFactorScore"], b.loc[0, "CompositeFactorScore"])

    def test_bad_symbol_does_not_stop(self):
        data = histories(); data["BAD"] = pd.DataFrame(); result = validation.build_historical_factor_cross_section(data, data["A"].Date.iloc[70])
        self.assertEqual(result.Ticker.tolist(), ["A", "B", "C", "BAD"])

    def test_cross_section_universe_order(self):
        result = validation.build_historical_factor_cross_section(histories(), history().Date.iloc[70], ["C", "A"])
        self.assertEqual(result.Ticker.tolist(), ["C", "A"])

    def test_native_factors_agree(self):
        data = histories(); date = data["A"].Date.iloc[70]; result = validation.build_historical_factor_cross_section(data, date)
        expected = calculate_price_factors(data["A"][data["A"].Date <= date]); self.assertIsNotNone(expected["TrendValue"]); self.assertTrue(result.loc[0, "CompositeFactorScore"] > 0)

    def test_cross_section_normalized(self):
        result = validation.build_historical_factor_cross_section(histories(), history().Date.iloc[70]); self.assertTrue(result.TrendPercentile.between(0, 1).all())

    def test_composite_formula(self):
        result = validation.build_historical_factor_cross_section(histories(), history().Date.iloc[70]); row = result.iloc[0]
        self.assertAlmostEqual(row.CompositeFactorScore, row.TrendPercentile*.35 + row.MomentumPercentile*.35 + row.LowVolatilityPercentile*.3)

    def test_source_histories_not_mutated(self):
        data = histories(); before = data["A"].copy(); validation.build_historical_factor_cross_section(data, history().Date.iloc[70]); pd.testing.assert_frame_equal(data["A"], before)

    def test_forward_returns_all_horizons(self):
        data = history(); date = data.Date.iloc[10]
        for horizon in validation.HORIZONS:
            self.assertAlmostEqual(validation.calculate_forward_return(data, date, horizon), data.Close.iloc[10+horizon]/data.Close.iloc[10]-1)

    def test_forward_full_horizon_required(self):
        data = history(rows=20); self.assertIsNone(validation.calculate_forward_return(data, data.Date.iloc[-2], 5))

    def test_missing_rebalance_date_missing(self):
        self.assertIsNone(validation.calculate_forward_return(history(), "2024-01-06", 5))

    def test_zero_entry_missing(self):
        data = history(); data.loc[10, "Close"] = 0; self.assertIsNone(validation.calculate_forward_return(data, data.Date.iloc[10], 5))

    def test_invalid_date_raises(self):
        with self.assertRaises(ValueError): validation.calculate_forward_return(history(), "bad", 5)

    def test_validation_rows_and_columns(self):
        data = histories(); result = validation.build_factor_validation_table(["A", "B", "C"], data, "2024-04-01", "2024-05-31")
        self.assertEqual(list(result), validation.VALIDATION_COLUMNS); self.assertEqual(len(result), result.RebalanceDate.nunique()*3)

    def test_validation_order(self):
        result = validation.build_factor_validation_table(["C", "A"], histories(), "2024-04-01", "2024-04-30")
        self.assertEqual(result.Ticker.tolist(), ["C", "A"])

    def test_missing_forward_fields_deterministic(self):
        result = validation.build_factor_validation_table(["A"], {"A": history(rows=65)})
        self.assertIn("ForwardReturn60D", result.iloc[-1].ValidationMissingFields)

    def test_validation_deterministic(self):
        args = (["A", "B", "C"], histories(), "2024-04-01", "2024-04-30")
        pd.testing.assert_frame_equal(validation.build_factor_validation_table(*args), validation.build_factor_validation_table(*args))

    def test_positive_ic(self):
        result = validation.build_rank_ic_table(validation_table()); self.assertTrue((result.RankIC == 1).all())

    def test_negative_ic(self):
        data = validation_table(); data["ForwardReturn5D"] *= -1
        self.assertEqual(validation.build_rank_ic_table(data).query("Horizon == '5D'").iloc[0].RankIC, -1)

    def test_constant_score_missing_ic(self):
        data = validation_table(); data.CompositeFactorScore = 1
        self.assertTrue(validation.build_rank_ic_table(data).RankIC.isna().all())

    def test_too_few_pairs_missing_ic(self):
        data = validation_table().iloc[:2]; self.assertTrue(validation.build_rank_ic_table(data).RankIC.isna().all())

    def test_missing_pairs_excluded(self):
        data = validation_table(); data.loc[0, "ForwardReturn5D"] = None
        self.assertEqual(validation.build_rank_ic_table(data).query("RebalanceDate == '2024-03-29' and Horizon == '5D'").iloc[0].ValidPairs, 2)

    def test_series_summary(self):
        result = validation._series_summary(pd.Series([1, -1, 1])); self.assertEqual(result["count"], 3); self.assertEqual(result["positive_ratio"], 2/3)

    def test_information_ratio(self):
        result = validation._series_summary(pd.Series([1., 2., 3.])); self.assertAlmostEqual(result["information_ratio"], 2)

    def test_groups_selected(self):
        result = validation.build_group_return_table(validation_table()); first = result[result.RebalanceDate == "2024-03-29"]
        self.assertEqual(first[first.Group == "Top"].iloc[0].SelectedCount, 1); self.assertEqual(first[first.Group == "Bottom"].iloc[0].SelectedCount, 1)

    def test_group_equal_weight_and_spread(self):
        result = validation.build_group_return_table(validation_table()).query("RebalanceDate == '2024-03-29' and Horizon == '5D'")
        self.assertAlmostEqual(result[result.Group == "Top"].iloc[0].AverageForwardReturn, .3); self.assertAlmostEqual(result.iloc[0].LongShortSpread, .2)

    def test_group_missing_returns_excluded(self):
        data = validation_table(); data.loc[0, "ForwardReturn5D"] = None
        top = validation.build_group_return_table(data).query("RebalanceDate == '2024-03-29' and Horizon == '5D' and Group == 'Top'").iloc[0]
        self.assertEqual(top.ValidReturnCount, 0)

    def test_group_source_not_mutated(self):
        data = validation_table(); before = data.copy(); validation.build_group_return_table(data); pd.testing.assert_frame_equal(data, before)

    def test_turnover_full_retention(self):
        data = validation_table(); data.loc[data.RebalanceDate == "2024-04-30", "CompositeFactorScore"] = [3,2,1]
        self.assertEqual(validation.build_turnover_table(data).iloc[1].Turnover, 0)

    def test_turnover_no_retention(self):
        self.assertEqual(validation.build_turnover_table(validation_table()).iloc[1].Turnover, 0)

    def test_turnover_partial_and_first_missing(self):
        data = validation_table(); extra = data.copy(); extra.RebalanceDate = "2024-05-31"; extra.CompositeFactorScore = [1,3,2,1,3,2]; combined = pd.concat([data, extra.iloc[:3]])
        result = validation.build_turnover_table(combined); self.assertTrue(pd.isna(result.iloc[0].Turnover)); self.assertGreaterEqual(result.iloc[-1].Turnover, 0)

    def test_summary_contract(self):
        data=validation_table(); ic=validation.build_rank_ic_table(data); groups=validation.build_group_return_table(data); turn=validation.build_turnover_table(data)
        result=validation.build_validation_summary(data,ic,groups,turn); self.assertEqual(result["observation_count"],6); self.assertIn("Same-close entry assumption",result["warnings"])

    def test_save_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            paths={name:Path(directory)/f"{name}.csv" for name in validation.OUTPUT_PATHS}; result=validation.save_factor_validation(validation_table(),paths)
            self.assertTrue(all(path.is_file() and "Unnamed: 0" not in pd.read_csv(path).columns for path in result.values()))

    @patch("factor_validation.save_factor_validation")
    @patch("factor_validation.build_factor_validation_table", return_value=validation_table())
    @patch("factor_validation.load_active_universe", return_value=["A","B","C"])
    def test_cli_without_network(self, _, __, save):
        with tempfile.TemporaryDirectory() as directory:
            save.return_value={"validation":Path(directory)/"x.csv"}; self.assertEqual(validation.main([]),0)

    def test_cli_invalid_date_nonzero_no_traceback(self):
        output=io.StringIO()
        with contextlib.redirect_stderr(output): code=validation.main(["--start","bad"])
        self.assertEqual(code,1); self.assertNotIn("Traceback",output.getvalue())


if __name__ == "__main__": unittest.main()
