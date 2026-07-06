from pathlib import Path

import pandas as pd


POSITION_SIZING_INPUT = Path("results/model_portfolio_sizing.csv")
ORDER_DRAFT_OUTPUT = Path("results/order_draft.csv")

REQUIRED_COLUMNS = [
    "Ticker",
    "BacktestScore",
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
    "Action",
    "TargetShares",
    "LatestClose",
    "EstimatedOrderValue",
    "TargetDollarAmount",
    "PositionCashRemainder",
    "RiskLevel",
    "RiskWeightMultiplier",
    "BacktestScore",
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


def build_order_draft():
    position_df = load_position_sizing()

    order_df = position_df[position_df["TargetShares"] > 0].copy()

    order_df["Action"] = "BUY"

    order_df["TargetShares"] = order_df["TargetShares"].astype(int)

    order_df["EstimatedOrderValue"] = (
        order_df["TargetShares"] * order_df["LatestClose"]
    ).round(2)

    order_df["OrderStatus"] = "DRAFT_ONLY"

    order_df = order_df[ORDER_COLUMNS]

    return order_df


def save_order_draft(order_df):
    ORDER_DRAFT_OUTPUT.parent.mkdir(exist_ok=True)

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
    print(f"Saved Order Draft To  : {output_path}")


if __name__ == "__main__":
    print_order_draft()