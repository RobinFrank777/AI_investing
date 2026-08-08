# Version History

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
