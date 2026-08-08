# Phase 9L Release Candidate

Version: `v3.7.0-rc1`

Current phase: `Phase 9L Step 7`

## Current capabilities

AI_investing provides a research-only Universe150 workflow from market-data
preparation through factor, signal, and risk artifacts to user-facing daily
outputs. The formal user entry point is:

```bash
python daily_report.py
```

It generates the risk-alert CSV first, then the static HTML dashboard, and
finally the Markdown daily investment research report. The entry point exposes
`VERSION`, `CURRENT_PHASE`, and `REPORT_DATE` metadata.

## Completed modules

- Universe150 research-universe loading and data-readiness inspection
- Factor preparation, normalization, ranking, and signal artifacts
- Per-symbol risk metrics and factor/risk research merge
- Research dataset validation and candidate selection
- Candidate report, daily snapshot, explanation, and deterministic AI-summary layers
- Thirteen-step daily research pipeline, CLI, logging, and scheduler entry
- Signal and research schema compatibility contracts
- Static daily dashboard and factual risk-alert presentation layer
- Static Markdown daily investment report and official user entry point

## Known limitations

- Outputs depend on the freshness and completeness of existing upstream artifacts.
- Validation `PARTIAL` and missing-history conditions require manual review.
- Risk `PASS` means metrics were calculated; it does not mean a security is low risk.
- Research summaries are deterministic templates and do not include external AI analysis.
- The user entry point does not download data or execute the research calculation pipeline.
- No fundamental conclusion, brokerage integration, order creation, or trade execution is provided.
- Historical observations and research rankings do not establish future performance.

## Release checklist

- [ ] `python daily_report.py` exits successfully.
- [ ] `results/risk_alerts.csv` is generated and has the documented alert fields.
- [ ] `results/daily_dashboard.html` is generated as a standalone offline page.
- [ ] `results/daily_investment_report.md` contains Top 10, summaries, alerts, data quality, and disclaimer sections.
- [ ] Validation `PARTIAL` or `FAILED` is prominently visible.
- [ ] Unit and regression tests pass.
- [ ] `python -m compileall .` passes.
- [ ] `git diff --check` passes.
- [ ] Production factor, ranking, signal, risk, portfolio, order, and broker logic remains unchanged.
- [ ] Git changes are reviewed and staged manually.
