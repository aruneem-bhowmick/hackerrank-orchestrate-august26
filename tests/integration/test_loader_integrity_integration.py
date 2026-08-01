"""Integration tests confirming the integrity guard is wired into the loader."""

from pathlib import Path

import pytest

from router.dataset import integrity
from router.dataset.loader import load_dataset_bundle
from router.dataset.schema import DATASET_ALLOWLIST
from router.errors import DatasetIntegrityError, DatasetSchemaError

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_extra_csv_and_broken_schema_raises_integrity_error_first():
    """A fixture broken both ways surfaces the integrity error, naming the extra file."""
    fixture_dir = FIXTURES_DIR / "dataset_with_extra_csv"
    with pytest.raises(DatasetIntegrityError, match="notes.csv"):
        load_dataset_bundle(fixture_dir, repo_root=fixture_dir)


def test_extra_csv_fixture_does_not_raise_schema_error():
    """The same broken fixture never reaches schema validation at all."""
    fixture_dir = FIXTURES_DIR / "dataset_with_extra_csv"
    try:
        load_dataset_bundle(fixture_dir, repo_root=fixture_dir)
    except DatasetIntegrityError:
        return
    except DatasetSchemaError:
        pytest.fail("guard did not run before schema validation")
    pytest.fail("expected DatasetIntegrityError, no exception was raised")


def test_ground_truth_file_outside_dataset_dir_raises():
    """A ground-truth-named file next to dataset/ halts the guard, naming it."""
    fixture_dir = FIXTURES_DIR / "repo_with_ground_truth_file"
    with pytest.raises(DatasetIntegrityError, match="ground_truth_labels.csv"):
        integrity.enforce_dataset_integrity(
            repo_root=fixture_dir,
            dataset_dir=fixture_dir / "dataset",
            allowlist=DATASET_ALLOWLIST,
        )


def test_real_repository_has_no_integrity_violation():
    """The guard passes cleanly on this project's own real repository tree."""
    assert (
        integrity.enforce_dataset_integrity(
            repo_root=REPO_ROOT,
            dataset_dir=REPO_ROOT / "dataset",
            allowlist=DATASET_ALLOWLIST,
        )
        is None
    )
