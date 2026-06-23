import pandas as pd
from pathlib import Path

# 读取CSV
summary_df = pd.read_csv("results/summary.csv")
rank_df = pd.read_csv("results/stock_rank.csv")
risk_df = pd.read_csv("results/risk_analysis.csv")
sharpe_df = pd.read_csv("results/sharpe_analysis.csv")

tickers = ["AAPL", "NVDA", "TSLA", "AMD", "GOOGL"]

charts_html = ""

for ticker in tickers:

    chart_file = f"charts/{ticker}_chart.png"

    charts_html += f"""
    <h2>{ticker} Chart</h2>

    <img src="{chart_file}"
         width="900">
    """
# HTML内容
html_content = f"""
<html>

<head>
    <title>AI Investing Report</title>

    <style>

        body {{
            font-family: Arial;
            margin: 40px;
            background-color: #f5f5f5;
        }}

        h1 {{
            color: #333;
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            background-color: white;
            margin-bottom: 40px;
        }}

        th, td {{
            border: 1px solid #ccc;
            padding: 10px;
            text-align: center;
        }}

        th {{
            background-color: #222;
            color: white;
        }}

    </style>

</head>

<body>

    <h1>AI Investing Report</h1>

    <h2>Summary</h2>
    {summary_df.to_html(index=False)}

    <h2>Stock Ranking</h2>
    {rank_df.to_html(index=False)}

    <h2>Risk Analysis</h2>
    {risk_df.to_html(index=False)}

    <h2>Sharpe Ratio Analysis</h2>
    {sharpe_df.to_html(index=False)}
    
    <h2>Stock Charts</h2>
    {charts_html}
</body>

</html>
"""

# 保存HTML
with open("reports/ai_report.html", "w") as file:
    file.write(html_content)

print("HTML报告已生成: reports/ai_report.html")