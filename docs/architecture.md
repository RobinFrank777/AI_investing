# AI_investing Architecture

## Document status

This document describes the AI_investing V3.2.x architecture baseline. It is a documentation proposal, not a specification for automatic trading and not evidence that every planned capability has been implemented.

AI_investing is a personal, AI-assisted investing research system. It produces screening results, backtest summaries, model-portfolio research, draft-only order reviews, and human-readable reports. It does not connect to a brokerage account or place trades. Any result intended to inform a real trade requires manual review.

## Design principles

The current system is intended to remain:

- Simple enough to inspect module by module.
- Explainable through explicit rules and intermediate artifacts.
- Verifiable through validation scripts and manual checks.
- Incremental, with one small version developed at a time.
- Human-controlled, with no automatic brokerage execution.

## Architectural style

The project is a flat, script-oriented Python application with three related pipelines:

1. Daily market-data and stock-ranking pipeline.
2. Historical backtest pipeline.
3. Portfolio research and manual-review pipeline.

Modules exchange data mainly through CSV and text files in `data/`, `results/`, `reports/`, and `logs/`. These files are the current integration contracts between pipeline stages.

The project does not currently use a database, service layer, package hierarchy, workflow engine, or brokerage adapter.

## System context

```text
data/watchlist.csv
data/<ticker>.csv
        |
        +--> Daily screening pipeline
        |       -> update_data.py
        |       -> rank_stocks_v2.py
        |       -> results/stock_rank.csv
        |       -> results/top10.csv
        |       -> report.py
        |       -> reports/daily_trading_report_<date>.txt
        |
        +--> Backtest pipeline
        |       -> backtest_engine.py
        |       -> results/backtest_summary_20d.csv
        |       -> results/backtest_qualified_20d.csv
        |       -> results/backtest_all_trades_20d.csv
        |
        +--> Portfolio research pipeline
                -> uses qualified backtest candidates
                -> uses manual fundamental data
                -> uses per-ticker market data
                -> produces draft-only outputs
                -> requires manual human review
```
The daily screening pipeline and the backtest pipeline both depend on market data, but they do not depend on each other.

The backtest pipeline reads `data/watchlist.csv` and `data/<ticker>.csv` directly. It does not consume `results/stock_rank.csv`, `results/top10.csv`, or `reports/daily_trading_report_<date>.txt`.
```
No component after the manual-review boundary submits, routes, or executes an order.

## Repository organization

The current repository has several categories of files at its root.

### Pipeline entry points

- `run_all.py`: runs the complete active research workflow in a fixed sequence
  with fail-closed step handling, artifact-freshness checks, logging, and a final
  runtime summary.
- `run_daily.py`: updates market data and runs the current ranking pipeline.
- `run_backtest.py`: runs batch historical backtests and validates their outputs.
- `run_portfolio.py`: orchestrates portfolio construction, scoring, sizing, draft-order review, reporting, and system checks.

### Daily screening modules

- `update_data.py`: downloads and stores market data.
- `watchlist.py`: loads the stock universe.
- `stock_loader.py`: loads stored stock data.
- `data_validator.py`: checks source-data quality.
- `indicators.py`: calculates technical indicators.
- `trade_signal.py`: assigns BUY, WATCH, or IGNORE signals.
- `score.py`: calculates ranking scores.
- `position.py`: provides ranking-stage position calculations.
- `reason.py`: creates readable signal explanations.
- `report.py`: generates daily ranking reports.
- `rank_stocks_v2.py`: coordinates the current ranking workflow.

### Backtest modules

- `backtest_engine.py`: creates historical signals, fixed-holding-period trades, performance summaries, qualification results, and backtest artifacts.
- `validate_backtest_outputs.py`: checks the generated backtest files.

### Portfolio research modules

- `portfolio_risk.py`: selects qualified backtest candidates and assigns risk-adjusted target weights.
- `fundamental_scoring.py`: scores manually supplied fundamental data.
- `combined_scoring.py`: combines backtest and fundamental scores.
- `position_sizing.py`: converts target weights to dollar and share quantities.
- `order_draft.py`: creates research-only, draft-status orders.
- `order_review.py`: applies order-level and portfolio-level review rules.
- `portfolio_action_report.py`: summarizes reviewed draft orders.
- `daily_decision_report.py`: combines the daily trading report and portfolio action report.

### Configuration and operational modules

- `config.py`: central source for account, risk, scoring, review, directory, and output-path settings.
- `validate_config.py`: validates configuration types, ranges, relationships, allowed values, and paths.
- `system_version.py`: writes a version and module inventory report.
- `system_health_check.py`: checks required files, input-contract recovery templates and their headers, runtime-directory readiness, and manual-input readiness.

### Output validators

- `validate_portfolio_outputs.py`
- `validate_fundamental_outputs.py`
- `validate_combined_outputs.py`
- `validate_position_sizing_outputs.py`
- `validate_order_draft_outputs.py`
- `validate_order_review_outputs.py`
- `validate_daily_decision_report_outputs.py`

### Manual test utilities

- `config_validation_failure_demo.py`: confirms that invalid runtime configuration is rejected without modifying `config.py` on disk.
- `pipeline_smoke_test.py`: runs configuration checks and the portfolio pipeline, then checks for required artifacts.

These are manual test scripts rather than a conventional automated unit-test suite.

### Other material

The root also contains earlier-generation analysis utilities and generated-looking artifacts. The `practice/` directory contains learning exercises and prototypes. These files are not clearly classified as supported, experimental, historical, or generated by the current architecture.

## Pipeline architecture

### Daily pipeline

Entry point: `run_daily.py`

```text
update_all_stocks()
    |
    v
