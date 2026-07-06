## AI_investing

AI_investing is a technical stock screening and daily report system.

Current version:
AI_investing Technical Screener & Daily Report V1.0.1

## Current Purpose

This system is designed for:

updating market data
validating stock data quality
calculating technical indicators
ranking stocks
generating BUY / WATCH / IGNORE signals
generating a daily trading report

This system is not a verified automatic trading system.

Before a full backtest is completed, any BUY signal should be treated only as a candidate screening signal, not as a real trading instruction.

## Daily Usage

Run the full daily pipeline:

python3 run_daily.py

This command will automatically run:

1. update_all_stocks()
2. run_ranking_pipeline()

The pipeline will:

1. update market data
2. validate all watchlist data files
3. exclude invalid stocks
4. calculate indicators
5. rank stocks
6. generate stock signal cards
7. generate the daily trading report
8. write a runtime log

## Backtest Usage

Run the full backtest pipeline:

```bash
python3 run_backtest.py
```
This command will automatically run:

1. `backtest_watchlist(holding_days=20)`
2. `validate_backtest_outputs()`

The backtest pipeline will:

1. generate historical BUY / WATCH / IGNORE signals
2. detect EntrySignal days
3. simulate fixed 20-trading-day holding trades
4. run batch backtests across the full watchlist
5. save summary, qualified, and trade CSV files
6. validate that key CSV columns remain numeric

## Portfolio Usage

Run the full portfolio pipeline:

```bash
python3 run_portfolio.py
```
This command will automatically run:

1. `print_model_portfolio()`
2. `validate_portfolio_outputs()`
3. `print_position_sizing()`
4. `validate_position_sizing_outputs()`
5. `print_order_draft()`
6. `validate_order_draft_outputs()`
7. `print_order_review()`
8. `validate_order_review_outputs()`
9. `print_portfolio_action_report()`
10. `print_daily_decision_report()`
11. `validate_daily_decision_report_outputs()`
12. `run_system_health_check()`

The full portfolio pipeline currently runs:

1. build model portfolio
2. validate portfolio outputs
3. calculate position sizing
4. validate position sizing outputs
5. generate order draft
6. validate order draft outputs
7. review order draft
8. validate order review outputs
9. generate portfolio action report
10. generate daily decision report
11. validate daily decision report outputs
12. run system health check
13. write a portfolio pipeline log

Current portfolio risk rules:

- maximum single position weight: 10%
- maximum total exposure: 80%
- maximum holdings: 10
- cash reserve: 20%

## Main Output Files

Daily trading report:

reports/daily_trading_report_YYYY-MM-DD.txt

Ranking result:

results/stock_rank.csv

Top 10 candidates:

results/top10.csv

Runtime log:

logs/daily_pipeline_YYYY-MM-DD.log

Model portfolio:

results/model_portfolio.csv

This file contains the current model portfolio generated from qualified backtest candidates.

It includes:

- ticker
- backtest score
- historical return metrics
- risk metrics
- risk level
- risk weight multiplier
- target weight
- portfolio role

Position sizing:

results/model_portfolio_sizing.csv

This file converts model portfolio target weights into actual share sizing.

It includes:

- ticker
- backtest score
- risk level
- risk weight multiplier
- target weight
- target weight percent
- latest close price
- account value
- target dollar amount
- target shares
- estimated position value
- position cash remainder
- portfolio role

The position sizing output is validated by `validate_position_sizing_outputs.py`.

Current risk level rules:

- `Low`: MaxDrawdown >= -10% and SharpeRatio >= 2
- `Medium`: MaxDrawdown >= -25% and SharpeRatio >= 1
- `High`: all other cases
- `Unknown`: missing MaxDrawdown or SharpeRatio

Current risk weight multipliers:

- `Low`: 1.00
- `Medium`: 0.80
- `High`: 0.50
- `Unknown`: 0.40

The final target weight is calculated from normalized risk-adjusted weights:

risk weight multiplier / sum of all selected risk weight multipliers * maximum total exposure

Each position is still capped by the maximum single position weight.

The portfolio output is validated by `validate_portfolio_outputs.py`.

Portfolio pipeline log:

