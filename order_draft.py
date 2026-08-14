from pathlib import Path

import pandas as pd
import numpy as np

from config import (
    POSITION_SIZING_OUTPUT_PATH,
    ORDER_DRAFT_OUTPUT_PATH,
    ALLOWED_ACTIONS,
    ALLOWED_ORDER_STATUS,
    display_path,
)


POSITION_SIZING_INPUT = POSITION_SIZING_OUTPUT_PATH
ORDER_DRAFT_OUTPUT = ORDER_DRAFT_OUTPUT_PATH

DEFAULT_ACTION = ALLOWED_ACTIONS[0]
DEFAULT_ORDER_STATUS = ALLOWED_ORDER_STATUS[0]
DRAFT_READY = "DRAFT_READY"
NO_DRAFT_ORDERS = "NO_DRAFT_ORDERS"

REQUIRED_COLUMNS = [
    "Ticker",
    "BacktestScore",
    "FundamentalScore",
    "CombinedScore",
    "FundamentalRating",
    "RiskLevel",
    "RiskWeightMultiplier",
    "TargetWeightPercent",
    "LatestClose",
    "TargetDollarAmount",
    "TargetShares",
    "EstimatedPositionValue",
    "PositionCashRemainder",
    "PortfolioRole",
]

ORDER_COLUMNS = [
    "Ticker",
    "RunId",
    "AsOfDate",
    "UniverseVersion",
    "ScoreModelVersion",
    "RiskModelVersion",
    "BacktestScore",
    "FundamentalScore",
    "CombinedScore",
    "FundamentalRating",
    "Action",
    "TargetShares",
    "LatestClose",
    "LatestCloseAsOf",
    "EstimatedOrderValue",
    "TargetDollarAmount",
    "PositionCashRemainder",
    "RiskLevel",
    "RiskWeightMultiplier",
    "PortfolioRole",
    "OrderStatus",
]


def load_position_sizing():
    if not POSITION_SIZING_INPUT.exists():
        raise FileNotFoundError(
            f"Missing position sizing file: {POSITION_SIZING_INPUT}"
        )

    df = pd.read_csv(POSITION_SIZING_INPUT)

    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    return df


def build_order_draft(position_df=None):
    position_df = load_position_sizing() if position_df is None else position_df.copy()
    missing = [column for column in REQUIRED_COLUMNS if column not in position_df]
    if missing: raise ValueError(f"Missing required columns: {missing}")
    if position_df.empty:
        order_df = pd.DataFrame(columns=ORDER_COLUMNS)
        order_df.attrs["OrderDraftStatus"] = NO_DRAFT_ORDERS
        return order_df
    shares = pd.to_numeric(position_df["TargetShares"], errors="coerce")
    prices = pd.to_numeric(position_df["LatestClose"], errors="coerce")
    values = pd.to_numeric(position_df["TargetDollarAmount"], errors="coerce")
    valid = (shares.notna() & np.isfinite(shares) & (shares > 0) & (shares % 1 == 0)
             & prices.notna() & np.isfinite(prices) & (prices > 0)
             & values.notna() & np.isfinite(values) & (values >= 0))
    if "SizingStatus" in position_df:
        valid &= position_df["SizingStatus"].eq("POSITION_READY")
    order_df = position_df.loc[valid].copy()

    order_df["Action"] = DEFAULT_ACTION

    order_df["TargetShares"] = order_df["TargetShares"].astype(int)

    order_df["EstimatedOrderValue"] = (
        order_df["TargetShares"] * order_df["LatestClose"]
    ).round(2)

    order_df["OrderStatus"] = DEFAULT_ORDER_STATUS

    for column in (
        "RunId", "AsOfDate", "UniverseVersion", "ScoreModelVersion",
        "RiskModelVersion", "LatestCloseAsOf",
    ):
        if column not in order_df:
            order_df[column] = pd.NA

    order_df = order_df[ORDER_COLUMNS]
    order_df.attrs["OrderDraftStatus"] = DRAFT_READY if not order_df.empty else NO_DRAFT_ORDERS
    return order_df


def save_order_draft(order_df):
    ORDER_DRAFT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    order_df.to_csv(
        ORDER_DRAFT_OUTPUT,
        index=False,
    )

    return ORDER_DRAFT_OUTPUT


def print_order_draft():
    order_df = build_order_draft()
    output_path = save_order_draft(order_df)

    total_order_value = order_df["EstimatedOrderValue"].sum()

    print("=" * 70)
    print("ORDER DRAFT")
    print("=" * 70)

    print(
        order_df[
            [
                "Ticker",
                "BacktestScore",
                "FundamentalScore",
                "CombinedScore",
                "FundamentalRating",
                "Action",
                "TargetShares",
                "LatestClose",
                "EstimatedOrderValue",
                "RiskLevel",
                "OrderStatus",
            ]
        ].to_string(index=False)
    )

    print("\nOrder Draft Summary")
    print(f"Orders Count          : {len(order_df)}")
    print(f"Total Estimated Value : ${total_order_value:,.2f}")
    print(f"Saved Order Draft To  : {display_path(output_path)}")


if __name__ == "__main__":
    print_order_draft()
