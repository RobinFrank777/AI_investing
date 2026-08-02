# AI_investing Module Catalog

## Document status

This document describes the current module structure observed in AI_investing V3.2.1.

It is a documentation catalog only. It does not change trading logic, portfolio rules, scoring formulas, or execution behavior.

AI_investing is a personal, AI-assisted investing research system. It produces screening results, backtest summaries, portfolio research outputs, draft-only order reviews, and human-readable reports. It does not connect to a brokerage account or place trades.

---

## Module status definitions

| Status | Meaning |
|---|---|
| Active | Current module used by one of the main pipelines. |
| Validation | Module that checks output files, schemas, formulas, or configured rules. |
| Test | Manual or smoke-test script used for system checks. |
| Utility | Supporting script or helper module. |
| Legacy / Experimental | Older, exploratory, or not yet classified script. |
| Practice | Learning or practice code, not part of the production pipeline. |

---

## Primary entry points

| Module | Pipeline | Purpose | Main inputs | Main outputs | Status |
|---|---|---|---|---|---|
| `run_daily.py` | Daily screening | Runs the daily data, ranking, and report pipeline. | `data/watchlist.csv`, downloaded price data | `results/stock_rank.csv`, `results/top10.csv`,`reports/daily_trading_report_<date>.txt` | Active |
| `run_backtest.py` | Backtest | Runs the 20-day backtest pipeline and validates outputs. | `data/watchlist.csv`, `data/<ticker>.csv` | `results/backtest_summary_20d.csv`, `results/backtest_qualified_20d.csv`, `results/backtest_all_trades_20d.csv` | Active |
| `run_portfolio.py` | Portfolio research | Runs the portfolio research, scoring, sizing, order review, and decision-report pipeline. | Backtest outputs, fundamentals, price data, daily report | Portfolio research CSVs and reports | Active |

---

## Configuration and system modules

| Module | Purpose | Main inputs | Main outputs | Status |
|---|---|---|---|---|
| `config.py` | Central configuration for account, risk, output paths, order rules, and project version. | Manual configuration constants | Shared constants used by pipeline modules | Active |
| `system_version.py` | Generates system version and module inventory report. | `config.py`, Git metadata | `results/system_version.txt` | Active |
| `system_health_check.py` | Checks required source files, validators, test modules, directories, and `.gitignore` rules. | Project structure | Health-check output in terminal | Active |

---

## Daily screening modules

| Module | Purpose | Main inputs | Main outputs | Status |
|---|---|---|---|---|
| `update_data.py` | Downloads or updates market data. | `data/watchlist.csv` | `data/<ticker>.csv` | Active |
| `watchlist.py` | Loads the ticker universe. | `data/watchlist.csv` | Ticker list | Active |
| `stock_loader.py` | Loads per-ticker price data. | `data/<ticker>.csv` | DataFrame for each ticker | Active |
| `data_validator.py` | Checks market-data quality. | Price DataFrames | Data-quality results | Active |
| `indicators.py` | Calculates technical indicators. | Price DataFrames | Indicator columns | Active |
| `trade_signal.py` | Produces BUY, WATCH, or IGNORE classifications. | Technical indicators | Signal classification | Active |
| `score.py` | Calculates technical ranking scores. | Signals and indicators | Score fields | Active |
| `position.py` | Calculates risk-based position information for screening. | Score and risk inputs | Position-related fields | Active |
| `reason.py` | Produces plain-language signal reasons. | Signals and indicators | Human-readable reasons | Active |
| `report.py` | Generates daily technical reports. | Ranking output | Daily trading report text | Active |
| `rank_stocks_v2.py` | Current stock-ranking orchestrator. | Market data and scoring modules | `results/stock_rank.csv`, `results/top10.csv` | Active |
| `rank_stocks.py` | Earlier ranking implementation. | Market data | Ranking output | Legacy / Experimental |

---

## Backtest modules

| Module | Purpose | Main inputs | Main outputs | Status |
|---|---|---|---|---|
| `backtest_engine.py` | Runs historical signal testing, trade simulation, performance scoring, and qualification. | `data/watchlist.csv`, `data/<ticker>.csv` | `results/backtest_summary_20d.csv`, `results/backtest_qualified_20d.csv`, `results/backtest_all_trades_20d.csv` | Active |
| `validate_backtest_outputs.py` | Validates backtest output artifacts. | Backtest CSV outputs | Validation result in terminal | Validation |

---

## Portfolio research modules

