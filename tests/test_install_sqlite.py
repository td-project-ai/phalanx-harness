"""Guard tests for the Install (sqlite) workflow.

PR-H1: the workflow runs phalanx core's installer with sqlite-only backend
wiring and asserts the install-state file records ``state["runtime"]`` with
postgres disabled and both memory + activity on sqlite.

These guard tests run locally (cheap) and protect the workflow YAML from
silent regressions - someone trimming the matrix, dropping the runtime
record step, or weakening the assertions.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "install-sqlite.yml"

# Platforms the matrix MUST exercise. Each runs the install end-to-end.
REQUIRED_PLATFORMS = {"claude", "copilot", "codex"}


@pytest.fixture(scope="module")
def workflow_text() -> str:
    assert WORKFLOW.is_file(), f"workflow missing: {WORKFLOW}"
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow_yaml() -> dict:
    import yaml
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_parses(workflow_yaml):
    assert workflow_yaml.get("name") == "Install (sqlite)"
    assert "install-sqlite" in workflow_yaml.get("jobs", {})


def test_required_platforms_present(workflow_yaml):
    matrix = (
        workflow_yaml["jobs"]["install-sqlite"]
        .get("strategy", {})
        .get("matrix", {})
    )
    platforms = set(matrix.get("platform", []))
    missing = REQUIRED_PLATFORMS - platforms
    assert not missing, (
        f"required platforms missing from matrix: {missing}. "
        f"Dropping one means a platform stops being integration-tested."
    )


def test_workflow_runs_installer(workflow_text):
    """The job must actually run phalanx core's installer."""
    assert "phalanx_install.py" in workflow_text, (
        "workflow must invoke core/tools/platform/phalanx_install.py"
    )
    assert "--skip-healthcheck" in workflow_text, (
        "harness installs should skip healthcheck (no real platform present)"
    )


def test_workflow_writes_sqlite_config(workflow_text):
    """An sqlite-only config.yaml must be staged so runtime_summary reads
    sqlite as the backend for both memory and activity. The config must
    NOT declare a services.postgres block."""
    assert "target/.phalanx/config.yaml" in workflow_text, (
        "workflow must write .phalanx/config.yaml under the install target"
    )
    # Lightweight check: the config heredoc names both memory + activity
    # as sqlite. Avoids brittle exact-text matching.
    assert "memory:" in workflow_text and "backend: sqlite" in workflow_text, (
        "workflow must wire memory backend to sqlite"
    )
    assert "activity:" in workflow_text, (
        "workflow must wire activity backend to sqlite"
    )
    assert "services:" not in workflow_text or "postgres:" not in workflow_text, (
        "sqlite-only workflow must NOT declare a services.postgres block"
    )


def test_workflow_records_runtime(workflow_text):
    """The runtime snapshot must be stamped into installed.json by calling
    bootstrap_state.py --record-runtime."""
    assert "bootstrap_state.py" in workflow_text, (
        "workflow must invoke bootstrap_state.py"
    )
    assert "--record-runtime" in workflow_text, (
        "workflow must stamp the runtime snapshot into installed.json"
    )
    assert "--root" in workflow_text, (
        "workflow must pass --root pointing at the install target"
    )


def test_workflow_asserts_runtime_block(workflow_text):
    """The assertion step must check all three invariants of an sqlite
    install: postgres disabled, memory==sqlite, activity==sqlite. Any
    drift here weakens the harness."""
    # Reads installed.json
    assert "installed.json" in workflow_text, (
        "assertion step must read installed.json"
    )
    # Checks the three keys
    assert "services" in workflow_text and "postgres" in workflow_text, (
        "assertion step must check services.postgres state"
    )
    assert "enabled" in workflow_text, (
        "assertion step must verify services.postgres.enabled is False"
    )
    assert '"sqlite"' in workflow_text or "'sqlite'" in workflow_text, (
        "assertion step must compare backend strings against 'sqlite'"
    )
    # Both consumers asserted
    assert workflow_text.count("sqlite") >= 3, (
        "assertion step should assert sqlite for BOTH memory and activity "
        "(plus the config heredoc) - at least 3 occurrences expected"
    )


def test_workflow_uses_phalanx_pat(workflow_text):
    """Checkout of private phalanx core requires PHALANX_PAT."""
    assert "PHALANX_PAT" in workflow_text, (
        "workflow must use secrets.PHALANX_PAT to clone private phalanx core"
    )


def test_workflow_runs_on_pull_request(workflow_yaml):
    """PR triggers must include the workflow file and its guard test so
    edits are validated before merge."""
    pr = workflow_yaml.get(True, workflow_yaml.get("on", {})).get("pull_request", {})
    # PyYAML parses bare `on:` as True - the fixture handles that fallback.
    paths = pr.get("paths", []) if isinstance(pr, dict) else []
    assert ".github/workflows/install-sqlite.yml" in paths, (
        "pull_request trigger must include the workflow file in paths"
    )
    assert "tests/test_install_sqlite.py" in paths, (
        "pull_request trigger must include the guard test in paths"
    )
