import pandas as pd
from pathlib import Path

from config import (
    ACCOUNT_VALUE,
    CASH_RESERVE_RATIO,
    MODEL_PORTFOLIO_OUTPUT as CONFIG_MODEL_PORTFOLIO_OUTPUT,
    POSITION_SIZING_OUTPUT as CONFIG_POSITION_SIZING_OUTPUT,
)

MODEL_PORTFOLIO_INPUT = Path(CONFIG_MODEL_PORTFOLIO_OUTPUT)
POSITION_SIZING_OUTPUT = Path(CONFIG_POSITION_SIZING_OUTPUT)
STOCK_DATA_DIR = Path("data")



def load_model_portfolio():
    portfolio_df = pd.read_csv(MODEL_PORTFOLIO_INPUT)

    portfolio_df = portfolio_df.sort_values(
        by="BacktestScore",
        ascending=False,
    )

    return portfolio_df

def get_latest_close(ticker):
    stock_path = STOCK_DATA_DIR / f"{ticker}.csv"

    if not stock_path.exists():
        raise FileNotFoundError(
            f"Missing stock data file for {ticker}: {stock_path}"
        )

    stock_df = pd.read_csv(stock_path)

    if "Close" not in stock_df.columns:
        raise ValueError(
            f"Missing Close column for {ticker}: {stock_path}"
        )

    close_series = pd.to_numeric(
        stock_df["Close"],
        errors="coerce",
    ).dropna()

    if close_series.empty:
        raise ValueError(
            f"No valid Close price for {ticker}: {stock_path}"
        )

    return close_series.iloc[-1]

def add_target_dollar_amount(portfolio_df):
    portfolio_df = portfolio_df.copy()

    portfolio_df["AccountValue"] = ACCOUNT_VALUE

    portfolio_df["TargetDollarAmount"] = (
        portfolio_df["TargetWeight"] * ACCOUNT_VALUE
    ).round(2)

    return portfolio_df

def add_share_sizing(position_df):
    position_df = position_df.copy()

    position_df["LatestClose"] = position_df["Ticker"].apply(get_latest_close)

    position_df["TargetShares"] = (
        position_df["TargetDollarAmount"] / position_df["LatestClose"]
    ).astype(int)

    position_df["EstimatedPositionValue"] = (
        position_df["TargetShares"] * position_df["LatestClose"]
    ).round(2)

    position_df["PositionCashRemainder"] = (
        position_df["TargetDollarAmount"] - position_df["EstimatedPositionValue"]
    ).round(2)

    return position_df

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
    position_df = add_share_sizing(position_df)
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
                "LatestClose",
                "TargetDollarAmount",
                "TargetShares",
                "EstimatedPositionValue",
                "PositionCashRemainder",
                "PortfolioRole",
            ]
        ].to_string(index=False)
    )

    total_target_amount = position_df["TargetDollarAmount"].sum()
    estimated_invested = position_df["EstimatedPositionValue"].sum()
    cash_reserve = ACCOUNT_VALUE - estimated_invested

    print(f"Account Value       : ${ACCOUNT_VALUE:,.2f}")
    print(f"Cash Reserve Ratio  : {CASH_RESERVE_RATIO:.0%}")
    print(f"Target Invested     : ${total_target_amount:,.2f}")
    print(f"Estimated Invested  : ${estimated_invested:,.2f}")
    print(f"Cash Reserve        : ${cash_reserve:,.2f}")
    print(f"Saved Position Size : {output_path}")


if __name__ == "__main__":
    print_position_sizing()