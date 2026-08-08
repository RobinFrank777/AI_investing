# Phase 9L Daily Research Output Audit

Audit date: 2026-08-08
Audited report date: 2026-08-08
Scope: Phase 9K Universe150 daily research outputs
Nature: research-output audit only; no investment or execution recommendation

## 1. Executive Summary

The Phase 9K pipeline successfully produced all five audited daily artifacts and
recorded all 13 pipeline steps as `PASS`. The output chain preserves ranking,
composite score, signal, research tone, summaries, and report date. It is
therefore technically usable as a research dataset.

It is not yet an efficient investor-facing daily product. The final Markdown is
3,112 lines (38,346 bytes) and lists 148 of 150 universe members as research
candidates. Every displayed candidate is marked `READY`, `HIGH`, and `ACTIVE`.
This makes the term "candidate" too broad and prevents a reader from quickly
identifying a genuinely prioritized shortlist.

The most important missing user-facing context is:

- No explicit Top 10/Top 20 summary at the beginning of the final report.
- No risk metrics or risk watchlist in the final Markdown.
- No data-quality warning, even though validation is `PARTIAL`.
- No notice that SKHY and SPCX have insufficient history.
- No concise list of names requiring manual fundamental investigation.
- Scores are displayed with excessive precision.

Current data facts:

| Measure | Current value |
|---|---:|
| Universe rows | 150 |
| Research PASS | 148 |
| Research PARTIAL | 2 |
| Displayed candidates | 148 |
| Candidate READY / HIGH / ACTIVE | 148 |
| Signal A / B / C / D | 2 / 36 / 32 / 78 |
| Research Tone POSITIVE / NEUTRAL / CAUTION | 3 / 57 / 88 |
| Data-ready symbols | 148 |
| Insufficient-history symbols | 2 (SKHY, SPCX) |

Conclusion: the system is operational, but the final output needs curation,
risk visibility, and quality disclosure before it becomes a strong daily-view
tool for an investor.

## 2. Current Output Assessment

### 2.1 Investor question coverage

| Daily investor question | Current support | Assessment |
|---|---|---|
| What are the top candidates? | Rank exists, but 148 names are shown | Partial |
| How are candidates ranked? | `Rank` and `CompositeScore` are present | Good |
| What is the signal classification? | A/B/C/D `Signal` is present | Good, but labels need explanation |
| What is the research interpretation? | `ResearchTone` and two summaries are present | Good |
| What are the risk concerns? | Only `RiskStatus` appears in intermediate CSVs | Weak |
| Are there data-quality problems? | Available in validation/readiness artifacts only | Missing from user output |
| Which names need human research? | Generic summary says further review, but no dedicated list | Weak |

The current output can support detailed research inspection, but it requires the
reader to manually scan and reconcile several files. It does not yet support a
fast daily decision about what deserves attention first.

### 2.2 Top candidate clarity

The report is ranked and its first ten names are:

| Rank | Ticker | CompositeScore | Signal | ResearchTone |
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

However, this Top 10 view must currently be inferred from a 148-entry report.
The final user output should explicitly promote it to a summary section.

Only RTX, MA, and BMY currently have `ResearchTone=POSITIVE`. These form a
natural manual-review list, but the system does not present them together.
They are research priorities, not buy recommendations.

### 2.3 Risk and quality visibility

All 148 displayed candidates have `RiskStatus=PASS`, but this status alone does
not tell the reader the level of volatility, drawdown, or Sharpe ratio. Those
metrics exist in `universe150_research_raw.csv` and are absent from the five
audited user-facing outputs.

The dataset validator reports:

- Overall status: `PARTIAL`.
- Missing metric cells: 8.
- Research PASS: 148.
- Research PARTIAL: 2.
- Research FAILED: 0.

Data readiness identifies SKHY (21 rows) and SPCX (39 rows) as below the
252-row readiness threshold. They are excluded from candidates, but the final
report does not explain why the displayed count is 148 rather than 150.

### 2.4 Markdown quality

Strengths:

- Clear headings and consistent per-candidate blocks.
- Rank, score, signal, tone, and summaries are easy to locate.
- No trading instruction or brokerage action is presented.

Weaknesses:

- 3,112 lines are too long for daily scanning.
- `CompositeScore` is shown with 15–16 decimal places.
- The same neutral/caution template is repeated many times.
- There is no executive table, risk section, quality banner, or navigation.
- Signal A/B/C/D is not explained in the report.
- English-only rule text may be less accessible for the intended daily user.

A concise Chinese or bilingual explanation layer would improve accessibility,
provided it remains rule-based, preserves the original fields, and avoids
turning research classifications into trading advice.

## 3. User Layer Recommendation

The investor should normally open one daily dashboard or concise report, not
five separate artifacts.

Recommended daily user layer:

1. A one-page overview containing universe, readiness, validation, and pipeline
   status.
2. A Top 10 candidate table with rank, rounded score, signal, tone, and one-line
   explanation.
3. A separate positive-tone/manual-review shortlist.
4. A risk and data-warning section.
5. Optional expandable detail for the remaining candidates.

Recommended visibility by current file:

| File | Daily user value | Recommendation |
|---|---|---|
| `universe150_research_report.md` | Primary readable output | Keep, but shorten and add overview |
| `universe150_ai_research_summary.csv` | Useful detail/export | Hide behind dashboard download or detail view |
| `universe150_research_explanation.csv` | Explanation trace | Merge into dashboard detail; hide by default |
| `universe150_daily_research_snapshot.csv` | Stable daily snapshot | Keep as system artifact; optional download |
| `universe150_candidate_report.csv` | Intermediate presentation table | Merge with snapshot/dashboard; hide by default |

