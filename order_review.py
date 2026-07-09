from pathlib import Path

import pandas as pd

from config import (
    ORDER_DRAFT_OUTPUT as CONFIG_ORDER_DRAFT_OUTPUT,
    ORDER_REVIEW_OUTPUT as CONFIG_ORDER_REVIEW_OUTPUT,
    MAX_SINGLE_ORDER_VALUE,
    MAX_TOTAL_ORDER_VALUE,
    MAX_ORDER_COUNT,
    ALLOWED_ACTIONS,
    ALLOWED_ORDER_STATUS,
    ALLOWED_REVIEW_STATUS,
    ALLOWED_PORTFOLIO_REVIEW_FLAG,
)

ORDER_DRAFT_INPUT = Path(CONFIG_ORDER_DRAFT_OUTPUT)
ORDER_REVIEW_OUTPUT = Path(CONFIG_ORDER_REVIEW_OUTPUT)



REQUIRED_COLUMNS = [
    "Ticker",
    "BacktestScore",
    "FundamentalScore",
    "CombinedScore",
    "FundamentalRating",
    "Action",
    "TargetShares",
    "LatestClose",
    "EstimatedOrderValue",
    "TargetDollarAmount",
    "PositionCashRemainder",
    "RiskLevel",
    "RiskWeightMultiplier",
    "PortfolioRole",
    "OrderStatus",
]


def load_order_draft():
    if not ORDER_DRAFT_INPUT.exists():
        raise FileNotFoundError(
            f"Missing order draft file: {ORDER_DRAFT_INPUT}"
        )

    order_df = pd.read_csv(ORDER_DRAFT_INPUT)

    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in order_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    return order_df


def assign_review_status(row):
    if row["Action"] not in ALLOWED_ACTIONS:
        return "BLOCKED"

    if row["OrderStatus"] not in ALLOWED_ORDER_STATUS:
        return "BLOCKED"

    if row["TargetShares"] <= 0:
        return "BLOCKED"

    if row["EstimatedOrderValue"] <= 0:
        return "BLOCKED"

    if row["EstimatedOrderValue"] > MAX_SINGLE_ORDER_VALUE:
        return "REVIEW"

    if row["RiskLevel"] == "High":
        return "REVIEW"

    return "PASS"


def assign_review_reason(row):
    reasons = []

    if row["Action"] not in ALLOWED_ACTIONS:
        reasons.append("action not allowed")

    if row["OrderStatus"] not in ALLOWED_ORDER_STATUS:
        reasons.append("order status not draft")

    if row["TargetShares"] <= 0:
        reasons.append("target shares must be positive")

    if row["EstimatedOrderValue"] <= 0:
        reasons.append("estimated order value must be positive")

    if row["EstimatedOrderValue"] > MAX_SINGLE_ORDER_VALUE:
        reasons.append("single order value above review limit")

    if row["RiskLevel"] == "High":
        reasons.append("high risk level")

    if not reasons:
        return "no issue"

    return "; ".join(reasons)


def build_order_review():
    order_df = load_order_draft().copy()

    order_df["ReviewStatus"] = order_df.apply(
        assign_review_status,
        axis=1,
    )

    order_df["ReviewReason"] = order_df.apply(
        assign_review_reason,
        axis=1,
    )

    total_order_value = order_df["EstimatedOrderValue"].sum()
    order_count = len(order_df)

    portfolio_level_warnings = []

    if order_count > MAX_ORDER_COUNT:
        portfolio_level_warnings.append("order count above limit")

    if total_order_value > MAX_TOTAL_ORDER_VALUE:
        portfolio_level_warnings.append("total order value above limit")

    if portfolio_level_warnings:
        order_df["PortfolioReviewFlag"] = "REVIEW"
        order_df["PortfolioReviewReason"] = "; ".join(
            portfolio_level_warnings
        )
    else:
        order_df["PortfolioReviewFlag"] = "PASS"
        order_df["PortfolioReviewReason"] = "portfolio level checks passed"

    return order_df


def save_order_review(order_df):
    ORDER_REVIEW_OUTPUT.parent.mkdir(exist_ok=True)

    order_df.to_csv(
        ORDER_REVIEW_OUTPUT,
        index=False,
    )

    return ORDER_REVIEW_OUTPUT


def print_order_review():
    review_df = build_order_review()
    output_path = save_order_review(review_df)

    total_order_value = review_df["EstimatedOrderValue"].sum()

    pass_count = (review_df["ReviewStatus"] == "PASS").sum()
    review_count = (review_df["ReviewStatus"] == "REVIEW").sum()
    blocked_count = (review_df["ReviewStatus"] == "BLOCKED").sum()

    print("=" * 70)
    print("ORDER REVIEW")
    print("=" * 70)

    print(
        review_df[
            [
                "Ticker",
                "Action",
                "TargetShares",
                "EstimatedOrderValue",
                "RiskLevel",
                "ReviewStatus",
                "ReviewReason",
            ]
        ].to_string(index=False)
    )

    print("\nOrder Review Summary")
    print(f"Orders Count          : {len(review_df)}")
    print(f"Total Estimated Value : ${total_order_value:,.2f}")
    print(f"PASS Count            : {pass_count}")
    print(f"REVIEW Count          : {review_count}")
    print(f"BLOCKED Count         : {blocked_count}")
    print(f"Portfolio Flag        : {review_df['PortfolioReviewFlag'].iloc[0]}")
    print(f"Saved Order Review To : {output_path}")


if __name__ == "__main__":
    print_order_review()