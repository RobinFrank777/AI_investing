# Research Artifact Schema

## Purpose

`results/scale50_factor_report.json` is the canonical interface between the
Phase 8B research report and the Phase 8C static dashboard. It is a research
artifact, not a production ranking, portfolio instruction, order, or investment
recommendation.

The JSON document must be UTF-8, standards-compliant JSON with an object at its
root. JSON `NaN` and infinity values are not permitted. Missing numeric results
are represented by `null`, not by non-standard numeric tokens.

## Top-level contract

| Field | Type | Required | Description |
|---|---|---:|---|
| `metadata` | object | Yes | Universe and validation-window metadata. |
| `factor_model` | object | Yes | Model name, component weights, and saved factor ranking. |
| `ic_analysis` | array | Yes | Rank-IC summaries by holding horizon. |
| `group_analysis` | array | Yes | Top, middle, bottom, and long-short group summaries. |
| `turnover_analysis` | object | Yes | Saved turnover summary. |
| `robustness_analysis` | object | Yes | Saved robustness diagnostics. |
| `limitations` | array of strings | Yes | Research limitations shown without reinterpretation. |
| `conclusion` | string | Yes | Rule-based Phase 8B conclusion, preserved verbatim by the dashboard. |
| `risk_summary` | object | No | Reserved for risk metrics supplied by a future report producer. |

Unknown top-level fields must be ignored by compatible readers. A missing
required section, a non-object root, or an incorrect required-section type is a
contract error and must be rejected.

## `metadata`

Required producer fields:

| Field | Type | Meaning |
|---|---|---|
| `universe` | string | Research universe name, normally `Scale50`. |
| `period` | array of two strings | First and last validation dates. |
| `rebalance` | string | Rebalance frequency, currently `Monthly`. |
| `holding_periods` | array of strings | Currently `5D`, `10D`, `20D`, and `60D`. |

Optional compatibility fields are `project_version` (string), `universe_mode`
(string), and `symbol_count` (integer). Readers must not infer these values from
the filename. When absent, the dashboard displays that the value is not
available in the canonical report.

## `factor_model`

Required producer fields:

- `name`: string; currently `Composite Score`.
- `components`: array of objects containing `factor` (string) and `weight`
  (number). The current saved weights are Trend 0.35, Momentum 0.35, and Low
  Volatility 0.30.
- `factor_ranking`: array of saved ranking objects. Readers display these values
  and must not recalculate rankings.

Ranking objects may contain `factor`, `mean_rank_ic`, `ic_std`, `rank`, and
additional Phase 8B summary fields. Missing display fields render as `Not
available`.

## `ic_analysis`

Each array item represents one holding horizon and may contain:

| Field | Type | Required from Phase 8B |
|---|---|---:|
| `horizon` | string | Yes |
| `rank_ic` | number or null | Yes |
| `count` | integer | Yes |
| `mean` | number or null | Yes |
| `win_rate` | number or null | Yes |
| `volatility` | number or null | Yes |

`win_rate` is the positive-IC ratio. The dashboard may identify the best and
weakest available horizon from the saved `rank_ic` values; it does not
recalculate IC observations.

## `group_analysis`

Each item contains `horizon` and the objects `top_20`, `middle`, `bottom_20`, and
`long_short_spread`. Each group summary contains:

- `count`: integer
- `mean`: number or null
- `win_rate`: number or null
- `volatility`: number or null

All values are summaries already produced by the research report. Dashboard
rendering must not rebuild portfolio groups or forward returns.

## Turnover and robustness

`turnover_analysis.monthly_turnover` contains the standard `count`, `mean`,
`win_rate`, and `volatility` summary fields.

`robustness_analysis` contains:

- `stability_score`: number or null.
- `performance_consistency`: array of objects containing saved horizon,
  positive-ratio, series, and observation-count values.
- `period_or_regime_checks`: array of saved robustness records. Record columns
  may expand compatibly.
- `minimum_score_coverage`: number or null.

Missing nested robustness or risk metrics are displayed as `Not available`.
They must not be estimated, inferred, or recalculated by the dashboard.

## Missing-field and compatibility rules

1. Required top-level sections are strict. Missing or incorrectly typed
   sections cause loading to fail.
2. Optional metadata, risk metrics, and nested display fields are tolerant and
   render as `Not available`.
3. `null` is the canonical representation for unavailable numeric results.
4. Readers must HTML-escape all text and preserve the conclusion text.
5. Readers must ignore unknown fields so additive producer changes remain
   backward compatible.
6. Removing or renaming a required section, changing its type, changing metric
   meaning, or changing units is a breaking contract change and requires a new
   artifact contract revision plus regression-test updates.
7. Array order is presentation order. JSON object-key order is not semantic.
8. The artifact contains research diagnostics only. It must never be consumed
   as an order or portfolio-allocation instruction.

The current V3.6.0 preparation contract is documented rather than embedded as a
new runtime `schema_version`, because release preparation must not alter the
Phase 8B producer. A future additive revision should introduce an explicit
schema-version field before multiple producer versions need simultaneous
support.
