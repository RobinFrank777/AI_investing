# Research Roadmap

## Current release line

`V3.8.0`

Runtime version metadata is controlled by `config.PROJECT_VERSION`.

## V3.8.0 — Investment Profile & Research Context Enhancement

### Completed

- Investment Profile foundation
- Company Profile master-data validation
- reusable validated Profile loader
- Universe150 and tier-level coverage audit
- Tier1/Tier2 coverage management
- Stock Research Card Investment Profile display
- Research Terminal Long-Term Context
- runtime version synchronization to `v3.8.0`

These capabilities add qualitative research context and coverage governance.
They do not change scoring, ranking, signals, position sizing, portfolio
construction, order review, or the production pipeline.

## Next phase: research governance and reproducibility

Recommended future work:

1. Add an explicit artifact schema version and producer metadata.
2. Record universe, data, configuration, and source-artifact provenance.
3. Support reproducible report timestamps through explicit build metadata.
4. Add point-in-time universe membership before making survivorship-safe claims.
5. Add transaction-cost, liquidity, and market-impact sensitivity as separate
   research diagnostics.
6. Define objective gates for any future research-to-production promotion.
7. Expand Company Profile coverage beyond the completed Tier1 set.
8. Improve qualitative research presentation while preserving the separation
   from quantitative decision logic.
9. Evaluate a future AI-assisted analysis layer only through a separate design,
   validation, and approval phase. This capability is not currently implemented.

## Explicitly out of scope

- changing factor formulas or optimizing the fixed weights;
- changing the production universe or `run_all.py` pipeline;
- connecting the dashboard to a server, database, or broker;
- automatically producing orders or portfolio changes;
- AI-generated investment recommendations; and
- treating historical validation as a forecast guarantee.

The research presentation stack must remain downstream of calculation and
validation. Production adoption, if ever proposed, requires a separate review
and authorization.
