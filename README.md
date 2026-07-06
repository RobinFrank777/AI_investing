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

## Main Output Files

Daily trading report:

reports/daily_trading_report_YYYY-MM-DD.txt

Ranking result:

results/stock_rank.csv

Top 10 candidates:

results/top10.csv

Runtime log:

logs/daily_pipeline_YYYY-MM-DD.log

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

BacktestScore currently combines:

- average return
- win rate
- completed trade count
- worst trade risk
- max drawdown risk

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

V2.0 Risk and Portfolio Layer
- portfolio exposure
- position limits
- sector concentration
- drawdown control

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