# Version History

## V3.6.0 — Research validation and presentation release

V3.6.0 packages the completed Scale50 research path for release review while
preserving the V3.5.0 production configuration and workflow.

Included milestones:

- Phase 7B: isolated Scale50 universe and data-readiness validation.
- Phase 8A: reusable factor forward-return validation engine.
- Phase 8B: standardized research report with canonical JSON and HTML outputs.
- Phase 8C: standalone offline research dashboard driven by the JSON report.
- Release preparation: artifact-contract documentation and regression coverage.

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

During release preparation, `PROJECT_VERSION` intentionally remains `v3.5.0`,
`UNIVERSE_MODE` remains `single`, and the production pipeline remains 18 steps.
Version activation is a separate production-controlled release action.

## V3.5.0 — Scalable market universe foundation

V3.5.0 centralized deterministic universe loading and validation, added
configurable universe sources, and retained the formal single-watchlist
production workflow as the safe default.

Earlier project history remains documented in `README.md` and the repository
commit history.
