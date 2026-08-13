from pathlib import Path

import pandas as pd
import numpy as np

from config import (
    ORDER_DRAFT_OUTPUT_PATH,
    ORDER_REVIEW_OUTPUT_PATH,
    MAX_SINGLE_ORDER_VALUE,
    MAX_TOTAL_ORDER_VALUE,
    MAX_ORDER_COUNT,
    ALLOWED_ACTIONS,
    ALLOWED_ORDER_STATUS,
    ALLOWED_REVIEW_STATUS,
    ALLOWED_PORTFOLIO_REVIEW_FLAG,
    display_path,
)

ORDER_DRAFT_INPUT = ORDER_DRAFT_OUTPUT_PATH
ORDER_REVIEW_OUTPUT = ORDER_REVIEW_OUTPUT_PATH
REVIEW_COMPLETE = "REVIEW_COMPLETE"
NO_ORDERS_TO_REVIEW = "NO_ORDERS_TO_REVIEW"



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
    numeric = [row.get("TargetShares"), row.get("LatestClose"), row.get("EstimatedOrderValue")]
    try: valid_numeric = np.isfinite([float(value) for value in numeric]).all()
    except (TypeError, ValueError): valid_numeric = False
    if not valid_numeric or float(row.get("TargetShares", 0)) <= 0 or float(row.get("LatestClose", 0)) <= 0 or float(row.get("EstimatedOrderValue", 0)) <= 0:
        return "BLOCKED"
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
    if pd.isna(row.get("FundamentalRating")) or str(row.get("FundamentalRating", "")).strip().upper() in ("", "MISSING"):
        return "REVIEW"

    return "PASS"


def assign_review_reason(row):
    reasons = []
    numeric_fields = ("TargetShares", "LatestClose", "EstimatedOrderValue")
    for field in numeric_fields:
        try: valid = np.isfinite(float(row.get(field)))
        except (TypeError, ValueError): valid = False
        if not valid: reasons.append(f"{field} must be finite")

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
    if pd.isna(row.get("FundamentalRating")) or str(row.get("FundamentalRating", "")).strip().upper() in ("", "MISSING"):
        reasons.append("fundamental rating missing; manual review required")

    if not reasons:
        return "no issue"

    return "; ".join(reasons)


def build_order_review(order_df=None):
    order_df = load_order_draft().copy() if order_df is None else order_df.copy()
    missing = [column for column in REQUIRED_COLUMNS if column not in order_df]
    if missing: raise ValueError(f"Missing required columns: {missing}")

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

    blocked_count = int((order_df["ReviewStatus"] == "BLOCKED").sum())
    review_count = int((order_df["ReviewStatus"] == "REVIEW").sum())

    if order_df.empty:
        order_df["PortfolioReviewFlag"] = pd.Series(dtype="object")
        order_df["PortfolioReviewReason"] = pd.Series(dtype="object")
        order_df.attrs["ReviewStatus"] = NO_ORDERS_TO_REVIEW
        order_df.attrs["PortfolioReviewFlag"] = "NOT_APPLICABLE"
    elif blocked_count:
        order_df["PortfolioReviewFlag"] = "BLOCKED"
        order_df["PortfolioReviewReason"] = "one or more orders failed validation"
    elif review_count or portfolio_level_warnings:
        order_df["PortfolioReviewFlag"] = "REVIEW_REQUIRED"
        order_df["PortfolioReviewReason"] = "; ".join(
            (["one or more orders require manual review"] if review_count else [])
            + portfolio_level_warnings
        )
    else:
        order_df["PortfolioReviewFlag"] = "PASS"
        order_df["PortfolioReviewReason"] = "portfolio level checks passed"
    if not order_df.empty: order_df.attrs["ReviewStatus"] = REVIEW_COMPLETE
    return order_df


def save_order_review(order_df):
    ORDER_REVIEW_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

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
    portfolio_flag = review_df.attrs.get("PortfolioReviewFlag", review_df["PortfolioReviewFlag"].iloc[0] if not review_df.empty else "NOT_APPLICABLE")
    print(f"Portfolio Flag        : {portfolio_flag}")
    print(f"Saved Order Review To : {display_path(output_path)}")


if __name__ == "__main__":
    print_order_review()