| Module | Purpose | Main inputs | Main outputs | Status |
|---|---|---|---|---|
| `portfolio_risk.py` | Builds a model portfolio from qualified backtest candidates and applies risk-adjusted weights. | `results/backtest_qualified_20d.csv` | `results/model_portfolio.csv` | Active |
| `fundamental_scoring.py` | Scores manually maintained fundamental data. | `data/fundamentals.csv` | `results/fundamental_score.csv` | Active |
| `combined_scoring.py` | Combines backtest score and fundamental score. | `results/model_portfolio.csv`, `results/fundamental_score.csv` | `results/combined_score.csv` | Active |
| `position_sizing.py` | Converts model portfolio weights into dollar allocation and target shares. | Model portfolio, combined score, price data | `results/model_portfolio_sizing.csv` | Active |
| `order_draft.py` | Creates draft-only research orders. | `results/model_portfolio_sizing.csv` | `results/order_draft.csv` | Active |
| `order_review.py` | Applies order and portfolio review rules. | `results/order_draft.csv` | `results/order_review.csv` | Active |
| `portfolio_action_report.py` | Produces a human-readable portfolio action summary. | `results/order_review.csv` | `results/portfolio_action_report.txt` | Active |
| `daily_decision_report.py` | Combines daily technical report and portfolio action report. | Daily trading report, portfolio action report | `reports/daily_decision_report_<date>.txt` | Active |

---

## Validation modules

| Module | Purpose | Main inputs | Main outputs | Status |
|---|---|---|---|---|
| `validate_config.py` | Validates configuration values and configured constraints. | `config.py` | Terminal validation result | Validation |
| `validate_portfolio_outputs.py` | Validates model portfolio output. | `results/model_portfolio.csv` | Terminal validation result | Validation |
| `validate_fundamental_outputs.py` | Validates fundamental score output. | `results/fundamental_score.csv` | Terminal validation result | Validation |
| `validate_combined_outputs.py` | Validates combined score output and score formula. | `results/combined_score.csv` | Terminal validation result | Validation |
| `validate_position_sizing_outputs.py` | Validates position sizing formulas and risk constraints. | `results/model_portfolio_sizing.csv` | Terminal validation result | Validation |
| `validate_order_draft_outputs.py` | Validates order draft output. | `results/order_draft.csv` | Terminal validation result | Validation |
| `validate_order_review_outputs.py` | Validates order review output. | `results/order_review.csv` | Terminal validation result | Validation |
| `validate_daily_decision_report_outputs.py` | Validates daily decision report text output. | `reports/daily_decision_report_<date>.txt` | Terminal validation result | Validation |

---

## Test and smoke-check modules

| Module | Purpose | Main inputs | Main outputs | Status |
|---|---|---|---|---|
| `config_validation_failure_demo.py` | Demonstrates that invalid configuration values are rejected. | Runtime-mutated config values | Terminal result | Test |
| `pipeline_smoke_test.py` | Runs high-level smoke checks for the portfolio pipeline. | Project files and configured outputs | Terminal result | Test |

---

## Utility, legacy, and experimental modules

The following modules exist in the project but are not currently documented as part of the main V3.2 pipeline contract.

They should not be deleted or moved until their status and unique functionality are reviewed.

| Module | Status | Current handling |
|---|---|---|
| `analyze_stock.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `compare_stocks.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `fetch_stock.py` | Utility / Legacy | Keep for review; not part of V3.2 active pipeline. |
| `generate_report.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `heatmap.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `holding_chart.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `holding_period.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `plot_top10.py` | Utility / Legacy | Keep for review; not part of V3.2 active pipeline. |
| `portfolio_metrics.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `portfolio_report.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `portfolio_v3.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `risk_analysis.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `risk_return_chart.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `sharpe_analysis.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `stock_personality.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `stock_personality_chart.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |
| `stock_score.py` | Legacy / Experimental | Keep for review; not part of V3.2 active pipeline. |

Current status:

| Category | Rule |
|---|---|
| Active pipeline modules | May be updated only through versioned changes and validation. |
| Validation modules | Must remain aligned with producer outputs. |
| Test modules | May be expanded but should not change trading logic. |
| Legacy / experimental modules | Do not modify unless explicitly reviewed. |
| Practice modules | Keep separate from production pipeline decisions. |

---

## Practice directory

The `practice/` directory contains learning and experimentation files.

It is not part of the production AI_investing pipeline and should not be used as a source of trading, scoring, or validation logic unless explicitly promoted through a reviewed version.

---

## Current main pipeline map

```text
run_daily.py
    -> update_data.py
    -> rank_stocks_v2.py
        -> results/stock_rank.csv
        -> results/top10.csv
    -> report.py
    -> reports/daily_trading_report_<date>.txt

run_backtest.py
    -> backtest_engine.py
    -> validate_backtest_outputs.py
    -> results/backtest_summary_20d.csv
    -> results/backtest_qualified_20d.csv
    -> results/backtest_all_trades_20d.csv

run_portfolio.py
    -> validate_config.py
    -> system_version.py
    -> portfolio_risk.py
    -> validate_portfolio_outputs.py
    -> fundamental_scoring.py
    -> validate_fundamental_outputs.py
    -> combined_scoring.py
    -> validate_combined_outputs.py
    -> position_sizing.py
    -> validate_position_sizing_outputs.py
    -> order_draft.py
    -> validate_order_draft_outputs.py
    -> order_review.py
    -> validate_order_review_outputs.py
    -> portfolio_action_report.py
    -> daily_decision_report.py
    -> validate_daily_decision_report_outputs.py
    -> system_health_check.py

```
## Safety note

Module classification is not an execution instruction.

A module marked as Active means it participates in the research pipeline. It does not mean the system is authorized to trade.

All generated orders remain draft-only. Real trading requires independent human review.