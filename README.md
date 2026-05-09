# phalanx-harness

> Multi-repo integration + bundle packaging tests for the Phalanx framework.
> Per [ADR-001](https://github.com/td-project-ai/phalanx/blob/main/docs/adr/0001-three-repo-split.md).
> v3.0.0+ baseline only - cross-version upgrade from v1.x/v2.x is intentionally not supported.

## Purpose

This repository hosts test infrastructure that exercises the Phalanx
framework across boundaries that no single repo can validate on its own:

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
| `td-project-ai/phalanx-harness` (this repo) | Multi-repo integration + bundle packaging test harness |

## Status

Bootstrapped on the **v3.0.0 clean-break baseline**. Cross-version upgrade
testing (v1.x/v2.x -> v3.x) is intentionally out of scope - the v3.0.0 cutover
removed bundle source content, so older installs cannot be meaningfully migrated.

PR roadmap:

- **PR-F1** - bootstrap: README, layout, smoke test ✅
- **PR-F2** - ~~cross-version upgrade matrix~~ DROPPED (v3.0.0 = clean-break)
- **PR-F3** (this PR) - multi-repo integration: validates `--bundle-source` against an external directory, across all platforms
- **PR-F4** - bundle packaging end-to-end against the live `phalanx-market` catalog

## Layout

```
phalanx-harness/
├── tests/                              # guard tests for workflows + smoke
│   ├── test_smoke.py
│   └── test_multi_repo_integration.py
├── .github/workflows/
│   ├── smoke.yml                       # pytest on push/PR
│   └── multi-repo-integration.yml      # nightly + on-demand
└── requirements-dev.txt
```

## Running locally

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
