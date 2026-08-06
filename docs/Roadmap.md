# Research Roadmap

## V3.6.0 release gate

Before release review:

- document the Phase 8B JSON artifact contract;
- protect required sections, types, missing-field behavior, HTML escaping, and
  deterministic rendering with regression tests;
- run the full unit-test and Python compilation checks;
- confirm `PROJECT_VERSION = "v3.5.0"`, `UNIVERSE_MODE = "single"`, and 18
  production pipeline steps; and
- confirm that protected production modules are unchanged.

## Next phase: research governance and reproducibility

Recommended future work:

1. Add an explicit artifact schema version and producer metadata.
2. Record universe, data, configuration, and source-artifact provenance.
3. Support reproducible report timestamps through explicit build metadata.
4. Add point-in-time universe membership before making survivorship-safe claims.
5. Add transaction-cost, liquidity, and market-impact sensitivity as separate
   research diagnostics.
6. Define objective gates for any future research-to-production promotion.

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
