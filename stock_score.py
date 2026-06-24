import pandas as pd


def calculate_score(df):

    df["Return Score"] = (
        df["Annual Return %"]
        / df["Annual Return %"].max()
    )

    df["Sharpe Score"] = (
        df["Sharpe"]
        / df["Sharpe"].max()
    )

    df["Drawdown Score"] = (
        1
        - df["Max Drawdown %"]
        / df["Max Drawdown %"].max()
    )

    df["Volatility Score"] = (
        1
        - df["Annual Volatility %"]
        / df["Annual Volatility %"].max()
    )

    df["Final Score"] = (
        df["Return Score"] * 0.4
        + df["Sharpe Score"] * 0.3
        + df["Drawdown Score"] * 0.2
        + df["Volatility Score"] * 0.1
    )

    df = df.sort_values(
        by="Final Score",
        ascending=False
    )

    return df


if __name__ == "__main__":

    df = pd.read_csv("results/stock_personality.csv")

    df = calculate_score(df)

    print(
        df[
            [
                "Ticker",
                "Final Score"
            ]
        ]
    )