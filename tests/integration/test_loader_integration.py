"""Integration tests for loading a full dataset directory into a bundle."""

import dataclasses
from pathlib import Path

import pytest

from router.dataset.loader import load_dataset_bundle
from router.errors import DatasetSchemaError

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load(fixture_name: str):
    """Load a named fixture, scanning only within it for stray files.

    repo_root is pinned to the fixture directory itself so this test is
    not affected by sibling fixtures under the shared fixtures directory
    that intentionally contain suspicious filenames for other tests.
    """
    fixture_dir = FIXTURES_DIR / fixture_name
    return load_dataset_bundle(fixture_dir, repo_root=fixture_dir)


def test_load_dataset_bundle_populates_every_field_from_valid_fixture():
    """Every DatasetBundle field is populated from a schema-complete fixture."""
    bundle = _load("dataset_valid")
    for field in dataclasses.fields(bundle):
        frame = getattr(bundle, field.name)
        assert frame is not None
        assert len(frame) > 0
    assert len(bundle.messages) == 2
    assert set(bundle.messages["message_id"]) == {"msg_test_001", "msg_test_002"}


def test_load_dataset_bundle_raises_on_missing_column():
    """A missing required column in one file fails the whole bundle load."""
    with pytest.raises(DatasetSchemaError) as exc_info:
        _load("dataset_missing_column")
    assert "users.csv" in str(exc_info.value)
    assert "messages_reported_30d" in str(exc_info.value)


def test_load_dataset_bundle_raises_on_missing_file():
    """A missing dataset file fails the whole bundle load, naming the file."""
    with pytest.raises(DatasetSchemaError, match="voice_notes.csv"):
        _load("dataset_missing_file")
