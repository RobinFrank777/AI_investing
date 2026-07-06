import pandas as pd


QUALIFIED_BACKTEST_OUTPUT = "results/backtest_qualified_20d.csv"
MODEL_PORTFOLIO_OUTPUT = "results/model_portfolio.csv"

MAX_POSITION_WEIGHT = 0.10
MAX_TOTAL_EXPOSURE = 0.80
MAX_HOLDINGS = 10

RISK_LEVEL_WEIGHT_MULTIPLIERS = {
    "Low": 1.00,
    "Medium": 0.80,
    "High": 0.50,
    "Unknown": 0.40,
}

def load_qualified_candidates():
    df = pd.read_csv(QUALIFIED_BACKTEST_OUTPUT)

    df = df.sort_values(
        by="BacktestScore",
        ascending=False,
    )

    return df

def assign_risk_level(row):
    max_drawdown = row["MaxDrawdown"]
    sharpe_ratio = row["SharpeRatio"]

    if pd.isna(max_drawdown) or pd.isna(sharpe_ratio):
        return "Unknown"

    if max_drawdown >= -0.10 and sharpe_ratio >= 2:
        return "Low"

    if max_drawdown >= -0.25 and sharpe_ratio >= 1:
        return "Medium"

    return "High"

def get_risk_weight_multiplier(risk_level):
    return RISK_LEVEL_WEIGHT_MULTIPLIERS.get(
        risk_level,
        RISK_LEVEL_WEIGHT_MULTIPLIERS["Unknown"],
    )

def build_model_portfolio():
    candidates_df = load_qualified_candidates()

    selected_df = candidates_df.head(MAX_HOLDINGS).copy()

    selected_df["RiskLevel"] = selected_df.apply(
        assign_risk_level,
        axis=1,
    )

    selected_df["RiskWeightMultiplier"] = selected_df["RiskLevel"].apply(
        get_risk_weight_multiplier
    )

    multiplier_sum = selected_df["RiskWeightMultiplier"].sum()

    selected_df["TargetWeight"] = (
        selected_df["RiskWeightMultiplier"] / multiplier_sum * MAX_TOTAL_EXPOSURE
    ).clip(upper=MAX_POSITION_WEIGHT)

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
                "RiskLevel",
                "RiskWeightMultiplier",
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