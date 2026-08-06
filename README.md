# AI_investing

AI_investing is a personal AI-assisted investing research system.

## Documentation

The project documentation is organized as follows:

- **[README.md](README.md)** — Project overview and quick start.
- **[architecture.md](docs/architecture.md)** — System architecture, pipeline design, safety boundary, and output contracts.
- **[module_catalog.md](docs/module_catalog.md)** — Module classification, module status, and system inventory.
- **[development_rules.md](docs/development_rules.md)** — Development workflow, validation requirements, Git workflow, release process, and project governance.

Current development release: `AI_investing v3.5.0`

These documents should be read together.
When documentation conflicts, the precedence defined in
docs/development_rules.md applies.

## Project purpose

The system supports:

- daily market screening
- historical backtesting
- fundamental scoring
- combined scoring
- portfolio research
- risk-aware position sizing
- draft-only order review
- human-readable decision reports

## Safety boundary

AI_investing is a research and decision-support system.

- This system provides research outputs only.
- Validation PASS is not investment approval.
- Manual review is required before any real trade.
- No brokerage order is placed by this system.
- Deterministic Research Summary is not financial advice.

It does not:

- connect to brokerage accounts
- submit orders
- route trades
- execute transactions automatically

All generated outputs require independent human review.

BUY is a screening classification produced by the research pipeline.

It is not an automatic trading instruction.

## Installation and clean-clone recovery

Run supported commands from the repository root. The current modules use
repository-relative paths and are not designed to be launched from another
working directory.

Create a virtual environment and install the tracked dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Restore the two required, manually maintained inputs from their tracked input
contract recovery files:

```bash
cp data/watchlist.example.csv data/watchlist.csv
cp data/fundamentals.example.csv data/fundamentals.csv
```

Then populate and independently review both local files before running a
pipeline. The example files define the existing headers only; they do not
contain investment recommendations or recover user-maintained values.

- `data/watchlist.csv` is maintained by the user and supplies the ticker
  universe to the daily and backtest pipelines. Its required header is
  `Ticker`.
- `data/fundamentals.csv` is maintained by the user and supplies fundamental
  inputs to the portfolio pipeline. Its required headers are listed in the
  Fundamental scoring section below.

The real input files and downloaded market data are local runtime data and are
not tracked. Create the runtime output directories when preparing a clean
clone:

```bash
mkdir -p results reports logs
```

Check repository health and local readiness without running a production
pipeline:

```bash
python3 system_health_check.py
```

## One Command Pipeline

Run the complete supported research workflow in its required order:

```bash
python3 run_all.py
```

This command performs preflight checks, updates and validates market data, runs
the daily screening and fixed 20-day backtest, validates each produced artifact,
then runs the portfolio research, draft-only order-review, and reporting chain.
Every required step is fail-closed. Each producer must create or update a
nonempty expected artifact before its validator can pass.

The existing `run_daily.py`, `run_backtest.py`, and `run_portfolio.py` commands
remain independently usable with their existing meanings. Pipeline and
validation PASS statuses are research checks, not investment approval; the
system does not connect to a broker or submit orders.

The current unified pipeline has 18 required steps. The current release review
completed with 18/18 steps passing.

## v3.5.0 Scalable Market Universe

v3.5.0 adds a deterministic, configurable Market Universe layer while keeping
the existing formal watchlist and 18-step Pipeline as the default behavior.

### Universe Manager

`universe_manager.py` is the canonical loader for a single Universe CSV. It
normalizes ticker symbols, filters invalid and disabled values, validates the
ticker format, and removes duplicates while preserving first appearance.
An optional `Enabled` column can control membership. Stable summaries are
available without exposing pandas DataFrames:

```python
load_universe(...)
validate_universe(...)
```

### Universe Groups

`universe_groups.py` composes multiple Universe files. Enabled groups are
loaded in configuration order, cross-group duplicates retain their first
appearance, and ticker validation remains delegated to Universe Manager.
Absolute paths, URLs, parent-directory traversal, non-CSV paths, and paths
outside the project root are rejected.

```python
load_universe_config(...)
validate_universe_config(...)
load_combined_universe(...)
```

### Universe Source Selection

`universe_source.py` explicitly selects one of two modes:

