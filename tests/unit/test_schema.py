"""Unit tests for the dataset file registry."""

from router.dataset.schema import DATASET_ALLOWLIST, DATASET_FILES


def test_dataset_files_has_thirteen_entries():
    """The registry lists exactly the 13 known dataset files."""
    assert len(DATASET_FILES) == 13


def test_dataset_files_filenames_are_unique():
    """No filename appears twice in the registry."""
    filenames = [spec.filename for spec in DATASET_FILES]
    assert len(filenames) == len(set(filenames))


def test_allowlist_matches_dataset_files_filenames_exactly():
    """The allowlist is derived from, and matches, the registry's filenames."""
    assert DATASET_ALLOWLIST == frozenset(spec.filename for spec in DATASET_FILES)
