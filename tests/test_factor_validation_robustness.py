import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import factor_validation_robustness as robust
from factor_validation import GROUP_COLUMNS, VALIDATION_COLUMNS


def groups():
    rows=[]
    for date,top,bottom in [("2024-01-31",.3,.1),("2024-02-29",-.1,.2),("2024-03-29",.3,.1)]:
        for horizon in ["5D","10D","20D","60D"]:
            spread=top-bottom
            for name,value in [("Top",top),("Middle",.05),("Bottom",bottom)]: rows.append([date,horizon,name,2,2,value,spread])
    return pd.DataFrame(rows,columns=GROUP_COLUMNS)


def observations():
    rows=[]
    for date,scores in [("2024-01-31",[3,2,1]),("2024-02-29",[2,3,1])]:
        for ticker,score in zip(["A","B","C"],scores):
            row={c:None for c in VALIDATION_COLUMNS}; row.update({"RebalanceDate":date,"Ticker":ticker,"CompositeFactorScore":score,"TrendPercentile":score/3,"MomentumPercentile":score/3})
            for h in [5,10,20,60]: row[f"ForwardReturn{h}D"]=score/10
            rows.append(row)
    return pd.DataFrame(rows,columns=VALIDATION_COLUMNS)


def history(up=True,rows=130):
    values=list(range(100,100+rows)) if up else list(range(300,300-rows,-1))
    return pd.DataFrame({"Date":pd.bdate_range("2023-09-01",periods=rows),"Close":values})