- `single`: loads the existing formal `data/watchlist.csv`.
- `groups`: loads an explicit Universe Groups configuration.

The default remains `UNIVERSE_MODE = "single"`. There is no automatic mode
detection and no automatic fallback. Explicit function parameters override
configuration for isolated testing. The public interfaces are:

```python
load_active_universe(...)
validate_active_universe(...)
```

### Market-data update and result contract

`update_data.py` loads symbols once from the active Universe source instead of
maintaining separate ticker-cleaning logic. Market-data files continue to use
`data/{SYMBOL}.csv`, and no new `run_all.py` Pipeline step was required.

`update_one_stock(symbol)` returns a structured result containing `symbol`,
`status`, `rows`, `latest_date`, `output_path`, and `message`. The only statuses
are:

- `success`: downloaded data contains a valid row and the CSV was written.
- `empty`: the data provider returned no rows.
- `failed`: downloading, processing, or writing raised an error.

The absence of an exception is no longer automatically interpreted as a
successful download.

### Scale50 validation

`universe_scale_test.py` is offline by default. It checks local file existence,
CSV readability, required `Date` and `Close` columns, valid rows, latest dates,
and disk usage. Network access requires the explicit `--download` flag, while
`--limit` keeps the original Universe order:

```bash
python universe_scale_test.py
python universe_scale_test.py --limit 5
python universe_scale_test.py --download --limit 5
```

Download-attempt status and post-download local-file status remain separate.
For example, an older valid CSV does not turn a new `empty` or `failed` attempt
into a success.

### Example configuration

Tracked templates and scalability samples include:

```text
data/universe_config.example.csv
data/universes/ai.example.csv
data/universes/semiconductor.example.csv
data/universes/space.example.csv
data/universes/custom.example.csv
data/universes/scale50.example.csv
```

Files ending in `.example.csv` are templates or test samples. Formal runtime
Universe CSV files remain ignored by Git. `scale50.example.csv` is a technical
scalability sample, not an investment recommendation, and the system does not
automatically create a formal `scale50.csv`.

### Universe data flow

```text
Configuration
    ↓
Universe Source Selection
    ├── single → Universe Manager → data/watchlist.csv
    └── groups → Universe Groups → enabled Universe CSV files
    ↓
Active Symbol List
    ↓
Market Data Update
    ↓
Data Validation
    ↓
Technical Screening
    ↓
Backtest
    ↓
Fundamental Scoring
    ↓
Combined Scoring
    ↓
Position Sizing
    ↓
Order Review
    ↓
Research Summary
    ↓
Stock Cards
    ↓
Research Dashboard
    ↓
Research Terminal
```

Scale50 is not the default active Universe. Universe membership, successful
downloads, and validation results are not investment signals and do not
validate company fundamentals or valuation.

### Universe tests

```bash
python -m unittest tests.test_universe_manager -v
python -m unittest tests.test_universe_groups -v
python -m unittest tests.test_universe_source -v
python -m unittest tests.test_update_data_universe -v
python -m unittest tests.test_update_one_stock -v
python -m unittest tests.test_universe_scale_test -v
python -m unittest discover -s tests -p "test_*.py" -v
```

## v3.4.0 Research Center Upgrade

v3.4.0 expands the presentation layer into a deterministic Research Center:

- Deterministic Research Summary with rule-based strengths and risks
- Stance classification: `BUY CANDIDATE`, `HOLD / REVIEW`,
  `REDUCE / AVOID`, or `INSUFFICIENT DATA`
- Research Summary embedded in single-stock HTML Research Cards
- Research Summary embedded in the Research Terminal
- Today's Research Dashboard summary
- Top Opportunity Research Summary cards
- Model Portfolio Research Card links
- Centralized current-version metadata through `config.PROJECT_VERSION`

These features read existing research artifacts. They do not change screening,
scoring, backtesting, position sizing, or order-review logic.
The Research Summary is deterministic rule-based output: it does not call an
external LLM or the OpenAI API. It does not execute real trades.

### Recommended run order

Run the three commands from the repository root:

```bash
python run_all.py
python generate_stock_cards.py
python report_terminal.py
```

`python run_all.py` runs the existing 18-step unified pipeline and generates
the core CSV and TXT research outputs.

