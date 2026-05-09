"""Guard tests for the Multi-Repo Integration workflow.

The workflow runs in GitHub Actions against live phalanx core (too expensive
to run locally). These tests validate the workflow YAML stays well-formed
and preserves the multi-repo install contract.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "multi-repo-integration.yml"

# Platforms the matrix MUST exercise. Each tests a different emission backend
# in core's installer.
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
    assert workflow_yaml.get("name") == "Multi-Repo Integration"
    assert "install" in workflow_yaml.get("jobs", {})


def test_required_platforms_present(workflow_yaml):
    matrix = (
        workflow_yaml["jobs"]["install"]
        .get("strategy", {})
        .get("matrix", {})
    )
    platforms = set(matrix.get("platform", []))
    missing = REQUIRED_PLATFORMS - platforms
    assert not missing, (
        f"required platforms missing from matrix: {missing}. "
        f"Removing one means a backend stops being integration-tested."
    )


def test_workflow_uses_external_bundle_source(workflow_text):
    """The whole point of this workflow: --bundle-source must point OUTSIDE
    the cloned phalanx core checkout. We stage external-bundles/ as a sibling.
    """
    assert "--bundle-source" in workflow_text, "workflow must invoke --bundle-source"
    assert "external-bundles" in workflow_text, (
        "workflow must stage bundles in a sibling dir to prove --bundle-source "
        "is honoring an external path"
    )
    # The actual --bundle-source argument value (next non-blank token) must
    # not begin with `phalanx/` - that would point inside the core checkout
    # and defeat the multi-repo guarantee.
    invocations = re.findall(r'--bundle-source\s+"?([^\s"]+)"?', workflow_text)
    assert invocations, "expected at least one --bundle-source <value> invocation"
    for arg in invocations:
        assert "phalanx/" not in arg, (
            f"--bundle-source argument {arg!r} points inside the phalanx checkout"
        )


def test_workflow_targets_phalanx_repo(workflow_text):
    repo_refs = re.findall(r"repository:\s*(\S+)", workflow_text)
    assert repo_refs, "no `repository:` lines found"
    assert all(r == "td-project-ai/phalanx" for r in repo_refs), (
        f"unexpected repository targets: {set(repo_refs)}"
    )


def test_workflow_asserts_external_and_core_present(workflow_text):
    """Verification step must check BOTH the external bundle catalog AND a
    core skill landed - otherwise we don't know if --bundle-source is
    overlaying or replacing.
    """
    assert "bundles/synth-cloud.yaml" in workflow_text, (
        "verification must assert external bundle catalog (synth-cloud) is registered"
    )
    assert "skills/managing-memory" in workflow_text, (
        "verification must assert at least one core skill is also installed"
    )


def test_nightly_schedule_present(workflow_yaml):
    on_block = workflow_yaml.get("on", {}) or workflow_yaml.get(True, {})
    if isinstance(on_block, dict):
        assert "schedule" in on_block, "no schedule trigger configured"
