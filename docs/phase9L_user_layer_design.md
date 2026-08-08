# Phase 9L Daily Research User Layer Design

Design date: 2026-08-08
Input baseline: Phase 9K daily artifacts dated 2026-08-08
Scope: presentation and information architecture only

## 1. User Layer Goal

The Daily Research User Layer is the first screen an investor opens after the
Universe150 pipeline completes. Its goal is to let a user understand the day's
research state and identify the next manual research tasks within five minutes.

The first screen must answer five questions in order:

1. Did the research pipeline and its data complete successfully?
2. Which ten symbols rank highest today?
3. Which symbols have positive, neutral, or caution research interpretation?
4. Which symbols or data inputs require risk or quality review?
5. What should a human researcher investigate next?

The User Layer is not a transaction screen. It must not display buy/sell
instructions, allocation, position sizing, or brokerage actions. Rank, signal,
tone, and template summaries remain research diagnostics.

### Current baseline

| Item | Current result |
|---|---:|
| Universe size | 150 |
| Research completed (`ResearchStatus=PASS`) | 148 |
| Research partial | 2 |
| Candidate rows | 148 |
| Validation status | PARTIAL |
| Missing metric cells | 8 |
| Research tones | 3 POSITIVE / 57 NEUTRAL / 88 CAUTION |

The existing Markdown is complete but too long for a first screen: it contains
148 candidate blocks and 3,112 lines. The User Layer should summarize; full
artifacts remain available for drill-down and audit.

## 2. Daily Research Summary Layout

### Section A — Market Research Status

Place this section at the top as five compact cards plus one warning banner.

| Field | Source | Display |
|---|---|---|
| Report Date | Candidate/AI summary `ReportDate` | `YYYY-MM-DD` |
| Universe Size | Research raw or readiness row count | Integer |
| Data Ready | Data readiness `Ready=True` count | `148 / 150` |
| Research Completed | Research raw `ResearchStatus=PASS` count | `148 / 150` |
| Validation Status | Validation `OverallStatus` | PASS/PARTIAL/FAILED badge |

If validation is not `PASS`, show a visible banner immediately below the cards:

> Data quality requires review: 2 symbols have insufficient history and 8
> metric cells are missing.

Do not show Pipeline `PASS` as proof that every dataset is complete. Pipeline
execution status and dataset validation status are separate concepts.

### Section B — Top Research Candidates

Show exactly the first ten valid ranked rows by default. The full list should be
available through an expand action or CSV download.

| Field | Source | Display rule |
|---|---|---|
| Rank | Candidate report `Rank` | Integer |
| Symbol | Canonical `Ticker` | Label as “Symbol” in UI |
| Composite Score | `CompositeScore` | Round to 4 decimals |
| Signal | Canonical `Signal` | A/B/C/D badge with legend |
| Research Tone | AI summary `ResearchTone` | POSITIVE/NEUTRAL/CAUTION |
| Risk Level | Approved risk-display contract | Never infer from `RiskStatus` alone |
| AI Summary | `AIResearchSummary` | One or two wrapped lines |

Current Top 10 example:

| Rank | Symbol | Composite Score | Signal | Research Tone |
|---:|---|---:|---|---|
| 1 | SNOW | 0.8896 | A | NEUTRAL |
| 2 | RTX | 0.8509 | A | POSITIVE |
| 3 | REGN | 0.8473 | B | NEUTRAL |
| 4 | MA | 0.8408 | B | POSITIVE |
| 5 | JPM | 0.8258 | B | NEUTRAL |
| 6 | TGT | 0.8018 | B | NEUTRAL |
| 7 | ICE | 0.7983 | B | NEUTRAL |
| 8 | BMY | 0.7947 | B | POSITIVE |
| 9 | ADSK | 0.7934 | B | NEUTRAL |
| 10 | PYPL | 0.7931 | B | NEUTRAL |

`RiskStatus=PASS` means risk metrics were calculated. It does not mean the
security is low risk. The current risk artifact includes annualized volatility
up to approximately 1.74 and maximum drawdown down to approximately -0.86 while
all 150 rows still have `Status=PASS`. Until a separate risk-level contract is
approved, the dashboard should show factual risk metrics or “Risk level not
classified,” rather than relabeling PASS as LOW.