`python generate_stock_cards.py` reads `results/top10.csv` and
`results/model_portfolio.csv`, then generates one shared offline HTML Research
Card per unique ticker:

```text
reports/cards/{TICKER}.html
```

`python report_terminal.py` generates:

```text
reports/ai_terminal_report.html
```

The Research Terminal contains:

- System Status
- Today's Research Dashboard
- Top Opportunities table
- Top Opportunity Research Summary cards
- Model Portfolio with Research Card links
- Order Review
- Combined Score

The Dashboard displays Pipeline Status, Top Opportunities, counts for all four
stances, Average Combined Score, Highest Score, Model Portfolio Count, Research
Card Links, and Generated Time.

The resulting data flow is:

```text
Market Data
→ Validation
→ Screening
→ Backtest
→ Fundamental Score
→ Combined Score
→ Position Sizing
→ Order Review
→ Research Summary
→ Stock Cards
→ Research Dashboard
→ Research Terminal
```

### Core project structure

```text
AI_investing/
├── config.py
├── run_all.py
├── update_data.py
├── universe_manager.py
├── universe_groups.py
├── universe_source.py
├── universe_scale_test.py
├── research_summary.py
├── report_terminal.py
├── stock_card_builder.py
├── stock_card_report.py
├── generate_stock_cards.py
├── data/
│   ├── watchlist.example.csv
│   ├── universe_config.example.csv
│   └── universes/
│       ├── ai.example.csv
│       ├── semiconductor.example.csv
│       ├── space.example.csv
│       ├── custom.example.csv
│       └── scale50.example.csv
├── templates/
│   ├── report.css
│   └── stock_card.html
├── tests/
├── results/
├── reports/
│   └── cards/
└── logs/
```

- `results/`: runtime CSV outputs
- `reports/`: daily reports and HTML outputs
- `reports/cards/`: runtime-generated stock cards; not tracked by Git
- `templates/`: offline HTML templates and CSS
- `tests/`: unittest test modules

### Research Terminal tests

Run the Research Center tests from the repository root:

```bash
python -m unittest tests.test_research_summary -v
python -m unittest tests.test_stock_card_builder -v
python -m unittest tests.test_stock_card_report -v
python -m unittest tests.test_generate_stock_cards -v
python -m unittest tests.test_report_terminal -v
```

The unified `run_all.py` pipeline is currently 18/18 PASS, and all Research
Center unittest modules pass. These statuses confirm research-system validation
only; they are not investment approval.

The v3.5.0 Universe features retain the same safety boundary: Scale50 is a
technical validation Universe, a successful data download is not an investment
signal, Universe membership is not an investment recommendation, and download
success does not validate company fundamentals or valuation.

## Daily usage

Run the full daily pipeline:

```bash
python3 run_daily.py
```

This command will automatically run:

1. `update_all_stocks()`
2. `run_ranking_pipeline()`

The pipeline will:

1. update market data
2. validate all watchlist data files
3. exclude invalid stocks
4. calculate indicators
5. rank stocks
6. generate stock signal cards
7. generate the daily trading report
8. write a runtime log

## Backtest usage

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

## Portfolio usage

Run the full portfolio pipeline:

```bash
python3 run_portfolio.py
```

This command will automatically run:

1. `print_config_validation()`
2. `print_system_version()`
3. `print_model_portfolio()`
4. `validate_portfolio_outputs()`
5. `print_fundamental_score()`
6. `validate_fundamental_outputs()`
7. `print_combined_score()`
8. `validate_combined_outputs()`
9. `print_position_sizing()`
10. `validate_position_sizing_outputs()`
11. `print_order_draft()`
12. `validate_order_draft_outputs()`
13. `print_order_review()`
14. `validate_order_review_outputs()`
15. `print_portfolio_action_report()`
16. `print_daily_decision_report()`
17. `validate_daily_decision_report_outputs()`
18. `run_system_health_check()`
19. Write a portfolio pipeline log.

Current portfolio risk rules:

- maximum single position weight: 10%
- maximum total exposure: 80%
- maximum holdings: 10
- cash reserve: 20%

## Config validation failure demo

Run the config validation failure demo manually:

