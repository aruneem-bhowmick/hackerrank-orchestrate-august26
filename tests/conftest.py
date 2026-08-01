"""Adds the code/ directory to sys.path so tests can import the router package."""

import sys
from pathlib import Path

import pytest

CODE_DIR = Path(__file__).resolve().parent.parent / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from router.dataset.loader import load_dataset_bundle  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def fixtures_dir() -> Path:
    """Root directory containing this test suite's synthetic dataset fixtures."""
    return FIXTURES_DIR


@pytest.fixture
def repo_root() -> Path:
    """The real project repository root, for tests that scan the actual repo."""
    return REPO_ROOT


@pytest.fixture
def load_fixture_bundle():
    """Factory fixture: load a named fixture, scoping the integrity scan to just it.

    repo_root is pinned to the fixture directory itself so the caller is
    unaffected by sibling fixtures under the shared fixtures directory
    that intentionally contain suspicious filenames for other tests.
    """

    def _load(fixture_name: str):
        """Load the named fixture directory, scoping repo_root to itself."""
        fixture_dir = FIXTURES_DIR / fixture_name
        return load_dataset_bundle(fixture_dir, repo_root=fixture_dir)

    return _load
