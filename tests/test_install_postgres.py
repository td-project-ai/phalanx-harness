"""Guard tests for the Install (postgres-as-service) workflow.

PR-H2: companion to test_install_sqlite.py. The workflow runs phalanx
core's installer with a postgres-as-service runtime config and asserts
the install-state file records ``state["runtime"]`` with postgres enabled
and both memory + activity wired to postgres.

These guard tests run locally (cheap) and protect the workflow YAML from
silent regressions - someone trimming the matrix, dropping the runtime
record step, weakening the assertions, or worst of all letting credentials
slip into the redaction guarantee check.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "install-postgres.yml"

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
    assert workflow_yaml.get("name") == "Install (postgres-as-service)"
    assert "install-postgres" in workflow_yaml.get("jobs", {})


def test_required_platforms_present(workflow_yaml):
    matrix = (
        workflow_yaml["jobs"]["install-postgres"]
        .get("strategy", {})
        .get("matrix", {})
    )
    platforms = set(matrix.get("platform", []))
    missing = REQUIRED_PLATFORMS - platforms
    assert not missing, (
        f"required platforms missing from matrix: {missing}. "
        f"Dropping one means a platform stops being integration-tested."
    )


def test_workflow_starts_postgres_service(workflow_yaml):
    """The job must spin up a postgres service container so the runtime
    config has something real to point at."""
    services = workflow_yaml["jobs"]["install-postgres"].get("services", {})
    pg = services.get("postgres")
    assert pg is not None, "workflow must declare a 'postgres' service"
    assert "postgres" in str(pg.get("image", "")), (
        "service must use the postgres image"
    )
    env = pg.get("env", {})
    assert env.get("POSTGRES_USER") == "phalanx", (
        "service must create the phalanx role used by the runtime config"
    )


def test_workflow_runs_installer(workflow_text):
    """The job must actually run phalanx core's installer."""
    assert "phalanx_install.py" in workflow_text, (
        "workflow must invoke core/tools/platform/phalanx_install.py"
    )
    assert "--skip-healthcheck" in workflow_text, (
        "harness installs should skip healthcheck (no real platform present)"
    )


def test_workflow_writes_postgres_config(workflow_text):
    """A postgres-as-service config.yaml must be staged so runtime_summary
    reads postgres for services AND for both consumers."""
    assert "target/.phalanx/config.yaml" in workflow_text, (
        "workflow must write .phalanx/config.yaml under the install target"
    )
    assert "services:" in workflow_text and "postgres:" in workflow_text, (
        "workflow must declare a services.postgres block"
    )
    assert "enabled: true" in workflow_text, (
        "workflow must enable services.postgres"
    )
    assert "backend: postgres" in workflow_text, (
        "workflow must wire memory/activity backends to postgres"
    )
    assert "phalanx_memory" in workflow_text, (
        "workflow must name the memory database"
    )
    assert "phalanx_activity" in workflow_text, (
        "workflow must name the activity database"
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
    """The assertion step must check the full postgres invariant set:
    services.postgres enabled + correct host/port/user, both consumers on
    postgres with the right database names."""
    assert "installed.json" in workflow_text
    # services.postgres assertions
    assert "services.postgres.enabled != True" in workflow_text, (
        "must assert services.postgres.enabled is True"
    )
    assert "services.postgres.host" in workflow_text, (
        "must assert services.postgres.host"
    )
    assert "services.postgres.port" in workflow_text, (
        "must assert services.postgres.port"
    )
    # consumer assertions
    assert "memory.backend != 'postgres'" in workflow_text, (
        "must assert memory.backend is postgres"
    )
    assert "memory.database != 'phalanx_memory'" in workflow_text, (
        "must assert memory.database name"
    )
    assert "activity.backend != 'postgres'" in workflow_text, (
        "must assert activity.backend is postgres"
    )
    assert "activity.database != 'phalanx_activity'" in workflow_text, (
        "must assert activity.database name"
    )


def test_workflow_asserts_credential_redaction(workflow_text):
    """The runtime snapshot must NEVER carry the password or password_env.
    The assertion step has to grep for those tokens and fail if found.
    Without this guard a future refactor could silently start leaking
    credentials into installed.json."""
    assert "phalanx-test-pw" in workflow_text, (
        "redaction check must look for the literal password used in CI"
    )
    assert "password_env" in workflow_text, (
        "redaction check must look for 'password_env' key name"
    )
    assert "PHALANX_PG_PASSWORD" in workflow_text, (
        "redaction check must look for the env var name"
    )
    assert "leaks forbidden token" in workflow_text, (
        "assertion step must emit a clear failure when a forbidden token is found"
    )


def test_workflow_uses_phalanx_pat(workflow_text):
    """Checkout of private phalanx core requires PHALANX_PAT."""
    assert "PHALANX_PAT" in workflow_text


def test_workflow_runs_on_pull_request(workflow_yaml):
    """PR triggers must include the workflow file and its guard test so
    edits are validated before merge."""
    on_block = workflow_yaml.get(True, workflow_yaml.get("on", {}))
    # PyYAML parses bare `on:` as True - handle both.
    pr = on_block.get("pull_request", {}) if isinstance(on_block, dict) else {}
    paths = pr.get("paths", []) if isinstance(pr, dict) else []
    assert ".github/workflows/install-postgres.yml" in paths, (
        "pull_request trigger must include the workflow file in paths"
    )
    assert "tests/test_install_postgres.py" in paths, (
        "pull_request trigger must include the guard test in paths"
    )
