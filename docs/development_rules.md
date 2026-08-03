# AI_investing Development Rules

## Document status

This document defines the mandatory development, validation, Git, and release workflow for AI_investing.

It applies to planned versions, material changes, human contributors, and all AI-assisted development tools used with the repository. Minor typo and formatting fixes may be treated as documentation-only changes without a separate classification record.

This document governs how changes are proposed and delivered. It does not authorize automatic trading, brokerage integration, order submission, or any other form of execution.

## Documentation authority

When documentation conflicts:

1. `development_rules.md` governs development, validation, Git, and release workflow.
2. `architecture.md` governs system architecture and safety boundaries.
3. `module_catalog.md` governs module status and classification.
4. `README.md` provides project overview and user entry documentation.
5. Runtime behavior is determined by implementation and validation evidence.

Documentation conflicts affecting behavior, safety, contracts, or version claims MUST be resolved before release.

## Normative language

The terms `MUST`, `MUST NOT`, `REQUIRED`, `SHOULD`, `SHOULD NOT`, and `MAY` are normative.

- `MUST` and `REQUIRED` define mandatory rules.
- `MUST NOT` defines a prohibited action.
- `SHOULD` defines the expected practice unless a documented reason justifies an exception.
- `MAY` defines an optional practice.

When a planned version or material change belongs to more than one classification, the strictest applicable approval, validation, and release rules MUST be followed.

## Roles and decision authority

### User

The user has final decision authority over:

- system architecture;
- supported pipeline boundaries;
- investment methodology;
- scoring models;
- signal definitions;
- backtest rules;
- portfolio construction;
- position sizing;
- risk limits;
- review rules;
- safety and execution boundaries;
- implementation scope;
- release scope.

Material architecture, investment-system, safety, and release decisions MUST receive explicit user approval before implementation or release.

### ChatGPT

ChatGPT is an architecture and review assistant.

ChatGPT MAY:

- analyze requirements and existing behavior;
- identify assumptions, trade-offs, and risks;
- propose architecture and module designs;
- review investment-system proposals;
- review implementation plans and diffs;
- recommend validation and release checks.

ChatGPT is not a mandatory formal approver and does not replace user approval. A ChatGPT response is advisory unless the user explicitly adopts the proposal.

### Codex and Copilot

Codex and Copilot are implementation assistants.

They MAY:

- inspect the repository;
- explain existing behavior;
- draft proposals;
- implement an approved design;
- add or update validation;
- run approved checks;
- review diffs;
- prepare explicit Git commands.

They MUST NOT independently:

- change investment strategy;
- change scoring formulas or weights;
- change signal rules;
- change qualification thresholds;
- change backtest rules;
- change portfolio rules;
- change risk limits or multipliers;
- change order-review rules;
- weaken the manual-review boundary;
- add execution or brokerage capabilities;
- expand the approved scope of a version;
- create a release tag before the version is complete.

If requirements are ambiguous and the ambiguity could affect investment behavior, risk, safety, or execution, implementation MUST pause until the user decides the intended behavior.

AI-generated code and documentation MUST be reviewed as proposed work, not treated as an independent source of authority.

## Non-negotiable safety boundary

AI_investing is a research and decision-support system.

The supported system MUST NOT:

- connect to a brokerage account;
- authenticate with a broker for trading;
- submit an order;
- route an order;
- automatically approve an order;
- automatically execute a transaction;
- convert a research signal into an executable instruction;
- bypass independent human review.

All order-like outputs MUST remain draft-only.

`BUY`, `WATCH`, `IGNORE`, `PASS`, `REVIEW`, or similar statuses are research classifications. They are not authorization to trade.

A validation result indicates only that the implemented checks passed. It is not investment approval.

Every output that could inform a real investment decision requires independent human review.

A proposed change that weakens these boundaries MUST NOT be implemented under the current project scope.

## Change classification

Each planned version and each material change MUST be classified before implementation. The proposal or review record SHOULD identify the primary classification and any secondary classifications.

