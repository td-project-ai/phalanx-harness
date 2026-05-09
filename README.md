# phalanx-harness

> Cross-version + multi-repo integration testing for the Phalanx framework.
> Per [ADR-001](https://github.com/td-project-ai/phalanx/blob/main/docs/adr/0001-three-repo-split.md).

## Purpose

This repository hosts test infrastructure that exercises the Phalanx
framework across boundaries that no single repo can validate on its own:

- **Cross-version upgrade testing** - install a prior release of `phalanx`
  core, run HEAD's `upgrade.py` against it, and assert the upgraded install
  passes the HEAD test suite.
- **Multi-repo integration** - install `phalanx` core + `phalanx-market`
  bundles together and validate the combined install behaves as one
  coherent system.
- **Bundle packaging end-to-end** - exercise `plugin_pack.py` against
  the live `phalanx-market` catalog and verify produced archives + sidecars.

## Sibling repos

| Repo | Purpose |
|---|---|
| [`td-project-ai/phalanx`](https://github.com/td-project-ai/phalanx) | Core framework (skills, tools, agents) |
| [`td-project-ai/phalanx-market`](https://github.com/td-project-ai/phalanx-market) | Bundle catalog |
| `td-project-ai/phalanx-harness` (this repo) | Integration + cross-version test harness |

## Status

Bootstrapped. Test workflows land in follow-up PRs:

- **PR-F1** (this PR) - bootstrap: README, layout, smoke test
- **PR-F2** - cross-version upgrade matrix (migrated from core's removed `phalanx-upgrade.yml`)
- **PR-F3** - multi-repo integration tests (core + market combined install)
- **PR-F4** - bundle packaging tests (migrated from core)

## Layout

```
phalanx-harness/
├── tests/                      # pytest suites
│   └── test_smoke.py           # placeholder, asserts harness imports
├── .github/workflows/          # CI workflows (added in later PRs)
└── docs/                       # harness-specific docs
```

## Running locally

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