data/<ticker>.csv
    |
    v
run_ranking_pipeline()
    |
    +--> data validation
    +--> indicator calculation
    +--> signal and score calculation
    +--> results/stock_rank.csv
    +--> results/top10.csv
    +--> reports/daily_trading_report_<date>.txt
```

The daily runner logs step failures and exits with a nonzero status when a step raises an exception.

### Backtest pipeline

Entry point: `run_backtest.py`

```text
data/<ticker>.csv
    |
    v
backtest_watchlist(holding_days=20)
    |
    +--> backtest summary
    +--> qualified candidates
    +--> historical trades
    |
    v
validate_backtest_outputs()
```

The qualified-candidate artifact, currently `results/backtest_qualified_20d.csv`, is the principal input to the portfolio pipeline.

### Portfolio pipeline

Entry point: `run_portfolio.py`

The actual execution order is:

1. Validate configuration.
2. Generate the system-version report.
3. Build the model portfolio.
4. Validate the model portfolio.
5. Calculate fundamental scores.
6. Validate fundamental scores.
7. Calculate combined scores.
8. Validate combined scores.
9. Calculate position sizing.
10. Validate position sizing.
11. Generate draft orders.
12. Validate draft orders.
13. Review draft orders.
14. Validate order-review output.
15. Generate the portfolio action report.
16. Generate the daily decision report.
17. Validate the daily decision report.
18. Run the system health check.

The artifact flow is:

```text
results/backtest_qualified_20d.csv
    |
    v
portfolio_risk.py
    |
    v
results/model_portfolio.csv ------------------+
                                                |
data/fundamentals.csv                           |
    |                                           |
    v                                           |
fundamental_scoring.py                          |
    |                                           |
    v                                           |
results/fundamental_score.csv -----------------+
                                                |
                                                v
                                      combined_scoring.py
                                                |
                                                v
                                      results/combined_score.csv
                                                |
results/model_portfolio.csv -------------------+
data/<ticker>.csv -----------------------------+
                                                |
                                                v
                                       position_sizing.py
                                                |
                                                v
                              results/model_portfolio_sizing.csv
                                                |
                                                v
                                          order_draft.py
                                                |
                                                v
                                    results/order_draft.csv
                                                |
                                                v
                                          order_review.py
                                                |
                                                v
                                    results/order_review.csv
                                                |
                                                v
                                  portfolio_action_report.py
                                                |
                                                v
                          results/portfolio_action_report.txt
                                                |
reports/daily_trading_report_*.txt -------------+
                                                |
                                                v
                                   daily_decision_report.py
                                                |
                                                v
                       reports/daily_decision_report_<date>.txt
```

`run_portfolio.py` does not update market data, generate the daily ranking, or run the backtest. Those are upstream prerequisites and must be run separately when fresh inputs are required.

### One Command Pipeline

Entry point: `run_all.py`

The unified entry calls existing business functions rather than the `main()`
functions of the three independent runners. Its fixed order is:

```text
preflight and configuration
    -> repository and manual-input readiness
    -> market-data update and validation
    -> daily screening
    -> fixed 20-day backtest and validation
    -> model portfolio and validation
    -> fundamental and combined scoring with validation
    -> position sizing with validation
    -> draft-only order generation and review with validation
    -> portfolio action and daily decision reports
    -> final validation and runtime summary