Minor typo, punctuation, whitespace, and formatting fixes MAY be treated as documentation-only without a separate classification record, provided they do not alter meaning, version claims, commands, contracts, or behavior.

### Documentation-only

A documentation-only change affects prose, diagrams, comments, or metadata and does not change runtime behavior.

Examples include:

- correcting explanations;
- documenting existing modules;
- updating architecture diagrams;
- clarifying operating procedures;
- aligning version-specific references.

A documentation-only change MUST NOT contain a silent code, configuration, formula, threshold, contract, or behavior change.

### Configuration-only

A configuration-only change modifies values or paths in configuration without changing implementation structure.

This classification includes changes to:

- account settings;
- position or exposure limits;
- scoring weights;
- risk multipliers;
- allowed actions or statuses;
- order-review limits;
- artifact paths;
- project version.

A configuration-only change may materially change investment behavior. It MUST therefore receive investment-logic review whenever it affects scoring, signals, portfolio construction, risk, or review decisions.

### Validation

A validation change modifies checks for configuration, inputs, outputs, formulas, schemas, ranges, safety rules, or repository health.

Validation changes MUST remain aligned with the corresponding producer and contract.

A validation change MUST NOT silently redefine valid investment behavior. Tightening or weakening an accepted range, formula, threshold, or status is also an investment-logic or safety-boundary change when applicable.

### Refactoring

A refactoring changes implementation structure while intending to preserve externally observable behavior.

Examples include:

- extracting functions;
- centralizing paths;
- renaming internal helpers;
- reducing duplication;
- reorganizing modules;
- improving error handling without changing accepted results.

A refactoring MUST demonstrate behavior preservation through targeted checks and affected pipeline checks.

Refactoring MUST NOT be used to conceal formula, threshold, signal, schema, contract, or output changes.

### Investment logic

An investment-logic change affects any rule used to produce, rank, qualify, size, review, or explain an investment candidate.

This includes changes to:

- indicators or factor inputs;
- scoring formulas;
- weights;
- thresholds;
- signal definitions;
- backtest entries or exits;
- holding periods;
- qualification rules;
- fundamental scoring;
- combined scoring;
- risk classification;
- risk multipliers;
- candidate selection;
- position sizing;
- share rounding;
- exposure rules;
- portfolio limits;
- order-review rules.

Investment-logic changes require explicit user approval and an independent design review before implementation. The independent design review MAY use ChatGPT, another qualified reviewer, or a documented comparison against existing architecture, contracts, and validation evidence.

The independent design review MUST be separate from the original implementation proposal.

A restatement of the implementation proposal is not an independent review.

The review MUST challenge assumptions, identify affected contracts, consider alternatives, and record unresolved risks. The implementation assistant MUST NOT approve its own proposal; review must be a separate reasoning step.

The proposal MUST state the intended behavior, assumptions, affected modules, expected output changes, risks, and validation plan. The design reviewer MUST be able to identify unresolved assumptions and challenge whether the change preserves the project's safety boundary.

### Safety boundary

A safety-boundary change affects the separation between research output and real-world execution or affects a control intended to prevent unsafe behavior.

This includes changes involving:

- brokerage connectivity;
- order submission or routing;
- automatic execution;
- draft-only status;
- allowed order actions;
- automatic approval;
- mandatory human review;
- blocking and review statuses;
- fail-open versus fail-closed behavior.

Safety-boundary changes require explicit user approval and independent design review. A change that enables brokerage integration, automatic order submission, or automatic execution is prohibited under the current project scope.

### Release metadata

A release-metadata change affects:

- `PROJECT_VERSION` in `config.py`;
- the current version in `README.md`;
- version-specific statements in project documentation;
- version-report output;
- release notes;
- Git tags.

Release metadata MUST describe an already reviewed, coherent release. It MUST NOT be used to make an incomplete change appear released.

## Mandatory development workflow

Every planned version and material repository change MUST follow this sequence.

### 1. Requirement analysis

Before editing, determine:

- the requested outcome;
- the current behavior;
- the files and modules likely to be affected;
- the change classification;
- whether investment logic or safety boundaries are involved;
- the acceptance criteria;
- the required validation;
- whether a version change is intended.

