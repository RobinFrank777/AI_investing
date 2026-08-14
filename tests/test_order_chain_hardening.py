import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import position_sizing as sizing
import order_draft as draft
import order_review as review


def portfolio():
    return pd.DataFrame({"Ticker":["AAA"],"BacktestScore":[80.0],"AverageReturn":[.1],"WinRate":[.6],"MaxDrawdown":[-.1],"SharpeRatio":[2.0],"RiskLevel":["Low"],"RiskReady":[True],"RiskWeightMultiplier":[1.0],"TargetWeight":[.1],"TargetWeightPercent":["10.0%"],"PortfolioRole":["candidate"],"PortfolioStatus":["PORTFOLIO_READY"],"FundamentalScore":[70.0],"CombinedScore":[77.0],"FundamentalRating":["GOOD"]})

def sized():
    p=sizing.add_target_dollar_amount(portfolio(),1000)
    with patch.object(sizing,"get_latest_close",return_value=100.0): return sizing.add_share_sizing(p)


class PositionSizingHardeningTests(unittest.TestCase):
    def test_normal_and_empty(self):
        result=sized(); self.assertEqual(result.TargetShares.tolist(),[1]); self.assertEqual(result.SizingStatus.tolist(),[sizing.POSITION_READY])
        empty=sizing.add_target_dollar_amount(portfolio().iloc[:0],1000)
        with patch.object(sizing,"get_latest_close"):
            result=sizing.add_share_sizing(empty)
        self.assertTrue(result.empty); self.assertIn("TargetShares",result)

    def test_invalid_prices_and_zero_shares(self):
        base=sizing.add_target_dollar_amount(portfolio(),1000)
        for price in (np.nan,np.inf,-np.inf,0,-1):
            with self.subTest(price=price):
                data=base.copy(); data["LatestClose"]=price
                result=sizing.add_share_sizing(data); self.assertEqual(result.at[0,"SizingStatus"],sizing.INVALID_PRICE); self.assertEqual(result.at[0,"TargetShares"],0)
        data=base.copy(); data["LatestClose"]=2000
        result=sizing.add_share_sizing(data); self.assertEqual(result.at[0,"SizingStatus"],sizing.NO_SIZABLE_POSITION)

    def test_point_in_time_price_is_preserved_without_latest_reader(self):
        data=sizing.add_target_dollar_amount(portfolio(),1000)
        data["LatestClose"] = 125.0; data["LatestCloseAsOf"]="2026-06-18"; data["AsOfDate"]="2026-06-18"
        with patch.object(sizing,"get_latest_close",side_effect=AssertionError("must not read current price")):
            result=sizing.add_share_sizing(data)
        self.assertEqual(result.at[0,"LatestClose"],125.0)
        future=data.copy(); future["LatestCloseAsOf"]="2026-06-19"
        self.assertEqual(sizing.add_share_sizing(future).at[0,"SizingStatus"],sizing.INVALID_PRICE)

    def test_invalid_weight_and_capital(self):
        for weight in (np.nan,np.inf,-1):
            data=portfolio(); data.loc[0,"TargetWeight"]=weight
            self.assertEqual(sizing.add_target_dollar_amount(data,1000).at[0,"SizingStatus"],sizing.INVALID_SIZING_INPUT)
        for capital in (np.nan,np.inf,-1):
            with self.assertRaises(ValueError): sizing.add_target_dollar_amount(portfolio(),capital)
        self.assertEqual(sizing.add_target_dollar_amount(portfolio(),0).at[0,"TargetDollarAmount"],0)


class OrderDraftHardeningTests(unittest.TestCase):
    def test_normal_and_empty_schema(self):
        result=draft.build_order_draft(sized()); self.assertEqual(len(result),1); self.assertEqual(result.attrs["OrderDraftStatus"],draft.DRAFT_READY)
        empty=draft.build_order_draft(sized().iloc[:0]); self.assertTrue(empty.empty); self.assertEqual(empty.columns.tolist(),draft.ORDER_COLUMNS); self.assertEqual(empty.attrs["OrderDraftStatus"],draft.NO_DRAFT_ORDERS)
        csv_empty=draft.build_order_draft(pd.DataFrame(columns=draft.REQUIRED_COLUMNS)); self.assertTrue(csv_empty.empty); self.assertEqual(csv_empty.columns.tolist(),draft.ORDER_COLUMNS); self.assertEqual(csv_empty.attrs["OrderDraftStatus"],draft.NO_DRAFT_ORDERS)

    def test_invalid_rows_do_not_become_orders(self):
        for field,value in (("TargetShares",0),("TargetShares",-1),("TargetShares",np.nan),("TargetShares",np.inf),("LatestClose",0),("LatestClose",np.nan),("LatestClose",np.inf)):
            data=sized(); data.loc[0,field]=value
            with self.subTest(field=field,value=value): self.assertTrue(draft.build_order_draft(data).empty)


class OrderReviewHardeningTests(unittest.TestCase):
    def order(self): return draft.build_order_draft(sized())

    def test_normal_missing_fundamentals_and_empty(self):
        normal=review.build_order_review(self.order()); self.assertEqual(normal.at[0,"ReviewStatus"],"PASS"); self.assertEqual(normal.at[0,"PortfolioReviewFlag"],"PASS")
        missing=self.order(); missing.loc[0,"FundamentalRating"]="MISSING"
        missing_review=review.build_order_review(missing); self.assertEqual(missing_review.at[0,"ReviewStatus"],"REVIEW"); self.assertEqual(missing_review.at[0,"PortfolioReviewFlag"],"REVIEW_REQUIRED")
        empty=review.build_order_review(self.order().iloc[:0]); self.assertTrue(empty.empty); self.assertEqual(empty.attrs["ReviewStatus"],review.NO_ORDERS_TO_REVIEW); self.assertEqual(empty.attrs["PortfolioReviewFlag"],"NOT_APPLICABLE")

    def test_invalid_numeric_never_passes(self):
        for field,value in (("TargetShares",np.nan),("TargetShares",np.inf),("TargetShares",0),("TargetShares",-1),("LatestClose",np.nan),("LatestClose",0),("LatestClose",-1),("EstimatedOrderValue",np.nan),("EstimatedOrderValue",0)):
            data=self.order(); data.loc[0,field]=value
            with self.subTest(field=field,value=value):
                result=review.build_order_review(data); self.assertEqual(result.at[0,"ReviewStatus"],"BLOCKED"); self.assertEqual(result.at[0,"PortfolioReviewFlag"],"BLOCKED")

    def test_aggregate_severity_ordering(self):
        base=self.order()
        passing=base.copy()
        reviewing=base.copy(); reviewing.loc[:,"FundamentalRating"]="MISSING"
        blocked=base.copy(); blocked.loc[:,"TargetShares"]=0
        cases=[
            ([passing,reviewing],"REVIEW_REQUIRED"),
            ([reviewing],"REVIEW_REQUIRED"),
            ([passing,blocked],"BLOCKED"),
            ([reviewing,blocked],"BLOCKED"),
            ([passing,reviewing,blocked],"BLOCKED"),
        ]
        for frames,expected in cases:
            with self.subTest(expected=expected):
                result=review.build_order_review(pd.concat(frames,ignore_index=True))
                self.assertTrue((result.PortfolioReviewFlag==expected).all())


if __name__=="__main__": unittest.main()
