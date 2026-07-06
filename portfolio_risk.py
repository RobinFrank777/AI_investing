import pandas as pd


QUALIFIED_BACKTEST_OUTPUT = "results/backtest_qualified_20d.csv"
MODEL_PORTFOLIO_OUTPUT = "results/model_portfolio.csv"

MAX_POSITION_WEIGHT = 0.10
MAX_TOTAL_EXPOSURE = 0.80
MAX_HOLDINGS = 10


def load_qualified_candidates():
    df = pd.read_csv(QUALIFIED_BACKTEST_OUTPUT)

    df = df.sort_values(
        by="BacktestScore",
        ascending=False,
    )

    return df


def build_model_portfolio():
    candidates_df = load_qualified_candidates()

    selected_df = candidates_df.head(MAX_HOLDINGS).copy()

    equal_weight = MAX_TOTAL_EXPOSURE / len(selected_df)

    position_weight = min(
        equal_weight,
        MAX_POSITION_WEIGHT,
    )

    selected_df["TargetWeight"] = position_weight

    selected_df["TargetWeightPercent"] = (
        selected_df["TargetWeight"] * 100
    ).round(2).astype(str) + "%"

    selected_df["PortfolioRole"] = "candidate"

    return selected_df

def save_model_portfolio(portfolio_df):
    portfolio_df.to_csv(
        MODEL_PORTFOLIO_OUTPUT,
        index=False,
    )

    return MODEL_PORTFOLIO_OUTPUT

def print_model_portfolio():
    portfolio_df = build_model_portfolio()

    print("=" * 70)
    print("MODEL PORTFOLIO")
    print("=" * 70)

    print(
        portfolio_df[
            [
                "Ticker",
                "BacktestScore",
                "AverageReturn",
                "WinRate",
                "MaxDrawdown",
                "SharpeRatio",
                "TargetWeightPercent",
                "PortfolioRole",
            ]
        ].to_string(index=False)
    )

    total_weight = portfolio_df["TargetWeight"].sum()
    output_path = save_model_portfolio(portfolio_df)

    print("\nPortfolio Summary")
    print(f"Holdings Count             : {len(portfolio_df)}")
    print(f"Total Exposure             : {total_weight:.2%}")
    print(f"Cash Reserve               : {1 - total_weight:.2%}")
    print(f"Saved Model Portfolio To   : {output_path}")


if __name__ == "__main__":
    print_model_portfolio()