Assumptions and unresolved questions that could affect behavior MUST be made explicit.

### 2. Module design

For code, configuration, validation, or architecture changes, identify:

- affected producers and consumers;
- input and output contracts;
- configuration dependencies;
- validation dependencies;
- generated artifacts;
- failure behavior;
- backward-compatibility requirements;
- safety implications.

Changes SHOULD be kept as small and inspectable as practical.

### 3. AI-assisted proposal

An AI implementation assistant SHOULD present a proposal before material implementation.

The proposal SHOULD include:

- change classification;
- files to be changed;
- behavior that will change;
- behavior that must remain unchanged;
- validation commands;
- version and release impact;
- identified risks.

For investment-logic and safety-boundary changes, a proposal and independent design review are REQUIRED.

### 4. Human review

The user MUST review and approve the proposal before implementation when the change affects:

- architecture;
- investment logic;
- risk;
- portfolio rules;
- signals;
- thresholds;
- execution boundaries;
- release scope.

ChatGPT or another reviewer MAY support the review, but user approval remains controlling.

### 5. Implementation

Implementation MUST remain within the approved scope.

The implementation assistant MUST NOT add unrelated cleanup, change an unapproved setting, or silently alter behavior.

Producer, consumer, validator, configuration, and documentation changes that form one contract MUST remain aligned.

### 6. Validation

Run validation appropriate to the change classification.

Validation results MUST be reviewed, not merely executed.

Required validation failures MUST be resolved before commit or release.

A known limitation or non-applicable check MAY be accepted by the user only when:

- the failed check is not required for the change classification;
- the reason is documented;
- the limitation does not affect investment logic, data integrity, risk controls, safety boundaries, or release correctness.

A required safety, investment-logic, contract, or version-consistency check MUST NOT be waived.

An accepted documented limitation is not a passing validation result. It records why a non-required check does not apply or cannot currently provide additional evidence. Any required validation failure remains a blocking failure and MUST prevent commit or release.

Generated runtime artifacts created during validation MUST NOT be staged unless their inclusion was explicitly approved.

Successful use of existing or stale artifacts does not prove end-to-end correctness. A passing pipeline or smoke test that reuses prior outputs proves only what the executed checks establish. When end-to-end correctness matters, validation MUST establish artifact freshness, compatible inputs, and the required upstream-to-downstream flow.

### 7. Git review

Before staging, review:

```bash
git status
git diff
git diff --check
```

The review MUST confirm:

- only intended files changed;
- no secrets or credentials were introduced;
- no generated runtime artifacts were included;
- no unexplained behavior changes occurred;
- version declarations are correct when applicable;
- documentation matches implementation.

### 8. Explicit staging

Stage only explicitly reviewed files:

```bash
git add <file_1> <file_2>
```

Then review the staged change:

```bash
git diff --cached
git status
```

Do not commit until the staged diff exactly matches the approved release scope.

### 9. Commit

Create a commit only after required validation and staged-diff review pass.

The commit message SHOULD describe the coherent development theme and SHOULD distinguish documentation, validation, refactoring, investment-logic, safety, and release-metadata changes where relevant.

### 10. Push the commit

Push the reviewed commit before creating the release tag:

```bash
git push
```

Confirm that the intended remote branch contains the release commit.

### 11. Create and push the release tag

Create a release tag only after:

- the release scope is complete;
- validation has passed;
- version metadata is aligned;
- the release commit has been reviewed and committed;
- the commit has been pushed;
- the working tree is clean.

The tag MUST be annotated:

```bash
git tag -a vX.Y.Z -m "AI_investing vX.Y.Z"
git push origin vX.Y.Z
```

The tag MUST point to the reviewed release commit.

### 12. Verify

After pushing the tag, verify:

- the local and remote branch contain the intended release commit;
- the annotated tag points to that commit;
- the tag is present on the remote;
- the working tree is clean;
- version-specific declarations remain aligned.

The required release order is:

```text
validate
-> review
-> explicit stage
-> commit
-> push commit
-> create annotated tag
-> push tag
-> verify
```

## Validation requirements

### Required checks for every change

Every change MUST include:

```bash
git diff --check
git status
```

Python files that changed MUST receive an appropriate syntax check, for example:

```bash
python3 -m py_compile <changed_python_files>
```

Equivalent non-mutating syntax checks MAY be used where appropriate.

### Targeted module checks

Changed modules MUST receive focused validation covering their direct behavior and contracts.

Examples include:

- running the corresponding validation module;
- exercising a changed pure calculation;
- checking required columns and formulas;
- checking allowed values and boundary conditions;
- verifying producer and validator agreement;
- reviewing generated text or CSV output.

A validator must not be treated as proof of correctness outside the behavior it actually checks.

### Pipeline checks

Affected pipeline checks are REQUIRED when a change can alter runtime behavior.

- Daily screening changes require the relevant daily-pipeline checks.
- Backtest changes require the backtest pipeline and backtest-output validation.
- Portfolio, scoring, sizing, order-draft, order-review, reporting, or system-health changes require the affected portfolio checks.
- Cross-pipeline contract changes require every affected pipeline.

A full pipeline run is not automatically required for a documentation-only change that cannot affect runtime behavior. Documentation must still be checked for accuracy, links, formatting, and version consistency.

Pipeline checks that update market data, rely on external services, or overwrite runtime artifacts MUST be run only with explicit awareness of those effects.

File existence alone does not prove freshness or provenance. Successful use of stale daily, backtest, portfolio, or report artifacts MUST NOT be represented as proof of end-to-end correctness.

### Repository checks

Before commit, run:

```bash
git diff --check
git status
```

Before release, also inspect:

```bash
git diff --cached
git status
```

After commit, push, and tag publication, verify the branch, tag, and working tree again.

### Version-consistency checks

For a release, confirm alignment among all version-specific declarations, including:

- `PROJECT_VERSION` in `config.py`;
- the current version in `README.md`;
- version-specific metadata in `docs/`;
- the version reported by `system_version.py`;
- the intended Git release tag.

Documents MAY describe a version family such as `V3.2.x`. A family-level declaration does not require a patch-version update unless the document's content, scope, or claims change. A document that names a specific patch version MUST align with the release it claims to describe.

The generated system-version report MUST be regenerated or otherwise verified during release validation. Because it is a runtime artifact, it SHOULD remain untracked unless explicitly approved.

The release MUST NOT proceed if any version-specific authoritative declaration disagrees.

## Validation matrix

| Change classification | Minimum required validation |
|---|---|
| Documentation-only | Review rendered Markdown or source formatting, check links and references, `git diff --check`, `git status`, and version consistency when version-specific metadata changes |
| Configuration-only | Syntax/import check, `validate_config.py`, targeted affected-module checks, affected pipeline checks, and boundary-value review |
| Validation | Syntax check, focused passing and failing cases, producer/validator contract review, and affected pipeline checks |
| Refactoring | Syntax check, targeted behavior checks, affected validators, affected pipeline checks, and before/after output comparison where practical |
| Investment logic | Syntax check, focused formula and boundary tests, affected validators, affected pipelines, output comparison, explicit user approval, and independent design review |
| Safety boundary | All affected checks, explicit fail-closed tests, manual-review verification, explicit user approval, and independent design review |
| Release metadata | Version consistency, system-version output review, Git commit/tag review, and clean-working-tree verification |

When classifications overlap, apply the strongest row.

## Git rules

### Explicit staging

Do not use:

```bash
git add .
```

Do not use broad staging commands or globs that could include unrelated files.

Stage explicit reviewed files only:

```bash
git add README.md docs/architecture.md
```

### Generated artifacts

Do not commit generated runtime artifacts unless their inclusion is explicitly approved and documented.

This includes ordinary outputs under:

- `data/` when the files are downloaded market data or runtime-generated data;
- `results/`;
- `reports/`;
- `logs/`.

