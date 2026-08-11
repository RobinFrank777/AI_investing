# AI_investing Version Management Strategy

## 1. Purpose

Starting with V3.9.0 development, AI_investing follows semantic versioning
principles to distinguish stable releases, development milestones, and release
candidates.

The strategy keeps project history clear and prevents internal development
checkpoints from being confused with production releases. Each version label
must communicate whether an artifact is stable, under active development, or
awaiting final release approval.

## 2. Version Format

Official versions use:

```text
vMAJOR.MINOR.PATCH
```

Examples:

```text
v3.8.0
v3.9.0
v4.0.0
```

### MAJOR

Increment `MAJOR` for large or incompatible architecture changes, including:

- a new system architecture
- incompatible data-model changes
- a major pipeline redesign

Example:

```text
v4.0.0
```

### MINOR

Increment `MINOR` for new features or meaningful capability expansion,
including:

- a new research module
- a new analysis layer
- a new workflow

Example:

```text
v3.9.0
```

### PATCH

Increment `PATCH` for small, backward-compatible changes, including:

- bug fixes
- documentation fixes
- small improvements

Examples:

```text
v3.9.1
v3.9.2
```

## 3. Release Tags

Official release tags use only:

```text
vX.Y.Z
```

Examples:

```text
v3.8.0
v3.9.0
```

Official release tags represent:

- stable versions
- GitHub releases
- production milestones

An official release tag must identify a reviewed, immutable repository state.

## 4. Development Milestones

Development progress must not use a production-style stable tag. Internal
checkpoints may use phase naming such as:

```text
v3.9.0-phase1
v3.9.0-phase2
```

The preferred naming convention is:

```text
milestone/v3.9-phase1
milestone/v3.9-phase2
```

Development milestones are internal checkpoints only. They do not represent an
official release, a GitHub release, or a production milestone.

## 5. Release Candidate

Before a final stable release, use release-candidate tags:

```text
v3.9.0-rc1
v3.9.0-rc2
```

A release candidate indicates that the planned release scope is complete and is
under final validation. Before creating an RC tag:

- required tests must be completed
- release documentation must be updated
- release review must be completed

An RC remains a pre-release and must not be presented as the stable version.

## 6. Git Workflow

The intended release progression is:

```text
feature branch
      |
      v
development milestone
      |
      v
release candidate
      |
      v
stable release tag
```

For the V3.9.0 release line, the final stable tag is:

```text
v3.9.0
```

Feature work should be reviewed and validated before it is included in a
milestone. Milestones may be used during development, RC tags identify final
release candidates, and only the stable tag represents the official release.

## 7. Current Version History Note

Previous stable versions include:

```text
v3.7.0
v3.8.0
```

Current stable version:

```text
v3.8.0
```

Future development line:

```text
v3.9.x
```

## 8. Rules

- Never move an existing release tag.
- Never overwrite a published version.
- Stable tags represent immutable releases.
- Development tags are optional and must remain distinguishable from stable
  release tags.
- Documentation version metadata must match the runtime version.
- Release-candidate and milestone labels must not be presented as stable
  releases.
- A stable release tag may be created only after validation and release review
  are complete.