### Section C — Watchlist

Use three tabs or columns. A symbol may appear in more than one research queue.

#### Positive Watch

Definition for display: existing `ResearchTone=POSITIVE`.

Current examples: RTX, MA, and BMY. This is a manual research priority list, not
an instruction to transact.

#### Neutral Review

Definition for display: Top 10 symbols with `ResearchTone=NEUTRAL`, especially
high-score names where quantitative strength and semantic interpretation differ.

Current examples include SNOW, REGN, JPM, TGT, ICE, ADSK, and PYPL.

#### Risk Warning

Display factual exceptions from existing artifacts:

- `RiskStatus` is PARTIAL or FAILED.
- Risk metrics are missing.
- Observation count is below the approved history requirement.
- Data readiness is false.
- Dataset validation is PARTIAL or FAILED.

Do not use unapproved volatility or drawdown thresholds in this first User Layer
iteration. If thresholds are later approved, they belong in one documented
`risk_alert` contract rather than being duplicated in dashboard code.

### Section D — Data Quality

Show a compact quality panel with counts and expandable details.

| Quality item | Current value | User presentation |
|---|---:|---|
| Missing Data | 8 metric cells | Warning |
| Historical Insufficient | 2 symbols | SKHY (21 rows), SPCX (39 rows) |
| Validation Partial | Yes | Visible PARTIAL badge |
| Download Warning | None in audited artifact | “No recorded warning” |

The dashboard must not silently omit partial symbols. It should explain why 148
of 150 symbols reached the candidate layer.

### Section E — Human Research Queue

This section converts existing research classifications into explicit manual
work queues without generating investment advice.

#### High Score + Neutral Signal

Purpose: investigate why a high composite rank does not produce a positive
research tone. Start with Top 10 names such as SNOW and REGN.

#### Historical Data Limited

Purpose: verify listing history and data sufficiency. Current entries: SKHY and
SPCX.

#### Fundamental Review Required

Purpose: perform business, valuation, management, and financial-statement review
for names already tagged POSITIVE by the rule-based research layer. Current
entries: RTX, MA, and BMY.

Each queue item should include a reason, source status, and next manual check.
It must not include an automatic action.

## 3. File Hierarchy Design

### User Layer

Files intended for routine investor viewing:

```text
results/daily_dashboard.html       # primary five-minute view
results/daily_dashboard.md         # portable/offline text view
results/daily_summary.csv          # compact combined export
results/top10_candidates.csv       # optional convenience export
```

The HTML and Markdown should be generated from the same prepared User Layer
dataset so their counts and labels cannot diverge.

### System Layer

Stable artifacts consumed by presentation modules:

```text
results/universe150_candidate_report.csv
results/universe150_daily_research_snapshot.csv
results/universe150_ai_research_summary.csv
results/universe150_research_report.csv
results/universe150_risk_raw.csv
results/universe150_research_validation.csv
results/universe150_data_readiness.csv
```

These files should remain downloadable for inspection but hidden from the main
daily navigation.

### Debug Layer

Engineering and traceability artifacts:

```text
results/universe150_factor_raw.csv
results/universe150_factor_ranking.csv
results/universe150_signal.csv
results/universe150_research_raw.csv
results/universe150_research_explanation.csv
results/daily_research_pipeline_status.csv
logs/daily_research_pipeline_YYYYMMDD.json
```

Validation details belong in the Debug Layer, but their aggregate status and
warnings must be promoted into the User Layer.

### Merge and hide recommendations

- Merge candidate rank/score, tone, AI summary, risk facts, and quality warnings
  into `daily_summary.csv` for presentation.
- Keep source artifacts unchanged as contracts and audit evidence.
- Hide raw factor, raw risk, normalized signal, and pipeline-step tables by
  default.
- Do not ask investors to reconcile candidate, explanation, and AI-summary CSVs
  manually.

## 4. Dashboard Field Design

Future output: `results/research_dashboard.html` or a versioned daily-dashboard
equivalent. It must remain static, offline, and research-only.