Downloaded market data and manually maintained input contracts are not the same category.

- Downloaded market data SHOULD remain ignored and recoverable from its documented source.
- Required manually maintained input files MUST have an explicit policy defining whether they are tracked, represented by a tracked template or schema, or recoverable through a documented procedure.
- A required manual input MUST NOT depend on an undocumented local-only file with no template, schema, or recovery path.
- Sensitive, licensed, or environment-specific input data MUST NOT be committed merely because it is required at runtime.

Existing approved tracked artifacts do not create general permission to add new generated artifacts.

### Coherent versions

One version MUST represent one coherent development theme.

Unrelated investment logic, cleanup, documentation, and experimental changes SHOULD NOT be bundled into one release.

A release commit or tightly related commit sequence MUST be reviewable as one deliberate unit.

### Tag timing and order

Do not create a release tag before the version is complete.

The required order is:

1. validate;
2. review the Git diff and results;
3. stage explicit files;
4. commit;
5. push the commit;
6. create an annotated release tag;
7. push the tag;
8. verify the release state.

### Clean working tree

Before tagging and after pushing the tag, verify:

```bash
git status
```

The working tree MUST be clean.

The release tag MUST resolve to the intended release commit, and that commit MUST be present on the release branch's remote.

## Version rules

For every release, all version-specific declarations MUST remain aligned, including:

1. `PROJECT_VERSION` in `config.py`;
2. the current version declared in `README.md`;
3. patch-specific metadata in architecture, module-catalog, release, and other applicable documentation;
4. the project version emitted by `system_version.py`;
5. the Git release tag.

Version strings SHOULD use the existing `vX.Y.Z` format.

Documents MAY intentionally describe a compatible version family, such as `V3.2.x`, instead of a specific patch version. Such documents do not require patch-version edits for every release unless their content, supported architecture, module inventory, contracts, or claims change.

Changing the Git tag alone is not sufficient to change the project version.

Changing `config.py` alone is not sufficient to complete a release.

If a document states that it describes a specific patch version, that statement MUST be updated or intentionally described as historical.

The Git tag MUST be created only after the release commit contains all intended version metadata.

## Version update timing

Version metadata SHOULD be updated only after the release scope is substantially complete.

The version MUST be aligned before:

- final validation;
- staging;
- commit;
- release tagging.

A version number MUST NOT be advanced merely because development has started.

The intended sequence is:

1. complete the release content;
2. update version metadata once;
3. validate;
4. commit;
5. tag.

## Documentation and cleanup release restrictions

A documentation-only or cleanup release MUST preserve runtime behavior.

Unless separately proposed, approved, implemented, validated, and classified as an investment-logic change, it MUST NOT change:

- scoring formulas;
- scoring inputs;
- scoring weights;
- qualification thresholds;
- signal thresholds;
- signal meanings;
- backtest entry rules;
- backtest exit rules;
- holding periods;
- portfolio-selection rules;
- portfolio exposure rules;
- maximum holding rules;
- maximum position rules;
- cash-reserve rules;
- risk classifications;
- risk multipliers;
- position-sizing behavior;
- share-rounding behavior;
- order-review rules;
- allowed actions or statuses;
- draft-only behavior;
- the mandatory human-review boundary.

Documentation and cleanup releases MUST NOT introduce silent behavior changes.

If implementation behavior must change to make documentation accurate, the change MUST be reclassified and reviewed under the applicable runtime category.

## Generated files and repository hygiene

Generated files MUST follow `.gitignore` policy unless explicit approval is given to track a specific artifact.

The following locations normally contain runtime data or generated output:

- `data/` for downloaded or generated data;
- `results/`;
- `reports/`;
- `logs/`.

Manually maintained input contracts under `data/` MUST follow their explicit tracking, template, schema, or recovery policy rather than being treated as downloaded market data.

Before staging, contributors MUST inspect `git status` for:

- downloaded market data;
- generated CSV files;
- generated text or HTML reports;
- pipeline logs;
- caches;
- temporary files;
- editor files;
- credentials;
- environment-specific files.

