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
    allowed = {"td-project-ai/phalanx", "td-project-ai/phalanx-market"}
    unexpected = set(repo_refs) - allowed
    assert not unexpected, (
        f"unexpected repository targets: {unexpected}"
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


# ---------------------------------------------------------------------------
# market-install job (PR-F4): live phalanx-market overlay via --market-source
# ---------------------------------------------------------------------------

def test_market_install_job_present(workflow_yaml):
    jobs = workflow_yaml.get("jobs", {})
    assert "market-install" in jobs, (
        "PR-F4 added a market-install job that exercises --market-source "
        "against the live td-project-ai/phalanx-market repo"
    )


def test_market_install_required_platforms(workflow_yaml):
    matrix = (
        workflow_yaml["jobs"]["market-install"]
        .get("strategy", {})
        .get("matrix", {})
    )
    platforms = set(matrix.get("platform", []))
    missing = REQUIRED_PLATFORMS - platforms
    assert not missing, (
        f"market-install matrix missing platforms: {missing}"
    )


def test_market_install_checks_out_phalanx_market(workflow_text):
    """The live overlay job must clone the phalanx-market repo as a sibling."""
    assert "td-project-ai/phalanx-market" in workflow_text, (
        "market-install job must check out td-project-ai/phalanx-market"
    )


def _strip_yaml_comments(text: str) -> str:
    """Drop YAML/shell `#` comment tails so flag-extraction regexes don't match
    documentation prose like ``# exercises --market-source against ...``.
    """
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Strip trailing ` # ...` comments (preserve `#` inside quoted strings
        # by only splitting when the `#` is preceded by whitespace).
        out.append(re.sub(r"\s+#.*$", "", line))
    return "\n".join(out)


def test_market_install_uses_market_source_flag(workflow_text):
    """--market-source (not --bundle-source) is the correct flag for market overlays."""
    assert "--market-source" in workflow_text, (
        "market-install job must invoke --market-source to overlay the market repo"
    )
    code = _strip_yaml_comments(workflow_text)
    # The argument value must point at the phalanx-market checkout dir, not phalanx core.
    invocations = re.findall(r'--market-source\s+"?([^\s"]+)"?', code)
    assert invocations, "expected at least one --market-source <value> invocation"
    for arg in invocations:
        assert "phalanx-market" in arg, (
            f"--market-source argument {arg!r} should reference the phalanx-market checkout"
        )
        # Must not collapse to the core checkout.
        assert not arg.endswith("/phalanx") and "phalanx/tests" not in arg, (
            f"--market-source argument {arg!r} points inside phalanx core"
        )


def test_market_install_targets_writing_bundle(workflow_text):
    assert "--bundles writing" in workflow_text, (
        "market-install must install the live `writing` bundle from phalanx-market"
    )


def test_market_install_verifies_writing_bundle_assets(workflow_text):
    """Verification must assert every layer the writing bundle contributes -
    bundle catalog, skill, agent, tools, and context files - so a regression
    in any one overlay layer (skills/agents/tools/context) trips the build.
    """
    required_artifacts = [
        "bundles/writing.yaml",
        "skills/editing-copy/SKILL.md",
        "agents/copy-editor.md",
        "tools/writing/lint_copy.py",
        "tools/writing/manage_glossary.py",
        "context/writing/terminology.yaml",
        "context/style-guide.md",  # core-owned; proves market didn't strip core context
    ]
    missing = [a for a in required_artifacts if a not in workflow_text]
    assert not missing, (
        f"market-install verification step does not assert on: {missing}"
    )
