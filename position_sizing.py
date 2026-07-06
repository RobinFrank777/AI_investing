import pandas as pd
from pathlib import Path


MODEL_PORTFOLIO_INPUT = "results/model_portfolio.csv"
POSITION_SIZING_OUTPUT = "results/model_portfolio_sizing.csv"

ACCOUNT_VALUE = 100000


def load_model_portfolio():
    portfolio_df = pd.read_csv(MODEL_PORTFOLIO_INPUT)

    portfolio_df = portfolio_df.sort_values(
        by="BacktestScore",
        ascending=False,
    )

    return portfolio_df


def add_target_dollar_amount(portfolio_df):
    portfolio_df = portfolio_df.copy()

    portfolio_df["AccountValue"] = ACCOUNT_VALUE

    portfolio_df["TargetDollarAmount"] = (
        portfolio_df["TargetWeight"] * ACCOUNT_VALUE
    ).round(2)

    return portfolio_df


def save_position_sizing(position_df):
    output_path = Path(POSITION_SIZING_OUTPUT)
    output_path.parent.mkdir(exist_ok=True)

    position_df.to_csv(
        output_path,
        index=False,
    )

    return output_path


def print_position_sizing():
    portfolio_df = load_model_portfolio()
    position_df = add_target_dollar_amount(portfolio_df)
    output_path = save_position_sizing(position_df)

    print("=" * 70)
    print("POSITION SIZING")
    print("=" * 70)

    print(
        position_df[
            [
                "Ticker",
                "BacktestScore",
                "RiskLevel",
                "RiskWeightMultiplier",
                "TargetWeightPercent",
                "AccountValue",
                "TargetDollarAmount",
                "PortfolioRole",
            ]
        ].to_string(index=False)
    )

    total_target_amount = position_df["TargetDollarAmount"].sum()
    cash_reserve = ACCOUNT_VALUE - total_target_amount

    print("\nPosition Sizing Summary")
    print(f"Account Value       : ${ACCOUNT_VALUE:,.2f}")
    print(f"Target Invested     : ${total_target_amount:,.2f}")
    print(f"Cash Reserve        : ${cash_reserve:,.2f}")
    print(f"Saved Position Size : {output_path}")


if __name__ == "__main__":
    print_position_sizing()