### Header

```text
AI_investing Daily Research
Report Date | Universe150 | Pipeline Status | Validation Status
Research diagnostics only — manual review required
```

### Cards

#### Market Status Card

- Universe size.
- Data-ready count.
- Research-completed count.
- Validation status.
- Last report date.

#### Top Candidate Card

- Rank 1 symbol.
- Composite score rounded to four decimals.
- Signal and ResearchTone.
- Short research summary.
- Link/anchor to Top 10 table.

#### Risk Alert Card

- Count of risk/data warnings.
- Worst data-quality exception by observation count.
- Missing metric count.
- Link/anchor to factual risk table.

#### AI Summary Card

- Count of POSITIVE/NEUTRAL/CAUTION rows.
- Positive Watch names.
- Selected candidate AI template summary.
- Label: “Rule-based template; no external AI API.”

### Proposed desktop wireframe

```text
+------------------------------------------------------------------+
| AI_investing Daily Research | 2026-08-08 | Validation: PARTIAL   |
+----------------+----------------+----------------+----------------+
| Market Status  | Top Candidate  | Risk Alert     | AI Summary     |
| 148 / 150      | SNOW, Rank 1   | 2 data issues  | 3 positive     |
+----------------+----------------+----------------+----------------+
| Top 10 Research Candidates                                      |
| Rank | Symbol | Score | Signal | Tone | Risk Level | Summary     |
+------------------------------------------------------------------+
| Positive Watch | Neutral Review | Risk / Data Warning            |
+------------------------------------------------------------------+
| Human Research Queue                                            |
+------------------------------------------------------------------+
```

The mobile or narrow-screen version should stack cards, retain the Top 10 only,
and collapse detailed summaries.

## 5. Output Principles

### Must display to investors

- Report date and research-universe identity.
- Pipeline completion and dataset validation as separate statuses.
- Universe, readiness, completed, partial, and failed counts.
- Top 10 rank, symbol, rounded score, signal, and tone.
- Risk/data warnings with factual reasons.
- Concise research and AI-template summaries.
- Clear statement that outputs require manual research.

### Hide by default

- Raw factor values and normalization internals.
- Full 148-row candidate list.
- Factor and risk calculation status columns unless abnormal.
- File paths, stack traces, and per-step technical messages.
- Duplicate `CompositeSignal`/`Signal` compatibility fields.
- Full-precision floating-point values.
- Repeated template text for every neutral/caution candidate.

### Governing principle

> Investors see conclusions, context, limitations, and next research tasks.
> Engineers see raw data, contracts, intermediate artifacts, and logs.

The User Layer must summarize existing results; it must not recalculate factors,
rankings, signals, or risk metrics.

## 6. Phase 9L Step 3 Recommendation

### Priority 1 — A. Create `daily_dashboard.py`

Recommended next step. It should be a static offline presentation module that:

- Reads existing candidate, AI-summary, risk, readiness, and validation files.
- Produces the five sections specified above.
- Shows Top 10 by consuming the existing ranked report.
- Does not implement calculations or execution behavior.

This directly solves the five-minute scanning problem identified in the audit.

### Priority 2 — C. Create `risk_alert_module.py`

Only proceed after documenting an approved risk-display contract. Initially it
should aggregate factual exceptions (missing metrics, insufficient observations,
non-PASS statuses) without inventing investment-risk thresholds. If volatility,
drawdown, or Sharpe thresholds are later introduced, they must be configurable,
tested, and clearly described as research presentation rules.

### Priority 3 — B. Create `top10_generator.py`

Do not create this immediately. The project already has a Top-N artifact builder
and `universe150_research_report.csv`. A second ranking/filter module would risk
duplicating selection behavior. Prefer a thin dashboard adapter that reads the
existing rank and selects the first ten rows for display. Create a dedicated
generator only if a stable `top10_candidates.csv` contract is required by more
than one independent consumer.

Recommended sequence:

1. Define the dashboard input contract and build `daily_dashboard.py`.
2. Add factual quality/risk alerts using existing fields.
3. Evaluate whether a reusable Top 10 export is still necessary.