```bash
python3 config_validation_failure_demo.py
```
This script intentionally injects invalid config values into the validation module during runtime.

It is used to confirm that `validate_config.py` can detect unsafe or invalid settings, including:

1. negative account value
2. total exposure above 100%
3. cash reserve plus exposure above 100%
4. zero max order count
5. missing BUY action
6. project version missing the `v` prefix

Important safety notes:

- this script does not modify `config.py` on disk
- this script restores temporary values after each test case
- this script is for manual testing only
- this script must not be integrated into `run_portfolio.py`
- this script does not place trades

## Pipeline smoke test

Run the pipeline smoke test manually:

```bash
python3 pipeline_smoke_test.py
```
This script runs a smoke check of the portfolio pipeline.

It executes:

1. `validate_config.py`
2. `config_validation_failure_demo.py`
3. `run_portfolio.py`

It then checks that the required output files exist, including:

- `results/stock_rank.csv`
- `results/top10.csv`
- `results/model_portfolio.csv`
- `results/model_portfolio_sizing.csv`
- `results/order_draft.csv`
- `results/order_review.csv`
- `results/portfolio_action_report.txt`
- `results/system_version.txt`
- `reports/daily_decision_report_YYYY-MM-DD.txt`

Important safety notes:

- this script is for manual testing only
- this script must not be integrated into `run_portfolio.py`
- this script does not place trades
- this script does not connect to a brokerage account
- this script does not run the daily or backtest pipelines
- daily and backtest inputs must be prepared separately when fresh data is required
- output existence checks may accept prerequisite artifacts created by an earlier run
- a passing result confirms only that the configured checks and portfolio pipeline completed with the available inputs

## System module classification

The module catalog assigns project files one of six statuses:

- `Active`: participates in a current pipeline
- `Validation`: checks artifacts, schemas, formulas, or configured rules
- `Test`: provides manual or smoke-test system checks
- `Utility`: supports other modules without serving as a main pipeline stage
- `Legacy / Experimental`: is older, exploratory, or outside the supported V3.2 pipelines
- `Practice`: is learning or practice code and does not participate in production pipeline decisions

The sections below summarize the active, validation, and test groups most relevant to normal operation. See the [module catalog](docs/module_catalog.md) for the complete file-by-file classification.

### Active modules

Active modules are current pipeline and system execution files.

They include the daily runner, backtest runner, portfolio pipeline, risk model, position sizing, order draft, order review, action report, daily decision report, system health check, and system version report.

### Validation modules

Validation modules check whether generated outputs are structurally valid.

They include:

- `validate_config.py`
- `validate_backtest_outputs.py`
- `validate_fundamental_outputs.py`
- `validate_combined_outputs.py`
- `validate_portfolio_outputs.py`
- `validate_position_sizing_outputs.py`
- `validate_order_draft_outputs.py`
- `validate_order_review_outputs.py`
- `validate_daily_decision_report_outputs.py`

### Test modules

Test modules are manual system testing tools.

They include:

- `config_validation_failure_demo.py`
- `pipeline_smoke_test.py`

Important notes:

- test modules are not trading modules
- test modules do not place trades
- test modules do not connect to a brokerage account
- test modules should not be integrated into `run_portfolio.py`
- test modules are used to verify system safety and pipeline reliability

## Fundamental scoring

The fundamental scoring module reads manual fundamental data from:

```bash
data/fundamentals.csv
```

It writes the scoring result to:

```text
results/fundamental_score.csv
```

The required input columns are:

- Ticker
- RevenueGrowth
- EPSGrowth
- GrossMargin
- OperatingMargin
- ROE
- FreeCashFlowMargin
- DebtToEquity
- PE
- PS

The module calculates:

- FundamentalScore
- FundamentalRating

Current rating rules:

- STRONG: score >= 75
- GOOD: score >= 60
- NEUTRAL: score >= 45
- WEAK: score < 45

The fundamental scoring output is validated with:

```bash
python3 validate_fundamental_outputs.py
```

The module is integrated into the full portfolio pipeline:

```bash
python3 run_portfolio.py
```

This module does not place trades and does not connect to a brokerage account.

## Main output files

### System version report

`results/system_version.txt`

