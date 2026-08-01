"""Unit tests for normalized message IDs at the batch-output boundary."""

import pandas as pd
import pytest

from router.errors import MediaIngestionError
from router.ingestion.pipeline import run_media_ingestion

from ingestion_fakes import FakeASRClient, FakeOCRClient


def test_batch_keys_non_string_message_ids_the_same_way_as_normalized_messages(
    load_fixture_bundle, fixtures_dir
):
    """The dictionary key always matches the normalized message's string ID."""
    bundle = load_fixture_bundle("dataset_valid")
    bundle.messages.loc[0, "message_id"] = 17

    normalized = run_media_ingestion(
        bundle, fixtures_dir / "dataset_valid", FakeOCRClient(), FakeASRClient()
    )

    assert "" in normalized
    assert normalized[""].message_id == ""


def test_batch_detects_duplicate_normalized_message_ids(load_fixture_bundle, fixtures_dir):
    """Two non-string IDs normalize to one key and are rejected rather than silently overwritten."""
    bundle = load_fixture_bundle("dataset_valid")
    duplicate = bundle.messages.iloc[0].copy()
    duplicate["message_id"] = 17
    bundle.messages.loc[0, "message_id"] = 42
    bundle.messages = pd.concat([bundle.messages, pd.DataFrame([duplicate])], ignore_index=True)

    with pytest.raises(MediaIngestionError, match="duplicate message_id"):
        run_media_ingestion(bundle, fixtures_dir / "dataset_valid", FakeOCRClient(), FakeASRClient())