The explanation and AI-summary CSVs overlap heavily. They can remain separate
system contracts while being presented as one combined user-facing table.

## 4. Dashboard Design Proposal

### Section 1 — Market Universe Status

Display:

- Report date and pipeline status.
- Universe size: 150.
- Data ready: 148.
- Insufficient history: 2.
- Research PASS / PARTIAL / FAILED counts.
- Dataset validation status and a visible warning when not `PASS`.

### Section 2 — Top Research Candidates

Default to Top 10, with an option to expand.

| Field | Presentation rule |
|---|---|
| Rank | Integer |
| Ticker | Canonical `Ticker` label |
| CompositeScore | Round to 3 or 4 decimals |
| Signal | A/B/C/D plus a legend |
| ResearchTone | Color-neutral POSITIVE/NEUTRAL/CAUTION badge |
| ResearchSummary | One concise line |

The dashboard must state that ranking is a research diagnostic and not an
instruction to transact.

### Section 3 — Risk Watchlist

Display names meeting any of these conditions:

- `RiskStatus` is not `PASS`.
- Research status is `PARTIAL` or `FAILED`.
- Data readiness is false.
- Risk metrics are missing.

Suggested columns:

- Ticker.
- RiskStatus.
- Annualized volatility.
- Maximum drawdown.
- Sharpe ratio.
- Observation count.
- Data warning.

For the audited run, SKHY and SPCX should appear with an insufficient-history
warning even though they are absent from the candidate list.

### Section 4 — AI Research Summary

Display for the selected Top 10 or manually chosen ticker:

- Normalized trend, momentum, and volatility semantics.
- ResearchTone.
- ResearchSummary.
- AIResearchSummary template.
- ReportDate.

The label should clarify that the current “AI” text is deterministic template
output and not external model analysis.

### Section 5 — Manual Research Queue

Provide explicit research queues rather than one 148-name candidate pool:

- Positive-tone review queue.
- Caution/risk review queue.
- Data-quality exception queue.
- Remaining neutral candidates, collapsed by default.

## 5. File Classification

### Current dependency chain

```text
Daily Research Pipeline
  |
  +-- System and diagnostic artifacts
  |     +-- universe150_factor_raw.csv
  |     +-- universe150_factor_ranking.csv
  |     +-- universe150_signal.csv
  |     +-- universe150_risk_raw.csv
  |     +-- universe150_research_raw.csv
  |     +-- universe150_research_validation.csv
  |     +-- daily_research_pipeline_status.csv
  |
  +-- Research presentation artifacts
  |     +-- universe150_research_candidates.csv
  |     +-- universe150_candidate_report.csv
  |     +-- universe150_daily_research_snapshot.csv
  |     +-- universe150_research_explanation.csv
  |     +-- universe150_ai_research_summary.csv
  |
  +-- Daily user output
        +-- universe150_research_report.md
        +-- future daily research dashboard
```

### Layer assignment

| Artifact | Layer | Default visibility |
|---|---|---|
| `universe150_research_report.md` | A. User Layer | Visible |
| Future daily dashboard | A. User Layer | Primary daily view |
| `universe150_ai_research_summary.csv` | B. System Layer | Download/detail |
| `universe150_daily_research_snapshot.csv` | B. System Layer | Hidden by default |
| `universe150_candidate_report.csv` | B. System Layer | Hidden by default |
| `universe150_research_candidates.csv` | B. System Layer | Hidden by default |
| `universe150_research_explanation.csv` | C. Debug Layer | Hidden |
| `universe150_research_validation.csv` | C. Debug Layer, summarized to user | Hidden table; show status |
| `universe150_data_readiness.csv` | C. Debug Layer, summarized to user | Hidden table; show warnings |
| `universe150_research_raw.csv` | C. Debug Layer | Hidden |
| Factor, ranking, signal, and risk raw CSVs | C. Debug Layer | Hidden |
| `daily_research_pipeline_status.csv` | C. Debug Layer, summarized to user | Hidden table; show counts |

## 6. Development Roadmap

### Priority 1 — Must optimize

1. Build a single daily dashboard/report overview from existing artifacts; do
   not introduce new calculations.
2. Limit the default candidate presentation to Top 10 or Top 20 while retaining
   full data as a downloadable artifact.
3. Add visible data-quality and validation banners, including the two
   insufficient-history symbols.
4. Add a risk watchlist using already-calculated risk metrics.
5. Round display scores and document the A/B/C/D signal legend.
6. Separate “research candidate” from “manual priority”; 148 READY/HIGH rows do
   not provide useful prioritization.

### Priority 2 — Recommended

1. Present POSITIVE, NEUTRAL, and CAUTION groups as separate research queues.
2. Combine explanation and AI-template text in one expandable candidate detail.
3. Add Chinese or bilingual rule explanations while preserving source values.
4. Explain that AIResearchSummary is currently template-generated.
5. Add report navigation and compact tables rather than repeating full blocks.

### Priority 3 — Consider later

1. Historical comparison of daily rank, signal, and tone changes.
2. User-selectable filtering by sector, signal, tone, and risk status.
3. Export-friendly dashboard views and archived daily reports.
4. Optional charting of existing score and risk fields without changing their
   calculations.

No dashboard should generate buy/sell instructions, position sizing, or
brokerage actions. All outputs remain research diagnostics requiring human
review.
