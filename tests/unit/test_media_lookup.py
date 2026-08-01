"""Unit tests for resolving image and voice media paths."""

from pathlib import Path

import pandas as pd

from router.ingestion.media import lookup_media_file_path, resolve_media_path


def test_resolve_media_path_preserves_the_dataset_relative_location(tmp_path):
    """A media-table path is rooted at the active dataset directory."""
    assert resolve_media_path(tmp_path, "media/images/example.jpg") == (
        tmp_path / "media/images/example.jpg"
    )


def test_lookup_media_file_path_returns_the_first_matching_record(tmp_path):
    """A known media ID resolves to its recorded relative path."""
    table = pd.DataFrame(
        [
            {"image_id": "img_1", "file_path": "media/images/first.jpg"},
            {"image_id": "img_1", "file_path": "media/images/second.jpg"},
        ]
    )

    assert lookup_media_file_path("img_1", table, "image_id", tmp_path) == (
        tmp_path / "media/images/first.jpg"
    )


def test_lookup_media_file_path_returns_none_for_blank_or_unknown_ids(tmp_path):
    """Missing references defer to the pipeline's graceful fallback path."""
    table = pd.DataFrame([{"voice_note_id": "vn_1", "file_path": "media/audio/one.mp3"}])

    assert lookup_media_file_path("", table, "voice_note_id", tmp_path) is None
    assert lookup_media_file_path("vn_missing", table, "voice_note_id", tmp_path) is None