logs/portfolio_pipeline_YYYY-MM-DD.log

This file records the full terminal output from the model portfolio pipeline.

It includes:

- pipeline start time
- model portfolio table
- portfolio summary
- portfolio output validation result
- pipeline finish time

## Data Quality Rules

Before ranking, the system validates each stock file.

A stock may be excluded if:

- data file is missing
- required columns are missing
- Date column contains invalid values
- numeric columns contain invalid values
- duplicate dates exist
- historical data is less than 252 rows

A stock may receive a warning if:

- its latest data date is behind the universe latest date

Invalid stocks are excluded from ranking.
Warning-only stocks are kept in the ranking.

## Signal Meaning

The system currently produces three trade signals:

BUY
WATCH
IGNORE

Important rule:

BUY means "candidate for further review".
BUY does not mean "verified buy order".

## Git Rules

The following files are ignored by Git because they are generated automatically:

data/*.csv
results/*.csv
reports/daily_trading_report_*.txt
logs/*.log

Code files should still be committed.

Typical Git workflow:

git status
git diff --check
git add <changed_code_files>
git commit -m "Message"
git push
git status

## Current System Boundary

The current system is based mainly on technical indicators and rule-based scoring.

It does not yet include:

- full historical backtesting
- benchmark comparison
- slippage and transaction cost modeling
- portfolio-level risk simulation
- fundamental scoring
- AI analyst summary
- paper trading execution
- live broker connection

## Development Roadmap

Next development stages:

V1.0.1 System Hardening
- improve validation
- improve logging
- improve report reliability
- clean project structure

## V1.1 Backtesting Foundation

The system now includes a basic backtesting foundation.

Current backtest capabilities:

- generate historical BUY / WATCH / IGNORE signals
- detect EntrySignal to avoid counting repeated BUY days as separate entries
- simulate fixed 20-trading-day holding trades
- run batch backtests across the full watchlist
- save all historical simulated trades
- save per-stock backtest summaries
- filter qualified stocks using basic performance rules
- calculate BacktestScore for ranking qualified candidates

Main backtest output files:

- `results/backtest_summary_20d.csv`
- `results/backtest_qualified_20d.csv`
- `results/backtest_all_trades_20d.csv`
- `results/backtest_signals_<TICKER>.csv`
- `results/backtest_entries_<TICKER>.csv`
- `results/backtest_trades_<TICKER>_20d.csv`

Terminal backtest output:

The batch backtest prints two compact terminal tables:

1. `Top 10 by Average Return`

This table shows the stocks with the highest average fixed-holding trade return, regardless of whether they pass the qualified filter.

It is useful for research discovery, but some stocks in this table may have too few completed trades or may fail the qualified rules.

Displayed fields:

- `Ticker`
- `AverageReturn`
- `WinRate`
- `CompletedTradeCount`
- `TotalReturn`
- `MaxDrawdown`
- `SharpeRatio`
- `BacktestScore`
- `IsQualified`

2. `Qualified Top 10 by BacktestScore`

This table only includes stocks that pass the qualified filter.

It is the more important candidate list for further review.

Displayed fields:

- `Ticker`
- `BacktestScore`
- `CompletedTradeCount`
- `AverageReturn`
- `WinRate`
- `TotalReturn`
- `MaxDrawdown`
- `SharpeRatio`

Current backtest metrics:

- `EntrySignalCount`
- `CompletedTradeCount`
- `AverageReturn`
- `WinRate`
- `BestTrade`
- `WorstTrade`
- `TotalReturn`
- `MaxDrawdown`
- `CAGR`
- `SharpeRatio`
- `BacktestScore`

Backtest metric notes:

- `AverageReturn` is the average return of completed fixed-holding trades.
- `WinRate` is the percentage of completed trades with positive return.
- `TotalReturn` is calculated from the compounded sequence of simulated trades for one stock.
- `MaxDrawdown` is calculated from the simulated trade equity curve.
- `CAGR` is a simplified research metric based on the simulated trade sequence.
- `SharpeRatio` is a simplified trade-return-based Sharpe ratio.
- `BacktestScore` is used only for ranking research candidates.

Important warning:

`CAGR` and `TotalReturn` are not real portfolio-level returns.

They do not yet account for:

- position sizing
- overlapping trades
- cash availability
- transaction costs
- slippage
- portfolio allocation
- benchmark comparison
- real execution constraints

Therefore, a high `CAGR` should not be interpreted as a real achievable annual return.

Qualified stock rule:

A stock is currently marked as qualified if:

- `CompletedTradeCount >= 10`
- `AverageReturn > 0`
- `WinRate >= 0.5`
- no backtest error exists

BacktestScore formula:

The current `BacktestScore` is a rule-based research score.

It is calculated from the following components:

- `AverageReturnScore`
- `WinRateScore`
- `TradeCountScore`
- `RiskScore`
- `DrawdownScore`

Current scoring rules:

```text
AverageReturnScore =
    clipped AverageReturn between -20% and +30%
    × 100

WinRateScore =
    WinRate
    × 40

TradeCountScore =
    min(CompletedTradeCount, 30)
    / 30
    × 20

RiskScore =
    clipped (1 + WorstTrade) between 0 and 1
    × 10

DrawdownScore =
    clipped (1 + MaxDrawdown) between 0 and 1
    × 20

BacktestScore =
    AverageReturnScore
    + WinRateScore
    + TradeCountScore
    + RiskScore
    + DrawdownScore

```
Important limitation:

The current backtest is still a simplified research backtest. It does not yet include:

- transaction costs
- slippage
- position sizing
- overlapping portfolio positions
- benchmark comparison
- CAGR
- Sharpe ratio
- real order execution

Backtest output validation:

The system includes a validation script for backtest output CSV files:

```bash
python3 validate_backtest_outputs.py
```

This script checks that the following columns remain numeric in both summary and qualified output files:

AverageReturn
WinRate
TotalReturn
MaxDrawdown
SharpeRatio
BacktestScore

The terminal display may show percentage strings such as 45.08%, but the CSV files must keep raw numeric values such as 0.450785.

This is important because future analysis, scoring, charting, and portfolio simulation require numeric CSV data.

V2.0 Risk and Portfolio Layer
- portfolio exposure
- position limits
- sector concentration
- drawdown control

V2.3.0 actual share sizing:
- reads latest close price from `data/{Ticker}.csv`
- converts target dollar amount into target shares
- calculates estimated position value
- calculates remaining cash per position
- validates share sizing formulas

V2.4.0 order draft pipeline:
- reads `results/model_portfolio_sizing.csv`
- generates draft BUY orders
- keeps all orders in DRAFT_ONLY status
- calculates estimated order value
- writes `results/order_draft.csv`
- validates order draft output with `validate_order_draft_outputs.py`

V2.5.0 order review pipeline:
- reads `results/order_draft.csv`
- reviews each draft order before execution
- assigns ReviewStatus: PASS / REVIEW / BLOCKED
- flags high-risk orders for manual review
- checks maximum single order value
- checks portfolio-level total order value
- writes `results/order_review.csv`
- validates order review output with `validate_order_review_outputs.py`

Current order review rules:
- only BUY actions are allowed
- only DRAFT_ONLY orders are allowed
- TargetShares must be greater than 0
- EstimatedOrderValue must be greater than 0
- single order value above $10,000 requires REVIEW
- High risk level requires REVIEW
- total order value above $80,000 requires portfolio-level REVIEW
- order count above 10 requires portfolio-level REVIEW

V2.8.0 system health check:
- checks required source files
- checks required output directories
- checks key `.gitignore` rules
- confirms generated result files are ignored by Git
- validates the project structure before future development

V2.8.1 system health check integration:
- integrates `system_health_check.py` into `run_portfolio.py`
- runs the health check at the end of the full portfolio pipeline
- confirms source files, output directories, and ignore rules after each full run

V3.0 Fundamental Scoring
- PE, EPS, revenue growth, ROE
- quality and valuation filters

V4.0 AI Analyst Summary
- English stock commentary
- daily candidate explanation
- risk notes

V5.1 Paper Trading
- simulated order generation
- daily paper trade log
- performance tracking

---Robin