class RobustnessTests(unittest.TestCase):
    def test_best_worst_dates(self):
        summary=robust.summarize_date_contributions(robust.build_date_contribution_diagnostics(groups()))["5D"]
        self.assertEqual(summary["BestDate"],"2024-01-31"); self.assertEqual(summary["WorstDate"],"2024-02-29")

    def test_positive_ratio_and_contributions(self):
        summary=robust.summarize_date_contributions(robust.build_date_contribution_diagnostics(groups()))["5D"]
        self.assertEqual(summary["PositiveRatio"],2/3); self.assertAlmostEqual(summary["BestDateContribution"],2); self.assertAlmostEqual(summary["BestThreeContribution"],1)

    def test_excluding_best_worst(self):
        summary=robust.summarize_date_contributions(robust.build_date_contribution_diagnostics(groups()))["5D"]
        self.assertAlmostEqual(summary["MeanExcludingBest"],-.05); self.assertAlmostEqual(summary["MeanExcludingWorst"],.2)

    def test_missing_spreads_excluded(self):
        data=groups(); data.loc[(data.Group=="Top")&(data.RebalanceDate=="2024-01-31"),"AverageForwardReturn"]=None
        self.assertEqual(robust.summarize_date_contributions(robust.build_date_contribution_diagnostics(data))["5D"]["ObservationCount"],2)

    def test_robust_stats(self):
        row=robust.build_robust_return_statistics(groups()).query("Horizon=='5D' and Series=='Top-Bottom'").iloc[0]
        self.assertAlmostEqual(row.Mean,1/30); self.assertAlmostEqual(row.Median,.2); self.assertAlmostEqual(row.P25,-.05); self.assertAlmostEqual(row.P75,.2)

    def test_small_trim_missing(self):
        row=robust.build_robust_return_statistics(groups()).iloc[0]; self.assertTrue(pd.isna(row.TrimmedMean))

    def test_trimmed_mean(self):
        self.assertAlmostEqual(robust._trimmed_mean(pd.Series(range(10))),4.5)

    def test_stats_source_not_mutated(self):
        data=groups(); before=data.copy(); robust.build_robust_return_statistics(data); pd.testing.assert_frame_equal(data,before)

    def test_symbol_appearances_and_means(self):
        result=robust.build_symbol_influence_table(observations()); a=result.query("Ticker=='A' and Horizon=='5D'").iloc[0]
        self.assertEqual(a.TopAppearances,1); self.assertEqual(a.BottomAppearances,0); self.assertAlmostEqual(a.TopForwardReturnMean,.3)

    def test_symbol_no_appearance(self):
        result=robust.build_symbol_influence_table(observations()); b=result.query("Ticker=='B' and Horizon=='5D'").iloc[0]
        self.assertEqual(b.BottomAppearances,0); self.assertTrue(pd.isna(b.BottomForwardReturnMean))

    def test_leave_one_out_exists(self):
        result=robust.build_symbol_influence_table(observations()); self.assertTrue(result.SpreadChange.notna().any())

    def test_no_symbol_removed(self):
        self.assertEqual(robust.build_symbol_influence_table(observations()).Ticker.nunique(),3)

    def test_next_close_manual(self):
        data=history(); date=data.Date.iloc[60]; self.assertAlmostEqual(robust.calculate_next_close_return(data,date,5),data.Close.iloc[66]/data.Close.iloc[61]-1)

    def test_next_close_full_horizon(self):
        data=history(rows=65); self.assertIsNone(robust.calculate_next_close_return(data,data.Date.iloc[-2],5))

    def test_next_close_zero_entry(self):
        data=history(); data.loc[61,"Close"]=0; self.assertIsNone(robust.calculate_next_close_return(data,data.Date.iloc[60],5))

    def test_alternative_keeps_scores_and_separate(self):
        source=observations(); before=source.copy(); market={x:history() for x in ["A","B","C"]}; result=robust.build_alternative_entry_validation(source,market)
        pd.testing.assert_series_equal(result.CompositeFactorScore,source.CompositeFactorScore); pd.testing.assert_frame_equal(source,before)

    def test_regime_risk_on_and_equality(self):
        data=history(); dates=[data.Date.iloc[59].strftime("%Y-%m-%d")]; self.assertEqual(robust.classify_market_regimes(dates,data).iloc[0].Regime,"Risk-On")
        flat=data.copy(); flat.Close=1; self.assertEqual(robust.classify_market_regimes(dates,flat).iloc[0].Regime,"Risk-On")

    def test_regime_risk_off(self):
        data=history(False); date=data.Date.iloc[59].strftime("%Y-%m-%d"); self.assertEqual(robust.classify_market_regimes([date],data).iloc[0].Regime,"Risk-Off")

    def test_regime_insufficient_unavailable(self):
        data=history(rows=50); date=data.Date.iloc[-1].strftime("%Y-%m-%d"); self.assertEqual(robust.classify_market_regimes([date],data).iloc[0].Regime,"Unavailable")

    def test_future_benchmark_no_effect(self):
        data=history(); date=data.Date.iloc[70].strftime("%Y-%m-%d"); first=robust.classify_market_regimes([date],data).iloc[0].Regime; data.loc[71:,"Close"]=0; self.assertEqual(robust.classify_market_regimes([date],data).iloc[0].Regime,first)

    def test_spy_absence_unavailable(self):
        self.assertEqual(robust.classify_market_regimes(["2024-01-31"],None).iloc[0].Regime,"Unavailable")

    def test_regime_diagnostics(self):
        regimes=pd.DataFrame({"RebalanceDate":["2024-01-31","2024-02-29"],"Regime":["Risk-On","Risk-Off"]}); result=robust.build_regime_diagnostics(observations(),regimes)
        self.assertEqual(result.query("Regime=='Risk-On' and Horizon=='5D'").iloc[0].DateCount,1)

    def test_coverage_ratio_counts(self):
        data=observations(); data.loc[0,"CompositeFactorScore"]=None; data.loc[1,"ForwardReturn5D"]=None; result=robust.build_coverage_diagnostics(data).iloc[0]
        self.assertEqual(result.ScoreCoverageRatio,2/3); self.assertEqual(result.ValidForward5D,2)

    def test_coverage_fixed_filters(self):
        data=observations(); coverage=robust.build_coverage_diagnostics(data); result=robust.build_coverage_filter_comparison(data,coverage)
        self.assertEqual(result.Filter.drop_duplicates().tolist(),["No filter","Coverage >= 80%","Coverage >= 90%","Coverage = 100%"])

    def test_coverage_no_winner_field(self):
        result=robust.build_coverage_filter_comparison(observations(),robust.build_coverage_diagnostics(observations())); self.assertNotIn("Selected",result.columns)

    def test_entry_comparison_columns(self):
        result=robust.build_entry_comparison(observations(),observations()); self.assertTrue({"ICDifference","SpreadDifference"}.issubset(result.columns)); self.assertTrue((result.ICDifference==0).all())

    def test_summary_spy_warning(self):
        date=robust.summarize_date_contributions(robust.build_date_contribution_diagnostics(groups())); stats=robust.build_robust_return_statistics(groups()); influence=robust.build_symbol_influence_table(observations()); entry=robust.build_entry_comparison(observations(),observations()); empty=pd.DataFrame(); coverage=pd.DataFrame()
        summary=robust.build_robustness_summary(date,stats,influence,entry,empty,coverage,False); self.assertIn("SPY benchmark unavailable",summary["warnings"])

    def test_save_outputs_no_index(self):
        with tempfile.TemporaryDirectory() as directory:
            tables={"date_contributions":robust.build_date_contribution_diagnostics(groups())}; paths={"date_contributions":Path(directory)/"out.csv"}; result=robust.save_robustness_outputs(tables,paths); self.assertNotIn("Unnamed: 0",pd.read_csv(result["date_contributions"]).columns)

    @patch("factor_validation_robustness.save_robustness_outputs")
    @patch("factor_validation_robustness.load_stock",return_value=history())
    @patch("factor_validation_robustness.load_active_universe",return_value=["A","B","C"])
    @patch("factor_validation_robustness.pd.read_csv",side_effect=[observations(),groups()])
    def test_cli_no_network(self,*mocks):
        mocks[-1].return_value={}; self.assertEqual(robust.main([]),0)

    def test_cli_expected_error_no_traceback(self):
        output=io.StringIO()
        with contextlib.redirect_stderr(output): code=robust.main(["--validation","/missing.csv"])
        self.assertEqual(code,1); self.assertNotIn("Traceback",output.getvalue())