Generated reports MUST NOT be committed merely because they demonstrate that a pipeline ran.

A generated artifact MAY be tracked only when:

- it serves a deliberate documentation, fixture, or contract purpose;
- its ownership and update procedure are defined;
- it contains no sensitive or misleading runtime data;
- its inclusion is explicitly approved;
- `.gitignore` is adjusted narrowly where necessary.

Never force-add an ignored runtime artifact without explicit approval.

## Release completion checklists

### Mandatory release gate

A release MUST NOT be tagged until every applicable item in this gate is satisfied.

#### Scope and authority

- [ ] The release has a defined, coherent development theme.
- [ ] Planned-version and material-change classifications are recorded.
- [ ] The user approved all material architecture, investment-system, safety, and release decisions.
- [ ] Implementation assistants remained within the approved scope.
- [ ] No prohibited brokerage or execution capability was introduced.

#### Validation and review

- [ ] Required syntax checks passed.
- [ ] Required targeted module checks passed.
- [ ] Required affected validators passed.
- [ ] Required affected pipeline checks passed.
- [ ] Validation limitations, artifact freshness, and stale-artifact risks were reviewed.
- [ ] `git diff --check` passed.
- [ ] The Git diff contains only intended changes.
- [ ] Documentation matches the implemented behavior.

#### Repository hygiene

- [ ] No secrets, credentials, caches, logs, or unintended runtime artifacts are included.
- [ ] Downloaded market data follows ignore and recovery policy.
- [ ] Required manual inputs have a tracking, template, schema, or recovery policy.
- [ ] Generated files follow `.gitignore` or have explicit approval.
- [ ] Files were staged explicitly.
- [ ] `git add .` was not used.
- [ ] `git diff --cached` matches the approved release scope.

#### Version and release sequence

- [ ] All version-specific declarations are aligned.
- [ ] Version-family documentation remains accurate for the release.
- [ ] `system_version.py` output was verified.
- [ ] The reviewed changes were committed.
- [ ] The release commit was pushed before tag creation.
- [ ] The annotated release tag was created after the commit was pushed.
- [ ] The annotated tag was pushed.
- [ ] The tag points to the intended remote release commit.
- [ ] The final working tree is clean.

### Extended checklist for investment logic, safety, or major refactoring

This checklist is REQUIRED in addition to the mandatory release gate when a release changes investment logic, safety controls, or performs major refactoring.

#### Design authority and traceability

- [ ] The intended behavior and unchanged behavior are documented.
- [ ] Key assumptions and unresolved uncertainties are explicit.
- [ ] The user explicitly approved the design.
- [ ] An independent design review was completed and recorded.
- [ ] Affected producers, consumers, validators, and contracts are identified.
- [ ] Backward-compatibility and migration effects are documented.

#### Investment logic

- [ ] Formula, weight, threshold, signal, holding-period, and qualification changes are individually identified.
- [ ] Boundary cases and representative examples were checked.
- [ ] Before-and-after outputs were compared where practical.
- [ ] Unexpected ranking, qualification, sizing, or review changes were investigated.
- [ ] The change remains explainable to a human reviewer.

#### Safety boundary

- [ ] Draft-only status remains enforced.
- [ ] Independent human review remains mandatory.
- [ ] No order submission, routing, or automatic execution path exists.
- [ ] Failure behavior is fail-closed where safety is affected.
- [ ] `PASS` or equivalent validation status cannot be mistaken for investment approval.

#### Major refactoring

- [ ] Behavior-preservation evidence is recorded.
- [ ] Input and output schemas remain compatible or have an approved migration.
- [ ] Paths, filenames, units, and column meanings were checked.
- [ ] All affected pipelines were exercised with controlled,reproducible, or sufficiently fresh inputs appropriate to the validation objective.
- [ ] Successful reuse of stale artifacts was not treated as end-to-end proof.

The validation record should identify whether inputs were:

- live data;
- cached data;
- fixture data;
- manually maintained inputs.

A release is complete only after the mandatory release gate and every applicable extended item are satisfied.