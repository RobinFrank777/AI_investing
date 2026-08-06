# V3.6.0 Module List

## Universe and data

| Module | Responsibility | Boundary |
|---|---|---|
| `universe_manager.py` | Validate and load canonical universe files. | Shared infrastructure; unchanged for release preparation. |
| `universe_source.py` | Select the configured active production universe. | Production-facing; default remains single mode. |
| `universe_scale_test.py` | Inspect Scale50 local-data readiness; downloads only when explicitly requested. | Research utility. |
| `factor_research_universe.py` | Orchestrate isolated Scale50 snapshots, validation, robustness, and reports. | Research only. |
| `update_data.py` | Update market data for the configured universe. | Production workflow; unchanged. |

## Factor model

| Module | Responsibility |
|---|---|
| `price_factors.py` | Calculate Trend, Momentum, and Low Volatility from price history. |
| `factor_normalization.py` | Perform cross-sectional percentile normalization. |
| `factor_composite.py` | Apply the fixed 35%/35%/30% composite weights. |
| `factor_snapshot.py` | Build dated factor snapshots from available histories. |

Release preparation does not modify these modules or their formulas.

## Validation and robustness

| Module | Responsibility |
|---|---|
| `factor_validation.py` | Build monthly validation observations, Rank IC, group returns, and turnover. |
| `factor_validation_robustness.py` | Produce saved stability, regime, coverage, and influence diagnostics. |

The validation assumptions are same-close entry, monthly rebalance, 5D/10D/20D/60D
horizons, 20% groups, and 60 observations of factor history.

## Research presentation

| Module | Responsibility | Input/output contract |
|---|---|---|
| `factor_report.py` | Build the baseline human-readable validation summary. | Reads saved validation CSV files. |
| `factor_research_report.py` | Assemble the Phase 8B report and export canonical JSON and HTML. | Produces `scale50_factor_report.json` and `.html`. |
| `research_dashboard.py` | Render the Phase 8C standalone dashboard. | Reads only the canonical report JSON. |

## Production workflow

`config.py`, `run_all.py`, production ranking, portfolio, order, and backtest
modules remain outside the V3.6.0 release-preparation change set. The production
pipeline remains 18 steps and does not consume the Scale50 report or dashboard.

For the complete legacy inventory, see `docs/module_catalog.md`.