def _add_horizon_contract_tests():
    for horizon in ("5D", "10D", "20D", "60D"):
        def date_contract(self, selected=horizon):
            table = robust.build_date_contribution_diagnostics(groups())
            self.assertEqual(len(table[table.Horizon == selected]), 3)
        setattr(RobustnessTests, f"test_date_contract_{horizon.lower()}", date_contract)

        def stats_contract(self, selected=horizon):
            table = robust.build_robust_return_statistics(groups())
            self.assertEqual(set(table[table.Horizon == selected].Series), {"Top", "Middle", "Bottom", "Top-Bottom"})
        setattr(RobustnessTests, f"test_stats_contract_{horizon.lower()}", stats_contract)

        def entry_contract(self, selected=horizon):
            table = robust.build_entry_comparison(observations(), observations())
            row = table[table.Horizon == selected].iloc[0]
            self.assertEqual((row.ICDifference, row.SpreadDifference), (0, 0))
        setattr(RobustnessTests, f"test_entry_contract_{horizon.lower()}", entry_contract)

        def coverage_contract(self, selected=horizon):
            data = observations(); coverage = robust.build_coverage_diagnostics(data)
            table = robust.build_coverage_filter_comparison(data, coverage)
            self.assertEqual(len(table[table.Horizon == selected]), 4)
        setattr(RobustnessTests, f"test_coverage_contract_{horizon.lower()}", coverage_contract)

        def unavailable_regime_contract(self, selected=horizon):
            regimes = pd.DataFrame({"RebalanceDate": ["2024-01-31", "2024-02-29"], "Regime": ["Unavailable", "Unavailable"]})
            table = robust.build_regime_diagnostics(observations(), regimes)
            self.assertEqual(table[(table.Regime == "Unavailable") & (table.Horizon == selected)].iloc[0].DateCount, 2)
        setattr(RobustnessTests, f"test_unavailable_regime_contract_{horizon.lower()}", unavailable_regime_contract)


_add_horizon_contract_tests()


if __name__=="__main__": unittest.main()
