"""Smoke test - PR-F1 bootstrap.

Asserts the harness package layout is intact. Real cross-version and
multi-repo integration tests land in PR-F2+.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_repo_layout():
    assert (REPO / "README.md").is_file()
    assert (REPO / "LICENSE").is_file()
    assert (REPO / "tests").is_dir()


def test_pytest_runs():
    """Trivial assertion - presence of this passing test means pytest works."""
    assert 1 + 1 == 2