```

Before each producer runs, the entry records the expected artifacts' existence,
modification time, and size. A required producer fails unless every expected
artifact exists, is nonempty, and changed during that step. A producer or
validator failure prevents every dependent step from running and produces exit
code `1`; complete success produces exit code `0`.

This freshness evidence applies only to the current process. It is not a
persistent manifest or a change to any production CSV or text schema.

## Configuration architecture

`config.py` groups settings into:

- Account value and backward-compatible account-size alias.
- Per-trade risk.
- Portfolio exposure, holding-count, position-cap, and cash-reserve limits.
- Backtest and fundamental score weights.
- Risk-level weight multipliers.
- Draft-order review limits and allowed values.
- Output directories and artifact paths.
- Project version.

`validate_config.py` is a fail-fast gate at the beginning of the portfolio pipeline. It checks basic types and ranges, cross-setting relationships, required allowed values, nonempty paths, and version formatting.

Centralization is incomplete. Some active production and validation modules still contain hardcoded input directories or output paths. The architecture should therefore treat `config.py` as the intended central configuration source, not yet a complete one.

## Validation architecture

Validation occurs at four levels.

### Source-data validation

`data_validator.py` checks stored stock data before ranking. It covers required columns, date validity, numeric validity, duplicate dates, history length, and relative freshness warnings.

### Configuration validation

`validate_config.py` checks the safety and internal consistency of configured values before portfolio outputs are generated.

### Artifact validation

Each major portfolio artifact is normally validated immediately after generation. Checks include:

- Required columns.
- Numeric conversion and missing values.
- Allowed categorical values.
- Score or weight ranges.
- Formula consistency.
- Duplicate tickers.
- Exposure and order-value rules.
- Required sections and warnings in text reports.

### Structural health validation

`system_health_check.py` checks selected source files, validators, manual test
scripts, input-contract recovery templates, and the exact headers of those
templates. It reports runtime-directory and required-manual-input readiness
separately from repository health. It does not validate investment data quality,
numeric values, or investment-input correctness; the existing input and output
validators retain those responsibilities.

Structural presence is not the same as behavioral correctness. A present module may still be broken, and an existing artifact may be stale.

## Data and artifact contracts

The current interfaces are implicit contracts defined by filenames and DataFrame columns.

Important inputs include:

- `data/watchlist.csv`: manually maintained ticker universe.
- `data/<ticker>.csv`: downloaded per-ticker price history.
- `data/fundamentals.csv`: manually maintained fundamental inputs.
- `results/backtest_qualified_20d.csv`: qualified historical candidates.
- `reports/daily_trading_report_<date>.txt`: daily screening report used by the decision report.

The repository tracks `data/watchlist.example.csv` and
`data/fundamentals.example.csv` as input-contract recovery files. They preserve
the existing required headers for a clean clone but do not preserve a user's
manually maintained values. The corresponding real input files remain local and
must be restored and reviewed before the dependent pipelines are ready.

Important runtime outputs include:

### Daily screening outputs

- `results/stock_rank.csv`
  - Daily technical ranking output.
  - Produced by the daily screening pipeline.

- `results/top10.csv`
  - Top-ranked technical candidates.
  - Produced by the daily screening pipeline when enabled.

- `reports/daily_trading_report_<date>.txt`
  - Human-readable daily technical screening report.
  - Produced by `run_daily.py`.

### Backtest outputs

- `results/backtest_summary_20d.csv`
  - Backtest performance summary.
  - Contains return, win rate, drawdown, Sharpe ratio, and backtest score fields.

- `results/backtest_qualified_20d.csv`
  - Qualified candidates that passed the backtest filters.
  - Used by the portfolio research pipeline.

- `results/backtest_all_trades_20d.csv`
  - Trade-level backtest history.
  - Used for inspection and validation support.

### Portfolio research outputs

- `results/model_portfolio.csv`
  - Risk-adjusted model portfolio candidate list.

- `results/fundamental_score.csv`
  - Manual fundamental scoring output.

- `results/combined_score.csv`
  - Combined backtest and fundamental score output.

- `results/model_portfolio_sizing.csv`
  - Position sizing output with target weights, target dollars, target shares, estimated position value, and cash remainder.

- `results/order_draft.csv`
  - Draft-only order research output.

- `results/order_review.csv`
  - Manual review status and review reason output.

- `results/portfolio_action_report.txt`
  - Human-readable portfolio action report.

- `results/system_version.txt`
  - Current system version and module inventory report.

- `reports/daily_decision_report_<date>.txt`
  - Final daily decision report combining technical screening and portfolio action summary.

### Runtime directories

The following directories are runtime or input/output directories. They may be absent in a clean checkout and are created or populated during execution:

- `data/`
  - Market data and manually maintained input files.

- `results/`
  - Generated CSV and text outputs.

- `reports/`
  - Human-readable daily and portfolio reports.

- `logs/`
  - Pipeline execution logs.

The current artifacts do not carry an explicit run identifier, source-data timestamp, configuration fingerprint, schema version, or upstream provenance record. Consequently, file existence alone does not guarantee that inputs belong to the same research run.

Repository health and runtime readiness are distinct. A clean clone can be
structurally healthy while generated runtime directories or real manual inputs
are absent. Missing manual inputs make the dependent pipelines not ready; they
do not make the tracked repository unrecoverable when the recovery files are
present and valid.

## Manual-review and safety boundary

The portfolio workflow intentionally stops before execution.

- BUY is a screening classification, not a trading instruction.
- Generated orders have draft-only status.
- Review statuses identify items that pass configured checks, need review, or are blocked.
- A PASS status means the artifact passed the implemented rules; it is not investment approval.
- Real trading requires independent human review.
- The project contains no supported live-broker execution path.

Manual review should consider data freshness, input accuracy, liquidity, portfolio context, market conditions, assumptions not captured by the rules, and whether the proposed action remains within the user's circle of competence and risk tolerance.

## Current architectural strengths

- Pipeline stages are explicit and readable.
- Intermediate CSV artifacts make calculations inspectable.
- Validation follows most major generated outputs.
- Configuration is substantially centralized.
- The system maintains a clear draft-only, manual-review boundary.
- Separate daily, backtest, and portfolio runners limit unintended coupling.
- The project can be understood without specialized infrastructure.

## Current architectural constraints and risks

### Artifact freshness

The portfolio pipeline can combine artifacts produced at different times. There is no shared run ID or mandatory freshness check.

### Contract duplication

Required filenames and columns are repeated across producers and validators. A schema change can update one side without updating the other.

### Partial configuration centralization

Some modules use configuration constants while others retain hardcoded paths. This can cause a producer and validator to refer to different artifacts.

### Relative working-directory assumptions

Most paths are relative. The supported execution model implicitly assumes that commands are run from the repository root.

### Partial-run artifacts

Pipeline stages write outputs as they complete. If a later stage fails, new earlier artifacts can coexist with older downstream artifacts.

### Smoke-test limitations

The smoke test checks output existence but does not establish that every checked file was created by the current run. It also does not run the daily or backtest pipelines before invoking the portfolio pipeline.

### Module growth

Several modules, particularly the backtest engine, contain multiple responsibilities. Continued feature additions will make isolated testing and review harder.

### Mixed repository generations

Current modules, older alternatives, experiments, practice scripts, and generated artifacts coexist without a formal lifecycle classification.

### Version-source inconsistency

The Git tag, configured project version, generated version report, and user documentation can disagree because they do not share one authoritative version source.

## Safe evolution guidelines

Future cleanup should preserve behavior while improving clarity and verification.

Recommended sequencing:

1. Align documentation and version reporting with the observed system.
2. Document artifact producers, consumers, schemas, units, and freshness requirements.
3. Complete path centralization without renaming artifacts.
4. Add focused tests for existing pure calculations and rule boundaries.
5. Improve run manifests, failure reporting, and artifact-freshness checks.
6. Classify active, legacy, experimental, practice, and generated files.
7. Only then consider moving active modules into a package structure.

Cleanup should not be combined with changes to investment or trading logic.

## Components that should remain stable during cleanup

Unless separately researched, reviewed, and versioned, architecture cleanup should not change:

- Signal definitions.
- Backtest entry and holding-period rules.
- Backtest qualification thresholds.
- Fundamental factor formulas or weights.
- Combined-score weights.
- Risk-level definitions or multipliers.
- Position and exposure limits.
- Share-rounding behavior.
- Draft-order and review rules.
- Output column names and meanings.
- The draft-only workflow.
- The mandatory manual-review boundary.
- The prohibition on automatic brokerage execution.

## Proposed future logical layout

The following is a documentation target, not the current filesystem layout and not a requirement for an immediate rewrite:

```text
AI_investing/
├── run_all.py
├── run_daily.py
├── run_backtest.py
├── run_portfolio.py
├── config.py
├── docs/
│   ├── architecture.md
│   ├── configuration.md
│   ├── data-contracts.md
│   ├── validation.md
│   └── operations.md
├── tests/
├── practice/
├── data/
├── results/
├── reports/
└── logs/
```

Any physical relocation of active Python modules should wait until imports and artifact behavior are protected by automated tests.

## Operational sequence

For a fully refreshed research cycle, the intended high-level order is:

```text
1. Review configuration and manual inputs.
2. Run the daily pipeline.
3. Inspect data-quality warnings and ranking output.
4. Run the backtest pipeline.
5. Inspect backtest validation and qualified candidates.
6. Run the portfolio pipeline.
7. Confirm all validations passed for the current run.
8. Perform manual investment review.
9. Commit code or documentation changes only after checks pass.
```

This sequence is a research workflow. It is not an instruction to place a trade.
