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
1. `print_config_validation()`
2. `print_system_version()`
3. `print_model_portfolio()`
4. `validate_portfolio_outputs()`
5. `print_position_sizing()`
6. `validate_position_sizing_outputs()`
7. `print_order_draft()`
8. `validate_order_draft_outputs()`
9. `print_order_review()`
10. `validate_order_review_outputs()`
11. `print_portfolio_action_report()`
12. `print_daily_decision_report()`
13. `validate_daily_decision_report_outputs()`
14. `run_system_health_check()`

The full portfolio pipeline currently runs:
1. validate config settings
2. generate system version report
3. build model portfolio
4. validate portfolio outputs
5. calculate position sizing
6. validate position sizing outputs
7. generate order draft
8. validate order draft outputs
9. review order draft
10. validate order review outputs
11. generate portfolio action report
12. generate daily decision report
13. validate daily decision report outputs
14. run system health check
15. write a portfolio pipeline log

Current portfolio risk rules:

- maximum single position weight: 10%
- maximum total exposure: 80%
- maximum holdings: 10
- cash reserve: 20%

## Config Validation Failure Demo

Run the config validation failure demo manually:

```bash
python3 config_validation_failure_demo.py
```
This script intentionally injects invalid config values into the validation module during runtime.

It is used to confirm that validate_config.py can detect unsafe or invalid settings, including:

1. negative account value
2. total exposure above 100%
3. cash reserve plus exposure above 100%
4. zero max order count
5. missing BUY action
6. project version missing the v prefix

Important safety notes:

- this script does not modify config.py on disk
- this script restores temporary values after each test case
- this script is for manual testing only
- this script must not be integrated into run_portfolio.py
- this script does not place trades

## Main Output Files

System version report:

results/system_version.txt

This file records the current system version, Git branch, latest Git tag, current commit, Python version, core modules, and validation modules.

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

## V2 Portfolio Pipeline Development

V2.0.0 Risk and Portfolio Layer
- portfolio exposure
- position limits
- sector concentration
- drawdown control

V2.1.0 risk adjusted portfolio weights:
- reads qualified backtest candidates
- assigns risk levels to candidates
- applies risk weight multipliers
- normalizes portfolio weights after risk adjustment
- limits portfolio exposure according to risk rules

V2.2.0 position sizing pipeline:
- calculates target dollar amount from account value
- converts portfolio weights into target position sizes
- prepares model portfolio sizing output
- creates the foundation for later share-based sizing

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

V2.6.0 portfolio action report:
- reads `results/order_review.csv`
- summarizes PASS / REVIEW / BLOCKED order counts
- calculates total estimated order value
- lists manual review items
- writes `results/portfolio_action_report.txt`

V2.6.1 portfolio action report integration:
- integrates `portfolio_action_report.py` into `run_portfolio.py`
- runs the portfolio action report after order review validation
- confirms reviewed orders before daily decision reporting

V2.7.0 daily decision report module:
- creates `daily_decision_report.py`
- combines the daily technical screening report with the portfolio action report
- adds final safety reminders
- writes `reports/daily_decision_report_YYYY-MM-DD.txt`

V2.7.1 daily decision report integration:
- integrates `daily_decision_report.py` into `run_portfolio.py`
- runs the daily decision report near the end of the full portfolio pipeline
- confirms technical screening and portfolio action review are shown together

V2.7.2 daily decision report validation:
- creates `validate_daily_decision_report_outputs.py`
- checks required daily decision report sections
- checks required safety warning text
- raises validation errors when report output is incomplete

V2.7.3 daily decision report validation integration:
- integrates daily decision report validation into `run_portfolio.py`
- validates the daily decision report after it is generated
- confirms the final decision report is complete before system health check

V2.8.0 system health check:
- creates `system_health_check.py`
- checks required source files
- checks required output directories
- checks key `.gitignore` rules
- validates the project structure before future development

V2.8.1 system health check integration:
- integrates `system_health_check.py` into `run_portfolio.py`
- runs the health check at the end of the full portfolio pipeline
- confirms source files, output directories, and ignore rules after each full run

V2.8.2 system health check documentation:
- documents the system health check in `README.md`
- records required files, directories, and Git ignore rules
- clarifies that generated output files should not be committed

V2.9.0 system version report:
- creates `system_version.py`
- records project version, Git branch, Git commit, and Python version
- checks core module and validation module status
- writes `results/system_version.txt`

V2.9.1 system version report integration:
- integrates `system_version.py` into `run_portfolio.py`
- runs the system version report at the beginning of the full portfolio pipeline
- records version information before pipeline execution

V2.9.2 system version report documentation:
- documents the system version report in `README.md`
- records how version tracking supports debugging and release review
- clarifies that the version report does not place trades

V2.10.0 central configuration module:
- creates `config.py` as the central configuration file
- stores account value, portfolio risk settings, order review rules, output directories, and output file paths
- keeps older variable names for backward compatibility

V2.10.1 portfolio risk config integration:
- reads portfolio risk parameters from `config.py`
- uses configured max holdings, max position weight, total exposure, cash reserve, and risk multipliers

V2.10.2 position sizing config integration:
- reads account value, cash reserve ratio, model portfolio output, and position sizing output from `config.py`
- reduces hard-coded sizing paths and account assumptions

V2.10.3 order draft config integration:
- reads position sizing input, order draft output, allowed action, and default order status from `config.py`

V2.10.4 order review config integration:
- reads order draft input, order review output, order limits, allowed actions, and review status rules from `config.py`

V2.10.5 order review validation config integration:
- reads order review output, allowed review statuses, order limits, and portfolio review flag rules from `config.py`

V2.10.6 portfolio action report config integration:
- reads order review input and portfolio action report output from `config.py`

V2.10.7 daily decision report config integration:
- reads portfolio action report output and report directory from `config.py`
- combines daily technical report and portfolio action report into a daily decision report

V2.10.8 daily decision validation config integration:
- reads report directory from `config.py`
- validates daily decision report sections and safety warnings

V2.10.9 system health check config integration:
- reads required output directories from `config.py`
- confirms project folders, source files, and Git ignore rules

V2.10.10 system version config integration:
- reads project version and system version output path from `config.py`
- writes `results/system_version.txt`
- records current project version, Git branch, Git commit, Python version, and module status

V2.11.0 config validation module:
- creates `validate_config.py`
- validates account settings, portfolio risk settings, order review settings, output paths, and project version
- fails fast when unsafe or invalid configuration values are detected
- confirms that `config.py` is safe before pipeline execution

V2.11.1 config validation integration:
- integrates `validate_config.py` into `run_portfolio.py`
- runs config validation at the beginning of the full portfolio pipeline
- stops the pipeline before report or order generation if configuration is invalid

V2.11.2 config validation system registration:
- registers `validate_config.py` in `system_health_check.py`
- registers `validate_config.py` in `system_version.py`
- confirms the config validation module is tracked by health checks and version reports

V2.12.0 config validation failure demo:
- creates `config_validation_failure_demo.py`
- intentionally injects invalid configuration values for testing
- confirms that `validate_config.py` detects unsafe or invalid settings
- restores temporary values after each failure case
- does not modify `config.py` on disk
- is a manual test script and is not part of the live portfolio pipeline

V2.12.1 config validation failure demo registration:
- registers `config_validation_failure_demo.py` in `system_health_check.py`
- registers `config_validation_failure_demo.py` in `system_version.py`
- confirms the failure demo script is tracked by system health checks and version reports
- keeps the failure demo outside `run_portfolio.py`

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