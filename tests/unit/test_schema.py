"""Unit tests for the dataset file registry."""

import dataclasses

from router.dataset.loader import DatasetBundle
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


def test_dataset_files_attributes_are_unique_and_populated():
    """Every registry entry names a DatasetBundle attribute, with no duplicates."""
    attributes = [spec.attribute for spec in DATASET_FILES]
    assert all(attribute is not None for attribute in attributes)
    assert len(attributes) == len(set(attributes))


def test_dataset_files_attributes_match_dataset_bundle_fields_exactly():
    """The registry's attribute names are exactly DatasetBundle's field names.

    Guards against the registry and the dataclass drifting apart, which
    would otherwise surface only as a confusing TypeError far from here.
    """
    registry_attributes = {spec.attribute for spec in DATASET_FILES}
    bundle_fields = {field.name for field in dataclasses.fields(DatasetBundle)}
    assert registry_attributes == bundle_fields
