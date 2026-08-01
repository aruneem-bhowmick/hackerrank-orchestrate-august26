from router.dataset.schema import DATASET_ALLOWLIST, DATASET_FILES


def test_dataset_files_has_thirteen_entries():
    assert len(DATASET_FILES) == 13


def test_dataset_files_filenames_are_unique():
    filenames = [spec.filename for spec in DATASET_FILES]
    assert len(filenames) == len(set(filenames))


def test_allowlist_matches_dataset_files_filenames_exactly():
    assert DATASET_ALLOWLIST == frozenset(spec.filename for spec in DATASET_FILES)
