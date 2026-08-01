"""Integration tests for loading a full dataset directory into a bundle."""

import dataclasses

import pytest

from router.errors import DatasetSchemaError


def test_load_dataset_bundle_populates_every_field_from_valid_fixture(load_fixture_bundle):
    """Every DatasetBundle field is populated from a schema-complete fixture."""
    bundle = load_fixture_bundle("dataset_valid")
    for field in dataclasses.fields(bundle):
        frame = getattr(bundle, field.name)
        assert frame is not None
        assert len(frame) > 0
    assert len(bundle.messages) == 2
    assert set(bundle.messages["message_id"]) == {"msg_test_001", "msg_test_002"}


def test_load_dataset_bundle_raises_on_missing_column(load_fixture_bundle):
    """A missing required column in one file fails the whole bundle load."""
    with pytest.raises(DatasetSchemaError) as exc_info:
        load_fixture_bundle("dataset_missing_column")
    assert "users.csv" in str(exc_info.value)
    assert "messages_reported_30d" in str(exc_info.value)


def test_load_dataset_bundle_raises_on_missing_file(load_fixture_bundle):
    """A missing dataset file fails the whole bundle load, naming the file."""
    with pytest.raises(DatasetSchemaError, match=r"voice_notes\.csv"):
        load_fixture_bundle("dataset_missing_file")
