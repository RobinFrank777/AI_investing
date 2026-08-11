# Version History

## V3.8.0

**Release theme:** Investment Profile & Research Context Enhancement

### Added features

#### Investment Profile system

V3.8.0 adds a validated qualitative company-research foundation:

- Company Profile master data layer
- Company Profile schema and data validation
- reusable Investment Profile loader
- profile coverage-audit framework
- Tier1/Tier2 coverage-management system

Core files:

- `data/company_profile.csv`
- `company_profile_validator.py`
- `investment_profile_loader.py`
- `investment_profile_coverage.py`
- `data/company_profile_tiers.csv`

#### Coverage expansion

Current Universe150 research-metadata coverage:

| Scope | Covered | Total | Coverage |
|---|---:|---:|---:|
| Tier1 | 34 | 34 | 100% |
| Tier2 | 30 | 50 | 60% |
| Universe150 | 66 | 150 | 44% |

Coverage is a research metadata expansion metric only. It does not affect
scoring, ranking, signals, portfolio construction, or order review.

### Research layer enhancement

Stock Research Cards add an Investment Profile section displaying:

- Company
- Business Model
- Investment Thesis
- Moat Score
- Investment Stage
- Investor Rating
- Risk Factor

The Research Terminal adds an optional Long-Term Context section for Top
Opportunities. This qualitative context is display-only.

### Architecture boundary

Investment Profile belongs to the **Qualitative Research Layer**, not the
**Quantitative Decision Layer**. It does not participate in:

- Combined Score
- trading signals
- position sizing
- portfolio construction
- order review

### Validation

- Full regression: 863 tests passed
- Runtime version: `v3.8.0`

## V3.7.0-rc2

User-layer refinement clarifies research status, separates investment-research
candidates from data-review issues, and removes duplicate warning text from
the daily Dashboard and Markdown report. Existing factor, ranking, signal,
risk, universe, pipeline, and validation logic remains unchanged.

## V3.7.0-rc1

Release-candidate preparation adds the Universe150 daily research presentation
and execution interface on top of the V3.6.0 research foundation.

Completed:

- Universe150 data readiness, factor, signal, risk, and research artifact layers;
- daily research pipeline orchestration, CLI, logging, and scheduler interface;
- schema compatibility and signal semantic contracts;
- candidate, snapshot, explanation, and deterministic AI-summary artifacts;
- factual risk alerts and the static daily research dashboard;
- investor-facing Markdown daily report; and
- formal `python daily_report.py` user entry point.

Release-candidate boundaries:

- Existing factor, ranking, signal, and risk calculations are unchanged.
- Research and production workflows remain isolated.
- No brokerage order, trade execution, or investment recommendation is created.
- Validation and historical-data warnings remain visible for manual review.

## V3.6.0

Release preparation completed for the Scale50 research validation and
presentation workflow.

Completed:

- Phase 7B: Scale50 research universe support
- Phase 8A: unified validation engine
- Phase 8B: factor research report layer
- Phase 8C: research dashboard layer
- Artifact schema documentation
- Research artifact contract testing

Status:

- Production pipeline unchanged.
- Research workflow isolated.
- No brokerage execution.

Model assumptions remain unchanged:

- Trend 35%, Momentum 35%, Low Volatility 30%;
- monthly rebalance;
- 5D, 10D, 20D, and 60D forward horizons;
- top and bottom 20% portfolio groups;
- same-close entry assumption; and
- 60 observations required for factor calculation.

Safety boundaries:

- Scale50 is a research universe, not a buy list.
- Research outputs do not modify production ranking, portfolios, or orders.
- Transaction costs and market impact are not included.
- Static universe membership may introduce survivorship bias.
- Historical validation is diagnostic and does not prove future returns.

The production universe mode remains `single`, and the production pipeline
remains 18 steps.

## V3.5.0 — Scalable market universe foundation

V3.5.0 centralized deterministic universe loading and validation, added
configurable universe sources, and retained the formal single-watchlist
production workflow as the safe default.

Earlier project history remains documented in `README.md` and the repository
commit history.
