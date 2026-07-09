from pathlib import Path
from datetime import datetime

import pandas as pd
from config import (
    ORDER_REVIEW_OUTPUT as CONFIG_ORDER_REVIEW_OUTPUT,
    PORTFOLIO_ACTION_REPORT_OUTPUT as CONFIG_PORTFOLIO_ACTION_REPORT_OUTPUT,
)

ORDER_REVIEW_OUTPUT = Path(CONFIG_ORDER_REVIEW_OUTPUT)
ACTION_REPORT_OUTPUT = Path(CONFIG_PORTFOLIO_ACTION_REPORT_OUTPUT)

DISPLAY_COLUMNS = [
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
    "ReviewStatus",
    "ReviewReason",
]


def load_order_review():
    return pd.read_csv(ORDER_REVIEW_OUTPUT)


def build_action_report_text(order_df):
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    orders_count = len(order_df)
    pass_count = (order_df["ReviewStatus"] == "PASS").sum()
    review_count = (order_df["ReviewStatus"] == "REVIEW").sum()
    blocked_count = (order_df["ReviewStatus"] == "BLOCKED").sum()
    total_estimated_value = order_df["EstimatedOrderValue"].sum()

    lines = []

    lines.append("=" * 70)
    lines.append("AI INVESTING PORTFOLIO ACTION REPORT")
    lines.append("=" * 70)
    lines.append(f"Generated At           : {generated_at}")
    lines.append(f"Source File            : {ORDER_REVIEW_OUTPUT}")
    lines.append(f"Orders Count           : {orders_count}")
    lines.append(f"PASS Count             : {pass_count}")
    lines.append(f"REVIEW Count           : {review_count}")
    lines.append(f"BLOCKED Count          : {blocked_count}")
    lines.append(f"Total Estimated Value  : ${total_estimated_value:,.2f}")
    lines.append("")

    if blocked_count > 0:
        portfolio_decision = "DO NOT EXECUTE - BLOCKED ORDER EXISTS"
    elif review_count > 0:
        portfolio_decision = "MANUAL REVIEW REQUIRED"
    else:
        portfolio_decision = "READY FOR MANUAL CONFIRMATION"

    lines.append(f"Portfolio Decision     : {portfolio_decision}")
    lines.append("")

    lines.append("=" * 70)
    lines.append("ORDER DETAILS")
    lines.append("=" * 70)

    display_df = order_df[DISPLAY_COLUMNS].copy()

    lines.append(
        display_df.to_string(
            index=False,
            formatters={
                "BacktestScore": lambda x: f"{x:.2f}",
                "FundamentalScore": lambda x: f"{x:.2f}",
                "CombinedScore": lambda x: f"{x:.2f}",
                "LatestClose": lambda x: f"{x:,.2f}",
                "EstimatedOrderValue": lambda x: f"${x:,.2f}",
            },
        )
    )

    lines.append("")
    lines.append("=" * 70)
    lines.append("REVIEW ITEMS")
    lines.append("=" * 70)

    review_df = order_df[order_df["ReviewStatus"] != "PASS"]

    if review_df.empty:
        lines.append("No review items.")
    else:
        for _, row in review_df.iterrows():
            lines.append(
                f"- {row['Ticker']}: {row['ReviewStatus']} | "
                f"CombinedScore {row['CombinedScore']:.2f} | "
                f"FundamentalRating {row['FundamentalRating']} | "
                f"{row['ReviewReason']} | "
                f"Estimated value ${row['EstimatedOrderValue']:,.2f}"
            )

    lines.append("")
    lines.append("=" * 70)
    lines.append("IMPORTANT")
    lines.append("=" * 70)
    lines.append("This report is for manual review only.")
    lines.append("The system does not place real brokerage orders.")
    lines.append("All trades must be reviewed before execution.")

    return "\n".join(lines)


def save_action_report(report_text):
    output_path = Path(ACTION_REPORT_OUTPUT)
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    return output_path


def print_portfolio_action_report():
    order_df = load_order_review()
    report_text = build_action_report_text(order_df)
    output_path = save_action_report(report_text)

    print(report_text)
    print("")
    print(f"Saved Portfolio Action Report To : {output_path}")


if __name__ == "__main__":
    print_portfolio_action_report()