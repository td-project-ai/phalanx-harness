"""Guard tests for the Cross-Version Upgrade workflow.

The workflow itself runs in GitHub Actions against real phalanx releases
(too expensive to run locally). These tests validate the workflow YAML stays
well-formed and references the steps the harness contract requires.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "cross-version-upgrade.yml"

# from_version tags the matrix MUST exercise. Update when adding a new
# major/minor that introduces a non-trivial upgrade path. Removing a tag
# requires an ADR amendment - older installs in the wild still need to be
# upgradable.
REQUIRED_FROM_VERSIONS = {"v1.8.1", "v1.9.4", "v1.11.0", "v2.1.0", "v2.10.0"}


@pytest.fixture(scope="module")
def workflow_text() -> str:
    assert WORKFLOW.is_file(), f"workflow missing: {WORKFLOW}"
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow_yaml() -> dict:
    import yaml
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_parses(workflow_yaml):
    assert workflow_yaml.get("name") == "Cross-Version Upgrade"
    assert "upgrade" in workflow_yaml.get("jobs", {})


def test_required_from_versions_present(workflow_text):
    """Every release tag in REQUIRED_FROM_VERSIONS must appear in the matrix.

    Catches accidental matrix shrinkage that would silently drop coverage.
    """
    # Extract the JSON list literal from the workflow_dispatch default
    match = re.search(r"default:\s*'(\[[^']+\])'", workflow_text)
    assert match, "workflow_dispatch input default not found"
    versions = set(json.loads(match.group(1)))
    missing = REQUIRED_FROM_VERSIONS - versions
    assert not missing, (
        f"required from_versions missing from default matrix: {missing}. "
        f"Removing requires an ADR amendment."
    )


def test_workflow_targets_phalanx_repo(workflow_text):
    """Both checkouts must point at td-project-ai/phalanx (not the harness)."""
    repo_refs = re.findall(r"repository:\s*(\S+)", workflow_text)
    assert repo_refs, "no `repository:` lines found"
    assert all(r == "td-project-ai/phalanx" for r in repo_refs), (
        f"unexpected repository targets: {set(repo_refs)}"
    )


def test_workflow_runs_upgrade_then_pytest(workflow_text):
    """Contract: --apply must precede pytest; tests overlaid from HEAD."""
    apply_idx = workflow_text.find("upgrade.py --apply")
    overlay_idx = workflow_text.find("rm -rf install/tests")
    pytest_idx = workflow_text.find("python -m pytest tests/")
    assert apply_idx >= 0, "missing --apply step"
    assert overlay_idx >= 0, "missing test overlay step"
    assert pytest_idx >= 0, "missing pytest step"
    assert apply_idx < overlay_idx < pytest_idx, (
        "step order broken: must be apply -> overlay -> pytest"
    )


def test_nightly_schedule_present(workflow_yaml):
    """Workflow must run on a schedule so drift is caught even without PRs."""
    on_block = workflow_yaml.get("on", {}) or workflow_yaml.get(True, {})
    # PyYAML parses bare `on:` as boolean True - handle both
    if isinstance(on_block, dict):
        assert "schedule" in on_block, "no schedule trigger configured"