This file records the configured project version, Git branch, current commit,
Python version, core modules, and validation modules.

### Daily screening outputs

- Daily trading report: `reports/daily_trading_report_YYYY-MM-DD.txt`
- Ranking result: `results/stock_rank.csv`
- Top 10 candidates: `results/top10.csv`
- Runtime log: `logs/daily_pipeline_YYYY-MM-DD.log`

### Model portfolio

`results/model_portfolio.csv`

This file contains the highest-ranked qualified backtest candidates together with historical return metrics, risk classifications, risk multipliers, target weights, and portfolio roles.

### Fundamental score

```text
results/fundamental_score.csv
```

This file contains the fundamental scores used by the portfolio research pipeline.

It includes:

- ticker
- valuation metrics
- profitability metrics
- growth metrics
- financial health metrics
- fundamental score

### Combined score

`results/combined_score.csv`

This file combines technical and fundamental scores into the final portfolio research score.

It includes:

- ticker
- backtest score
- fundamental score
- combined score
- fundamental rating

### Position sizing

`results/model_portfolio_sizing.csv`

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

### Order draft

`results/order_draft.csv`

This file contains draft BUY orders generated from the portfolio sizing results. Every order remains `DRAFT_ONLY`.

It includes:

- ticker
- action
- target shares
- estimated order value
- combined score
- risk level
- order status

### Order review

`results/order_review.csv`

This file contains the reviewed draft orders together with validation information.

It includes:

- ticker
- review status
- review reason
- portfolio review flag
- portfolio review reason

### Portfolio action and decision reports

- Portfolio action report: `results/portfolio_action_report.txt`
- Daily decision report: `reports/daily_decision_report_YYYY-MM-DD.txt`

These reports summarize recommended portfolio actions and final daily decisions for manual review.

### Backtest outputs

- `results/backtest_summary_20d.csv`
- `results/backtest_qualified_20d.csv`
- `results/backtest_all_trades_20d.csv`

These files contain the historical backtest summary, qualified candidates, and all simulated trades.

Current risk level rules:

- `Low`: MaxDrawdown >= -10% and SharpeRatio >= 2
- `Medium`: MaxDrawdown >= -25% and SharpeRatio >= 1
- `High`: all other cases
- `Unknown`: missing MaxDrawdown or SharpeRatio

Current risk weight multipliers:

- `Low`: 1.00
- `Medium`: 0.80
- `High`: 0.50
- `Unknown`: 0.00

The final target weight is calculated from normalized risk-adjusted weights:

risk weight multiplier / sum of all selected risk weight multipliers * maximum total exposure

Each position is still capped by the maximum single position weight.

The portfolio output is validated by `validate_portfolio_outputs.py`.

### Portfolio pipeline log

`logs/portfolio_pipeline_YYYY-MM-DD.log`

This file records the full terminal output from the model portfolio pipeline.

It includes:

- pipeline start time
- configuration validation
- system version report
- model portfolio table
- portfolio summary
- portfolio output validation result
- fundamental and combined scoring
- position sizing
- order draft and order review
- portfolio action and daily decision reports
- output validation results
- system health check
- pipeline finish time

## Project documentation

- [Architecture](docs/architecture.md): pipeline boundaries, data flow, artifacts, validation layers, safety constraints, and known limitations
- [Module catalog](docs/module_catalog.md): module responsibilities, inputs, outputs, and current classification status

## Data quality rules

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

## Signal meaning

The system currently produces three trade signals:

- `BUY`
- `WATCH`
- `IGNORE`

Important rule:

`BUY` means "candidate for further review".
`BUY` does not mean "verified buy order".

## Git rules

The following files are ignored by Git because they are generated automatically:

```gitignore
data/*.csv
results/
reports/daily_trading_report_*.txt
logs/
```

Code files should still be committed.

Typical Git workflow:

```bash
git status
git diff --check
git add <changed_code_files>
git commit -m "Message"
git push
git status
```

## Current system boundary

The current system combines technical screening, historical backtesting, manually supplied fundamental data, rule-based scoring, and portfolio risk controls.

It does not yet include:

- benchmark comparison
- slippage and transaction cost modeling
- portfolio-level risk simulation
- AI analyst summary
- paper trading execution
- live broker connection
